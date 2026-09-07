"""Additional coverage tests for deerflow.tools.tools and deferred-tool assembly.

Covers: MCP tool loading in get_available_tools (with and without enabled
servers) and the upstream deferred-tool setup built from MCP candidates.
"""

import logging
from unittest.mock import MagicMock, patch

from langchain_core.tools import BaseTool

from deerflow.tools.builtins.tool_search import assemble_deferred_tools, build_deferred_tool_setup
from deerflow.tools.mcp_metadata import tag_mcp_tool
from deerflow.tools.tools import get_available_tools


class _StubTool(BaseTool):
    name: str = "stub"
    description: str = "stub tool"

    def _run(self, *args, **kwargs):
        return ""


def _make_config(
    tools=None,
    models=None,
    skill_evolution_enabled=False,
    tool_search_enabled=False,
    acp_agents=None,
):
    cfg = MagicMock()
    cfg.tools = tools or []
    cfg.models = models or []
    cfg.skill_evolution = MagicMock(enabled=skill_evolution_enabled)
    cfg.tool_search = MagicMock(enabled=tool_search_enabled)
    cfg.acp_agents = acp_agents or {}
    cfg.get_model_config = lambda name: None
    return cfg


class TestDeferredToolSetupFromMcpCandidates:
    """Deferred-tool assembly: MCP candidates are withheld behind tool_search."""

    def test_enabled_with_mcp_candidates_builds_search_tool(self):
        mcp_a = _StubTool(name="mcp_a", description="MCP tool a")
        mcp_b = _StubTool(name="mcp_b", description="MCP tool b")
        plain = _StubTool(name="plain", description="plain tool")
        tag_mcp_tool(mcp_a)
        tag_mcp_tool(mcp_b)
        candidates = [plain, mcp_a, mcp_b]

        setup = build_deferred_tool_setup(candidates, enabled=True)

        assert setup.tool_search_tool is not None
        assert setup.tool_search_tool.name == "tool_search"
        assert setup.deferred_names == frozenset({"mcp_a", "mcp_b"})
        assert setup.catalog_hash

        final_tools, assembled_setup = assemble_deferred_tools(candidates, enabled=True)
        assert [t.name for t in final_tools] == ["plain", "mcp_a", "mcp_b", "tool_search"]
        assert assembled_setup.deferred_names == setup.deferred_names
        assert assembled_setup.catalog_hash == setup.catalog_hash

    def test_disabled_binds_all_tools_without_deferral(self):
        mcp_a = _StubTool(name="mcp_a", description="MCP tool a")
        tag_mcp_tool(mcp_a)
        candidates = [mcp_a]

        setup = build_deferred_tool_setup(candidates, enabled=False)

        assert setup.tool_search_tool is None
        assert setup.deferred_names == frozenset()
        assert setup.catalog_hash is None

        final_tools, assembled_setup = assemble_deferred_tools(candidates, enabled=False)
        assert final_tools == candidates
        assert assembled_setup == setup


class TestMCPToolsLoadedByGetAvailableTools:
    """MCP tools loaded; tool_search assembly happens at agent build, not here."""

    @patch("deerflow.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("deerflow.tools.tools.resolve_variable")
    def test_mcp_tools_without_tool_search(self, mock_resolve, mock_bash, caplog):
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], tool_search_enabled=False)

        mock_mcp_tool = MagicMock(spec=BaseTool)
        mock_mcp_tool.name = "mcp_tool"
        mock_mcp_tool.func = None
        mock_mcp_tool.coroutine = None

        mock_ext_config = MagicMock()
        mock_ext_config.get_enabled_mcp_servers.return_value = ["server1"]

        import sys

        mock_ext_module = MagicMock()
        mock_ext_module.ExtensionsConfig.from_file.return_value = mock_ext_config
        mock_mcp_cache_module = MagicMock()
        mock_mcp_cache_module.get_cached_mcp_tools.return_value = [mock_mcp_tool]

        with (
            patch.dict(
                sys.modules,
                {
                    "deerflow.config.extensions_config": mock_ext_module,
                    "deerflow.mcp.cache": mock_mcp_cache_module,
                },
            ),
            caplog.at_level(logging.INFO),
        ):
            result = get_available_tools(app_config=config, include_mcp=True)

        tool_names = [t.name for t in result]
        assert "mcp_tool" in tool_names
        assert "cached MCP tool" in caplog.text


class TestMCPNoEnabledServers:
    """No MCP servers enabled -> no MCP tools loaded."""

    @patch("deerflow.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("deerflow.tools.tools.resolve_variable")
    def test_no_enabled_mcp_servers(self, mock_resolve, mock_bash):
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], tool_search_enabled=False)

        mock_ext_config = MagicMock()
        mock_ext_config.get_enabled_mcp_servers.return_value = []

        import sys

        mock_ext_module = MagicMock()
        mock_ext_module.ExtensionsConfig.from_file.return_value = mock_ext_config

        with patch.dict(
            sys.modules,
            {
                "deerflow.config.extensions_config": mock_ext_module,
            },
        ):
            result = get_available_tools(app_config=config, include_mcp=True)

        # No MCP tools should be loaded
        assert len(result) == len([t for t in result if t.name != "mcp_tool"])
