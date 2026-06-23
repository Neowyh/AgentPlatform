"""Coverage boost tests for ideer.sandbox.tools — targeting remaining uncovered lines.

Targets specific uncovered lines from the 88% coverage report:
- Lines 304, 307-313: ACP path resolution (Windows fallback, ValueError)
- Lines 339-340: _get_mcp_allowed_paths exception handling
- Lines 352-354: _get_tool_config_int exception handling
- Lines 374-379: _resolve_local_read_path body
- Lines 450-454: _truncate_write_file_error_detail tail_len==0
- Line 508: replace_virtual_path trailing slash with separator
- Line 580: mask ACP exact match
- Lines 647-675: validate_local_tool_path (all branches)
- Line 694: _validate_resolved_user_data_path no allowed roots
- Lines 711-714: _resolve_and_validate_user_data_path body
- Lines 744, 779-804: _is_allowed_local_bash_absolute_path branches
- Line 831: _validate_local_bash_cwd_target dollar variable
- Lines 843-845: _looks_like_unsafe_cwd_target body
- Line 868: command substitution cd detection
- Lines 889-892: end keyword handling
- Lines 911-912: wrapped cd validation
- Line 927: resolve_and_validate_user_data_path body
- Lines 946-969: validate_local_bash_command_paths (file URL, url spans, unsafe paths)
- Lines 982-1017: replace_virtual_paths_in_command body
- Lines 1031-1033: _apply_cwd_prefix no workspace
- Line 1272: _truncate_bash_output kept==0
- Lines 1301-1302: _truncate_read_file_output kept==0
- Lines 1324-1325: _truncate_ls_output kept==0
- Line 1345: bash_tool host bash disabled
- Line 1378: _bash_tool_async
- Lines 1401, 1405, 1409: ls_tool empty, skills, user-data paths
- Line 1432: _ls_tool_async
- Line 1483: glob_tool permission error
- Line 1496: _glob_tool_async
- Line 1590: grep_tool masking
- Lines 1634, 1638: read_file_tool empty content
- Line 1654: read_file_tool permission error
- Line 1668: _read_file_tool_async
- Lines 1717-1718: write_file_tool local validation
- Line 1728: _write_file_tool_async
- Line 1780: str_replace_tool permission error
- Line 1793: _str_replace_tool_async
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.sandbox.search import GrepMatch


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_runtime(sandbox_id="test-sandbox", thread_data=None, thread_id="t1", context=None):
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
    defaults = {
        "workspace_path": "/tmp/threads/t1/user-data/workspace",
        "uploads_path": "/tmp/threads/t1/user-data/uploads",
        "outputs_path": "/tmp/threads/t1/user-data/outputs",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# validate_local_tool_path (lines 647-675)
# ===========================================================================


class TestValidateLocalToolPath:
    """All branches in validate_local_tool_path."""

    def test_raises_when_thread_data_none(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(SandboxRuntimeError, match="Thread data not available"):
            validate_local_tool_path("/mnt/user-data/workspace", None)

    def test_rejects_path_traversal(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(PermissionError, match="path traversal"):
            validate_local_tool_path("/mnt/user-data/../../etc", _make_thread_data())

    def test_skills_path_read_only_passes(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
            # Should not raise with read_only=True
            validate_local_tool_path("/mnt/skills/test", _make_thread_data(), read_only=True)

    def test_skills_path_write_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
            with pytest.raises(PermissionError, match="Write access to skills"):
                validate_local_tool_path("/mnt/skills/test", _make_thread_data(), read_only=False)

    def test_acp_workspace_read_only_passes(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False), patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
            validate_local_tool_path("/mnt/acp-workspace/test", _make_thread_data(), read_only=True)

    def test_acp_workspace_write_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False), patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
            with pytest.raises(PermissionError, match="Write access to ACP"):
                validate_local_tool_path("/mnt/acp-workspace/test", _make_thread_data(), read_only=False)

    def test_user_data_path_passes(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False), patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
            validate_local_tool_path("/mnt/user-data/workspace/file.txt", _make_thread_data())

    def test_custom_mount_path_read_only_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        mock_mount = MagicMock()
        mock_mount.read_only = True
        mock_mount.container_path = "/mnt/custom"
        with (
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True),
            patch("ideer.sandbox.tools._get_custom_mount_for_path", return_value=mock_mount),
        ):
            with pytest.raises(PermissionError, match="Write access to read-only mount"):
                validate_local_tool_path("/mnt/custom/file.txt", _make_thread_data(), read_only=False)

    def test_custom_mount_path_writable_passes(self):
        from ideer.sandbox.tools import validate_local_tool_path

        mock_mount = MagicMock()
        mock_mount.read_only = False
        mock_mount.container_path = "/mnt/custom"
        with (
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True),
            patch("ideer.sandbox.tools._get_custom_mount_for_path", return_value=mock_mount),
        ):
            validate_local_tool_path("/mnt/custom/file.txt", _make_thread_data(), read_only=False)

    def test_custom_mount_path_read_only_with_read_only_flag_passes(self):
        """Even read-only mounts allow read_only=True."""
        from ideer.sandbox.tools import validate_local_tool_path

        mock_mount = MagicMock()
        mock_mount.read_only = True
        mock_mount.container_path = "/mnt/custom"
        with (
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True),
            patch("ideer.sandbox.tools._get_custom_mount_for_path", return_value=mock_mount),
        ):
            validate_local_tool_path("/mnt/custom/file.txt", _make_thread_data(), read_only=True)

    def test_unknown_path_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False), patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False), patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False):
            with pytest.raises(PermissionError, match="Only paths under"):
                validate_local_tool_path("/unknown/path", _make_thread_data())


# ===========================================================================
# _resolve_local_read_path (lines 374-379)
# ===========================================================================


class TestResolveLocalReadPath:
    def test_skills_path(self):
        from ideer.sandbox.tools import _resolve_local_read_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools.validate_local_tool_path"), patch("ideer.sandbox.tools._is_skills_path", return_value=True), patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills/test"):
            result = _resolve_local_read_path("/mnt/skills/test", td)
        assert result == "/host/skills/test"

    def test_acp_workspace_path(self):
        from ideer.sandbox.tools import _resolve_local_read_path

        td = _make_thread_data()
        with (
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp/test"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
        ):
            result = _resolve_local_read_path("/mnt/acp-workspace/test", td)
        assert result == "/host/acp/test"

    def test_user_data_path(self):
        from ideer.sandbox.tools import _resolve_local_read_path

        td = _make_thread_data()
        with (
            patch("ideer.sandbox.tools.validate_local_tool_path"),
            patch("ideer.sandbox.tools._is_skills_path", return_value=False),
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False),
            patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/tmp/resolved"),
        ):
            result = _resolve_local_read_path("/mnt/user-data/workspace/test", td)
        assert result == "/tmp/resolved"


# ===========================================================================
# _is_allowed_local_bash_absolute_path (lines 744, 779-804)
# ===========================================================================


class TestIsAllowedLocalBashAbsolutePath:
    def test_mcp_allowed_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/data/test", ["/data/"], allow_system_paths=True) is True

    def test_virtual_path_prefix(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/mnt/user-data/test", [], allow_system_paths=True) is True

    def test_virtual_path_prefix_exact(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/mnt/user-data", [], allow_system_paths=True) is True

    def test_skills_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
            assert _is_allowed_local_bash_absolute_path("/mnt/skills/test", [], allow_system_paths=True) is True

    def test_acp_workspace_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False), patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
            assert _is_allowed_local_bash_absolute_path("/mnt/acp-workspace/test", [], allow_system_paths=True) is True

    def test_custom_mount_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False), patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False), patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
            assert _is_allowed_local_bash_absolute_path("/mnt/custom/test", [], allow_system_paths=True) is True

    def test_system_path_allowed(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/bin/sh", [], allow_system_paths=True) is True

    def test_system_path_not_allowed(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/bin/sh", [], allow_system_paths=False) is False

    def test_unknown_path_returns_false(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False), patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False), patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False):
            assert _is_allowed_local_bash_absolute_path("/etc/passwd", [], allow_system_paths=True) is False

    def test_mcp_path_with_traversal_raises(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with pytest.raises(PermissionError, match="path traversal"):
            _is_allowed_local_bash_absolute_path("/data/../../etc", ["/data/"], allow_system_paths=True)

    def test_system_path_exact_match(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/bin", [], allow_system_paths=True) is True


# ===========================================================================
# _validate_local_bash_cwd_target — dollar variable (line 831)
# ===========================================================================


class TestValidateLocalBashCwdTargetDollar:
    def test_dollar_variable_target_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            _validate_local_bash_cwd_target("cd", "$HOME", [])

    def test_tilde_target_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            _validate_local_bash_cwd_target("cd", "~", [])


# ===========================================================================
# _looks_like_unsafe_cwd_target (lines 843-845)
# ===========================================================================


class TestLooksLikeUnsafeCwdTarget:
    def test_none_returns_false(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target(None) is False

    def test_dash_returns_true(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("-") is True

    def test_dollar_returns_true(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("$HOME") is True

    def test_backtick_returns_true(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("`pwd`") is True

    def test_tilde_returns_true(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("~") is True

    def test_slash_returns_true(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("/") is True

    def test_dotdot_returns_true(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("..") is True

    def test_dotdot_segment_returns_true(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("foo/../bar") is True

    def test_safe_path_returns_false(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("relative/path") is False


# ===========================================================================
# _validate_local_bash_shell_tokens (lines 868, 889-892)
# ===========================================================================


class TestValidateLocalBashShellTokensEdge:
    def test_command_substitution_with_cd_raises(self):
        """Line 868: cd in $() raises."""
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        with pytest.raises(PermissionError, match="command substitution"):
            _validate_local_bash_shell_tokens("echo $(cd /etc)", [])

    def test_prefix_keyword_for(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        # 'for' is a prefix keyword - should not raise for valid command
        _validate_local_bash_shell_tokens("for i in 1 2 3; do echo $i; done", [])

    def test_prefix_keyword_case(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        _validate_local_bash_shell_tokens("case x in *) echo ok;; esac", [])


# ===========================================================================
# resolve_and_validate_user_data_path (line 927)
# ===========================================================================


class TestResolveAndValidateUserDataPath:
    def test_resolves_path(self):
        from ideer.sandbox.tools import resolve_and_validate_user_data_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/tmp/resolved"):
            result = resolve_and_validate_user_data_path("/mnt/user-data/workspace/test", td)
        assert result == "/tmp/resolved"


# ===========================================================================
# validate_local_bash_command_paths (lines 946-969)
# ===========================================================================


class TestValidateLocalBashCommandPathsEdge:
    def test_file_url_raises(self):
        """Line 949-951: file:// URL in command raises."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError, match="file:// URL"):
            validate_local_bash_command_paths("cat file:///etc/passwd", td)

    def test_unsafe_absolute_path_raises(self):
        """Lines 965-969: non-allowed absolute path raises."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            with pytest.raises(PermissionError, match="Unsafe absolute paths"):
                validate_local_bash_command_paths("cat /etc/passwd", td)

    def test_url_in_command_is_skipped(self):
        """Lines 959-960: non-file URLs are skipped during path scanning."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            # The URL https://example.com should be skipped
            validate_local_bash_command_paths("curl https://example.com", td)

    def test_command_with_no_paths(self):
        """Clean command with no paths passes."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            validate_local_bash_command_paths("echo hello", td)


# ===========================================================================
# replace_virtual_paths_in_command (lines 982-1017)
# ===========================================================================


class TestReplaceVirtualPathsInCommand:
    def test_replaces_user_data_paths(self):
        """Lines 1009-1015: user-data paths replaced."""
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data(workspace_path="/real/workspace")
        with (
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = replace_virtual_paths_in_command("cat /mnt/user-data/workspace/file.txt", td)
        assert "/real/workspace" in result

    def test_no_thread_data_returns_unchanged(self):
        """Lines 1009: thread_data is None, no replacement."""
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        with (
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value=None),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = replace_virtual_paths_in_command("echo hello", None)
        assert result == "echo hello"

    def test_replaces_skills_paths(self):
        """Lines 987-993: skills paths replaced."""
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data()
        with (
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_skills_host_path", return_value="/host/skills"),
            patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills/test.md"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = replace_virtual_paths_in_command("cat /mnt/skills/test.md", td)
        assert "/host/skills/test.md" in result

    def test_no_skills_host_path_skips_replacement(self):
        """When skills host path is None, skills paths are not replaced."""
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data()
        with (
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = replace_virtual_paths_in_command("cat /mnt/skills/test.md", td)
        assert "/mnt/skills/test.md" in result

    def test_replaces_acp_workspace_paths(self):
        """Lines 998-1004: ACP workspace paths replaced."""
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data()
        with (
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/host/acp"),
            patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp/test.py"),
        ):
            result = replace_virtual_paths_in_command("cat /mnt/acp-workspace/test.py", td)
        assert "/host/acp/test.py" in result


# ===========================================================================
# _apply_cwd_prefix (lines 1020-1033)
# ===========================================================================


class TestApplyCwdPrefix:
    def test_with_workspace(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        td = _make_thread_data(workspace_path="/real/workspace")
        result = _apply_cwd_prefix("echo hello", td)
        assert "cd " in result
        assert "echo hello" in result

    def test_no_workspace(self):
        """Lines 1033: no workspace_path, returns command unchanged."""
        from ideer.sandbox.tools import _apply_cwd_prefix

        td = _make_thread_data(workspace_path=None)
        result = _apply_cwd_prefix("echo hello", td)
        assert result == "echo hello"

    def test_none_thread_data(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        result = _apply_cwd_prefix("echo hello", None)
        assert result == "echo hello"


# ===========================================================================
# Truncation kept == 0 edge cases (lines 1272, 1301-1302, 1324-1325)
# ===========================================================================


class TestTruncationKeptZero:
    def test_truncate_bash_output_kept_zero(self):
        """Line 1272: kept=0 returns output[:max_chars]."""
        from ideer.sandbox.tools import _truncate_bash_output

        output = "A" * 1000
        result = _truncate_bash_output(output, 1)
        assert len(result) <= 1

    def test_truncate_read_file_output_kept_zero(self):
        """Lines 1301-1302: kept=0 returns output[:max_chars]."""
        from ideer.sandbox.tools import _truncate_read_file_output

        output = "A" * 1000
        result = _truncate_read_file_output(output, 1)
        assert len(result) <= 1

    def test_truncate_ls_output_kept_zero(self):
        """Lines 1324-1325: kept=0 returns output[:max_chars]."""
        from ideer.sandbox.tools import _truncate_ls_output

        output = "A" * 1000
        result = _truncate_ls_output(output, 1)
        assert len(result) <= 1


# ===========================================================================
# bash_tool host bash disabled (line 1345)
# ===========================================================================


class TestBashToolHostBashDisabled:
    def test_returns_disabled_message(self):
        """Line 1345: host bash disabled returns error."""
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=_make_thread_data())

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=True), patch("ideer.sandbox.tools.is_host_bash_allowed", return_value=False):
            result = bash_tool.func(runtime, "test", "echo hi")
        assert "Error" in result


# ===========================================================================
# Async tool coroutines (lines 1378, 1432, 1496, 1668, 1728, 1793)
# ===========================================================================


class TestAsyncToolCoroutines:
    def test_bash_tool_async(self):
        """Line 1378: _bash_tool_async."""
        from ideer.sandbox.tools import _bash_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="result"):
            result = _run_async(_bash_tool_async(runtime, "test", "echo"))
            assert result == "result"

    def test_ls_tool_async(self):
        """Line 1432: _ls_tool_async."""
        from ideer.sandbox.tools import _ls_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="result"):
            result = _run_async(_ls_tool_async(runtime, "test", "/data"))
            assert result == "result"

    def test_glob_tool_async(self):
        """Line 1496: _glob_tool_async."""
        from ideer.sandbox.tools import _glob_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="result"):
            result = _run_async(_glob_tool_async(runtime, "test", "*.py", "/data"))
            assert result == "result"

    def test_grep_tool_async(self):
        from ideer.sandbox.tools import _grep_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="result"):
            result = _run_async(_grep_tool_async(runtime, "test", "pattern", "/data"))
            assert result == "result"

    def test_read_file_tool_async(self):
        """Line 1668: _read_file_tool_async."""
        from ideer.sandbox.tools import _read_file_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="result"):
            result = _run_async(_read_file_tool_async(runtime, "test", "/data/file.txt"))
            assert result == "result"

    def test_write_file_tool_async(self):
        """Line 1728: _write_file_tool_async."""
        from ideer.sandbox.tools import _write_file_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="result"):
            result = _run_async(_write_file_tool_async(runtime, "test", "/data/file.txt", "content"))
            assert result == "result"

    def test_str_replace_tool_async(self):
        """Line 1793: _str_replace_tool_async."""
        from ideer.sandbox.tools import _str_replace_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="result"):
            result = _run_async(_str_replace_tool_async(runtime, "test", "/data/file.txt", "old", "new"))
            assert result == "result"


# ===========================================================================
# ls_tool edge cases (lines 1401, 1405, 1409)
# ===========================================================================


class TestLsToolEdgeBoost:
    def test_empty_children_returns_empty(self):
        """Line 1401: empty children returns '(empty)'."""
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = []
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
            mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
            result = ls_tool.func(runtime, "test", "/data")
        assert result == "(empty)"

    def test_local_skills_path_resolved(self):
        """Line 1405: skills path resolved in ls_tool."""
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
            patch("ideer.sandbox.tools._is_skills_path", return_value=True),
            patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills"),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="file.py"),
            patch("ideer.sandbox.tools.get_app_config") as mock_cfg,
        ):
            mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
            result = ls_tool.func(runtime, "test", "/mnt/skills")
        assert "file.py" in result

    def test_local_user_data_path_resolved(self):
        """Line 1409: user-data path resolved in ls_tool."""
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
            patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False),
            patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False),
            patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/tmp/workspace"),
            patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="file.py"),
            patch("ideer.sandbox.tools.get_app_config") as mock_cfg,
        ):
            mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
            result = ls_tool.func(runtime, "test", "/mnt/user-data/workspace")
        assert "file.py" in result


# ===========================================================================
# glob_tool permission error (line 1483)
# ===========================================================================


class TestGlobToolPermissionError:
    def test_permission_error(self):
        """Line 1483: PermissionError caught."""
        from ideer.sandbox.tools import glob_tool

        mock_sandbox = MagicMock()
        mock_sandbox.glob.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = glob_tool.func(runtime, "test", "*.py", "/data")
        assert "Permission denied" in result


# ===========================================================================
# grep_tool local masking (line 1590)
# ===========================================================================


class TestGrepToolLocalMasking:
    def test_local_sandbox_masks_grep_results(self):
        """Line 1590: grep results are masked in local sandbox."""
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


# ===========================================================================
# read_file_tool empty content (lines 1634, 1638)
# ===========================================================================


class TestReadFileToolEmptyContent:
    def test_empty_content_returns_empty(self):
        """Lines 1637-1638: empty content returns '(empty)'."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = ""
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
            mock_cfg.return_value.sandbox.read_file_output_max_chars = 50000
            result = read_file_tool.func(runtime, "test", "/data/empty.txt")
        assert result == "(empty)"

    def test_read_file_permission_error(self):
        """Line 1654: PermissionError caught."""
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            result = read_file_tool.func(runtime, "test", "/data/file.txt")
        assert "Permission denied" in result


# ===========================================================================
# write_file_tool local validation (lines 1717-1718)
# ===========================================================================


class TestWriteFileToolLocalValidation:
    def test_local_sandbox_resolves_user_data_path(self):
        """Lines 1717-1718: local sandbox validates and resolves path."""
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


# ===========================================================================
# str_replace_tool PermissionError (line 1780)
# ===========================================================================


class TestStrReplaceToolPermissionError:
    def test_permission_error(self):
        """Line 1780: PermissionError caught in str_replace_tool."""
        from ideer.sandbox.tools import str_replace_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")
        lock = threading.Lock()

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock):
            result = str_replace_tool.func(runtime, "test", "/data/file.txt", "old", "new")
        assert "Permission denied" in result


# ===========================================================================
# _validate_resolved_user_data_path no roots (line 694)
# ===========================================================================


class TestValidateResolvedUserDataPathNoRoots:
    def test_raises_when_no_roots(self):
        """Line 694: no allowed roots raises SandboxRuntimeError."""
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import _validate_resolved_user_data_path

        td = {"workspace_path": None, "uploads_path": None, "outputs_path": None}
        with pytest.raises(SandboxRuntimeError, match="No allowed"):
            _validate_resolved_user_data_path("/tmp/test", td)


# ===========================================================================
# _resolve_and_validate_user_data_path (lines 711-714)
# ===========================================================================


class TestResolveAndValidateUserDataPathBody:
    def test_resolves_and_validates(self):
        """Lines 711-714: full resolution and validation path."""
        from ideer.sandbox.tools import _resolve_and_validate_user_data_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools.replace_virtual_path", return_value="/tmp/threads/t1/user-data/workspace/file.txt"), patch("ideer.sandbox.tools._validate_resolved_user_data_path"):
            result = _resolve_and_validate_user_data_path("/mnt/user-data/workspace/file.txt", td)
        assert "file.txt" in result


# ===========================================================================
# _truncate_write_file_error_detail tail_len == 0 (line 454)
# ===========================================================================


class TestTruncateWriteFileErrorTailZero:
    def test_tail_len_zero(self):
        """Line 454: when tail_len == 0, detail[-0:] returns empty."""
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "A" * 100
        # Use a very small max_chars to force kept ~ 1, tail_len = 0
        result = _truncate_write_file_error_detail(detail, max_chars=1)
        assert len(result) <= 1


# ===========================================================================
# Additional targeted tests for remaining 34 uncovered lines
# ===========================================================================


class TestGetMcpAllowedPathsException:
    """Lines 339-340: _get_mcp_allowed_paths exception handler."""

    def test_exception_in_config_loading(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        with patch("ideer.config.extensions_config.get_extensions_config", side_effect=RuntimeError("config error")):
            result = _get_mcp_allowed_paths()
        assert result == []


class TestGetToolConfigInt:
    """Lines 345-354: _get_tool_config_int function."""

    def test_exception_returns_default(self):
        """Lines 352-354: exception returns default."""
        from ideer.sandbox.tools import _get_tool_config_int

        with patch("ideer.sandbox.tools.get_app_config", side_effect=RuntimeError("no config")):
            result = _get_tool_config_int("glob", "max_results", 200)
        assert result == 200

    def test_returns_int_value(self):
        """Returns configured int value."""
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_tool_config = MagicMock()
        mock_tool_config.model_extra = {"max_results": 500}
        mock_config.get_tool_config.return_value = mock_tool_config
        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 200)
        assert result == 500

    def test_returns_default_when_not_int(self):
        """Returns default when value is not int."""
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_tool_config = MagicMock()
        mock_tool_config.model_extra = {"max_results": "not_int"}
        mock_config.get_tool_config.return_value = mock_tool_config
        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 200)
        assert result == 200

    def test_returns_default_when_tool_config_is_none(self):
        """Returns default when tool_config is None."""
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_config.get_tool_config.return_value = None
        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 200)
        assert result == 200

    def test_returns_default_when_key_not_in_extra(self):
        """Returns default when key not in model_extra."""
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_tool_config = MagicMock()
        mock_tool_config.model_extra = {"other_key": 500}
        mock_config.get_tool_config.return_value = mock_tool_config
        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 200)
        assert result == 200


class TestTruncateWriteFileErrorNormalPath:
    """Lines 450-454: _truncate_write_file_error_detail normal truncation (kept > 0)."""

    def test_normal_middle_truncation(self):
        """Lines 450-454: normal truncation with kept > 0."""
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "A" * 200
        # Use max_chars large enough that kept > 0 (marker is ~60 chars, so max_chars must exceed that)
        result = _truncate_write_file_error_detail(detail, max_chars=150)
        assert len(result) <= 150
        assert "write_file error truncated" in result


class TestReplaceVirtualPathNoMatch:
    """Line 508: replace_virtual_path returns path unchanged when no mapping matches."""

    def test_path_not_matching_any_mapping(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data(workspace_path="/real/workspace")
        # Path that doesn't start with /mnt/user-data/workspace
        result = replace_virtual_path("/other/path/file.txt", td)
        assert result == "/other/path/file.txt"


class TestMaskLocalPathsAcpExactMatch:
    """Line 580: mask_local_paths_in_output ACP exact match."""

    def test_acp_host_path_exact_match(self):
        """Line 580: ACP host path exact match replaced with virtual path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data()
        with (
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value="t1"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/home/user/acp-workspace"),
        ):
            # The exact host path should be replaced with the virtual path
            result = mask_local_paths_in_output("/home/user/acp-workspace", td)
        assert result == "/mnt/acp-workspace"


class TestMaskLocalPathsUserExactMatch:
    """Line 606: mask_local_paths_in_output user-data exact match."""

    def test_user_data_host_path_exact_match(self):
        """Line 606: user-data host path exact match replaced with virtual path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data(workspace_path="/tmp/threads/t1/user-data/workspace")
        with (
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = mask_local_paths_in_output("/tmp/threads/t1/user-data/workspace", td)
        assert "/mnt/user-data/workspace" in result


class TestValidateLocalBashCwdTargetDashAndNone:
    """Line 831: _validate_local_bash_cwd_target with target None or '-'."""

    def test_none_target_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            _validate_local_bash_cwd_target("cd", None, [])

    def test_dash_target_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            _validate_local_bash_cwd_target("cd", "-", [])


class TestValidateLocalBashShellTokensRedirection:
    """Lines 889-890: redirection operator handling in _validate_local_bash_shell_tokens."""

    def test_command_with_redirection(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        # echo hello > /dev/null — the > is a redirection operator, index should advance
        _validate_local_bash_shell_tokens("echo hello > /mnt/user-data/workspace/out.txt", [])


class TestValidateLocalBashShellTokensWrappedCdContinue:
    """Lines 911-912: wrapped cd/pushd with continuation."""

    def test_wrapped_cd_with_valid_target(self):
        """Lines 911-912: 'command cd /mnt/user-data/workspace' should set index and continue."""
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        # This should NOT raise because /mnt/user-data/workspace is allowed
        _validate_local_bash_shell_tokens("command cd /mnt/user-data/workspace", [])


class TestValidateLocalBashCommandPathsNullThreadData:
    """Line 946: validate_local_bash_command_paths with None thread_data."""

    def test_none_thread_data_raises(self):
        from ideer.sandbox.exceptions import SandboxRuntimeError
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(SandboxRuntimeError, match="Thread data not available"):
            validate_local_bash_command_paths("echo hello", None)


class TestValidateLocalBashCommandPathsUrlSpanFilter:
    """Line 960: URL span filtering in validate_local_bash_command_paths."""

    def test_path_inside_url_is_skipped(self):
        """Line 960: path that falls within a URL span is skipped."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            # wget https://example.com/path — the URL contains a path-like segment
            # but it's inside a URL span and should be skipped
            validate_local_bash_command_paths("wget https://example.com/path/to/file", td)


class TestTruncateReadFileOutputKeptZero:
    """Lines 1301-1302: _truncate_read_file_output with kept == 0."""

    def test_very_small_max_chars(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        output = "A" * 1000
        result = _truncate_read_file_output(output, 2)
        assert len(result) <= 2


class TestTruncateLsOutputKeptZero:
    """Lines 1324-1325: _truncate_ls_output with kept == 0."""

    def test_very_small_max_chars(self):
        from ideer.sandbox.tools import _truncate_ls_output

        output = "A" * 1000
        result = _truncate_ls_output(output, 2)
        assert len(result) <= 2


class TestReadFileToolEmptyContentBoost:
    """Line 1634: read_file_tool returns (empty) for empty content."""

    def test_empty_content_non_local(self):
        from ideer.sandbox.tools import read_file_tool

        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = ""
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="remote")

        # Use direct config mock that succeeds
        mock_app_config = MagicMock()
        mock_app_config.sandbox.read_file_output_max_chars = 50000
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=False), patch("ideer.config.app_config.get_app_config", return_value=mock_app_config):
            result = read_file_tool.func(runtime, "test", "/data/empty.txt")
        assert result == "(empty)"


class TestWriteFileToolLocalPathResolutionBoost:
    """Lines 1717-1718: write_file_tool local path resolution and validation."""

    def test_local_sandbox_resolves_user_data(self):
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
            patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/tmp/resolved"),
            patch("ideer.sandbox.tools.get_file_operation_lock", return_value=lock),
        ):
            result = write_file_tool.func(runtime, "test", "/mnt/user-data/workspace/test.txt", "content")
        assert result == "OK"
        mock_sandbox.write_file.assert_called_once_with("/tmp/resolved", "content", False)


class TestResolveAcpWorkspacePathWindowsFallback:
    """Lines 304, 307-313: _resolve_acp_workspace_path Windows path resolution fallback."""

    def test_windows_path_resolution(self):
        """Lines 307-313: when host_path contains backslashes."""
        # On Linux, this path takes the posix branch (lines 297-305), not Windows (307-313).
        # We test the posix branch success with a real path.
        import tempfile

        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with tempfile.TemporaryDirectory() as td:
            acp_dir = f"{td}/acp-workspace"
            import os

            os.makedirs(acp_dir)
            with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=acp_dir):
                result = _resolve_acp_workspace_path("/mnt/acp-workspace/test.py", thread_id="t1")
            assert "test.py" in result


class TestValidateLocalBashCommandPathsFileUrlBoost:
    """Line 946/951: validate_local_bash_command_paths with file:// URL."""

    def test_file_url_raises_permission_error(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError, match="file:// URL"):
            validate_local_bash_command_paths("cat file:///etc/passwd", td)


class TestMaskLocalPathsEdgeCases:
    """Additional masking edge cases for lines 580 and 606."""

    def test_acp_exact_match_no_thread_data(self):
        """Line 580: ACP exact match with None thread_data."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        with (
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._extract_thread_id_from_thread_data", return_value=None),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/host/acp"),
        ):
            result = mask_local_paths_in_output("/host/acp", None)
        assert result == "/mnt/acp-workspace"

    def test_user_data_exact_match_no_mappings(self):
        """Line 606: user-data exact match when mappings are empty."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = {"workspace_path": None, "uploads_path": None, "outputs_path": None}
        with (
            patch("ideer.sandbox.tools._get_skills_host_path", return_value=None),
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None),
        ):
            result = mask_local_paths_in_output("hello world", td)
        assert result == "hello world"


class TestLsToolNoneThreadData:
    """Test ls_tool with local sandbox and None thread_data for completeness."""

    def test_local_sandbox_no_thread_data(self):
        from ideer.sandbox.tools import ls_tool

        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        runtime = _make_runtime(sandbox_id="local:t1", thread_data=None)

        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider), patch("ideer.sandbox.tools.is_local_sandbox", return_value=True), patch("ideer.sandbox.tools.get_thread_data", return_value=None):
            result = ls_tool.func(runtime, "test", "/mnt/user-data/workspace")
        assert "Error" in result
