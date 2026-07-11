"""Tests to cover uncovered lines in ideer.tools.tools."""

import logging
from unittest.mock import MagicMock, patch

from langchain_core.tools import BaseTool

from ideer.tools.tools import get_available_tools


def _is_host_bash_tool(tool):
    """Wrapper to access the private function under test."""
    from ideer.tools.tools import _is_host_bash_tool as _impl

    return _impl(tool)


def _ensure_sync_invocable_tool(tool):
    """Wrapper to access the private function under test."""
    from ideer.tools.tools import _ensure_sync_invocable_tool as _impl

    return _impl(tool)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str = "dummy_tool", func=None, coroutine=None) -> BaseTool:
    """Create a minimal BaseTool for testing."""
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    tool.group = None
    tool.use = None
    tool.func = func
    tool.coroutine = coroutine
    # Ensure getattr(tool, "func", None) returns the right thing
    tool.__getattr__ = lambda self, attr: {
        "name": name,
        "group": None,
        "use": None,
        "func": func,
        "coroutine": coroutine,
    }.get(attr, None)
    return tool


def _make_config(
    tools=None,
    models=None,
    skill_evolution_enabled=False,
    tool_search_enabled=False,
    acp_agents=None,
    extensions_get_enabled=None,
):
    """Build a minimal AppConfig via model_construct (bypasses validation)."""
    cfg = MagicMock()
    cfg.tools = tools or []
    cfg.models = models or []
    cfg.skill_evolution = MagicMock(enabled=skill_evolution_enabled)
    cfg.tool_search = MagicMock(enabled=tool_search_enabled)
    cfg.acp_agents = acp_agents or {}

    def _get_model_config(name):
        for m in models or []:
            if m.name == name:
                return m
        return None

    cfg.get_model_config = _get_model_config
    return cfg


def _make_model_config(name="test-model", supports_vision=False):
    """Build a minimal ModelConfig mock."""
    mc = MagicMock()
    mc.name = name
    mc.supports_vision = supports_vision
    return mc


def _make_tool_config(name="my_tool", group="core", use="some.module:my_tool", requires_network=False):
    """Build a minimal ToolConfig mock."""
    tc = MagicMock()
    tc.name = name
    tc.group = group
    tc.use = use
    tc.requires_network = requires_network
    return tc


# ---------------------------------------------------------------------------
# Line 34: _is_host_bash_tool – use == "ideer.sandbox.tools:bash_tool"
# ---------------------------------------------------------------------------


class TestIsHostBashTool:
    def test_use_field_matches_bash_tool(self):
        """Line 34: returns True when use == 'ideer.sandbox.tools:bash_tool'."""
        tool = MagicMock(spec=BaseTool)
        tool.group = "not_bash"
        tool.use = "ideer.sandbox.tools:bash_tool"
        assert _is_host_bash_tool(tool) is True

    def test_group_bash(self):
        """Line 31-32: returns True when group == 'bash'."""
        tool = MagicMock(spec=BaseTool)
        tool.group = "bash"
        tool.use = "something.else"
        assert _is_host_bash_tool(tool) is True

    def test_neither(self):
        """Line 35: returns False when neither matches."""
        tool = MagicMock(spec=BaseTool)
        tool.group = "other"
        tool.use = "some.other:module"
        assert _is_host_bash_tool(tool) is False


# ---------------------------------------------------------------------------
# Lines 72-79: Offline mode filtering
# ---------------------------------------------------------------------------


class TestOfflineModeFiltering:
    @patch("ideer.tools.tools.is_offline", return_value=True)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_offline_skips_network_tools(self, mock_resolve, mock_bash, mock_offline):
        """Lines 72-79: network-dependent tools are excluded in offline mode."""
        net_tool = _make_tool_config(name="net_tool", requires_network=True)
        local_tool = _make_tool_config(name="local_tool", requires_network=False)

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "local_tool"
        mock_tool.func = None
        mock_tool.coroutine = None
        mock_resolve.return_value = mock_tool

        config = _make_config(tools=[net_tool, local_tool])
        result = get_available_tools(app_config=config, include_mcp=False)

        tool_names = [t.name for t in result]
        assert "net_tool" not in tool_names
        assert "local_tool" in tool_names

    @patch("ideer.tools.tools.is_offline", return_value=True)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_offline_logs_skipped_tools(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Lines 72-78: logging when offline tools are skipped."""
        net_tool = _make_tool_config(name="web_search", requires_network=True)

        config = _make_config(tools=[net_tool])

        with caplog.at_level(logging.INFO):
            get_available_tools(app_config=config, include_mcp=False)

        assert "Offline mode" in caplog.text
        assert "web_search" in caplog.text

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_online_keeps_network_tools(self, mock_resolve, mock_bash, mock_offline):
        """Lines 71-79: online mode does not filter network tools."""
        net_tool = _make_tool_config(name="net_tool", requires_network=True)

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "net_tool"
        mock_tool.func = None
        mock_tool.coroutine = None
        mock_resolve.return_value = mock_tool

        config = _make_config(tools=[net_tool])
        result = get_available_tools(app_config=config, include_mcp=False)

        tool_names = [t.name for t in result]
        assert "net_tool" in tool_names


# ---------------------------------------------------------------------------
# Line 93: Tool name mismatch warning
# ---------------------------------------------------------------------------


class TestToolNameMismatch:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_name_mismatch_logs_warning(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Line 93: warning when config name != tool .name."""
        cfg = _make_tool_config(name="config_name", use="some.module:tool_name")
        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "tool_name"  # different from config name
        mock_tool.func = None
        mock_tool.coroutine = None
        mock_resolve.return_value = mock_tool

        config = _make_config(tools=[cfg])

        with caplog.at_level(logging.WARNING):
            get_available_tools(app_config=config, include_mcp=False)

        assert "config name" in caplog.text
        assert "Tool name mismatch" in caplog.text

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_name_match_no_warning(self, mock_resolve, mock_bash, mock_offline, caplog):
        """No mismatch warning when names match."""
        cfg = _make_tool_config(name="my_tool", use="some.module:my_tool")
        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "my_tool"  # same as config name
        mock_tool.func = None
        mock_tool.coroutine = None
        mock_resolve.return_value = mock_tool

        config = _make_config(tools=[cfg])

        with caplog.at_level(logging.WARNING):
            get_available_tools(app_config=config, include_mcp=False)

        assert "Tool name mismatch" not in caplog.text


# ---------------------------------------------------------------------------
# Lines 106-108: skill_evolution enabled path
# ---------------------------------------------------------------------------


class TestSkillEvolution:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_skill_evolution_enabled_adds_tool(self, mock_resolve, mock_bash, mock_offline):
        """Lines 106-108: skill_manage_tool is added when skill_evolution is enabled."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)

        config = _make_config(tools=[], skill_evolution_enabled=True)

        # skill_manage_tool is imported locally inside the function body
        mock_skill_tool = MagicMock(spec=BaseTool)
        mock_skill_tool.name = "skill_manage"
        with patch("ideer.tools.skill_manage_tool.skill_manage_tool", mock_skill_tool):
            result = get_available_tools(app_config=config, include_mcp=False)

        assert mock_skill_tool in result

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_skill_evolution_disabled_no_extra(self, mock_resolve, mock_bash, mock_offline):
        """skill_manage_tool is NOT added when skill_evolution is disabled."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)

        config = _make_config(tools=[], skill_evolution_enabled=False)

        mock_skill_tool = MagicMock(spec=BaseTool)
        mock_skill_tool.name = "skill_manage"
        with patch("ideer.tools.skill_manage_tool.skill_manage_tool", mock_skill_tool):
            result = get_available_tools(app_config=config, include_mcp=False)

        assert mock_skill_tool not in result


# ---------------------------------------------------------------------------
# Lines 122-123: Model supports vision – view_image_tool appended
# ---------------------------------------------------------------------------


class TestVisionSupport:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_vision_model_includes_view_image_tool(self, mock_resolve, mock_bash, mock_offline):
        """Lines 122-123: view_image_tool is added when model supports vision."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)

        model = _make_model_config(name="gpt-4o", supports_vision=True)
        config = _make_config(tools=[], models=[model])

        with patch("ideer.tools.tools.view_image_tool") as mock_vi:
            result = get_available_tools(app_config=config, include_mcp=False)

        assert mock_vi in result

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_no_vision_no_view_image_tool(self, mock_resolve, mock_bash, mock_offline):
        """view_image_tool is NOT added when model does not support vision."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)

        model = _make_model_config(name="gpt-3.5", supports_vision=False)
        config = _make_config(tools=[], models=[model])

        with patch("ideer.tools.tools.view_image_tool") as mock_vi:
            result = get_available_tools(app_config=config, include_mcp=False)

        assert mock_vi not in result

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_no_models_skips_vision_check(self, mock_resolve, mock_bash, mock_offline):
        """When models list is empty and no model_name, vision check is skipped."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)

        config = _make_config(tools=[], models=[])

        with patch("ideer.tools.tools.view_image_tool") as mock_vi:
            result = get_available_tools(app_config=config, include_mcp=False)

        assert mock_vi not in result

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_explicit_model_name_vision(self, mock_resolve, mock_bash, mock_offline):
        """Lines 115-117: explicit model_name overrides default, triggers vision check."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)

        _make_model_config(name="gpt-4o", supports_vision=True)
        model_no_vision = _make_model_config(name="gpt-3.5", supports_vision=False)
        config = _make_config(tools=[], models=[model_no_vision])

        with patch("ideer.tools.tools.view_image_tool") as mock_vi:
            result = get_available_tools(
                app_config=config,
                include_mcp=False,
                model_name="gpt-4o",
            )

        # model_name=gpt-4o is not in models list, so get_model_config returns None
        # view_image_tool should NOT be added
        assert mock_vi not in result


# ---------------------------------------------------------------------------
# Lines 193-196: MCP ImportError / Exception handlers
# ---------------------------------------------------------------------------


class TestMCPErrorHandling:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_mcp_import_error_handled(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Lines 193-194: ImportError when ExtensionsConfig cannot be imported."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], tool_search_enabled=False)

        with patch.dict("sys.modules", {"ideer.config.extensions_config": None}):
            with caplog.at_level(logging.WARNING):
                get_available_tools(app_config=config, include_mcp=True)

        assert "MCP module not available" in caplog.text

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_mcp_generic_exception_handled(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Lines 195-196: generic Exception when getting cached MCP tools fails."""
        mock_resolve.return_value = MagicMock(name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], tool_search_enabled=False)

        # Mock the local imports: ExtensionsConfig.from_file() returns config
        # with MCP servers enabled, get_cached_mcp_tools raises RuntimeError
        mock_ext_config = MagicMock()
        mock_ext_config.get_enabled_mcp_servers.return_value = ["server1"]
        mock_extensions = MagicMock()
        mock_extensions.ExtensionsConfig.from_file.return_value = mock_ext_config
        mock_cache = MagicMock()
        mock_cache.get_cached_mcp_tools.side_effect = RuntimeError("MCP connection failed")

        with (
            patch.dict(
                "sys.modules",
                {
                    "ideer.config.extensions_config": mock_extensions,
                    "ideer.mcp.cache": mock_cache,
                },
            ),
            caplog.at_level(logging.ERROR),
        ):
            get_available_tools(app_config=config, include_mcp=True)

        assert "Failed to get cached MCP tools" in caplog.text


# ---------------------------------------------------------------------------
# Lines 212-213: ACP tools Exception handler
# ---------------------------------------------------------------------------


class TestACPErrorHandling:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_acp_import_error_handled(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Lines 212-213: Exception when ACP tool module import fails."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], acp_agents={"agent1": {"desc": "test"}})

        with patch.dict("sys.modules", {"ideer.tools.builtins.invoke_acp_agent_tool": None}):
            with caplog.at_level(logging.WARNING):
                get_available_tools(app_config=config, include_mcp=False)

        assert "Failed to load ACP tool" in caplog.text

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_acp_build_raises_exception(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Lines 212-213: exception during build_invoke_acp_agent_tool call."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], acp_agents={"agent1": {"desc": "test"}})

        # build_invoke_acp_agent_tool is imported locally; patch at source module
        with patch("ideer.tools.builtins.invoke_acp_agent_tool.build_invoke_acp_agent_tool", side_effect=ValueError("bad config")):
            with caplog.at_level(logging.WARNING):
                get_available_tools(app_config=config, include_mcp=False)

        assert "Failed to load ACP tool" in caplog.text
        assert "bad config" in caplog.text


# ---------------------------------------------------------------------------
# Line 83: Bash tool filtering when host bash not allowed
# ---------------------------------------------------------------------------


class TestBashToolFiltering:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=False)
    @patch("ideer.tools.tools.resolve_variable")
    def test_bash_tool_excluded_when_not_allowed(self, mock_resolve, mock_bash, mock_offline):
        """Line 83: bash tools are filtered out when is_host_bash_allowed returns False."""
        bash_tool = _make_tool_config(name="bash_tool", group="bash", use="ideer.sandbox.tools:bash_tool")
        other_tool = _make_tool_config(name="other_tool", group="core", use="some.module:other")

        mock_t1 = MagicMock(spec=BaseTool)
        mock_t1.name = "bash_tool"
        mock_t1.func = None
        mock_t1.coroutine = None
        mock_t2 = MagicMock(spec=BaseTool)
        mock_t2.name = "other_tool"
        mock_t2.func = None
        mock_t2.coroutine = None
        mock_resolve.side_effect = lambda use, bt: mock_t1 if "bash" in use else mock_t2

        config = _make_config(tools=[bash_tool, other_tool])
        result = get_available_tools(app_config=config, include_mcp=False)

        tool_names = [t.name for t in result]
        assert "bash_tool" not in tool_names
        assert "other_tool" in tool_names


# ---------------------------------------------------------------------------
# Lines 112-113: Subagent tools
# ---------------------------------------------------------------------------


class TestSubagentTools:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_subagent_enabled_adds_task_tool(self, mock_resolve, mock_bash, mock_offline):
        """Lines 112-113: subagent tools are added when subagent_enabled=True."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[])

        result = get_available_tools(app_config=config, include_mcp=False, subagent_enabled=True)

        tool_names = [t.name for t in result]
        assert "task" in tool_names

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_subagent_disabled_no_task_tool(self, mock_resolve, mock_bash, mock_offline):
        """subagent tools are NOT added when subagent_enabled=False."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[])

        result = get_available_tools(app_config=config, include_mcp=False, subagent_enabled=False)

        tool_names = [t.name for t in result]
        assert "task" not in tool_names


# ---------------------------------------------------------------------------
# Lines 204-206, 211: ACP agents with app_config=None
# ---------------------------------------------------------------------------


class TestACPWithNoAppConfig:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_acp_with_app_config_none_uses_get_acp_agents(self, mock_resolve, mock_bash, mock_offline):
        """Lines 203-206: when app_config is None, get_acp_agents() is called."""
        mock_loaded = MagicMock()
        mock_loaded.name = "acp_tool"
        mock_loaded.description = "A tool"
        mock_resolve.return_value = mock_loaded

        tool_cfg = _make_tool_config(name="acp_tool", group="acp", use="some.mod:acp_tool")

        mock_acp = {"agent1": {"command": "cmd1", "args": [], "description": "Agent 1"}}
        # When app_config=None, function falls back to get_app_config()
        # We need to mock get_app_config AND get_acp_agents (local import)
        fallback_config = _make_config(tools=[tool_cfg], acp_agents={})
        with patch("ideer.tools.tools.get_app_config", return_value=fallback_config):
            with patch("ideer.config.acp_config.get_acp_agents", return_value=mock_acp) as mock_get:
                mock_tool = MagicMock()
                mock_tool.name = "invoke_acp_agent"
                mock_tool.description = "Invoke ACP agent"
                with patch("ideer.tools.builtins.invoke_acp_agent_tool.build_invoke_acp_agent_tool", return_value=mock_tool):
                    get_available_tools(app_config=None, include_mcp=False)

        mock_get.assert_called_once()

    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_acp_logging_line(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Line 211: logging when ACP agents are configured."""
        mock_resolve.return_value = MagicMock(spec=BaseTool, name="dummy", func=None, coroutine=None)
        config = _make_config(tools=[], acp_agents={"agent1": {"desc": "test"}})

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "invoke_acp_agent"
        with patch("ideer.tools.builtins.invoke_acp_agent_tool.build_invoke_acp_agent_tool", return_value=mock_tool):
            with caplog.at_level(logging.INFO):
                get_available_tools(app_config=config, include_mcp=False)

        assert "invoke_acp_agent" in caplog.text


# ---------------------------------------------------------------------------
# Line 228: Duplicate tool name warning
# ---------------------------------------------------------------------------


class TestDuplicateToolNames:
    @patch("ideer.tools.tools.is_offline", return_value=False)
    @patch("ideer.tools.tools.is_host_bash_allowed", return_value=True)
    @patch("ideer.tools.tools.resolve_variable")
    def test_duplicate_tool_name_skipped(self, mock_resolve, mock_bash, mock_offline, caplog):
        """Line 228: duplicate tool names are detected and skipped."""
        # Create two tool configs with the same resolved name
        tool_cfg1 = _make_tool_config(name="tool_a", group="g1", use="mod1:tool_dup")
        tool_cfg2 = _make_tool_config(name="tool_b", group="g2", use="mod2:tool_dup")

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "tool_dup"
        mock_tool.func = None
        mock_tool.coroutine = None
        mock_resolve.return_value = mock_tool

        config = _make_config(tools=[tool_cfg1, tool_cfg2])
        with caplog.at_level(logging.WARNING):
            result = get_available_tools(app_config=config, include_mcp=False)

        # Only one instance of the tool should appear
        count = sum(1 for t in result if t.name == "tool_dup")
        assert count == 1
        assert "Duplicate tool name" in caplog.text


# ---------------------------------------------------------------------------
# _ensure_sync_invocable_tool
# ---------------------------------------------------------------------------


class TestEnsureSyncInvocableTool:
    def test_async_only_tool_gets_sync_wrapper(self):
        """Tool with coroutine but no func gets a sync wrapper."""
        tool = MagicMock()
        tool.func = None
        tool.coroutine = MagicMock()
        tool.name = "async_tool"

        with patch("ideer.tools.tools.make_sync_tool_wrapper") as mock_wrapper:
            mock_wrapper.return_value = MagicMock()
            result = _ensure_sync_invocable_tool(tool)

        mock_wrapper.assert_called_once_with(tool.coroutine, tool.name)
        assert result is not None

    def test_tool_with_func_unchanged(self):
        """Tool that already has a func is returned unchanged."""
        tool = MagicMock()
        tool.func = MagicMock()
        tool.coroutine = MagicMock()

        result = _ensure_sync_invocable_tool(tool)
        assert result is tool
