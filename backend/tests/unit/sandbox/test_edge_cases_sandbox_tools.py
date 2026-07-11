"""Additional coverage tests for ideer.sandbox.tools — targeting uncovered lines."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.sandbox.exceptions import SandboxError, SandboxNotFoundError, SandboxRuntimeError

# ---------------------------------------------------------------------------
# Helper to create mock Runtime
# ---------------------------------------------------------------------------


def _make_runtime(
    sandbox_id: str = "local:test",
    thread_data: dict | None = None,
    thread_id: str = "test_thread",
    context: dict | None = None,
) -> MagicMock:
    runtime = MagicMock()
    runtime.state = {}
    if sandbox_id:
        runtime.state["sandbox"] = {"sandbox_id": sandbox_id}
    if thread_data is not None:
        runtime.state["thread_data"] = thread_data
    runtime.context = context or {"thread_id": thread_id}
    runtime.config = {"configurable": {"thread_id": thread_id}}
    return runtime


def _make_thread_data(**overrides) -> dict:
    defaults = {
        "workspace_path": "/tmp/threads/t1/user-data/workspace",
        "uploads_path": "/tmp/threads/t1/user-data/uploads",
        "outputs_path": "/tmp/threads/t1/user-data/outputs",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# _resolve_skills_path edge cases
# ===========================================================================


class TestResolveSkillsPathEdge:
    def test_root_only(self):
        from ideer.sandbox.tools import _resolve_skills_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills"):
                result = _resolve_skills_path("/mnt/skills")
                assert result == "/opt/skills"

    def test_subpath(self):
        from ideer.sandbox.tools import _resolve_skills_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills"):
                result = _resolve_skills_path("/mnt/skills/public/SKILL.md")
                assert result == "/opt/skills/public/SKILL.md"

    def test_no_host_path(self):
        from ideer.sandbox.tools import _resolve_skills_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with patch("ideer.sandbox.tools._get_skills_host_path", return_value=None):
                with pytest.raises(FileNotFoundError):
                    _resolve_skills_path("/mnt/skills/test")


# ===========================================================================
# _resolve_acp_workspace_path edge cases
# ===========================================================================


class TestResolveAcpWorkspacePathEdge:
    def test_root_only(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/base/acp"):
            result = _resolve_acp_workspace_path("/mnt/acp-workspace")
            assert result == "/base/acp"

    def test_subpath(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/base/acp"):
            result = _resolve_acp_workspace_path("/mnt/acp-workspace/test.py")
            assert "test.py" in result

    def test_no_host(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None):
            with pytest.raises(FileNotFoundError):
                _resolve_acp_workspace_path("/mnt/acp-workspace/test")

    def test_traversal(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with pytest.raises(PermissionError):
            _resolve_acp_workspace_path("/mnt/acp-workspace/../../etc/passwd")


# ===========================================================================
# _get_acp_workspace_host_path edge cases
# ===========================================================================


class TestGetAcpWorkspaceHostPathEdge:
    def test_with_thread_id_found(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.__str__ = MagicMock(return_value="/base/threads/t1/acp-workspace")
        with patch("ideer.config.paths.get_paths") as mock_get_paths:
            mock_get_paths.return_value.acp_workspace_dir.return_value = mock_path
            with patch("ideer.runtime.user_context.get_effective_user_id", return_value="u1"):
                result = _get_acp_workspace_host_path("t1")
                assert result == "/base/threads/t1/acp-workspace"

    def test_with_thread_id_not_found(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        mock_path = MagicMock()
        mock_path.exists.return_value = False
        with patch("ideer.config.paths.get_paths") as mock_get_paths:
            mock_get_paths.return_value.acp_workspace_dir.return_value = mock_path
            with patch("ideer.runtime.user_context.get_effective_user_id", return_value="u1"):
                result = _get_acp_workspace_host_path("t1")
                assert result is None

    def test_with_thread_id_exception(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        with patch("ideer.config.paths.get_paths", side_effect=Exception("fail")):
            result = _get_acp_workspace_host_path("t1")
            assert result is None

    def test_global_cached(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        saved = getattr(_get_acp_workspace_host_path, "_cached", None)
        try:
            _get_acp_workspace_host_path._cached = "/base/acp"
            result = _get_acp_workspace_host_path(None)
            assert result == "/base/acp"
        finally:
            if hasattr(_get_acp_workspace_host_path, "_cached"):
                delattr(_get_acp_workspace_host_path, "_cached")
            if saved is not None:
                _get_acp_workspace_host_path._cached = saved

    def test_global_not_found(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        saved = getattr(_get_acp_workspace_host_path, "_cached", None)
        if hasattr(_get_acp_workspace_host_path, "_cached"):
            delattr(_get_acp_workspace_host_path, "_cached")
        try:
            mock_paths = MagicMock()
            mock_paths.base_dir = Path("/nonexistent")
            with patch("ideer.config.paths.get_paths", return_value=mock_paths):
                result = _get_acp_workspace_host_path(None)
                assert result is None
        finally:
            if saved is not None:
                _get_acp_workspace_host_path._cached = saved

    def test_global_exception(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        saved = getattr(_get_acp_workspace_host_path, "_cached", None)
        if hasattr(_get_acp_workspace_host_path, "_cached"):
            delattr(_get_acp_workspace_host_path, "_cached")
        try:
            with patch("ideer.config.paths.get_paths", side_effect=Exception("fail")):
                result = _get_acp_workspace_host_path(None)
                assert result is None
        finally:
            if saved is not None:
                _get_acp_workspace_host_path._cached = saved


# ===========================================================================
# _get_mcp_allowed_paths edge cases
# ===========================================================================


class TestGetMcpAllowedPathsEdge:
    def test_no_filesystem_server(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = True
        mock_server.args = ["--flag", "other-server", "/data/"]
        mock_ext = MagicMock()
        mock_ext.mcp_servers = {"fs": mock_server}
        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext):
            result = _get_mcp_allowed_paths()
            assert result == []

    def test_no_args(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = True
        mock_server.args = None
        mock_ext = MagicMock()
        mock_ext.mcp_servers = {"fs": mock_server}
        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext):
            result = _get_mcp_allowed_paths()
            assert result == []

    def test_non_absolute_arg_skipped(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = True
        mock_server.args = ["@modelcontextprotocol/server-filesystem", "relative/path"]
        mock_ext = MagicMock()
        mock_ext.mcp_servers = {"fs": mock_server}
        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext):
            result = _get_mcp_allowed_paths()
            assert result == []


# ===========================================================================
# _truncate_write_file_error_detail — edge cases for kept==0 and tiny budgets
# ===========================================================================


class TestTruncateWriteFileErrorEdge:
    def test_kept_zero(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        result = _truncate_write_file_error_detail("x" * 100, 1)
        assert len(result) <= 1

    def test_very_small_budget(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        result = _truncate_write_file_error_detail("hello world", 5)
        assert len(result) <= 5


# ===========================================================================
# _format_write_file_error edge cases
# ===========================================================================


class TestFormatWriteFileErrorEdge:
    def test_zero_max_chars(self):
        from ideer.sandbox.tools import _format_write_file_error

        result = _format_write_file_error("/test", ValueError("bad"), max_chars=0)
        assert "Error:" in result
        assert "/test" in result

    def test_header_fits_but_detail_budget_zero(self):
        from ideer.sandbox.tools import _format_write_file_error

        # max_chars = len(header) + 2 = detail_budget <= 0
        header = "Error: Failed to write file '/test'"
        result = _format_write_file_error("/test", ValueError("bad"), max_chars=len(header))
        assert "Error:" in result


# ===========================================================================
# _is_non_file_url_token edge cases
# ===========================================================================


class TestIsNonFileUrlTokenEdge:
    def test_ftp_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("ftp://example.com/file") is True

    def test_equals_with_non_file_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("URL=https://example.com") is True

    def test_equals_with_file_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("URL=file:///tmp/test") is False


# ===========================================================================
# _non_file_url_spans edge cases
# ===========================================================================


class TestNonFileUrlSpansEdge:
    def test_multiple_urls(self):
        from ideer.sandbox.tools import _non_file_url_spans

        spans = _non_file_url_spans("curl https://a.com > /tmp/out && curl http://b.com")
        assert len(spans) == 2

    def test_file_url_excluded(self):
        from ideer.sandbox.tools import _non_file_url_spans

        spans = _non_file_url_spans("cat file:///etc/passwd")
        assert len(spans) == 0


# ===========================================================================
# _validate_local_bash_cwd_target — backtick target
# ===========================================================================


class TestValidateLocalBashCwdTargetEdge:
    def test_backtick(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "`pwd`", [])

    def test_dotdot_with_absolute(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "/mnt/user-data/../etc", [])


# ===========================================================================
# _next_cd_target edge cases
# ===========================================================================


class TestNextCdTargetEdge:
    def test_double_dash(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = ["--", "/tmp"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/tmp"

    def test_unknown_flag(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = ["-e", "/tmp"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/tmp"

    def test_redirection_skipped(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = [">", "/dev/null", "/tmp"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/tmp"

    def test_empty_tokens(self):
        from ideer.sandbox.tools import _next_cd_target

        target, idx = _next_cd_target([], 0)
        assert target is None


# ===========================================================================
# _validate_local_bash_root_path_args edge cases
# ===========================================================================


class TestValidateLocalBashRootPathArgsEdge:
    def test_slash_only_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        with pytest.raises(PermissionError, match="/"):
            _validate_local_bash_root_path_args("cat", ["/"], 0)

    def test_non_root_command(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        # Should not raise for non-root command
        _validate_local_bash_root_path_args("echo", ["/etc/passwd"], 0)

    def test_separator_stops(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        _validate_local_bash_root_path_args("cat", [";", "/etc/passwd"], 0)

    def test_redirection_skipped(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        _validate_local_bash_root_path_args("cat", [">", "/tmp/out"], 0)


# ===========================================================================
# _validate_local_bash_shell_tokens edge cases
# ===========================================================================


class TestValidateLocalBashShellTokensEdge:
    def test_assignment_at_start(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        _validate_local_bash_shell_tokens("FOO=bar ls /mnt/user-data/workspace", [])

    def test_builtin_wrapper(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        with pytest.raises(PermissionError):
            _validate_local_bash_shell_tokens("builtin cd ~", [])

    def test_command_wrapper_with_non_cd(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        # 'command ls' is a wrapper but ls is not a cd command, so root path args check runs
        with pytest.raises(PermissionError, match="/"):
            _validate_local_bash_shell_tokens("command cat /", [])

    def test_prefix_keyword_if(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        _validate_local_bash_shell_tokens("if true; then echo ok; fi", [])

    def test_prefix_keyword_while(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        _validate_local_bash_shell_tokens("while true; do echo ok; done", [])

    def test_end_keyword_fi(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        _validate_local_bash_shell_tokens("fi", [])

    def test_end_keyword_done(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        _validate_local_bash_shell_tokens("done", [])


# ===========================================================================
# validate_local_bash_command_paths — cd with absolute path
# ===========================================================================


class TestValidateLocalBashCommandPathsEdge:
    def test_cd_to_allowed_absolute_path(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            validate_local_bash_command_paths("cd /mnt/user-data/workspace", td)

    def test_cd_to_disallowed_path(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError):
            validate_local_bash_command_paths("cd /etc", td)

    def test_command_wrapper_cd_disallowed(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError):
            validate_local_bash_command_paths("command cd /etc", td)

    def test_dotdot_in_token(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError):
            validate_local_bash_command_paths("cat path/../../file", td)


# ===========================================================================
# replace_virtual_path — edge cases
# ===========================================================================


class TestReplaceVirtualPathEdge:
    def test_trailing_slash(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data()
        result = replace_virtual_path("/mnt/user-data/workspace/", td)
        assert result.endswith("/") or result.endswith("\\")

    def test_empty_thread_data(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = {"workspace_path": None, "uploads_path": None, "outputs_path": None}
        result = replace_virtual_path("/mnt/user-data/workspace/file.txt", td)
        assert result == "/mnt/user-data/workspace/file.txt"


# ===========================================================================
# mask_local_paths_in_output — edge cases
# ===========================================================================


class TestMaskLocalPathsInOutputEdge:
    def test_with_acp_workspace_path(self):
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_skills_host_path", return_value=None):
            with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
                with patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"):
                    with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/base/acp"):
                        result = mask_local_paths_in_output("File at /base/acp/test.py", td)
                        assert "/mnt/acp-workspace" in result

    def test_empty_thread_data(self):
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = {"workspace_path": None, "uploads_path": None, "outputs_path": None}
        result = mask_local_paths_in_output("hello", td)
        assert result == "hello"


# ===========================================================================
# _thread_virtual_to_actual_mappings edge cases
# ===========================================================================


class TestThreadVirtualToActualMappingsEdge:
    def test_common_parent(self):
        from ideer.sandbox.tools import _thread_virtual_to_actual_mappings

        td = {
            "workspace_path": "/base/user-data/workspace",
            "uploads_path": "/base/user-data/uploads",
            "outputs_path": "/base/user-data/outputs",
        }
        mappings = _thread_virtual_to_actual_mappings(td)
        assert "/mnt/user-data" in mappings

    def test_mismatched_parents(self):
        from ideer.sandbox.tools import _thread_virtual_to_actual_mappings

        td = {
            "workspace_path": "/a/user-data/workspace",
            "uploads_path": "/b/user-data/uploads",
            "outputs_path": "/a/user-data/outputs",
        }
        mappings = _thread_virtual_to_actual_mappings(td)
        assert "/mnt/user-data" not in mappings

    def test_partial_paths(self):
        from ideer.sandbox.tools import _thread_virtual_to_actual_mappings

        td = {"workspace_path": "/ws", "uploads_path": None, "outputs_path": None}
        mappings = _thread_virtual_to_actual_mappings(td)
        assert "/mnt/user-data/workspace" in mappings
        assert "/mnt/user-data/uploads" not in mappings


# ===========================================================================
# _thread_actual_to_virtual_mappings
# ===========================================================================


class TestThreadActualToVirtualMappings:
    def test_basic(self):
        from ideer.sandbox.tools import _thread_actual_to_virtual_mappings

        td = _make_thread_data()
        mappings = _thread_actual_to_virtual_mappings(td)
        assert td["workspace_path"] in mappings
        assert mappings[td["workspace_path"]] == "/mnt/user-data/workspace"


# ===========================================================================
# ensure_sandbox_initialized_async edge cases
# ===========================================================================


class TestEnsureSandboxInitializedAsyncEdge:
    @pytest.mark.asyncio
    async def test_none_state_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        runtime = MagicMock()
        runtime.state = None
        with pytest.raises(SandboxRuntimeError):
            await ensure_sandbox_initialized_async(runtime)

    @pytest.mark.asyncio
    async def test_no_thread_id_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {}
        runtime.config = {}
        with pytest.raises(SandboxRuntimeError, match="Thread ID"):
            await ensure_sandbox_initialized_async(runtime)

    @pytest.mark.asyncio
    async def test_released_sandbox_reacquired(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        runtime = _make_runtime(sandbox_id="old_id")
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.side_effect = [None, mock_sandbox]
        mock_provider.acquire_async = AsyncMock(return_value="new_id")
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = await ensure_sandbox_initialized_async(runtime)
            assert result is mock_sandbox

    @pytest.mark.asyncio
    async def test_thread_id_from_config(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {}
        runtime.config = {"configurable": {"thread_id": "from_config"}}
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.acquire_async = AsyncMock(return_value="new_id")
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = await ensure_sandbox_initialized_async(runtime)
            assert result is mock_sandbox

    @pytest.mark.asyncio
    async def test_sandbox_not_found_after_acquire(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {"thread_id": "t1"}
        runtime.config = {"configurable": {"thread_id": "t1"}}
        mock_provider = MagicMock()
        mock_provider.acquire_async = AsyncMock(return_value="new_id")
        mock_provider.get.return_value = None
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with pytest.raises(SandboxNotFoundError):
                await ensure_sandbox_initialized_async(runtime)


# ===========================================================================
# _run_sync_tool_after_async_sandbox_init edge cases
# ===========================================================================


class TestRunSyncToolAfterAsyncEdge:
    @pytest.mark.asyncio
    async def test_sandbox_error(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", side_effect=SandboxError("fail")):
            result = await _run_sync_tool_after_async_sandbox_init(None, runtime)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_unexpected_error(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", side_effect=RuntimeError("boom")):
            result = await _run_sync_tool_after_async_sandbox_init(None, runtime)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_none_func(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", return_value=mock_sandbox):
            result = await _run_sync_tool_after_async_sandbox_init(None, runtime)
            assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_success_with_args(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        sync_func = MagicMock(return_value="result")
        with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", return_value=mock_sandbox):
            result = await _run_sync_tool_after_async_sandbox_init(sync_func, runtime, "arg1", "arg2")
            assert result == "result"


# ===========================================================================
# bash_tool — edge cases
# ===========================================================================


class TestBashToolEdge:
    def test_local_sandbox_unexpected_error(self):
        from ideer.sandbox.tools import bash_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = RuntimeError("unexpected")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.is_host_bash_allowed", return_value=True):
                    with patch("ideer.sandbox.tools.ensure_thread_directories_exist"):
                        with patch("ideer.sandbox.tools.get_thread_data", return_value=_make_thread_data()):
                            with patch("ideer.sandbox.tools.validate_local_bash_command_paths"):
                                with patch("ideer.sandbox.tools.replace_virtual_paths_in_command", return_value="ls"):
                                    with patch("ideer.sandbox.tools._apply_cwd_prefix", return_value="ls"):
                                        result = bash_tool.func(runtime, "test", "ls")
                                        assert "Error" in result


# ===========================================================================
# ls_tool — edge cases
# ===========================================================================


class TestLsToolEdge:
    def test_local_acp_workspace_path(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["file.py"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
                        with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
                            with patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp"):
                                with patch("ideer.sandbox.tools.get_thread_data", return_value=_make_thread_data()):
                                    with patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="file.py"):
                                        with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                                            mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
                                            result = ls_tool.func(runtime, "test", "/mnt/acp-workspace")
                                            assert "file.py" in result

    def test_local_custom_mount_path(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["data.txt"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
                        with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                            with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
                                with patch("ideer.sandbox.tools.get_thread_data", return_value=_make_thread_data()):
                                    with patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="data.txt"):
                                        with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                                            mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
                                            result = ls_tool.func(runtime, "test", "/mnt/custom/data.txt")
                                            assert "data.txt" in result


# ===========================================================================
# read_file_tool — edge cases
# ===========================================================================


class TestReadFileToolEdge:
    def test_local_skills_path(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
                        with patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills"):
                            with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                                mock_cfg.return_value.sandbox.read_file_output_max_chars = 50000
                                result = read_file_tool.func(runtime, "test", "/mnt/skills/test.md")
                                assert "content" in result

    def test_local_acp_path(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "acp content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
                        with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
                            with patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp"):
                                with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                                    mock_cfg.return_value.sandbox.read_file_output_max_chars = 50000
                                    result = read_file_tool.func(runtime, "test", "/mnt/acp-workspace/test.py")
                                    assert "acp content" in result

    def test_local_custom_mount_path(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "mount content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
                        with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                            with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
                                with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                                    mock_cfg.return_value.sandbox.read_file_output_max_chars = 50000
                                    result = read_file_tool.func(runtime, "test", "/mnt/mount/file.txt")
                                    assert "mount content" in result


# ===========================================================================
# write_file_tool — edge cases
# ===========================================================================


class TestWriteFileToolEdge:
    def test_local_custom_mount(self):
        from ideer.sandbox.tools import write_file_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
                        with patch("ideer.sandbox.tools.get_thread_data", return_value=_make_thread_data()):
                            with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                                result = write_file_tool.func(runtime, "test", "/mnt/mount/file.txt", "data")
                                assert result == "OK"


# ===========================================================================
# str_replace_tool — edge cases
# ===========================================================================


class TestStrReplaceToolEdge:
    def test_local_custom_mount(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "hello world"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
                        with patch("ideer.sandbox.tools.get_thread_data", return_value=_make_thread_data()):
                            with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                                result = str_replace_tool.func(runtime, "test", "/mnt/mount/file.txt", "hello", "bye")
                                assert result == "OK"


# ===========================================================================
# _validate_resolved_user_data_path edge cases
# ===========================================================================


class TestValidateResolvedUserDataPathEdge:
    def test_valid_in_uploads(self, tmp_path):
        from ideer.sandbox.tools import _validate_resolved_user_data_path

        uploads = tmp_path / "uploads"
        uploads.mkdir()
        file = uploads / "photo.png"
        file.touch()
        td = {"workspace_path": None, "uploads_path": str(uploads), "outputs_path": None}
        _validate_resolved_user_data_path(file.resolve(), td)

    def test_valid_in_outputs(self, tmp_path):
        from ideer.sandbox.tools import _validate_resolved_user_data_path

        outputs = tmp_path / "outputs"
        outputs.mkdir()
        file = outputs / "report.pdf"
        file.touch()
        td = {"workspace_path": None, "uploads_path": None, "outputs_path": str(outputs)}
        _validate_resolved_user_data_path(file.resolve(), td)

    def test_invalid_path(self, tmp_path):
        from ideer.sandbox.tools import _validate_resolved_user_data_path

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        file = outside / "secret.txt"
        file.touch()
        td = {"workspace_path": str(workspace), "uploads_path": None, "outputs_path": None}
        with pytest.raises(PermissionError, match="path traversal"):
            _validate_resolved_user_data_path(file.resolve(), td)


# ===========================================================================
# ensure_sandbox_initialized — thread_id from config
# ===========================================================================


class TestEnsureSandboxInitializedEdge:
    def test_thread_id_from_config(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {}
        runtime.config = {"configurable": {"thread_id": "from_config"}}
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.acquire.return_value = "new_id"
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = ensure_sandbox_initialized(runtime)
            assert result is mock_sandbox
            mock_provider.acquire.assert_called_once_with("from_config")

    def test_sandbox_not_found_after_acquire(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {"thread_id": "t1"}
        runtime.config = {"configurable": {"thread_id": "t1"}}
        mock_provider = MagicMock()
        mock_provider.acquire.return_value = "new_id"
        mock_provider.get.return_value = None
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with pytest.raises(SandboxNotFoundError):
                ensure_sandbox_initialized(runtime)
