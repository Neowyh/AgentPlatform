"""Coverage tests for ideer.sandbox.tools uncovered lines.

Targets the following uncovered lines:
- Lines 100-101, 124-126, 188-191: error paths in config-loading helpers
- Lines 227-228, 250-251, 262-266: path resolution error/success paths
- Lines 302-304, 307-313: ACP workspace path traversal / Windows resolution
- Line 333: MCP allowed paths skip non-filesystem server
- Line 449, 471: truncation edge cases
- Lines 561, 580, 606: mask_local_paths_in_output exact-match branches
- Lines 755-758: _split_shell_tokens ValueError fallback
- Lines 823-824: _next_cd_target unknown flag
- Lines 911-912: wrapped cd/pushd in shell validation
- Line 1189: async sandbox init SandboxNotFoundError
- Lines 1357-1358, 1366-1367: bash_tool config exception fallbacks
- Lines 1403, 1418-1419, 1422: ls_tool ACP path, config fallback, SandboxError
- Lines 1470, 1479, 1484-1485: glob_tool error paths
- Lines 1546, 1569, 1571, 1576-1577: grep_tool error paths
- Lines 1630, 1632, 1646-1647: read_file_tool skills/ACP path, config fallback
- Lines 1758-1761: str_replace_tool local sandbox path resolution
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.sandbox.search import GrepMatch


def _run_async(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runtime(sandbox_id="test-sandbox", thread_data=None, thread_id="t1", context=None):
    """Create a mock Runtime for tool functions."""
    runtime = MagicMock()
    runtime.state = {}
    if sandbox_id:
        runtime.state["sandbox"] = {"sandbox_id": sandbox_id}
    if thread_data is not None:
        runtime.state["thread_data"] = thread_data
    runtime.context = context or {"thread_id": thread_id}
    runtime.config = {"configurable": {"thread_id": thread_id}}
    return runtime


def _make_thread_data(**overrides):
    """Create thread data with sensible defaults."""
    defaults = {
        "workspace_path": "/tmp/threads/t1/user-data/workspace",
        "uploads_path": "/tmp/threads/t1/user-data/uploads",
        "outputs_path": "/tmp/threads/t1/user-data/outputs",
    }
    defaults.update(overrides)
    return defaults


def _patch_sandbox_and_provider():
    """Return a context-manager tuple (mock_sandbox, patch objects)."""
    mock_sandbox = MagicMock()
    mock_provider = MagicMock()
    mock_provider.get.return_value = mock_sandbox
    return mock_sandbox, mock_provider


# ===================================================================
# Lines 100-101: _get_skills_container_path error fallback
# ===================================================================


class TestGetSkillsContainerPathError:
    """Lines 100-101: when get_app_config raises, return default."""

    def test_returns_default_on_exception(self):
        from ideer.sandbox.tools import _get_skills_container_path

        # Clear any cached value
        if hasattr(_get_skills_container_path, "_cached"):
            delattr(_get_skills_container_path, "_cached")

        with patch("ideer.config.get_app_config", side_effect=RuntimeError("no config")):
            result = _get_skills_container_path()

        assert result == "/mnt/skills"

    def test_caches_after_success(self):
        from ideer.sandbox.tools import _get_skills_container_path

        if hasattr(_get_skills_container_path, "_cached"):
            delattr(_get_skills_container_path, "_cached")

        mock_config = MagicMock()
        mock_config.skills.container_path = "/custom/skills"
        with patch("ideer.config.get_app_config", return_value=mock_config):
            result = _get_skills_container_path()

        assert result == "/custom/skills"
        # Cleanup
        delattr(_get_skills_container_path, "_cached")


# ===================================================================
# Lines 124-126: _get_skills_host_path error fallback
# ===================================================================


class TestGetSkillsHostPathError:
    """Lines 124-126: when get_app_config raises, return None (no caching)."""

    def test_returns_none_on_exception(self):
        from ideer.sandbox.tools import _get_skills_host_path

        if hasattr(_get_skills_host_path, "_cached"):
            delattr(_get_skills_host_path, "_cached")

        with patch("ideer.config.get_app_config", side_effect=RuntimeError("fail")):
            result = _get_skills_host_path()

        assert result is None

    def test_returns_none_when_path_does_not_exist(self):
        from ideer.sandbox.tools import _get_skills_host_path

        if hasattr(_get_skills_host_path, "_cached"):
            delattr(_get_skills_host_path, "_cached")

        mock_config = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_config.skills.get_skills_path.return_value = mock_path
        with patch("ideer.config.get_app_config", return_value=mock_config):
            result = _get_skills_host_path()

        assert result is None


# ===================================================================
# Lines 188-191: _get_custom_mounts error fallback
# ===================================================================


class TestGetCustomMountsError:
    """Lines 188-191: when config loading fails, return empty list without caching."""

    def test_returns_empty_list_on_exception(self):
        from ideer.sandbox.tools import _get_custom_mounts

        if hasattr(_get_custom_mounts, "_cached"):
            delattr(_get_custom_mounts, "_cached")

        with patch("ideer.config.get_app_config", side_effect=RuntimeError("fail")):
            result = _get_custom_mounts()

        assert result == []

    def test_returns_empty_list_when_no_mounts_configured(self):
        from ideer.sandbox.tools import _get_custom_mounts

        if hasattr(_get_custom_mounts, "_cached"):
            delattr(_get_custom_mounts, "_cached")

        mock_config = MagicMock()
        mock_config.sandbox = None
        with patch("ideer.config.get_app_config", return_value=mock_config):
            result = _get_custom_mounts()

        assert result == []
        if hasattr(_get_custom_mounts, "_cached"):
            delattr(_get_custom_mounts, "_cached")


# ===================================================================
# Lines 227-228: _extract_thread_id_from_thread_data error path
# ===================================================================


class TestExtractThreadIdError:
    """Lines 227-228: Path().parent.parent.name raises."""

    def test_returns_none_when_path_operations_fail(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        thread_data = _make_thread_data(workspace_path=12345)  # not a string
        # Path(12345) raises TypeError, which is caught
        result = _extract_thread_id_from_thread_data(thread_data)
        assert result is None

    def test_returns_none_for_none_thread_data(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        assert _extract_thread_id_from_thread_data(None) is None

    def test_returns_none_for_empty_workspace_path(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        assert _extract_thread_id_from_thread_data({"workspace_path": ""}) is None


# ===================================================================
# Lines 250-251: _get_acp_workspace_host_path with thread_id error path
# ===================================================================


class TestGetAcpWorkspaceHostPathThreadIdError:
    """Lines 250-251: exception during per-thread ACP workspace resolution."""

    def test_returns_none_on_exception_with_thread_id(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        with patch("ideer.config.paths.get_paths", side_effect=RuntimeError("fail")):
            result = _get_acp_workspace_host_path("some-thread")

        assert result is None

    def test_returns_none_when_path_not_exists_with_thread_id(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        mock_paths = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_paths.acp_workspace_dir.return_value = mock_path

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            with patch("ideer.runtime.user_context.get_effective_user_id", return_value="user1"):
                result = _get_acp_workspace_host_path("some-thread")

        assert result is None


# ===================================================================
# Lines 262-266: _get_acp_workspace_host_path without thread_id success + cache
# ===================================================================


class TestGetAcpWorkspaceHostPathGlobal:
    """Lines 262-266: global ACP workspace path resolution and caching."""

    def test_returns_cached_global_path(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        if hasattr(_get_acp_workspace_host_path, "_cached"):
            delattr(_get_acp_workspace_host_path, "_cached")

        mock_paths = MagicMock()
        mock_base = MagicMock()
        mock_acp = MagicMock()
        mock_acp.exists.return_value = True
        mock_base.__truediv__ = MagicMock(return_value=mock_acp)
        mock_paths.base_dir = mock_base

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _get_acp_workspace_host_path(None)

        assert result == str(mock_acp)
        # Cleanup
        delattr(_get_acp_workspace_host_path, "_cached")

    def test_returns_none_when_global_path_not_exists(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        if hasattr(_get_acp_workspace_host_path, "_cached"):
            delattr(_get_acp_workspace_host_path, "_cached")

        mock_paths = MagicMock()
        mock_base = MagicMock()
        mock_acp = MagicMock()
        mock_acp.exists.return_value = False
        mock_base.__truediv__ = MagicMock(return_value=mock_acp)
        mock_paths.base_dir = mock_base

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _get_acp_workspace_host_path(None)

        assert result is None


# ===================================================================
# Lines 302-304, 307-313: _resolve_acp_workspace_path traversal checks
# ===================================================================


class TestResolveAcpWorkspacePathTraversal:
    """Lines 302-304 and 307-313: path traversal detection in ACP workspace."""

    def test_raises_permission_error_for_dotdot_traversal(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with pytest.raises(PermissionError, match="path traversal"):
            _resolve_acp_workspace_path("/mnt/acp-workspace/../../../etc/passwd")

    def test_raises_permission_error_when_commonpath_mismatch(self):
        """Lines 301-304: posixpath.commonpath does not match base."""
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        mock_host = "/home/user/acp-workspace"

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=mock_host):
            # Craft a path that would escape via symlinks/resolution
            # Use a path that when joined resolves outside the host
            with patch("posixpath.commonpath", return_value="/home/user/other"):
                with pytest.raises(PermissionError, match="path traversal"):
                    _resolve_acp_workspace_path("/mnt/acp-workspace/escape", thread_id="t1")

    def test_resolves_path_on_posix_success(self):
        """Lines 297-305: successful POSIX path resolution."""
        import os
        import tempfile

        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with tempfile.TemporaryDirectory() as td:
            acp_dir = os.path.join(td, "acp-workspace")
            os.makedirs(acp_dir)
            test_file = os.path.join(acp_dir, "test.py")
            Path(test_file).touch()

            with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=acp_dir):
                result = _resolve_acp_workspace_path("/mnt/acp-workspace/test.py", thread_id="t1")

            assert "test.py" in result


# ===================================================================
# Line 333: _get_mcp_allowed_paths skip non-filesystem server
# ===================================================================


class TestGetMcpAllowedPaths:
    """Line 333: skip server without server-filesystem in args."""

    def test_skips_non_filesystem_server(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = True
        mock_server.args = ["--some-flag", "/some/path"]

        mock_ext_config = MagicMock()
        mock_ext_config.mcp_servers = {"other": mock_server}

        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext_config):
            result = _get_mcp_allowed_paths()

        assert result == []

    def test_includes_filesystem_server_paths(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = True
        mock_server.args = ["npx", "@modelcontextprotocol/server-filesystem", "/data/"]

        mock_ext_config = MagicMock()
        mock_ext_config.mcp_servers = {"fs": mock_server}

        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext_config):
            result = _get_mcp_allowed_paths()

        assert "/data/" in result

    def test_skips_disabled_server(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = False
        mock_server.args = ["@modelcontextprotocol/server-filesystem", "/data/"]

        mock_ext_config = MagicMock()
        mock_ext_config.mcp_servers = {"fs": mock_server}

        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext_config):
            result = _get_mcp_allowed_paths()

        assert result == []


# ===================================================================
# Line 449: _truncate_write_file_error_detail kept == 0 fallback
# ===================================================================


class TestTruncateWriteFileErrorDetail:
    """Line 449: when kept == 0, return detail[:max_chars]."""

    def test_kept_zero_returns_head(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "A" * 100
        # Use a very small max_chars so kept = 0
        result = _truncate_write_file_error_detail(detail, max_chars=2)
        assert len(result) <= 2

    def test_zero_max_chars_returns_full(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "some error detail"
        result = _truncate_write_file_error_detail(detail, max_chars=0)
        assert result == detail

    def test_short_detail_returns_unchanged(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "short"
        result = _truncate_write_file_error_detail(detail, max_chars=200)
        assert result == detail


# ===================================================================
# Line 471: _format_write_file_error detail_budget <= 0
# ===================================================================


class TestFormatWriteFileError:
    """Line 471: when header is longer than max_chars."""

    def test_header_exceeds_max_chars(self):
        from ideer.sandbox.tools import _format_write_file_error

        error = RuntimeError("some error")
        result = _format_write_file_error("a" * 200, error, max_chars=10)
        assert "Error" in result
        assert len(result) <= 10

    def test_normal_case(self):
        from ideer.sandbox.tools import _format_write_file_error

        error = RuntimeError("disk full")
        result = _format_write_file_error("/tmp/test.txt", error, max_chars=200)
        assert "Error" in result
        assert "/tmp/test.txt" in result


# ===================================================================
# Lines 561, 580, 606: mask_local_paths_in_output exact-match branches
# ===================================================================


class TestMaskLocalPathsInOutput:
    """Lines 561, 580, 606: exact path matching in masking."""

    @patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None)
    @patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills")
    @patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills")
    def test_mask_skills_exact_match(self, *_):
        """Line 561: skills host path exact match replaced with container path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        result = mask_local_paths_in_output("/opt/skills", None)
        assert result == "/mnt/skills"

    @patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None)
    @patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills")
    @patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills")
    def test_mask_skills_with_relative_path(self, *_):
        """Skills host path with sub-path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        result = mask_local_paths_in_output("File at /opt/skills/public/SKILL.md", None)
        assert "/mnt/skills/public/SKILL.md" in result

    @patch("ideer.sandbox.tools._get_skills_host_path", return_value=None)
    @patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills")
    def test_mask_acp_workspace_exact_match(self, *_):
        """Line 580: ACP host path exact match replaced with virtual path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/home/user/acp"):
            result = mask_local_paths_in_output("/home/user/acp", None)
        assert result == "/mnt/acp-workspace"

    @patch("ideer.sandbox.tools._get_skills_host_path", return_value=None)
    @patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills")
    def test_mask_acp_workspace_with_subpath(self, *_):
        """ACP host path with sub-path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/home/user/acp"):
            result = mask_local_paths_in_output("output /home/user/acp/file.py done", None)
        assert "/mnt/acp-workspace/file.py" in result

    @patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None)
    @patch("ideer.sandbox.tools._get_skills_host_path", return_value=None)
    @patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills")
    def test_mask_user_data_exact_match(self, *_):
        """Line 606: user-data host path exact match replaced with virtual path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data(workspace_path="/tmp/threads/t1/user-data/workspace")
        result = mask_local_paths_in_output("/tmp/threads/t1/user-data/workspace", td)
        assert "/mnt/user-data/workspace" in result


# ===================================================================
# Lines 755-758: _split_shell_tokens ValueError fallback
# ===================================================================


class TestSplitShellTokens:
    """Lines 755-758: shlex ValueError fallback to str.split()."""

    def test_malformed_quoting_falls_back(self):
        from ideer.sandbox.tools import _split_shell_tokens

        # Unclosed quote triggers ValueError in shlex
        result = _split_shell_tokens('echo "unclosed')
        assert isinstance(result, list)
        assert len(result) > 0

    def test_normal_command(self):
        from ideer.sandbox.tools import _split_shell_tokens

        result = _split_shell_tokens("echo hello world")
        assert "echo" in result


# ===================================================================
# Lines 823-824: _next_cd_target unknown flag
# ===================================================================


class TestNextCdTarget:
    """Lines 823-824: unknown flags like -X are skipped."""

    def test_skips_unknown_flags(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = ["-X", "/some/path"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/some/path"

    def test_returns_none_at_separator(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = [";", "echo"]
        target, idx = _next_cd_target(tokens, 0)
        assert target is None

    def test_skips_redirection(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = [">", "/dev/null", "/target"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/target"

    def test_returns_none_when_no_target(self):
        from ideer.sandbox.tools import _next_cd_target

        target, idx = _next_cd_target([], 0)
        assert target is None


# ===================================================================
# Lines 911-912: wrapped cd/pushd in _validate_local_bash_shell_tokens
# ===================================================================


class TestWrappedCommandValidation:
    """Lines 911-912: 'command cd /path' and 'builtin pushd /path' validation."""

    def test_wrapped_cd_validates_cwd_target(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            _validate_local_bash_shell_tokens("command cd /etc", [])

    def test_wrapped_pushd_validates_cwd_target(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            _validate_local_bash_shell_tokens("builtin pushd /root", [])


# ===================================================================
# Line 1189: ensure_sandbox_initialized_async SandboxNotFoundError
# ===================================================================


class TestEnsureSandboxInitializedAsync:
    """Line 1189: async sandbox init raises SandboxNotFoundError."""

    def test_raises_not_found_after_async_acquisition(self):
        from ideer.sandbox.exceptions import SandboxNotFoundError
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            runtime = _make_runtime(sandbox_id=None)
            runtime.state = {}
            runtime.context = {"thread_id": "t1"}

            mock_provider = MagicMock()
            mock_provider.acquire_async = AsyncMock(return_value="new-id")
            mock_provider.get.return_value = None

            with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
                with pytest.raises(SandboxNotFoundError):
                    await ensure_sandbox_initialized_async(runtime)

        _run_async(go())

    def test_raises_when_runtime_is_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            with pytest.raises(SandboxRuntimeError, match="Tool runtime not available"):
                await ensure_sandbox_initialized_async(None)

        _run_async(go())

    def test_raises_when_state_is_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            runtime = MagicMock()
            runtime.state = None

            with pytest.raises(SandboxRuntimeError, match="Tool runtime state not available"):
                await ensure_sandbox_initialized_async(runtime)

        _run_async(go())

    def test_raises_when_thread_id_missing(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            runtime = MagicMock()
            runtime.state = {}
            runtime.context = {}
            runtime.config = {}

            with pytest.raises(SandboxRuntimeError, match="Thread ID not available"):
                await ensure_sandbox_initialized_async(runtime)

        _run_async(go())

    def test_returns_existing_sandbox_from_state(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            mock_sandbox = MagicMock()
            mock_provider = MagicMock()
            mock_provider.get.return_value = mock_sandbox

            runtime = _make_runtime(sandbox_id="existing-id")

            with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
                result = await ensure_sandbox_initialized_async(runtime)

            assert result is mock_sandbox

        _run_async(go())


# ===================================================================
# Lines 1357-1358, 1366-1367: bash_tool config exception fallbacks
# ===================================================================


class TestBashToolConfigFallback:
    """Lines 1357-1358 and 1366-1367: config load exception -> default max_chars."""

    def test_local_sandbox_config_exception_uses_default(self):
        """Lines 1357-1358."""
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "output"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.is_host_bash_allowed", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_bash_command_paths"),
            patch("ideer.sandbox.tools.replace_virtual_paths_in_command", return_value="echo hi"),
            patch("ideer.sandbox.tools._apply_cwd_prefix", return_value="echo hi"),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="output"),
            patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = bash_tool.func(runtime, "test desc", "echo hi")

        assert "output" in result

    def test_non_local_sandbox_config_exception_uses_default(self):
        """Lines 1366-1367."""
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "result"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        runtime = _make_runtime(sandbox_id="remote")

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=False),
            patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = bash_tool.func(runtime, "test desc", "ls")

        assert "result" in result


# ===================================================================
# Line 1403, 1418-1419, 1422: ls_tool ACP path, config fallback, SandboxError
# ===================================================================


class TestLsToolCoverage:
    """ls_tool uncovered paths."""

    def test_acp_workspace_path_resolution(self):
        """Line 1403: ls resolves ACP workspace path."""
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["file.py"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="file.py"),
            patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = ls_tool.func(runtime, "test", "/mnt/acp-workspace")

        assert "file.py" in result

    def test_config_exception_fallback(self):
        """Lines 1418-1419: config exception uses default max_chars."""
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["a.txt"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("fail")):
            result = ls_tool.func(runtime, "test", "/data")

        assert "a.txt" in result

    def test_sandbox_error_returns_error_string(self):
        """Line 1422: SandboxError caught."""
        from ideer.sandbox.exceptions import SandboxError
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.side_effect = SandboxError("sandbox down")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = ls_tool.func(runtime, "test", "/data")

        assert "Error" in result


# ===================================================================
# Lines 1470, 1479, 1484-1485: glob_tool error paths
# ===================================================================


class TestGlobToolCoverage:
    """glob_tool uncovered error paths."""

    def test_raises_when_local_thread_data_is_none(self):
        """Line 1470: SandboxRuntimeError for missing thread data."""
        from ideer.sandbox.tools import glob_tool

        mock_provider = MagicMock()
        mock_provider.get.return_value = MagicMock()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=None)

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=True), patch("ideer.sandbox.tools.get_thread_data", return_value=None):
            result = glob_tool.func(runtime, "test", "*.py", "/data")

        assert "Error" in result

    def test_file_not_found_error(self):
        """Line 1479: FileNotFoundError caught."""
        from ideer.sandbox.tools import glob_tool

        mock_sandbox = MagicMock()
        mock_sandbox.glob.side_effect = FileNotFoundError("not found")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = glob_tool.func(runtime, "test", "*.py", "/nonexistent")

        assert "not found" in result.lower() or "Error" in result

    def test_unexpected_exception(self):
        """Lines 1484-1485: generic Exception caught."""
        from ideer.sandbox.tools import glob_tool

        mock_sandbox = MagicMock()
        mock_sandbox.glob.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = glob_tool.func(runtime, "test", "*.py", "/data")

        assert "Error" in result

    def test_not_a_directory_error(self):
        """NotADirectoryError path."""
        from ideer.sandbox.tools import glob_tool

        mock_sandbox = MagicMock()
        mock_sandbox.glob.side_effect = NotADirectoryError("not a dir")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = glob_tool.func(runtime, "test", "*.py", "/file.txt")

        assert "not a directory" in result.lower()


# ===================================================================
# Lines 1546, 1569, 1571, 1576-1577: grep_tool error paths
# ===================================================================


class TestGrepToolCoverage:
    """grep_tool uncovered error paths."""

    def test_raises_when_local_thread_data_is_none(self):
        """Line 1546: SandboxRuntimeError for missing thread data."""
        from ideer.sandbox.tools import grep_tool

        mock_provider = MagicMock()
        mock_provider.get.return_value = MagicMock()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=None)

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=True), patch("ideer.sandbox.tools.get_thread_data", return_value=None):
            result = grep_tool.func(runtime, "test", "pattern", "/data")

        assert "Error" in result

    def test_file_not_found_error(self):
        """Line 1569: FileNotFoundError caught."""
        from ideer.sandbox.tools import grep_tool

        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = FileNotFoundError("not found")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = grep_tool.func(runtime, "test", "pattern", "/nonexistent")

        assert "Error" in result

    def test_not_a_directory_error(self):
        """Line 1571: NotADirectoryError caught."""
        from ideer.sandbox.tools import grep_tool

        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = NotADirectoryError("not a dir")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = grep_tool.func(runtime, "test", "pattern", "/file.txt")

        assert "not a directory" in result.lower()

    def test_unexpected_exception(self):
        """Lines 1576-1577: generic Exception caught."""
        from ideer.sandbox.tools import grep_tool

        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = grep_tool.func(runtime, "test", "pattern", "/data")

        assert "Error" in result

    def test_regex_error(self):
        """re.error path in grep."""
        import re as re_mod

        from ideer.sandbox.tools import grep_tool

        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = re_mod.error("bad regex")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = grep_tool.func(runtime, "test", "[invalid", "/data")

        assert "Invalid regex" in result

    def test_permission_error(self):
        """PermissionError path in grep."""
        from ideer.sandbox.tools import grep_tool

        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = grep_tool.func(runtime, "test", "pattern", "/data")

        assert "Permission denied" in result


# ===================================================================
# Lines 1630, 1632, 1646-1647: read_file_tool paths
# ===================================================================


class TestReadFileToolCoverage:
    """read_file_tool uncovered paths."""

    def test_skills_path_resolution(self):
        """Line 1630: skills path resolved in read_file_tool."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills/SKILL.md"),
            patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = read_file_tool.func(runtime, "test", "/mnt/skills/SKILL.md")

        assert "content" in result

    def test_acp_workspace_path_resolution(self):
        """Line 1632: ACP workspace path resolved in read_file_tool."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "acp content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp/file.py"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False),
            patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = read_file_tool.func(runtime, "test", "/mnt/acp-workspace/file.py")

        assert "acp content" in result

    def test_config_exception_fallback(self):
        """Lines 1646-1647: config exception uses default max_chars."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "some content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("fail")):
            result = read_file_tool.func(runtime, "test", "/data/file.txt")

        assert "some content" in result

    def test_start_line_end_line_slice(self):
        """Lines 1639-1640: start_line and end_line slice content."""
        from ideer.sandbox.tools import read_file_tool

        content = "line1\nline2\nline3\nline4\nline5"
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = content
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
            mock_cfg.return_value.sandbox.read_file_output_max_chars = 50000
            result = read_file_tool.func(runtime, "test", "/data/file.txt", start_line=2, end_line=4)

        assert "line2" in result
        assert "line4" in result


# ===================================================================
# Lines 1758-1761: str_replace_tool local sandbox path resolution
# ===================================================================


class TestStrReplaceToolCoverage:
    """Lines 1758-1761: local sandbox path validation and resolution."""

    def test_local_sandbox_custom_mount_path(self):
        """Lines 1760-1761: custom mount path skips user-data resolution."""
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "old content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        lock = threading.Lock()
        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True),
            patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock),
        ):
            result = str_replace_tool.func(runtime, "test", "/mnt/custom/file.txt", "old", "new")

        assert result == "OK"
        mock_sandbox.write_file.assert_called_once()

    def test_local_sandbox_user_data_path(self):
        """Lines 1758-1761: user-data path resolved."""
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "hello world"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        lock = threading.Lock()
        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False),
            patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/tmp/resolved/file.txt"),
            patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock),
        ):
            result = str_replace_tool.func(runtime, "test", "/mnt/user-data/workspace/file.txt", "hello", "bye")

        assert result == "OK"

    def test_replace_all(self):
        """replace_all=True replaces all occurrences."""
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "aaa bbb aaa"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = str_replace_tool.func(runtime, "test", "/data/file.txt", "aaa", "xxx", replace_all=True)

        assert result == "OK"
        written_content = mock_sandbox.write_file.call_args[0][1]
        assert "xxx bbb xxx" == written_content

    def test_string_not_found(self):
        """old_str not in content returns error."""
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "some content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = str_replace_tool.func(runtime, "test", "/data/file.txt", "not_found", "new")

        assert "not found" in result.lower()

    def test_empty_content_returns_ok(self):
        """Empty file content returns OK immediately."""
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = ""
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = str_replace_tool.func(runtime, "test", "/data/file.txt", "old", "new")

        assert result == "OK"


# ===================================================================
# Additional edge-case coverage
# ===================================================================


class TestWriteFileToolCoverage:
    """write_file_tool additional error paths."""

    def test_sandbox_error_returns_formatted_error(self):
        from ideer.sandbox.exceptions import SandboxFileError
        from ideer.sandbox.tools import write_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.write_file.side_effect = SandboxFileError("write failed", path="/x", operation="write")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = write_file_tool.func(runtime, "test", "/data/file.txt", "content")

        assert "Error" in result

    def test_permission_error(self):
        from ideer.sandbox.tools import write_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.write_file.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = write_file_tool.func(runtime, "test", "/data/file.txt", "content")

        assert "Permission denied" in result

    def test_is_a_directory_error(self):
        from ideer.sandbox.tools import write_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.write_file.side_effect = IsADirectoryError("is a dir")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = write_file_tool.func(runtime, "test", "/data/dir", "content")

        assert "directory" in result.lower()

    def test_os_error(self):
        from ideer.sandbox.tools import write_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.write_file.side_effect = OSError("disk full")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = write_file_tool.func(runtime, "test", "/data/file.txt", "content")

        assert "Error" in result


class TestReadFileToolErrors:
    """read_file_tool additional error paths."""

    def test_sandbox_error(self):
        from ideer.sandbox.exceptions import SandboxError
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = read_file_tool.func(runtime, "test", "/data/file.txt")

        assert "Error" in result

    def test_file_not_found(self):
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = FileNotFoundError("not found")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = read_file_tool.func(runtime, "test", "/data/missing.txt")

        assert "not found" in result.lower()

    def test_is_a_directory_error(self):
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = IsADirectoryError("is a dir")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = read_file_tool.func(runtime, "test", "/data/dir")

        assert "directory" in result.lower()

    def test_unexpected_error(self):
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = read_file_tool.func(runtime, "test", "/data/file.txt")

        assert "Error" in result


class TestLsToolErrors:
    """ls_tool additional error paths."""

    def test_file_not_found(self):
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.side_effect = FileNotFoundError("not found")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = ls_tool.func(runtime, "test", "/nonexistent")

        assert "not found" in result.lower()

    def test_permission_error(self):
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = ls_tool.func(runtime, "test", "/data")

        assert "Permission denied" in result

    def test_unexpected_error(self):
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = ls_tool.func(runtime, "test", "/data")

        assert "Error" in result


class TestBashToolErrors:
    """bash_tool additional error paths."""

    def test_sandbox_error(self):
        from ideer.sandbox.exceptions import SandboxError
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = bash_tool.func(runtime, "test", "bad cmd")

        assert "Error" in result

    def test_permission_error(self):
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = bash_tool.func(runtime, "test", "restricted cmd")

        assert "PermissionError" in result or "denied" in result

    def test_unexpected_error(self):
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = bash_tool.func(runtime, "test", "cmd")

        assert "Error" in result


class TestStrReplaceToolErrors:
    """str_replace_tool additional error paths."""

    def test_sandbox_error(self):
        from ideer.sandbox.exceptions import SandboxError
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = str_replace_tool.func(runtime, "test", "/data/file.txt", "old", "new")

        assert "Error" in result

    def test_file_not_found(self):
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = FileNotFoundError("not found")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = str_replace_tool.func(runtime, "test", "/data/file.txt", "old", "new")

        assert "not found" in result.lower()

    def test_unexpected_error(self):
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        lock = threading.Lock()
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = str_replace_tool.func(runtime, "test", "/data/file.txt", "old", "new")

        assert "Error" in result


# ===================================================================
# Additional helper coverage
# ===================================================================


class TestTruncationHelpers:
    """Edge cases in truncation functions."""

    def test_truncate_bash_output_zero_max(self):
        from ideer.sandbox.tools import _truncate_bash_output

        assert _truncate_bash_output("hello", 0) == "hello"

    def test_truncate_bash_output_short(self):
        from ideer.sandbox.tools import _truncate_bash_output

        assert _truncate_bash_output("hi", 100) == "hi"

    def test_truncate_bash_output_middle(self):
        from ideer.sandbox.tools import _truncate_bash_output

        long = "A" * 1000
        result = _truncate_bash_output(long, 100)
        assert len(result) <= 100

    def test_truncate_read_file_output_zero_max(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        assert _truncate_read_file_output("hello", 0) == "hello"

    def test_truncate_read_file_output_short(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        assert _truncate_read_file_output("hi", 100) == "hi"

    def test_truncate_read_file_output_long(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        long = "A" * 1000
        result = _truncate_read_file_output(long, 100)
        assert len(result) <= 100

    def test_truncate_ls_output_zero_max(self):
        from ideer.sandbox.tools import _truncate_ls_output

        assert _truncate_ls_output("hello", 0) == "hello"

    def test_truncate_ls_output_short(self):
        from ideer.sandbox.tools import _truncate_ls_output

        assert _truncate_ls_output("hi", 100) == "hi"

    def test_truncate_ls_output_long(self):
        from ideer.sandbox.tools import _truncate_ls_output

        long = "A" * 1000
        result = _truncate_ls_output(long, 100)
        assert len(result) <= 100


class TestFormatHelpers:
    """Format helper functions."""

    def test_format_glob_results_empty(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/data", [], False)
        assert "No files" in result

    def test_format_glob_results_with_matches(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/data", ["a.py", "b.py"], False)
        assert "2 paths" in result

    def test_format_glob_results_truncated(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/data", ["a.py"], True)
        assert "showing first" in result

    def test_format_grep_results_empty(self):
        from ideer.sandbox.tools import _format_grep_results

        result = _format_grep_results("/data", [], False)
        assert "No matches" in result

    def test_format_grep_results_with_matches(self):
        from ideer.sandbox.tools import _format_grep_results

        matches = [GrepMatch(path="a.py", line_number=1, line="hello")]
        result = _format_grep_results("/data", matches, False)
        assert "1 matches" in result

    def test_format_grep_results_truncated(self):
        from ideer.sandbox.tools import _format_grep_results

        matches = [GrepMatch(path="a.py", line_number=1, line="hello")]
        result = _format_grep_results("/data", matches, True)
        assert "showing first" in result


class TestPathHelpers:
    """Path helper functions."""

    def test_path_variants(self):
        from ideer.sandbox.tools import _path_variants

        result = _path_variants("/foo/bar")
        assert "/foo/bar" in result

    def test_path_separator_for_style_unix(self):
        from ideer.sandbox.tools import _path_separator_for_style

        assert _path_separator_for_style("/foo/bar") == "/"

    def test_path_separator_for_style_windows(self):
        from ideer.sandbox.tools import _path_separator_for_style

        assert _path_separator_for_style("C:\\foo\\bar") == "\\"

    def test_join_path_preserving_style_unix(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        result = _join_path_preserving_style("/base", "relative")
        assert result == "/base/relative"

    def test_join_path_preserving_style_empty_relative(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        assert _join_path_preserving_style("/base", "") == "/base"

    def test_join_path_preserving_style_windows(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        result = _join_path_preserving_style("C:\\base", "sub")
        assert result == "C:\\base\\sub"


class TestSanitizeError:
    """_sanitize_error function."""

    def test_basic_error(self):
        from ideer.sandbox.tools import _sanitize_error

        result = _sanitize_error(RuntimeError("test error"))
        assert "RuntimeError" in result
        assert "test error" in result

    def test_local_sandbox_masks_paths(self):
        from ideer.sandbox.tools import _sanitize_error

        td = _make_thread_data()
        runtime = MagicMock()
        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True), patch("ideer.sandbox.tools.get_thread_data", return_value=td), patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="masked msg"):
            result = _sanitize_error(RuntimeError("msg"), runtime)
        assert result == "masked msg"


class TestGetThreadData:
    """get_thread_data function."""

    def test_none_runtime(self):
        from ideer.sandbox.tools import get_thread_data

        assert get_thread_data(None) is None

    def test_none_state(self):
        from ideer.sandbox.tools import get_thread_data

        runtime = MagicMock()
        runtime.state = None
        assert get_thread_data(runtime) is None

    def test_returns_thread_data(self):
        from ideer.sandbox.tools import get_thread_data

        td = _make_thread_data()
        runtime = MagicMock()
        runtime.state = {"thread_data": td}
        assert get_thread_data(runtime) == td


class TestIsLocalSandbox:
    """is_local_sandbox function."""

    def test_none_runtime(self):
        from ideer.sandbox.tools import is_local_sandbox

        assert is_local_sandbox(None) is False

    def test_none_state(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = MagicMock()
        runtime.state = None
        assert is_local_sandbox(runtime) is False

    def test_no_sandbox_state(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = MagicMock()
        runtime.state = {}
        assert is_local_sandbox(runtime) is False

    def test_local_id(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = MagicMock()
        runtime.state = {"sandbox": {"sandbox_id": "local"}}
        assert is_local_sandbox(runtime) is True

    def test_local_with_thread_id(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = MagicMock()
        runtime.state = {"sandbox": {"sandbox_id": "local:t1"}}
        assert is_local_sandbox(runtime) is True

    def test_non_local_id(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = MagicMock()
        runtime.state = {"sandbox": {"sandbox_id": "remote"}}
        assert is_local_sandbox(runtime) is False

    def test_non_string_sandbox_id(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = MagicMock()
        runtime.state = {"sandbox": {"sandbox_id": 123}}
        assert is_local_sandbox(runtime) is False


class TestRejectPathTraversal:
    """_reject_path_traversal function."""

    def test_rejects_dotdot(self):
        from ideer.sandbox.tools import _reject_path_traversal

        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal("/foo/../bar")

    def test_allows_clean_path(self):
        from ideer.sandbox.tools import _reject_path_traversal

        _reject_path_traversal("/foo/bar/baz")  # Should not raise

    def test_rejects_backslash_dotdot(self):
        from ideer.sandbox.tools import _reject_path_traversal

        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal("C:\\foo\\..\\bar")


class TestIsShellHelpers:
    """Shell token helper functions."""

    def test_is_shell_command_separator(self):
        from ideer.sandbox.tools import _is_shell_command_separator

        assert _is_shell_command_separator(";") is True
        assert _is_shell_command_separator("&&") is True
        assert _is_shell_command_separator("echo") is False

    def test_is_shell_redirection_operator(self):
        from ideer.sandbox.tools import _is_shell_redirection_operator

        assert _is_shell_redirection_operator(">") is True
        assert _is_shell_redirection_operator(">>") is True
        assert _is_shell_redirection_operator("echo") is False

    def test_is_shell_assignment(self):
        from ideer.sandbox.tools import _is_shell_assignment

        assert _is_shell_assignment("FOO=bar") is True
        assert _is_shell_assignment("123=bar") is False
        assert _is_shell_assignment("=bar") is False
        assert _is_shell_assignment("echo") is False


class TestClampMaxResults:
    """_clamp_max_results function."""

    def test_zero_returns_default(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(0, default=100, upper_bound=500) == 100

    def test_negative_returns_default(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(-5, default=100, upper_bound=500) == 100

    def test_within_bounds(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(200, default=100, upper_bound=500) == 200

    def test_exceeds_upper_bound(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(999, default=100, upper_bound=500) == 500


class TestEnsureSandboxInitialized:
    """ensure_sandbox_initialized additional paths."""

    def test_raises_when_runtime_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import ensure_sandbox_initialized

        with pytest.raises(SandboxRuntimeError):
            ensure_sandbox_initialized(None)

    def test_raises_when_state_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = None
        with pytest.raises(SandboxRuntimeError):
            ensure_sandbox_initialized(runtime)

    def test_raises_when_thread_id_missing(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {}
        runtime.config = {}
        with pytest.raises(SandboxRuntimeError, match="Thread ID"):
            ensure_sandbox_initialized(runtime)

    def test_raises_not_found_after_acquisition(self):
        from ideer.sandbox.exceptions import SandboxNotFoundError
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {"thread_id": "t1"}
        runtime.config = {"configurable": {"thread_id": "t1"}}

        mock_provider = MagicMock()
        mock_provider.acquire.return_value = "new-id"
        mock_provider.get.return_value = None

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with pytest.raises(SandboxNotFoundError):
                ensure_sandbox_initialized(runtime)

    def test_returns_existing_sandbox(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="existing")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = ensure_sandbox_initialized(runtime)

        assert result is mock_sandbox

    def test_reacquires_when_sandbox_released(self):
        """Sandbox was released, falls through to acquire new one."""
        from ideer.sandbox.tools import ensure_sandbox_initialized

        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        # First get() returns None (released), then returns new sandbox
        mock_provider.get.side_effect = [None, mock_sandbox]
        mock_provider.acquire.return_value = "new-id"

        runtime = _make_runtime(sandbox_id="old-id")
        runtime.context = {"thread_id": "t1"}
        runtime.config = {"configurable": {"thread_id": "t1"}}

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = ensure_sandbox_initialized(runtime)

        assert result is mock_sandbox


class TestSandboxFromRuntime:
    """sandbox_from_runtime additional error paths."""

    def test_raises_when_runtime_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import sandbox_from_runtime

        with pytest.raises(SandboxRuntimeError):
            sandbox_from_runtime(None)

    def test_raises_when_state_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = None
        with pytest.raises(SandboxRuntimeError):
            sandbox_from_runtime(runtime)

    def test_raises_when_sandbox_state_missing(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = {}
        with pytest.raises(SandboxRuntimeError, match="Sandbox state"):
            sandbox_from_runtime(runtime)

    def test_raises_when_sandbox_id_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = {"sandbox": {}}
        with pytest.raises(SandboxRuntimeError, match="Sandbox ID"):
            sandbox_from_runtime(runtime)

    def test_raises_when_sandbox_not_found(self):
        from ideer.sandbox.exceptions import SandboxNotFoundError
        from ideer.sandbox.tools import sandbox_from_runtime

        mock_provider = MagicMock()
        mock_provider.get.return_value = None
        runtime = _make_runtime(sandbox_id="missing")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with pytest.raises(SandboxNotFoundError):
                sandbox_from_runtime(runtime)

    def test_returns_sandbox_and_sets_context(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="test-id")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = sandbox_from_runtime(runtime)

        assert result is mock_sandbox
        assert runtime.context["sandbox_id"] == "test-id"


class TestRunSyncToolAfterAsyncSandboxInit:
    """_run_sync_tool_after_async_sandbox_init additional paths."""

    def test_returns_error_on_sandbox_error(self):
        from ideer.sandbox.exceptions import SandboxError
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        async def go():
            runtime = MagicMock()
            with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", side_effect=SandboxError("fail")):
                result = await _run_sync_tool_after_async_sandbox_init(lambda r: "ok", runtime)
            assert "Error" in result

        _run_async(go())

    def test_returns_error_on_unexpected_exception(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        async def go():
            runtime = MagicMock()
            with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", side_effect=RuntimeError("boom")):
                result = await _run_sync_tool_after_async_sandbox_init(lambda r: "ok", runtime)
            assert "Error" in result

        _run_async(go())

    def test_returns_error_when_func_is_none(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        async def go():
            runtime = MagicMock()
            with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async"):
                result = await _run_sync_tool_after_async_sandbox_init(None, runtime)
            assert "not available" in result.lower()

        _run_async(go())


class TestEnsureThreadDirectoriesExist:
    """ensure_thread_directories_exist paths."""

    def test_none_runtime(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        ensure_thread_directories_exist(None)  # Should not raise

    def test_non_local_sandbox(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = MagicMock()
        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            ensure_thread_directories_exist(runtime)

    def test_no_thread_data(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = MagicMock()
        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True), patch("ideer.sandbox.tools.get_thread_data", return_value=None):
            ensure_thread_directories_exist(runtime)

    def test_already_created(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = MagicMock()
        runtime.state = {"thread_directories_created": True}
        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True), patch("ideer.sandbox.tools.get_thread_data", return_value=_make_thread_data()):
            ensure_thread_directories_exist(runtime)


class TestReplaceVirtualPath:
    """replace_virtual_path paths."""

    def test_none_thread_data(self):
        from ideer.sandbox.tools import replace_virtual_path

        assert replace_virtual_path("/mnt/user-data/workspace", None) == "/mnt/user-data/workspace"

    def test_no_mappings(self):
        from ideer.sandbox.tools import replace_virtual_path

        assert replace_virtual_path("/other/path", {}) == "/other/path"

    def test_workspace_mapping(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data(workspace_path="/real/workspace")
        result = replace_virtual_path("/mnt/user-data/workspace/file.py", td)
        assert "/real/workspace" in result

    def test_exact_virtual_base(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data(workspace_path="/real/workspace")
        result = replace_virtual_path("/mnt/user-data/workspace", td)
        assert result == "/real/workspace"


class TestNonFileUrlHelpers:
    """Non-file URL helper functions."""

    def test_is_non_file_url_token_http(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("https://example.com") is True

    def test_is_non_file_url_token_file(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("file:///tmp/test") is False

    def test_is_non_file_url_token_not_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("/tmp/test") is False

    def test_non_file_url_spans(self):
        from ideer.sandbox.tools import _non_file_url_spans

        spans = _non_file_url_spans("wget https://example.com/file")
        assert len(spans) > 0

    def test_is_in_spans(self):
        from ideer.sandbox.tools import _is_in_spans

        assert _is_in_spans(5, [(0, 10)]) is True
        assert _is_in_spans(15, [(0, 10)]) is False

    def test_has_dotdot_path_segment(self):
        from ideer.sandbox.tools import _has_dotdot_path_segment

        assert _has_dotdot_path_segment("../etc") is True
        assert _has_dotdot_path_segment("/foo/bar") is False


# ===================================================================
# Additional tests for remaining uncovered lines
# ===================================================================


class TestGetSkillsHostPathSuccess:
    """Lines 121-123: _get_skills_host_path success path with caching."""

    def test_returns_cached_path_when_exists(self):
        from ideer.sandbox.tools import _get_skills_host_path

        if hasattr(_get_skills_host_path, "_cached"):
            delattr(_get_skills_host_path, "_cached")

        mock_config = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.__str__ = MagicMock(return_value="/opt/skills")
        mock_config.skills.get_skills_path.return_value = mock_path

        with patch("ideer.config.get_app_config", return_value=mock_config):
            result = _get_skills_host_path()

        assert result == "/opt/skills"
        # Cleanup
        delattr(_get_skills_host_path, "_cached")


class TestGetCustomMountsSuccess:
    """Lines 185, 197-198, 204-209: _get_custom_mounts success with mounts."""

    def test_returns_mounts_with_existing_host_path(self):
        from ideer.sandbox.tools import _get_custom_mounts

        if hasattr(_get_custom_mounts, "_cached"):
            delattr(_get_custom_mounts, "_cached")

        mock_mount = MagicMock()
        mock_mount.host_path = "/opt/data"
        mock_mount.container_path = "/mnt/data"

        mock_config = MagicMock()
        mock_config.sandbox.mounts = [mock_mount]

        with patch("ideer.config.get_app_config", return_value=mock_config), patch("pathlib.Path.exists", return_value=True):
            result = _get_custom_mounts()

        assert len(result) == 1
        # Cleanup
        delattr(_get_custom_mounts, "_cached")

    def test_is_custom_mount_path(self):
        from ideer.sandbox.tools import _is_custom_mount_path

        mock_mount = MagicMock()
        mock_mount.container_path = "/mnt/data"

        with patch("ideer.sandbox.tools._get_custom_mounts", return_value=[mock_mount]):
            assert _is_custom_mount_path("/mnt/data") is True
            assert _is_custom_mount_path("/mnt/data/file.txt") is True
            assert _is_custom_mount_path("/other") is False

    def test_get_custom_mount_for_path(self):
        from ideer.sandbox.tools import _get_custom_mount_for_path

        mock_mount = MagicMock()
        mock_mount.container_path = "/mnt/data"

        with patch("ideer.sandbox.tools._get_custom_mounts", return_value=[mock_mount]):
            result = _get_custom_mount_for_path("/mnt/data/file.txt")
            assert result is mock_mount

            result = _get_custom_mount_for_path("/other")
            assert result is None


class TestTruncateWriteFileErrorDetailEdgeCases:
    """Line 449: _truncate_write_file_error_detail with kept==0."""

    def test_very_small_max_chars_with_large_detail(self):
        """Line 449: when kept=0, return detail[:max_chars]."""
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "A" * 1000
        # max_chars=1, marker would be huge, so kept=0
        result = _truncate_write_file_error_detail(detail, max_chars=1)
        assert len(result) == 1


class TestFormatWriteFileErrorEdgeCases:
    """Line 468: _format_write_file_error with max_chars=0."""

    def test_zero_max_chars_returns_full(self):
        """Line 468: max_chars=0 returns full error."""
        from ideer.sandbox.tools import _format_write_file_error

        error = RuntimeError("some error")
        result = _format_write_file_error("/tmp/test.txt", error, max_chars=0)
        assert "Error" in result
        assert "/tmp/test.txt" in result


class TestMaskLocalPathsUserDataExact:
    """Lines 594, 606: mask_local_paths_in_output user-data exact match."""

    def test_user_data_exact_match_masking(self):
        """Line 606: user-data host path exact match."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data(workspace_path="/tmp/threads/t1/user-data/workspace")

        with (
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = mask_local_paths_in_output("/tmp/threads/t1/user-data/workspace", td)

        assert "/mnt/user-data/workspace" in result

    def test_user_data_subpath_masking(self):
        """User-data host path with sub-path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data(workspace_path="/tmp/threads/t1/user-data/workspace")

        with (
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = mask_local_paths_in_output("output /tmp/threads/t1/user-data/workspace/file.py done", td)

        assert "/mnt/user-data/workspace/file.py" in result


class TestBashToolConfigExceptionFallbacks:
    """Lines 1357-1358, 1366-1367: bash_tool config exception fallbacks."""

    def test_local_sandbox_config_exception(self):
        """Lines 1357-1358: local sandbox config exception uses default max_chars."""
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "output"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.is_host_bash_allowed", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_bash_command_paths"),
            patch("ideer.sandbox.tools.replace_virtual_paths_in_command", return_value="echo hi"),
            patch("ideer.sandbox.tools._apply_cwd_prefix", return_value="echo hi"),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="output"),
            patch("ideer.config.app_config.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = bash_tool.func(runtime, "test desc", "echo hi")

        assert "output" in result

    def test_non_local_sandbox_config_exception(self):
        """Lines 1366-1367: non-local sandbox config exception uses default max_chars."""
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "result"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        runtime = _make_runtime(sandbox_id="remote")

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=False),
            patch("ideer.config.app_config.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = bash_tool.func(runtime, "test desc", "ls")

        assert "result" in result


class TestLsToolConfigException:
    """Lines 1418-1419: ls_tool config exception fallback."""

    def test_config_exception_uses_default(self):
        """Lines 1418-1419: config exception uses default max_chars."""
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["a.txt"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        runtime = _make_runtime(sandbox_id="remote")

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=False),
            patch("ideer.config.app_config.get_app_config", side_effect=RuntimeError("fail")),
        ):
            result = ls_tool.func(runtime, "test", "/data")

        assert "a.txt" in result


class TestReadFileToolConfigException:
    """Lines 1646-1647: read_file_tool config exception fallback."""

    def test_config_exception_uses_default(self):
        """Lines 1646-1647: config exception uses default max_chars."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "some content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        runtime = _make_runtime(sandbox_id="remote")

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=False),
            patch("ideer.config.app_config.get_app_config", side_effect=RuntimeError("fail")),
        ):
            result = read_file_tool.func(runtime, "test", "/data/file.txt")

        assert "some content" in result


class TestWriteFileToolLocalSandbox:
    """Lines 1695-1698, 1702: write_file_tool local sandbox path resolution."""

    def test_local_sandbox_custom_mount(self):
        """Lines 1697-1698: custom mount path skips user-data resolution."""
        from ideer.sandbox.tools import write_file_tool

        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        lock = threading.Lock()
        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True),
            patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock),
        ):
            result = write_file_tool.func(runtime, "test", "/mnt/custom/file.txt", "content")

        assert result == "OK"
        mock_sandbox.write_file.assert_called_once()

    def test_local_sandbox_user_data_path(self):
        """Lines 1695-1698: user-data path resolved."""
        from ideer.sandbox.tools import write_file_tool

        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        lock = threading.Lock()
        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False),
            patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/tmp/resolved/file.txt"),
            patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock),
        ):
            result = write_file_tool.func(runtime, "test", "/mnt/user-data/workspace/file.txt", "content")

        assert result == "OK"


class TestGrepToolLocalSandbox:
    """Lines 1556-1565: grep_tool local sandbox with thread_data masking."""

    def test_local_sandbox_masks_results(self):
        """Lines 1556-1565: grep results masked for local sandbox."""
        from ideer.sandbox.search import GrepMatch
        from ideer.sandbox.tools import grep_tool

        mock_sandbox = MagicMock()
        mock_sandbox.grep.return_value = (
            [GrepMatch(path="/tmp/a.py", line_number=1, line="hello")],
            False,
        )
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools._resolve_local_read_path", return_value="/tmp"),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="/mnt/user-data/workspace/a.py"),
        ):
            result = grep_tool.func(runtime, "test", "hello", "/mnt/user-data/workspace")

        assert "Found" in result


class TestGlobToolLocalSandbox:
    """Lines 1473-1475: glob_tool local sandbox with thread_data masking."""

    def test_local_sandbox_masks_results(self):
        """Lines 1473-1475: glob results masked for local sandbox."""
        from ideer.sandbox.tools import glob_tool

        mock_sandbox = MagicMock()
        mock_sandbox.glob.return_value = (["/tmp/a.py", "/tmp/b.py"], False)
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools._resolve_local_read_path", return_value="/tmp"),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="/mnt/user-data/workspace/a.py"),
        ):
            result = glob_tool.func(runtime, "test", "*.py", "/mnt/user-data/workspace")

        assert "Found" in result


class TestLsToolLocalSandboxAcpPath:
    """Line 1403: ls_tool resolves ACP workspace path in local sandbox."""

    def test_acp_workspace_path_resolved(self):
        """Line 1403: ACP workspace path resolved."""
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["file.py"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="file.py"),
            patch("ideer.config.app_config.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = ls_tool.func(runtime, "test", "/mnt/acp-workspace")

        assert "file.py" in result


class TestReadFileToolLocalSandboxSkillsPath:
    """Line 1630: read_file_tool resolves skills path in local sandbox."""

    def test_skills_path_resolved(self):
        """Line 1630: skills path resolved."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills/SKILL.md"),
            patch("ideer.config.app_config.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = read_file_tool.func(runtime, "test", "/mnt/skills/SKILL.md")

        assert "content" in result


class TestReadFileToolLocalSandboxAcpPath:
    """Line 1632: read_file_tool resolves ACP workspace path in local sandbox."""

    def test_acp_workspace_path_resolved(self):
        """Line 1632: ACP workspace path resolved."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "acp content"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox

        td = _make_thread_data()
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=td)

        with (
            patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider),
            patch("ideer.sandbox.tools.is_local_sandbox", return_value=True),
            patch("ideer.sandbox.tools.get_thread_data", return_value=td),
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp/file.py"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False),
            patch("ideer.config.app_config.get_app_config", side_effect=RuntimeError("no config")),
        ):
            result = read_file_tool.func(runtime, "test", "/mnt/acp-workspace/file.py")

        assert "acp content" in result
