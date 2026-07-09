"""Additional coverage tests for ideer.tools.tools.

Targets missed lines 139-192: MCP tool_search with existing registry path.
"""

import logging
from unittest.mock import MagicMock, patch

from langchain_core.tools import BaseTool

from ideer.tools.tools import get_available_tools


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


def _make_tool_config(name="my_tool", group="core", use="some.module:my_tool", requires_network=False):
    tc = MagicMock()
    tc.name = name
    tc.group = group
    tc.use = use
    tc.requires_network = requires_network
    return tc


class TestMCPToolSearchNewRegistry:
    """Lines 139-148: tool_search enabled, no existing registry -> create new registry."""

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_tool_search_creates_new_registry(self, mock_resolve, mock_bash, mock_offline, caplog):
        import sys

        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], tool_search_enabled=True)

        mock_mcp_tool = MagicMock(spec=BaseTool)
        mock_mcp_tool.name = "mcp_search"
        mock_mcp_tool.description = "Search tool"
        mock_mcp_tool.func = None
        mock_mcp_tool.coroutine = None

        mock_registry = MagicMock()
        mock_registry.__len__ = MagicMock(return_value=1)

        mock_ext_config = MagicMock()
        mock_ext_config.get_enabled_mcp_servers.return_value = ["server1"]

        mock_tool_search_tool = MagicMock(spec=BaseTool)
        mock_tool_search_tool.name = "tool_search"
        mock_tool_search_tool.func = None
        mock_tool_search_tool.coroutine = None

        mock_ext_module = MagicMock()
        mock_ext_module.ExtensionsConfig.from_file.return_value = mock_ext_config
        mock_mcp_cache_module = MagicMock()
        mock_mcp_cache_module.get_cached_mcp_tools.return_value = [mock_mcp_tool]

        mock_tool_search_module = MagicMock()
        mock_tool_search_module.DeferredToolRegistry.return_value = mock_registry
        mock_tool_search_module.get_deferred_registry.return_value = None
        mock_tool_search_module.set_deferred_registry = MagicMock()
        mock_tool_search_module.tool_search = mock_tool_search_tool

        with (
            patch.dict(
                sys.modules,
                {
                    "ideer.config.extensions_config": mock_ext_module,
                    "ideer.mcp.cache": mock_mcp_cache_module,
                    "ideer.tools.builtins.tool_search": mock_tool_search_module,
                },
            ),
            caplog.at_level(logging.INFO),
        ):
            get_available_tools(app_config=config, include_mcp=True)

        # Verify registry was created and tool was registered
        mock_tool_search_module.DeferredToolRegistry.assert_called_once()
        mock_registry.register.assert_called_once_with(mock_mcp_tool)
        mock_tool_search_module.set_deferred_registry.assert_called_once()
        assert "Tool search active" in caplog.text


class TestMCPToolSearchExistingRegistry:
    """Lines 149-191: tool_search enabled with existing registry -> preserve promotions."""

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    @patch("ideer.tools.tools.get_deferred_registry")
    def test_tool_search_preserves_existing_registry(self, mock_get_registry, mock_resolve, mock_bash, mock_offline, caplog):
        import sys

        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], tool_search_enabled=True)

        mock_mcp_tool = MagicMock(spec=BaseTool)
        mock_mcp_tool.name = "mcp_search"
        mock_mcp_tool.description = "Search tool"
        mock_mcp_tool.func = None
        mock_mcp_tool.coroutine = None

        existing_registry = MagicMock()
        existing_registry.__len__ = MagicMock(return_value=0)
        mock_get_registry.return_value = existing_registry

        mock_ext_config = MagicMock()
        mock_ext_config.get_enabled_mcp_servers.return_value = ["server1"]

        mock_tool_search_tool = MagicMock(spec=BaseTool)
        mock_tool_search_tool.name = "tool_search"
        mock_tool_search_tool.func = None
        mock_tool_search_tool.coroutine = None

        mock_ext_module = MagicMock()
        mock_ext_module.ExtensionsConfig.from_file.return_value = mock_ext_config
        mock_mcp_cache_module = MagicMock()
        mock_mcp_cache_module.get_cached_mcp_tools.return_value = [mock_mcp_tool]

        mock_tool_search_module = MagicMock()
        mock_tool_search_module.tool_search = mock_tool_search_tool

        with (
            patch.dict(
                sys.modules,
                {
                    "ideer.config.extensions_config": mock_ext_module,
                    "ideer.mcp.cache": mock_mcp_cache_module,
                    "ideer.tools.builtins.tool_search": mock_tool_search_module,
                },
            ),
            caplog.at_level(logging.INFO),
        ):
            get_available_tools(app_config=config, include_mcp=True)

        assert "preserved promotions" in caplog.text


class TestMCPToolsWithoutToolSearch:
    """Lines 138-139: MCP tools loaded but tool_search disabled."""

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_mcp_tools_without_tool_search(self, mock_resolve, mock_bash, mock_offline, caplog):
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
                    "ideer.config.extensions_config": mock_ext_module,
                    "ideer.mcp.cache": mock_mcp_cache_module,
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

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_no_enabled_mcp_servers(self, mock_resolve, mock_bash, mock_offline):
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
                "ideer.config.extensions_config": mock_ext_module,
            },
        ):
            result = get_available_tools(app_config=config, include_mcp=True)

        # No MCP tools should be loaded
        assert len(result) == len([t for t in result if t.name != "mcp_tool"])
