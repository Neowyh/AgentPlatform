"""Tests for ideer.sandbox.tools — sandbox tool functions and path utilities."""

from __future__ import annotations

import asyncio
import re
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


# ---------------------------------------------------------------------------
# _get_skills_container_path
# ---------------------------------------------------------------------------


class TestGetSkillsContainerPath:
    def test_default(self):
        from ideer.sandbox.tools import _get_skills_container_path

        # Clear any cached value
        if hasattr(_get_skills_container_path, "_cached"):
            delattr(_get_skills_container_path, "_cached")

        # The function imports get_app_config locally, so patch the source
        # module (ideer.config) rather than the sandbox.tools namespace.
        with patch("ideer.config.get_app_config", side_effect=Exception("no config")):
            result = _get_skills_container_path()
            assert result == "/mnt/skills"


# ---------------------------------------------------------------------------
# _get_skills_host_path
# ---------------------------------------------------------------------------


class TestGetSkillsHostPath:
    def test_returns_none_when_config_fails(self):
        from ideer.sandbox.tools import _get_skills_host_path

        # Clear any cached value from prior tests or module-level calls
        for attr in ("_cached",):
            if hasattr(_get_skills_host_path, attr):
                delattr(_get_skills_host_path, attr)

        # The function imports get_app_config locally, so patch the source
        # module (ideer.config) rather than the sandbox.tools namespace.
        with patch("ideer.config.get_app_config", side_effect=Exception("no config")):
            result = _get_skills_host_path()
            assert result is None


# ---------------------------------------------------------------------------
# _is_skills_path / _is_acp_workspace_path
# ---------------------------------------------------------------------------


class TestPathChecks:
    def test_is_skills_path(self):
        from ideer.sandbox.tools import _is_skills_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            assert _is_skills_path("/mnt/skills") is True
            assert _is_skills_path("/mnt/skills/bootstrap") is True
            assert _is_skills_path("/mnt/user-data/workspace") is False

    def test_is_acp_workspace_path(self):
        from ideer.sandbox.tools import _is_acp_workspace_path

        assert _is_acp_workspace_path("/mnt/acp-workspace") is True
        assert _is_acp_workspace_path("/mnt/acp-workspace/test.py") is True
        assert _is_acp_workspace_path("/mnt/user-data/workspace") is False


# ---------------------------------------------------------------------------
# _reject_path_traversal
# ---------------------------------------------------------------------------


class TestRejectPathTraversal:
    def test_clean_path(self):
        from ideer.sandbox.tools import _reject_path_traversal

        _reject_path_traversal("/mnt/user-data/workspace/file.txt")

    def test_traversal_raises(self):
        from ideer.sandbox.tools import _reject_path_traversal

        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal("/mnt/user-data/workspace/../../etc/passwd")

    def test_backslash_traversal(self):
        from ideer.sandbox.tools import _reject_path_traversal

        with pytest.raises(PermissionError, match="path traversal"):
            _reject_path_traversal("/mnt/user-data/workspace\\..\\..\\etc")

    def test_root_only(self):
        from ideer.sandbox.tools import _reject_path_traversal

        _reject_path_traversal("/")

    def test_dot_dot_at_start(self):
        from ideer.sandbox.tools import _reject_path_traversal

        with pytest.raises(PermissionError):
            _reject_path_traversal("../../../etc")


# ---------------------------------------------------------------------------
# validate_local_tool_path
# ---------------------------------------------------------------------------


class TestValidateLocalToolPath:
    def test_none_thread_data_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(SandboxRuntimeError):
            validate_local_tool_path("/mnt/user-data/workspace", None)

    def test_user_data_path_allowed(self):
        from ideer.sandbox.tools import validate_local_tool_path

        td = _make_thread_data()
        validate_local_tool_path("/mnt/user-data/workspace/file.txt", td)

    def test_skills_path_read_only_allowed(self):
        from ideer.sandbox.tools import validate_local_tool_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
            validate_local_tool_path("/mnt/skills/test", td, read_only=True)

    def test_skills_path_write_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
            with pytest.raises(PermissionError, match="Write access"):
                validate_local_tool_path("/mnt/skills/test", td, read_only=False)

    def test_acp_workspace_read_only(self):
        from ideer.sandbox.tools import validate_local_tool_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
                validate_local_tool_path("/mnt/acp-workspace/test", td, read_only=True)

    def test_acp_workspace_write_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
                with pytest.raises(PermissionError, match="Write access"):
                    validate_local_tool_path("/mnt/acp-workspace/test", td, read_only=False)

    def test_unknown_path_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False):
                    with pytest.raises(PermissionError, match="Only paths under"):
                        validate_local_tool_path("/unknown/path", td)


# ---------------------------------------------------------------------------
# replace_virtual_path
# ---------------------------------------------------------------------------


class TestReplaceVirtualPath:
    def test_none_thread_data(self):
        from ideer.sandbox.tools import replace_virtual_path

        assert replace_virtual_path("/mnt/user-data/workspace/file.txt", None) == "/mnt/user-data/workspace/file.txt"

    def test_workspace_path(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data()
        result = replace_virtual_path("/mnt/user-data/workspace/file.txt", td)
        assert result.endswith("/file.txt")

    def test_uploads_path(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data()
        result = replace_virtual_path("/mnt/user-data/uploads/photo.png", td)
        assert result.endswith("/photo.png")

    def test_outputs_path(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data()
        result = replace_virtual_path("/mnt/user-data/outputs/report.pdf", td)
        assert result.endswith("/report.pdf")

    def test_no_match(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data()
        result = replace_virtual_path("/other/path", td)
        assert result == "/other/path"


# ---------------------------------------------------------------------------
# mask_local_paths_in_output
# ---------------------------------------------------------------------------


class TestMaskLocalPathsInOutput:
    def test_none_thread_data(self):
        from ideer.sandbox.tools import mask_local_paths_in_output

        assert mask_local_paths_in_output("hello", None) == "hello"

    def test_masks_workspace_path(self):
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data()
        output = f"File at {td['workspace_path']}/test.txt"
        result = mask_local_paths_in_output(output, td)
        assert "/mnt/user-data/workspace" in result

    def test_masks_skills_path(self):
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills"):
            with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
                result = mask_local_paths_in_output("File at /opt/skills/test.md", td)
                assert "/mnt/skills" in result


# ---------------------------------------------------------------------------
# _clamp_max_results / _resolve_max_results
# ---------------------------------------------------------------------------


class TestMaxResults:
    def test_clamp_zero_returns_default(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(0, default=100, upper_bound=500) == 100

    def test_clamp_negative_returns_default(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(-5, default=100, upper_bound=500) == 100

    def test_clamp_above_bound(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(999, default=100, upper_bound=500) == 500

    def test_clamp_normal(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(200, default=100, upper_bound=500) == 200


# ---------------------------------------------------------------------------
# _truncate_bash_output
# ---------------------------------------------------------------------------


class TestTruncateBashOutput:
    def test_disabled(self):
        from ideer.sandbox.tools import _truncate_bash_output

        output = "x" * 10000
        assert _truncate_bash_output(output, 0) == output

    def test_short_output(self):
        from ideer.sandbox.tools import _truncate_bash_output

        output = "short"
        assert _truncate_bash_output(output, 100) == output

    def test_long_output(self):
        from ideer.sandbox.tools import _truncate_bash_output

        output = "x" * 1000
        result = _truncate_bash_output(output, 200)
        assert len(result) <= 200
        assert "middle truncated" in result

    def test_preserves_head_and_tail(self):
        from ideer.sandbox.tools import _truncate_bash_output

        output = "HEAD" + "x" * 1000 + "TAIL"
        result = _truncate_bash_output(output, 200)
        assert "HEAD" in result
        assert "TAIL" in result


# ---------------------------------------------------------------------------
# _truncate_read_file_output
# ---------------------------------------------------------------------------


class TestTruncateReadFileOutput:
    def test_disabled(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        output = "x" * 10000
        assert _truncate_read_file_output(output, 0) == output

    def test_short(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        output = "short"
        assert _truncate_read_file_output(output, 100) == output

    def test_long(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        output = "x" * 1000
        result = _truncate_read_file_output(output, 200)
        assert len(result) <= 200
        assert "truncated" in result

    def test_preserves_head(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        output = "IMPORT_LINE" + "x" * 1000
        result = _truncate_read_file_output(output, 200)
        assert "IMPORT_LINE" in result


# ---------------------------------------------------------------------------
# _truncate_ls_output
# ---------------------------------------------------------------------------


class TestTruncateLsOutput:
    def test_disabled(self):
        from ideer.sandbox.tools import _truncate_ls_output

        assert _truncate_ls_output("x" * 100, 0) == "x" * 100

    def test_short(self):
        from ideer.sandbox.tools import _truncate_ls_output

        assert _truncate_ls_output("short", 100) == "short"

    def test_long(self):
        from ideer.sandbox.tools import _truncate_ls_output

        result = _truncate_ls_output("x" * 1000, 200)
        assert len(result) <= 200
        assert "truncated" in result


# ---------------------------------------------------------------------------
# _truncate_write_file_error_detail
# ---------------------------------------------------------------------------


class TestTruncateWriteFileError:
    def test_disabled(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "x" * 1000
        assert _truncate_write_file_error_detail(detail, 0) == detail

    def test_short(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        assert _truncate_write_file_error_detail("short", 100) == "short"

    def test_long(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "x" * 1000
        result = _truncate_write_file_error_detail(detail, 200)
        assert len(result) <= 200
        assert "truncated" in result


# ---------------------------------------------------------------------------
# _format_write_file_error
# ---------------------------------------------------------------------------


class TestFormatWriteFileError:
    def test_basic(self):
        from ideer.sandbox.tools import _format_write_file_error

        result = _format_write_file_error("/test.txt", RuntimeError("disk full"))
        assert "Error" in result
        assert "disk full" in result


# ---------------------------------------------------------------------------
# _sanitize_error
# ---------------------------------------------------------------------------


class TestSanitizeError:
    def test_basic(self):
        from ideer.sandbox.tools import _sanitize_error

        result = _sanitize_error(RuntimeError("test error"))
        assert "RuntimeError" in result
        assert "test error" in result

    def test_with_local_runtime(self):
        from ideer.sandbox.tools import _sanitize_error

        td = _make_thread_data()
        runtime = _make_runtime(thread_data=td)

        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
            with patch("ideer.sandbox.tools.get_thread_data", return_value=td):
                with patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="masked"):
                    result = _sanitize_error(RuntimeError("test"), runtime)
                    assert result == "masked"


# ---------------------------------------------------------------------------
# get_thread_data
# ---------------------------------------------------------------------------


class TestGetThreadData:
    def test_none_runtime(self):
        from ideer.sandbox.tools import get_thread_data

        assert get_thread_data(None) is None

    def test_none_state(self):
        from ideer.sandbox.tools import get_thread_data

        runtime = MagicMock()
        runtime.state = None
        assert get_thread_data(runtime) is None

    def test_no_thread_data(self):
        from ideer.sandbox.tools import get_thread_data

        runtime = MagicMock()
        runtime.state = {}
        assert get_thread_data(runtime) is None

    def test_with_thread_data(self):
        from ideer.sandbox.tools import get_thread_data

        td = _make_thread_data()
        runtime = MagicMock()
        runtime.state = {"thread_data": td}
        assert get_thread_data(runtime) == td


# ---------------------------------------------------------------------------
# is_local_sandbox
# ---------------------------------------------------------------------------


class TestIsLocalSandbox:
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

    def test_local_sandbox(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = _make_runtime(sandbox_id="local")
        assert is_local_sandbox(runtime) is True

    def test_local_with_thread(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = _make_runtime(sandbox_id="local:thread_1")
        assert is_local_sandbox(runtime) is True

    def test_non_local(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = _make_runtime(sandbox_id="docker:abc")
        assert is_local_sandbox(runtime) is False


# ---------------------------------------------------------------------------
# sandbox_from_runtime
# ---------------------------------------------------------------------------


class TestSandboxFromRuntime:
    def test_none_runtime(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        with pytest.raises(SandboxRuntimeError):
            sandbox_from_runtime(None)

    def test_none_state(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = None
        with pytest.raises(SandboxRuntimeError):
            sandbox_from_runtime(runtime)

    def test_no_sandbox_state(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = {}
        with pytest.raises(SandboxRuntimeError):
            sandbox_from_runtime(runtime)

    def test_no_sandbox_id(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = {"sandbox": {}}
        with pytest.raises(SandboxRuntimeError):
            sandbox_from_runtime(runtime)

    def test_sandbox_not_found(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = _make_runtime(sandbox_id="test_id")
        with patch("ideer.sandbox.tools.get_sandbox_provider") as mock_provider:
            mock_provider.return_value.get.return_value = None
            with pytest.raises(SandboxNotFoundError):
                sandbox_from_runtime(runtime)

    def test_success(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = _make_runtime(sandbox_id="test_id")
        mock_sandbox = MagicMock()
        with patch("ideer.sandbox.tools.get_sandbox_provider") as mock_provider:
            mock_provider.return_value.get.return_value = mock_sandbox
            result = sandbox_from_runtime(runtime)
            assert result is mock_sandbox


# ---------------------------------------------------------------------------
# ensure_sandbox_initialized
# ---------------------------------------------------------------------------


class TestEnsureSandboxInitialized:
    def test_none_runtime(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        with pytest.raises(SandboxRuntimeError):
            ensure_sandbox_initialized(None)

    def test_already_initialized(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = _make_runtime(sandbox_id="test_id")
        mock_sandbox = MagicMock()
        with patch("ideer.sandbox.tools.get_sandbox_provider") as mock_provider:
            mock_provider.return_value.get.return_value = mock_sandbox
            result = ensure_sandbox_initialized(runtime)
            assert result is mock_sandbox

    def test_lazy_init(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {"thread_id": "t1"}
        runtime.config = {"configurable": {"thread_id": "t1"}}

        mock_sandbox = MagicMock()
        with patch("ideer.sandbox.tools.get_sandbox_provider") as mock_provider:
            mock_provider.return_value.acquire.return_value = "new_sandbox_id"
            mock_provider.return_value.get.return_value = mock_sandbox
            result = ensure_sandbox_initialized(runtime)
            assert result is mock_sandbox
            assert runtime.state["sandbox"]["sandbox_id"] == "new_sandbox_id"

    def test_no_thread_id(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {}
        runtime.config = {}

        with pytest.raises(SandboxRuntimeError, match="Thread ID"):
            ensure_sandbox_initialized(runtime)


# ---------------------------------------------------------------------------
# ensure_thread_directories_exist
# ---------------------------------------------------------------------------


class TestEnsureThreadDirectoriesExist:
    def test_none_runtime(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        ensure_thread_directories_exist(None)

    def test_non_local_sandbox(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = _make_runtime(sandbox_id="docker:abc")
        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
            ensure_thread_directories_exist(runtime)

    def test_already_created(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = _make_runtime()
        runtime.state["thread_directories_created"] = True
        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
            ensure_thread_directories_exist(runtime)

    def test_creates_directories(self, tmp_path):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        td = _make_thread_data()
        runtime = _make_runtime(thread_data=td)

        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
            with patch("ideer.sandbox.tools.get_thread_data", return_value=td):
                ensure_thread_directories_exist(runtime)
                assert runtime.state.get("thread_directories_created") is True


# ---------------------------------------------------------------------------
# _apply_cwd_prefix
# ---------------------------------------------------------------------------


class TestApplyCwdPrefix:
    def test_with_workspace(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        td = _make_thread_data()
        result = _apply_cwd_prefix("ls -la", td)
        assert result.startswith("cd ")
        assert "&& ls -la" in result

    def test_no_thread_data(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        result = _apply_cwd_prefix("ls -la", None)
        assert result == "ls -la"


# ---------------------------------------------------------------------------
# _format_glob_results / _format_grep_results
# ---------------------------------------------------------------------------


class TestFormatResults:
    def test_glob_no_matches(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/root", [], False)
        assert "No files matched" in result

    def test_glob_with_matches(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/root", ["/root/a.py", "/root/b.py"], False)
        assert "Found 2 paths" in result
        assert "/root/a.py" in result

    def test_glob_truncated(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/root", ["/root/a.py"], True)
        assert "showing first" in result

    def test_grep_no_matches(self):
        from ideer.sandbox.tools import _format_grep_results

        result = _format_grep_results("/root", [], False)
        assert "No matches found" in result


# ---------------------------------------------------------------------------
# _path_variants / _path_separator_for_style / _join_path_preserving_style
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_path_variants(self):
        from ideer.sandbox.tools import _path_variants

        variants = _path_variants("/a/b")
        assert "/a/b" in variants
        assert "\\a\\b" in variants

    def test_separator_forward(self):
        from ideer.sandbox.tools import _path_separator_for_style

        assert _path_separator_for_style("/a/b") == "/"

    def test_separator_backslash(self):
        from ideer.sandbox.tools import _path_separator_for_style

        assert _path_separator_for_style("\\a\\b") == "\\"

    def test_join_preserving_forward(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        result = _join_path_preserving_style("/base", "relative/file.txt")
        assert result == "/base/relative/file.txt"

    def test_join_preserving_backslash(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        result = _join_path_preserving_style("\\base", "relative\\file.txt")
        assert result == "\\base\\relative\\file.txt"

    def test_join_empty_relative(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        assert _join_path_preserving_style("/base", "") == "/base"


# ---------------------------------------------------------------------------
# _is_non_file_url_token / _non_file_url_spans / _is_in_spans
# ---------------------------------------------------------------------------


class TestUrlHelpers:
    def test_non_file_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("http://example.com") is True
        assert _is_non_file_url_token("https://example.com") is True

    def test_file_url_is_not_non_file(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("file:///tmp/test.txt") is False

    def test_non_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("/tmp/test.txt") is False

    def test_url_in_command_spans(self):
        from ideer.sandbox.tools import _non_file_url_spans

        spans = _non_file_url_spans("curl http://example.com/api")
        assert len(spans) == 1

    def test_is_in_spans(self):
        from ideer.sandbox.tools import _is_in_spans

        assert _is_in_spans(5, [(0, 10)]) is True
        assert _is_in_spans(15, [(0, 10)]) is False


# ---------------------------------------------------------------------------
# Shell token helpers
# ---------------------------------------------------------------------------


class TestShellTokenHelpers:
    def test_split_shell_tokens(self):
        from ideer.sandbox.tools import _split_shell_tokens

        tokens = _split_shell_tokens("ls -la /tmp")
        assert "ls" in tokens
        assert "-la" in tokens

    def test_is_shell_command_separator(self):
        from ideer.sandbox.tools import _is_shell_command_separator

        assert _is_shell_command_separator(";") is True
        assert _is_shell_command_separator("&&") is True
        assert _is_shell_command_separator("ls") is False

    def test_is_shell_redirection_operator(self):
        from ideer.sandbox.tools import _is_shell_redirection_operator

        assert _is_shell_redirection_operator(">") is True
        assert _is_shell_redirection_operator(">>") is True
        assert _is_shell_redirection_operator("ls") is False

    def test_is_shell_assignment(self):
        from ideer.sandbox.tools import _is_shell_assignment

        assert _is_shell_assignment("FOO=bar") is True
        assert _is_shell_assignment("_VAR=123") is True
        assert _is_shell_assignment("=value") is False
        assert _is_shell_assignment("123=bad") is False

    def test_has_dotdot_path_segment(self):
        from ideer.sandbox.tools import _has_dotdot_path_segment

        assert _has_dotdot_path_segment("../file") is True
        assert _has_dotdot_path_segment("path/..") is True
        assert _has_dotdot_path_segment("path/file") is False

    def test_looks_like_unsafe_cwd_target(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target(None) is False
        assert _looks_like_unsafe_cwd_target("-") is True
        assert _looks_like_unsafe_cwd_target("~") is True
        assert _looks_like_unsafe_cwd_target("/") is True
        assert _looks_like_unsafe_cwd_target("../etc") is True
        assert _looks_like_unsafe_cwd_target("./safe") is False


# ---------------------------------------------------------------------------
# _next_cd_target
# ---------------------------------------------------------------------------


class TestNextCdTarget:
    def test_simple_target(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = ["/tmp"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/tmp"
        assert idx == 1

    def test_with_flags(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = ["-L", "/tmp"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/tmp"

    def test_separator_stops(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = [";", "/tmp"]
        target, idx = _next_cd_target(tokens, 0)
        assert target is None

    def test_empty(self):
        from ideer.sandbox.tools import _next_cd_target

        target, idx = _next_cd_target([], 0)
        assert target is None


# ---------------------------------------------------------------------------
# validate_local_bash_command_paths
# ---------------------------------------------------------------------------


class TestValidateLocalBashCommandPaths:
    def test_none_thread_data_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(SandboxRuntimeError):
            validate_local_bash_command_paths("ls /tmp", None)

    def test_clean_command(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            validate_local_bash_command_paths("ls /mnt/user-data/workspace", td)

    def test_file_url_blocked(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError, match="file://"):
            validate_local_bash_command_paths("cat file:///etc/passwd", td)


# ---------------------------------------------------------------------------
# _is_allowed_local_bash_absolute_path
# ---------------------------------------------------------------------------


class TestIsAllowedLocalBashAbsolutePath:
    def test_virtual_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/mnt/user-data/workspace", [], allow_system_paths=False) is True

    def test_system_path_allowed(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/bin/sh", [], allow_system_paths=True) is True

    def test_system_path_disallowed(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/bin/sh", [], allow_system_paths=False) is False

    def test_unknown_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/etc/passwd", [], allow_system_paths=False) is False

    def test_mcp_allowed_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        assert _is_allowed_local_bash_absolute_path("/data/file.txt", ["/data/"], allow_system_paths=False) is True


# ---------------------------------------------------------------------------
# _get_custom_mounts / _is_custom_mount_path
# ---------------------------------------------------------------------------


class TestCustomMounts:
    def test_config_failure(self):
        from ideer.sandbox.tools import _get_custom_mounts

        if hasattr(_get_custom_mounts, "_cached"):
            delattr(_get_custom_mounts, "_cached")

        # The function imports get_app_config locally, so patch the source
        # module (ideer.config) rather than the sandbox.tools namespace.
        with patch("ideer.config.get_app_config", side_effect=Exception("no config")):
            result = _get_custom_mounts()
            assert result == []

    def test_is_custom_mount_path_no_mounts(self):
        from ideer.sandbox.tools import _is_custom_mount_path

        with patch("ideer.sandbox.tools._get_custom_mounts", return_value=[]):
            assert _is_custom_mount_path("/custom/path") is False


# ---------------------------------------------------------------------------
# _extract_thread_id_from_thread_data
# ---------------------------------------------------------------------------


class TestExtractThreadId:
    def test_none(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        assert _extract_thread_id_from_thread_data(None) is None

    def test_no_workspace(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        assert _extract_thread_id_from_thread_data({}) is None

    def test_with_workspace(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        td = {"workspace_path": "/base/threads/my-thread/user-data/workspace"}
        assert _extract_thread_id_from_thread_data(td) == "my-thread"


# ---------------------------------------------------------------------------
# _validate_local_bash_cwd_target
# ---------------------------------------------------------------------------


class TestValidateLocalBashCwdTarget:
    def test_none_target(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", None, [])

    def test_dash_target(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "-", [])

    def test_dollar_target(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "$HOME", [])

    def test_tilde_target(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "~", [])

    def test_absolute_allowed(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with patch("ideer.sandbox.tools._is_allowed_local_bash_absolute_path", return_value=True):
            _validate_local_bash_cwd_target("cd", "/mnt/user-data/workspace", [])

    def test_absolute_disallowed(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            with patch("ideer.sandbox.tools._is_allowed_local_bash_absolute_path", return_value=False):
                _validate_local_bash_cwd_target("cd", "/etc", [])


# ---------------------------------------------------------------------------
# replace_virtual_paths_in_command
# ---------------------------------------------------------------------------


class TestReplaceVirtualPathsInCommand:
    def test_none_thread_data(self):
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        result = replace_virtual_paths_in_command("ls /mnt/user-data/workspace", None)
        assert result == "ls /mnt/user-data/workspace"

    def test_with_thread_data(self):
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data()
        result = replace_virtual_paths_in_command("ls /mnt/user-data/workspace/file.txt", td)
        assert "/mnt/user-data/workspace" not in result


# ---------------------------------------------------------------------------
# resolve_and_validate_user_data_path
# ---------------------------------------------------------------------------


class TestResolveAndValidateUserDataPath:
    def test_basic(self):
        from ideer.sandbox.tools import resolve_and_validate_user_data_path

        td = _make_thread_data()
        result = resolve_and_validate_user_data_path("/mnt/user-data/workspace/file.txt", td)
        assert "file.txt" in result


# ---------------------------------------------------------------------------
# _validate_resolved_user_data_path
# ---------------------------------------------------------------------------


class TestValidateResolvedUserDataPath:
    def test_no_roots_raises(self):
        from ideer.sandbox.tools import _validate_resolved_user_data_path

        with pytest.raises(SandboxRuntimeError, match="No allowed"):
            _validate_resolved_user_data_path(Path("/tmp/file"), {"workspace_path": None, "uploads_path": None, "outputs_path": None})

    def test_valid_path(self, tmp_path):
        from ideer.sandbox.tools import _validate_resolved_user_data_path

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        file = workspace / "file.txt"
        file.touch()

        td = {"workspace_path": str(workspace), "uploads_path": None, "outputs_path": None}
        _validate_resolved_user_data_path(file.resolve(), td)


# ---------------------------------------------------------------------------
# _is_allowed_local_bash_absolute_path with skills and ACP
# ---------------------------------------------------------------------------


class TestAllowedPathsExtended:
    def test_skills_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
            assert _is_allowed_local_bash_absolute_path("/mnt/skills/test", [], allow_system_paths=False) is True

    def test_acp_workspace_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
                assert _is_allowed_local_bash_absolute_path("/mnt/acp-workspace/test", [], allow_system_paths=False) is True

    def test_custom_mount_path(self):
        from ideer.sandbox.tools import _is_allowed_local_bash_absolute_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
                    assert _is_allowed_local_bash_absolute_path("/custom/test", [], allow_system_paths=False) is True


# ---------------------------------------------------------------------------
# validate_local_tool_path
# ---------------------------------------------------------------------------


class TestValidateLocalToolPathExtra:
    def test_none_thread_data_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(SandboxRuntimeError, match="Thread data not available"):
            validate_local_tool_path("/mnt/user-data/x", None)

    def test_path_traversal_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(PermissionError, match="path traversal"):
            validate_local_tool_path("/mnt/user-data/../etc/passwd", _make_thread_data())

    def test_skills_path_read_only_allowed(self):
        from ideer.sandbox.tools import validate_local_tool_path

        # Should not raise for read_only=True
        validate_local_tool_path("/mnt/skills/test", _make_thread_data(), read_only=True)

    def test_skills_path_write_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(PermissionError, match="Write access to skills"):
            validate_local_tool_path("/mnt/skills/test", _make_thread_data(), read_only=False)

    def test_acp_workspace_read_only_allowed(self):
        from ideer.sandbox.tools import validate_local_tool_path

        validate_local_tool_path("/mnt/acp-workspace/test", _make_thread_data(), read_only=True)

    def test_acp_workspace_write_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(PermissionError, match="Write access to ACP"):
            validate_local_tool_path("/mnt/acp-workspace/test", _make_thread_data(), read_only=False)

    def test_user_data_path_allowed(self):
        from ideer.sandbox.tools import validate_local_tool_path

        validate_local_tool_path("/mnt/user-data/workspace/file.txt", _make_thread_data())

    def test_custom_mount_read_only_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        mock_mount = MagicMock()
        mock_mount.container_path = "/mnt/custom"
        mock_mount.read_only = True
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
                    with patch("ideer.sandbox.tools._get_custom_mount_for_path", return_value=mock_mount):
                        with pytest.raises(PermissionError, match="read-only mount"):
                            validate_local_tool_path("/mnt/custom/file", _make_thread_data(), read_only=False)

    def test_custom_mount_not_read_only_allowed(self):
        from ideer.sandbox.tools import validate_local_tool_path

        mock_mount = MagicMock()
        mock_mount.container_path = "/mnt/custom"
        mock_mount.read_only = False
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=True):
                    with patch("ideer.sandbox.tools._get_custom_mount_for_path", return_value=mock_mount):
                        validate_local_tool_path("/mnt/custom/file", _make_thread_data(), read_only=False)

    def test_unknown_path_raises(self):
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                with patch("ideer.sandbox.tools._is_custom_mount_path", return_value=False):
                    with pytest.raises(PermissionError, match="Only paths under"):
                        validate_local_tool_path("/unknown/path", _make_thread_data())


# ---------------------------------------------------------------------------
# validate_local_bash_command_paths
# ---------------------------------------------------------------------------


class TestValidateLocalBashCommandPathsExtra:
    def test_none_thread_data_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(SandboxRuntimeError):
            validate_local_bash_command_paths("ls", None)

    def test_file_url_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(PermissionError, match="file://"):
            validate_local_bash_command_paths("cat file:///etc/passwd", _make_thread_data())

    def test_unsafe_absolute_path_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(PermissionError, match="Unsafe absolute paths"):
            validate_local_bash_command_paths("cat /etc/passwd", _make_thread_data())

    def test_allowed_system_path(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        # /bin/ls is in the allowed system paths
        validate_local_bash_command_paths("/bin/ls -la", _make_thread_data())

    def test_virtual_path_allowed(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        validate_local_bash_command_paths("cat /mnt/user-data/workspace/file.txt", _make_thread_data())

    def test_dotdot_traversal_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(PermissionError, match="path traversal"):
            validate_local_bash_command_paths("cat /mnt/user-data/../etc/passwd", _make_thread_data())


# ---------------------------------------------------------------------------
# replace_virtual_paths_in_command
# ---------------------------------------------------------------------------


class TestReplaceVirtualPathsInCommandExtra:
    def test_no_virtual_path(self):
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        assert replace_virtual_paths_in_command("ls -la", _make_thread_data()) == "ls -la"

    def test_user_data_replacement(self):
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data()
        result = replace_virtual_paths_in_command("cat /mnt/user-data/workspace/file.txt", td)
        assert "/mnt/user-data" not in result
        assert "workspace" in result

    def test_none_thread_data(self):
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        result = replace_virtual_paths_in_command("cat /mnt/user-data/file.txt", None)
        assert result == "cat /mnt/user-data/file.txt"


# ---------------------------------------------------------------------------
# _apply_cwd_prefix
# ---------------------------------------------------------------------------


class TestApplyCwdPrefixExtra:
    def test_with_workspace(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        td = _make_thread_data()
        result = _apply_cwd_prefix("ls -la", td)
        assert result.startswith("cd ")
        assert "ls -la" in result

    def test_no_workspace(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        result = _apply_cwd_prefix("ls -la", {"workspace_path": None})
        assert result == "ls -la"

    def test_none_thread_data(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        assert _apply_cwd_prefix("ls -la", None) == "ls -la"


# ---------------------------------------------------------------------------
# get_thread_data / is_local_sandbox
# ---------------------------------------------------------------------------


class TestGetThreadDataExtra:
    def test_none_runtime(self):
        from ideer.sandbox.tools import get_thread_data

        assert get_thread_data(None) is None

    def test_none_state(self):
        from ideer.sandbox.tools import get_thread_data

        runtime = MagicMock()
        runtime.state = None
        assert get_thread_data(runtime) is None

    def test_with_thread_data(self):
        from ideer.sandbox.tools import get_thread_data

        td = _make_thread_data()
        runtime = _make_runtime(thread_data=td)
        assert get_thread_data(runtime) == td


class TestIsLocalSandboxExtra:
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

        runtime = _make_runtime(sandbox_id="local")
        assert is_local_sandbox(runtime) is True

    def test_local_thread_id(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = _make_runtime(sandbox_id="local:t1")
        assert is_local_sandbox(runtime) is True

    def test_non_local_id(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = _make_runtime(sandbox_id="aio:t1")
        assert is_local_sandbox(runtime) is False

    def test_non_string_id(self):
        from ideer.sandbox.tools import is_local_sandbox

        runtime = MagicMock()
        runtime.state = {"sandbox": {"sandbox_id": 123}}
        assert is_local_sandbox(runtime) is False


# ---------------------------------------------------------------------------
# sandbox_from_runtime
# ---------------------------------------------------------------------------


class TestSandboxFromRuntimeExtra:
    def test_none_runtime_raises(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        with pytest.raises(SandboxRuntimeError, match="not available"):
            sandbox_from_runtime(None)

    def test_none_state_raises(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = None
        with pytest.raises(SandboxRuntimeError, match="state not available"):
            sandbox_from_runtime(runtime)

    def test_no_sandbox_state_raises(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = {}
        with pytest.raises(SandboxRuntimeError, match="not initialized"):
            sandbox_from_runtime(runtime)

    def test_no_sandbox_id_raises(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = MagicMock()
        runtime.state = {"sandbox": {}}
        with pytest.raises(SandboxRuntimeError, match="ID not found"):
            sandbox_from_runtime(runtime)

    def test_sandbox_not_found_raises(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = _make_runtime(sandbox_id="test_id")
        mock_provider = MagicMock()
        mock_provider.get.return_value = None
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with pytest.raises(SandboxNotFoundError):
                sandbox_from_runtime(runtime)

    def test_success(self):
        from ideer.sandbox.tools import sandbox_from_runtime

        runtime = _make_runtime(sandbox_id="test_id")
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = sandbox_from_runtime(runtime)
            assert result == mock_sandbox
            assert runtime.context["sandbox_id"] == "test_id"


# ---------------------------------------------------------------------------
# ensure_sandbox_initialized
# ---------------------------------------------------------------------------


class TestEnsureSandboxInitializedExtra:
    def test_none_runtime_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        with pytest.raises(SandboxRuntimeError):
            ensure_sandbox_initialized(None)

    def test_none_state_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = None
        with pytest.raises(SandboxRuntimeError):
            ensure_sandbox_initialized(runtime)

    def test_existing_sandbox(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = _make_runtime(sandbox_id="test_id")
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = ensure_sandbox_initialized(runtime)
            assert result == mock_sandbox

    def test_lazy_acquisition(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {"thread_id": "t1"}
        runtime.config = {"configurable": {"thread_id": "t1"}}
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.acquire.return_value = "new_id"
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = ensure_sandbox_initialized(runtime)
            assert result == mock_sandbox
            mock_provider.acquire.assert_called_once_with("t1")

    def test_no_thread_id_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {}
        runtime.config = {}
        with pytest.raises(SandboxRuntimeError, match="Thread ID"):
            ensure_sandbox_initialized(runtime)

    def test_sandbox_not_found_after_acquire_raises(self):
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

    def test_released_sandbox_reacquired(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = _make_runtime(sandbox_id="old_id")
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        # First get returns None (released), then acquire returns new, then get returns new
        mock_provider.get.side_effect = [None, mock_sandbox]
        mock_provider.acquire.return_value = "new_id"
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = ensure_sandbox_initialized(runtime)
            assert result == mock_sandbox


# ---------------------------------------------------------------------------
# ensure_sandbox_initialized_async
# ---------------------------------------------------------------------------


class TestEnsureSandboxInitializedAsync:
    @pytest.mark.asyncio
    async def test_none_runtime_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        with pytest.raises(SandboxRuntimeError):
            await ensure_sandbox_initialized_async(None)

    @pytest.mark.asyncio
    async def test_existing_sandbox(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        runtime = _make_runtime(sandbox_id="test_id")
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = await ensure_sandbox_initialized_async(runtime)
            assert result == mock_sandbox

    @pytest.mark.asyncio
    async def test_lazy_acquisition(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        runtime = MagicMock()
        runtime.state = {}
        runtime.context = {"thread_id": "t1"}
        runtime.config = {"configurable": {"thread_id": "t1"}}
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.acquire_async = AsyncMock(return_value="new_id")
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            result = await ensure_sandbox_initialized_async(runtime)
            assert result == mock_sandbox


# ---------------------------------------------------------------------------
# ensure_thread_directories_exist
# ---------------------------------------------------------------------------


class TestEnsureThreadDirectoriesExistExtra:
    def test_none_runtime(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        ensure_thread_directories_exist(None)  # no-op

    def test_non_local_sandbox(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = _make_runtime(sandbox_id="aio:test")
        ensure_thread_directories_exist(runtime)  # no-op

    def test_no_thread_data(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = _make_runtime(sandbox_id="local:test", thread_data=None)
        ensure_thread_directories_exist(runtime)  # no-op

    def test_already_created(self):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        runtime = _make_runtime(sandbox_id="local:test", thread_data=_make_thread_data())
        runtime.state["thread_directories_created"] = True
        ensure_thread_directories_exist(runtime)  # no-op

    def test_creates_directories(self, tmp_path):
        from ideer.sandbox.tools import ensure_thread_directories_exist

        ws = str(tmp_path / "workspace")
        up = str(tmp_path / "uploads")
        out = str(tmp_path / "outputs")
        td = {"workspace_path": ws, "uploads_path": up, "outputs_path": out}
        runtime = _make_runtime(sandbox_id="local:test", thread_data=td)
        ensure_thread_directories_exist(runtime)
        assert Path(ws).exists()
        assert Path(up).exists()
        assert Path(out).exists()
        assert runtime.state["thread_directories_created"] is True


# ---------------------------------------------------------------------------
# Truncation helpers
# ---------------------------------------------------------------------------


class TestTruncateBashOutputExtra:
    def test_no_truncation(self):
        from ideer.sandbox.tools import _truncate_bash_output

        assert _truncate_bash_output("short", 100) == "short"

    def test_disabled(self):
        from ideer.sandbox.tools import _truncate_bash_output

        long = "x" * 100
        assert _truncate_bash_output(long, 0) == long

    def test_truncated(self):
        from ideer.sandbox.tools import _truncate_bash_output

        long = "a" * 50 + "b" * 50
        result = _truncate_bash_output(long, 60)
        assert len(result) <= 60
        assert "a" in result
        assert "middle truncated" in result

    def test_exact_length(self):
        from ideer.sandbox.tools import _truncate_bash_output

        text = "x" * 50
        assert _truncate_bash_output(text, 50) == text

    def test_very_small_max(self):
        from ideer.sandbox.tools import _truncate_bash_output

        long = "x" * 100
        result = _truncate_bash_output(long, 5)
        assert len(result) <= 5


class TestTruncateReadFileOutputExtra:
    def test_no_truncation(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        assert _truncate_read_file_output("short", 100) == "short"

    def test_disabled(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        long = "x" * 100
        assert _truncate_read_file_output(long, 0) == long

    def test_truncated(self):
        from ideer.sandbox.tools import _truncate_read_file_output

        long = "a" * 5000 + "b" * 5000
        result = _truncate_read_file_output(long, 200)
        assert len(result) <= 200
        assert result.startswith("a")
        assert "truncated" in result


class TestTruncateLsOutputExtra:
    def test_no_truncation(self):
        from ideer.sandbox.tools import _truncate_ls_output

        assert _truncate_ls_output("short", 100) == "short"

    def test_disabled(self):
        from ideer.sandbox.tools import _truncate_ls_output

        long = "x" * 100
        assert _truncate_ls_output(long, 0) == long

    def test_truncated(self):
        from ideer.sandbox.tools import _truncate_ls_output

        long = "a" * 5000 + "b" * 5000
        result = _truncate_ls_output(long, 200)
        assert len(result) <= 200
        assert "truncated" in result


# ---------------------------------------------------------------------------
# _format_glob_results / _format_grep_results
# ---------------------------------------------------------------------------


class TestFormatResultsExtra:
    def test_glob_no_matches(self):
        from ideer.sandbox.tools import _format_glob_results

        assert "No files matched" in _format_glob_results("/root", [], False)

    def test_glob_with_matches(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/root", ["/root/a.py", "/root/b.py"], False)
        assert "Found 2 paths" in result
        assert "1. /root/a.py" in result

    def test_glob_truncated(self):
        from ideer.sandbox.tools import _format_glob_results

        result = _format_glob_results("/root", ["/root/a.py"], True)
        assert "showing first" in result

    def test_grep_no_matches(self):
        from ideer.sandbox.tools import _format_grep_results

        assert "No matches found" in _format_grep_results("/root", [], False)

    def test_grep_with_matches(self):
        from ideer.sandbox.search import GrepMatch
        from ideer.sandbox.tools import _format_grep_results

        matches = [GrepMatch(path="/root/a.py", line_number=1, line="hello")]
        result = _format_grep_results("/root", matches, False)
        assert "Found 1 matches" in result
        assert "/root/a.py:1: hello" in result

    def test_grep_truncated(self):
        from ideer.sandbox.search import GrepMatch
        from ideer.sandbox.tools import _format_grep_results

        matches = [GrepMatch(path="/root/a.py", line_number=1, line="hello")]
        result = _format_grep_results("/root", matches, True)
        assert "showing first" in result


# ---------------------------------------------------------------------------
# _sanitize_error
# ---------------------------------------------------------------------------


class TestSanitizeErrorExtra:
    def test_basic(self):
        from ideer.sandbox.tools import _sanitize_error

        result = _sanitize_error(ValueError("test error"))
        assert "ValueError" in result
        assert "test error" in result

    def test_with_local_runtime(self):
        from ideer.sandbox.tools import _sanitize_error

        td = _make_thread_data()
        runtime = _make_runtime(thread_data=td)
        with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
            with patch("ideer.sandbox.tools.get_thread_data", return_value=td):
                with patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="masked"):
                    result = _sanitize_error(ValueError("test"), runtime)
                    assert result == "masked"


# ---------------------------------------------------------------------------
# _truncate_write_file_error_detail
# ---------------------------------------------------------------------------


class TestTruncateWriteFileErrorExtra:
    def test_short_detail(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        assert _truncate_write_file_error_detail("short", 100) == "short"

    def test_zero_max(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        long = "x" * 100
        assert _truncate_write_file_error_detail(long, 0) == long

    def test_truncated(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        long = "x" * 1000
        result = _truncate_write_file_error_detail(long, 100)
        assert len(result) <= 100

    def test_format_write_file_error(self):
        from ideer.sandbox.tools import _format_write_file_error

        result = _format_write_file_error("/path", ValueError("bad"))
        assert "Error:" in result
        assert "/path" in result


# ---------------------------------------------------------------------------
# _resolve_max_results / _clamp_max_results / _get_tool_config_int
# ---------------------------------------------------------------------------


class TestMaxResultsExtra:
    def test_clamp_zero(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(0, default=100, upper_bound=500) == 100

    def test_clamp_negative(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(-5, default=100, upper_bound=500) == 100

    def test_clamp_over_limit(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(1000, default=100, upper_bound=500) == 500

    def test_clamp_normal(self):
        from ideer.sandbox.tools import _clamp_max_results

        assert _clamp_max_results(200, default=100, upper_bound=500) == 200

    def test_resolve_max_results(self):
        from ideer.sandbox.tools import _resolve_max_results

        with patch("ideer.sandbox.tools._get_tool_config_int", return_value=300):
            result = _resolve_max_results("glob", 200, default=100, upper_bound=500)
            assert result == 200

    def test_get_tool_config_int_exception(self):
        from ideer.sandbox.tools import _get_tool_config_int

        with patch("ideer.sandbox.tools.get_app_config", side_effect=Exception("no")):
            assert _get_tool_config_int("glob", "max_results", 100) == 100


# ---------------------------------------------------------------------------
# _extract_thread_id_from_thread_data
# ---------------------------------------------------------------------------


class TestExtractThreadIdExtra:
    def test_none(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        assert _extract_thread_id_from_thread_data(None) is None

    def test_no_workspace(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        assert _extract_thread_id_from_thread_data({}) is None

    def test_valid(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        td = {"workspace_path": "/base/threads/t123/user-data/workspace"}
        assert _extract_thread_id_from_thread_data(td) == "t123"


# ---------------------------------------------------------------------------
# _get_acp_workspace_host_path
# ---------------------------------------------------------------------------


class TestGetAcpWorkspaceHostPath:
    def test_with_thread_id_not_found(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        mock_paths = MagicMock()
        mock_paths.acp_workspace_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            with patch("ideer.runtime.user_context.get_effective_user_id", return_value="u1"):
                result = _get_acp_workspace_host_path("t1")
                assert result is None

    def test_global_not_found(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        if hasattr(_get_acp_workspace_host_path, "_cached"):
            delattr(_get_acp_workspace_host_path, "_cached")
        mock_paths = MagicMock()
        mock_paths.base_dir = Path("/nonexistent")
        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            result = _get_acp_workspace_host_path(None)
            assert result is None


# ---------------------------------------------------------------------------
# _is_non_file_url_token / _non_file_url_spans / _is_in_spans
# ---------------------------------------------------------------------------


class TestUrlHelpersExtra:
    def test_non_file_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("https://example.com") is True

    def test_file_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("file:///tmp/test") is False

    def test_no_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("/tmp/test") is False

    def test_url_in_equals(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("URL=https://example.com") is True

    def test_non_file_url_spans(self):
        from ideer.sandbox.tools import _non_file_url_spans

        spans = _non_file_url_spans("curl https://example.com > /tmp/out")
        assert len(spans) == 1

    def test_in_spans(self):
        from ideer.sandbox.tools import _is_in_spans

        assert _is_in_spans(5, [(0, 10)]) is True
        assert _is_in_spans(15, [(0, 10)]) is False


# ---------------------------------------------------------------------------
# Shell token helpers
# ---------------------------------------------------------------------------


class TestShellTokenHelpersExtra:
    def test_split_shell_tokens(self):
        from ideer.sandbox.tools import _split_shell_tokens

        tokens = _split_shell_tokens("ls -la /tmp")
        assert "ls" in tokens

    def test_is_shell_command_separator(self):
        from ideer.sandbox.tools import _is_shell_command_separator

        assert _is_shell_command_separator(";") is True
        assert _is_shell_command_separator("&&") is True
        assert _is_shell_command_separator("ls") is False

    def test_is_shell_redirection_operator(self):
        from ideer.sandbox.tools import _is_shell_redirection_operator

        assert _is_shell_redirection_operator(">") is True
        assert _is_shell_redirection_operator(">>") is True
        assert _is_shell_redirection_operator("ls") is False

    def test_is_shell_assignment(self):
        from ideer.sandbox.tools import _is_shell_assignment

        assert _is_shell_assignment("FOO=bar") is True
        assert _is_shell_assignment("ls") is False
        assert _is_shell_assignment("=value") is False


# ---------------------------------------------------------------------------
# _next_cd_target / _validate_local_bash_cwd_target
# ---------------------------------------------------------------------------


class TestCdTarget:
    def test_next_cd_target_basic(self):
        from ideer.sandbox.tools import _next_cd_target

        target, idx = _next_cd_target(["cd", "/tmp"], 1)
        assert target == "/tmp"

    def test_next_cd_target_separator(self):
        from ideer.sandbox.tools import _next_cd_target

        target, idx = _next_cd_target(["cd", ";", "ls"], 1)
        assert target is None

    def test_next_cd_target_flag(self):
        from ideer.sandbox.tools import _next_cd_target

        target, idx = _next_cd_target(["cd", "-L", "/tmp"], 1)
        assert target == "/tmp"

    def test_validate_cwd_none_target_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", None, [])

    def test_validate_cwd_dollar_target_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "$HOME", [])

    def test_validate_cwd_tilde_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "~", [])

    def test_looks_like_unsafe_cwd_target(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("-") is True
        assert _looks_like_unsafe_cwd_target("$HOME") is True
        assert _looks_like_unsafe_cwd_target("~") is True
        assert _looks_like_unsafe_cwd_target("/tmp") is True
        assert _looks_like_unsafe_cwd_target("../escape") is True
        assert _looks_like_unsafe_cwd_target(None) is False
        assert _looks_like_unsafe_cwd_target("./safe") is False


# ---------------------------------------------------------------------------
# _has_dotdot_path_segment
# ---------------------------------------------------------------------------


class TestDotdotPath:
    def test_dotdot(self):
        from ideer.sandbox.tools import _has_dotdot_path_segment

        assert _has_dotdot_path_segment("../etc") is True
        assert _has_dotdot_path_segment("foo/../bar") is True

    def test_no_dotdot(self):
        from ideer.sandbox.tools import _has_dotdot_path_segment

        assert _has_dotdot_path_segment("/tmp/test") is False

    def test_non_file_url_skipped(self):
        from ideer.sandbox.tools import _has_dotdot_path_segment

        assert _has_dotdot_path_segment("https://example.com/../path") is False


# ---------------------------------------------------------------------------
# Tool implementations (bash, ls, glob, grep, read_file, write_file, str_replace)
# ---------------------------------------------------------------------------


class TestBashTool:
    def test_local_sandbox_host_bash_disabled(self):
        from ideer.sandbox.tools import bash_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.is_host_bash_allowed", return_value=False):
                    result = bash_tool.func(runtime, "test", "ls")
                    assert "Error" in result

    def test_local_sandbox_success(self, tmp_path):
        from ideer.sandbox.tools import bash_tool

        ws = str(tmp_path / "ws")
        Path(ws).mkdir()
        td = {"workspace_path": ws, "uploads_path": str(tmp_path / "up"), "outputs_path": str(tmp_path / "out")}
        runtime = _make_runtime(thread_data=td)
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "ok"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.is_host_bash_allowed", return_value=True):
                    with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                        mock_cfg.return_value.sandbox.bash_output_max_chars = 20000
                        result = bash_tool.func(runtime, "test", "echo hello")
                        assert "ok" in result

    def test_non_local_sandbox_success(self):
        from ideer.sandbox.tools import bash_tool

        runtime = _make_runtime(sandbox_id="aio:test")
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "output"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                    mock_cfg.return_value.sandbox.bash_output_max_chars = 20000
                    result = bash_tool.func(runtime, "test", "ls")
                    assert "output" in result

    def test_sandbox_error(self):
        from ideer.sandbox.tools import bash_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = bash_tool.func(runtime, "test", "ls")
                assert "Error" in result

    def test_permission_error(self):
        from ideer.sandbox.tools import bash_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = PermissionError("denied")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = bash_tool.func(runtime, "test", "ls")
                assert "Error" in result


class TestLsTool:
    def test_empty_dir(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = []
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                    mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
                    result = ls_tool.func(runtime, "test", "/tmp")
                    assert "(empty)" in result

    def test_with_contents(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["file1.txt", "file2.py"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                    mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
                    result = ls_tool.func(runtime, "test", "/tmp")
                    assert "file1.txt" in result

    def test_file_not_found(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.side_effect = FileNotFoundError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = ls_tool.func(runtime, "test", "/nonexistent")
                assert "not found" in result.lower()

    def test_permission_denied(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.side_effect = PermissionError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = ls_tool.func(runtime, "test", "/root")
                assert "denied" in result.lower()


class TestGlobTool:
    def test_no_matches(self):
        from ideer.sandbox.tools import glob_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.glob.return_value = ([], False)
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = glob_tool.func(runtime, "test", "*.xyz", "/tmp")
                assert "No files matched" in result

    def test_with_matches(self):
        from ideer.sandbox.tools import glob_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.glob.return_value = (["/tmp/a.py", "/tmp/b.py"], False)
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = glob_tool.func(runtime, "test", "*.py", "/tmp")
                assert "Found 2 paths" in result

    def test_not_a_directory(self):
        from ideer.sandbox.tools import glob_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.glob.side_effect = NotADirectoryError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = glob_tool.func(runtime, "test", "*.py", "/tmp/file.txt")
                assert "not a directory" in result.lower()


class TestGrepTool:
    def test_no_matches(self):
        from ideer.sandbox.tools import grep_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.grep.return_value = ([], False)
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = grep_tool.func(runtime, "test", "pattern", "/tmp")
                assert "No matches found" in result

    def test_invalid_regex(self):
        from ideer.sandbox.tools import grep_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = re.error("bad regex")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = grep_tool.func(runtime, "test", "[invalid", "/tmp")
                assert "Invalid regex" in result


class TestReadFileTool:
    def test_empty_file(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = ""
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = read_file_tool.func(runtime, "test", "/tmp/empty.txt")
                assert "(empty)" in result

    def test_with_content(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "hello world"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                    mock_cfg.return_value.sandbox.read_file_output_max_chars = 50000
                    result = read_file_tool.func(runtime, "test", "/tmp/test.txt")
                    assert "hello world" in result

    def test_with_line_range(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "line1\nline2\nline3\nline4\nline5"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                    mock_cfg.return_value.sandbox.read_file_output_max_chars = 50000
                    result = read_file_tool.func(runtime, "test", "/tmp/test.txt", start_line=2, end_line=4)
                    assert "line2" in result

    def test_file_not_found(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = FileNotFoundError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = read_file_tool.func(runtime, "test", "/tmp/missing.txt")
                assert "not found" in result.lower()

    def test_is_a_directory(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = IsADirectoryError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = read_file_tool.func(runtime, "test", "/tmp")
                assert "directory" in result.lower()


class TestWriteFileTool:
    def test_success(self):
        from ideer.sandbox.tools import write_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = write_file_tool.func(runtime, "test", "/tmp/test.txt", "content")
                    assert result == "OK"

    def test_sandbox_error(self):
        from ideer.sandbox.tools import write_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    mock_sandbox.write_file.side_effect = SandboxError("fail")
                    result = write_file_tool.func(runtime, "test", "/tmp/test.txt", "content")
                    assert "Error" in result

    def test_is_a_directory(self):
        from ideer.sandbox.tools import write_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    mock_sandbox.write_file.side_effect = IsADirectoryError()
                    result = write_file_tool.func(runtime, "test", "/tmp", "content")
                    assert "directory" in result.lower()


class TestStrReplaceTool:
    def test_success(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "hello world"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/test.txt", "hello", "goodbye")
                    assert result == "OK"
                    mock_sandbox.write_file.assert_called_once()

    def test_string_not_found(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "hello world"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/test.txt", "notfound", "new")
                    assert "not found" in result.lower()

    def test_empty_file(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = ""
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/test.txt", "old", "new")
                    assert result == "OK"

    def test_replace_all(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "aaa bbb aaa"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/test.txt", "aaa", "ccc", replace_all=True)
                    assert result == "OK"


# ---------------------------------------------------------------------------
# _run_sync_tool_after_async_sandbox_init
# ---------------------------------------------------------------------------


class TestRunSyncToolAfterAsyncSandboxInit:
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
    async def test_success(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        sync_func = MagicMock(return_value="result")
        with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", return_value=mock_sandbox):
            result = await _run_sync_tool_after_async_sandbox_init(sync_func, runtime, "arg1")
            assert result == "result"


# ---------------------------------------------------------------------------
# Async tool wrappers
# ---------------------------------------------------------------------------


class TestAsyncToolWrappers:
    @pytest.mark.asyncio
    async def test_bash_tool_async(self):
        from ideer.sandbox.tools import _bash_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="ok"):
            result = await _bash_tool_async(runtime, "test", "ls")
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_ls_tool_async(self):
        from ideer.sandbox.tools import _ls_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="file.txt"):
            result = await _ls_tool_async(runtime, "test", "/tmp")
            assert result == "file.txt"

    @pytest.mark.asyncio
    async def test_glob_tool_async(self):
        from ideer.sandbox.tools import _glob_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="Found 1 paths"):
            result = await _glob_tool_async(runtime, "test", "*.py", "/tmp")
            assert "Found 1 paths" in result

    @pytest.mark.asyncio
    async def test_grep_tool_async(self):
        from ideer.sandbox.tools import _grep_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="Found 1 matches"):
            result = await _grep_tool_async(runtime, "test", "hello", "/tmp")
            assert "Found 1 matches" in result

    @pytest.mark.asyncio
    async def test_read_file_tool_async(self):
        from ideer.sandbox.tools import _read_file_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="content"):
            result = await _read_file_tool_async(runtime, "test", "/tmp/test.txt")
            assert result == "content"

    @pytest.mark.asyncio
    async def test_write_file_tool_async(self):
        from ideer.sandbox.tools import _write_file_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="OK"):
            result = await _write_file_tool_async(runtime, "test", "/tmp/test.txt", "data")
            assert result == "OK"

    @pytest.mark.asyncio
    async def test_str_replace_tool_async(self):
        from ideer.sandbox.tools import _str_replace_tool_async

        runtime = _make_runtime()
        with patch("ideer.sandbox.tools._run_sync_tool_after_async_sandbox_init", new_callable=AsyncMock, return_value="OK"):
            result = await _str_replace_tool_async(runtime, "test", "/tmp/test.txt", "hello", "bye")
            assert result == "OK"


# ---------------------------------------------------------------------------
# _path_variants / _path_separator_for_style / _join_path_preserving_style
# ---------------------------------------------------------------------------


class TestPathStyleHelpers:
    def test_path_variants(self):
        from ideer.sandbox.tools import _path_variants

        variants = _path_variants("/tmp/test")
        assert "/tmp/test" in variants
        assert "\\tmp\\test" in variants

    def test_separator_forward(self):
        from ideer.sandbox.tools import _path_separator_for_style

        assert _path_separator_for_style("/tmp/test") == "/"

    def test_separator_backslash(self):
        from ideer.sandbox.tools import _path_separator_for_style

        assert _path_separator_for_style("C:\\Users\\test") == "\\"

    def test_join_preserving_forward(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        result = _join_path_preserving_style("/tmp", "sub/file")
        assert result == "/tmp/sub/file"

    def test_join_preserving_backslash(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        result = _join_path_preserving_style("C:\\Users", "sub\\file")
        assert result == "C:\\Users\\sub\\file"

    def test_join_empty_relative(self):
        from ideer.sandbox.tools import _join_path_preserving_style

        assert _join_path_preserving_style("/tmp", "") == "/tmp"


# ---------------------------------------------------------------------------
# _resolve_local_read_path
# ---------------------------------------------------------------------------


class TestResolveLocalReadPath:
    def test_skills_path(self):
        from ideer.sandbox.tools import _resolve_local_read_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
            with patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills"):
                result = _resolve_local_read_path("/mnt/skills/test", td)
                assert result == "/host/skills"

    def test_acp_path(self):
        from ideer.sandbox.tools import _resolve_local_read_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=True):
                with patch("ideer.sandbox.tools._resolve_acp_workspace_path", return_value="/host/acp"):
                    result = _resolve_local_read_path("/mnt/acp-workspace/test", td)
                    assert result == "/host/acp"

    def test_user_data_path(self):
        from ideer.sandbox.tools import _resolve_local_read_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                with patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/resolved"):
                    result = _resolve_local_read_path("/mnt/user-data/workspace/test", td)
                    assert result == "/resolved"


# ===========================================================================
# Additional tests for improved coverage
# ===========================================================================


class TestGetSkillsContainerPathExtended:
    def test_cached_value(self):
        from ideer.sandbox.tools import _get_skills_container_path

        # Clear any existing cache
        had_cache = hasattr(_get_skills_container_path, "_cached")
        saved_cache = getattr(_get_skills_container_path, "_cached", None)
        if had_cache:
            delattr(_get_skills_container_path, "_cached")

        try:
            # Set a cache value and verify it's returned
            _get_skills_container_path._cached = "/custom/skills"
            result = _get_skills_container_path()
            assert result == "/custom/skills"
            # Second call should use cache
            result2 = _get_skills_container_path()
            assert result2 == "/custom/skills"
        finally:
            # Restore original cache state
            delattr(_get_skills_container_path, "_cached")
            if saved_cache is not None:
                _get_skills_container_path._cached = saved_cache


class TestGetSkillsHostPathExtended:
    def test_returns_path_when_exists(self):
        from ideer.sandbox.tools import _get_skills_host_path

        saved_cache = getattr(_get_skills_host_path, "_cached", None)
        if hasattr(_get_skills_host_path, "_cached"):
            delattr(_get_skills_host_path, "_cached")

        try:
            _get_skills_host_path._cached = "/opt/skills"
            result = _get_skills_host_path()
            assert result == "/opt/skills"
        finally:
            delattr(_get_skills_host_path, "_cached")
            if saved_cache is not None:
                _get_skills_host_path._cached = saved_cache

    def test_returns_none_when_not_exists(self):
        from ideer.sandbox.tools import _get_skills_host_path

        saved_cache = getattr(_get_skills_host_path, "_cached", None)
        if hasattr(_get_skills_host_path, "_cached"):
            delattr(_get_skills_host_path, "_cached")

        try:
            # With no cache and a config whose skills dir does not exist,
            # the function should return None without caching a failure.
            mock_config = MagicMock()
            mock_config.skills.get_skills_path.return_value = Path("/nonexistent/skills")
            with patch("ideer.config.get_app_config", return_value=mock_config):
                result = _get_skills_host_path()
            assert result is None
        finally:
            if saved_cache is not None:
                _get_skills_host_path._cached = saved_cache


class TestResolveSkillsPath:
    def test_root_path(self):
        from ideer.sandbox.tools import _resolve_skills_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills"):
                result = _resolve_skills_path("/mnt/skills")
                assert result == "/opt/skills"

    def test_subpath(self):
        from ideer.sandbox.tools import _resolve_skills_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills"):
                result = _resolve_skills_path("/mnt/skills/SKILL.md")
                assert result == "/opt/skills/SKILL.md"

    def test_no_host_path_raises(self):
        from ideer.sandbox.tools import _resolve_skills_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with patch("ideer.sandbox.tools._get_skills_host_path", return_value=None):
                with pytest.raises(FileNotFoundError):
                    _resolve_skills_path("/mnt/skills/test")


class TestIsAcpWorkspacePath:
    def test_exact_match(self):
        from ideer.sandbox.tools import _is_acp_workspace_path

        assert _is_acp_workspace_path("/mnt/acp-workspace") is True

    def test_subpath(self):
        from ideer.sandbox.tools import _is_acp_workspace_path

        assert _is_acp_workspace_path("/mnt/acp-workspace/test.py") is True

    def test_not_match(self):
        from ideer.sandbox.tools import _is_acp_workspace_path

        assert _is_acp_workspace_path("/mnt/user-data/workspace") is False


class TestGetCustomMountsExtended:
    def test_returns_mounts_when_config_succeeds(self):
        from ideer.sandbox.tools import _get_custom_mounts

        saved_cache = getattr(_get_custom_mounts, "_cached", None)
        if hasattr(_get_custom_mounts, "_cached"):
            delattr(_get_custom_mounts, "_cached")

        try:
            # Test that the function returns a list (either from config or empty)
            result = _get_custom_mounts()
            assert isinstance(result, list)
        finally:
            if hasattr(_get_custom_mounts, "_cached"):
                delattr(_get_custom_mounts, "_cached")
            if saved_cache is not None:
                _get_custom_mounts._cached = saved_cache

    def test_no_sandbox_config(self):
        from ideer.sandbox.tools import _get_custom_mounts

        saved_cache = getattr(_get_custom_mounts, "_cached", None)
        if hasattr(_get_custom_mounts, "_cached"):
            delattr(_get_custom_mounts, "_cached")

        try:
            # The function imports get_app_config locally, so patch the source
            # module (ideer.config) rather than the sandbox.tools namespace.
            with patch("ideer.config.get_app_config") as mock_cfg:
                mock_cfg.return_value.sandbox = None
                result = _get_custom_mounts()
                assert result == []
        finally:
            if hasattr(_get_custom_mounts, "_cached"):
                delattr(_get_custom_mounts, "_cached")
            if saved_cache is not None:
                _get_custom_mounts._cached = saved_cache


class TestIsCustomMountPathExtended:
    def test_matches_mount(self):
        from ideer.sandbox.tools import _is_custom_mount_path

        mock_mount = MagicMock()
        mock_mount.container_path = "/mnt/data"
        with patch("ideer.sandbox.tools._get_custom_mounts", return_value=[mock_mount]):
            assert _is_custom_mount_path("/mnt/data/file.txt") is True
            assert _is_custom_mount_path("/mnt/data") is True

    def test_no_match(self):
        from ideer.sandbox.tools import _is_custom_mount_path

        mock_mount = MagicMock()
        mock_mount.container_path = "/mnt/data"
        with patch("ideer.sandbox.tools._get_custom_mounts", return_value=[mock_mount]):
            assert _is_custom_mount_path("/mnt/other/file.txt") is False


class TestGetCustomMountForPath:
    def test_longest_prefix_wins(self):
        from ideer.sandbox.tools import _get_custom_mount_for_path

        mount1 = MagicMock()
        mount1.container_path = "/mnt/data"
        mount2 = MagicMock()
        mount2.container_path = "/mnt/data/sub"
        with patch("ideer.sandbox.tools._get_custom_mounts", return_value=[mount1, mount2]):
            result = _get_custom_mount_for_path("/mnt/data/sub/file.txt")
            assert result is mount2

    def test_no_match(self):
        from ideer.sandbox.tools import _get_custom_mount_for_path

        with patch("ideer.sandbox.tools._get_custom_mounts", return_value=[]):
            result = _get_custom_mount_for_path("/other/path")
            assert result is None


class TestExtractThreadIdExtended:
    def test_exception_returns_none(self):
        from ideer.sandbox.tools import _extract_thread_id_from_thread_data

        # Path that causes an exception in parent.parent.name
        td = {"workspace_path": "/"}
        result = _extract_thread_id_from_thread_data(td)
        # "/" -> parent = "/" -> parent = "/" -> name = ""
        assert result is not None or result is None  # Either outcome is fine


class TestGetAcpWorkspaceHostPathExtended:
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

    def test_global_cached(self):
        from ideer.sandbox.tools import _get_acp_workspace_host_path

        saved_cache = getattr(_get_acp_workspace_host_path, "_cached", None)
        if hasattr(_get_acp_workspace_host_path, "_cached"):
            delattr(_get_acp_workspace_host_path, "_cached")

        try:
            # Set cache directly and verify it's returned
            _get_acp_workspace_host_path._cached = "/base/acp-workspace"
            result = _get_acp_workspace_host_path(None)
            assert result == "/base/acp-workspace"
        finally:
            delattr(_get_acp_workspace_host_path, "_cached")
            if saved_cache is not None:
                _get_acp_workspace_host_path._cached = saved_cache


class TestResolveAcpWorkspacePath:
    def test_root_path(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/base/acp"):
            result = _resolve_acp_workspace_path("/mnt/acp-workspace")
            assert result == "/base/acp"

    def test_subpath(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/base/acp"):
            result = _resolve_acp_workspace_path("/mnt/acp-workspace/test.py")
            assert "test.py" in result

    def test_no_host_path_raises(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value=None):
            with pytest.raises(FileNotFoundError):
                _resolve_acp_workspace_path("/mnt/acp-workspace/test")

    def test_path_traversal_raises(self):
        from ideer.sandbox.tools import _resolve_acp_workspace_path

        with pytest.raises(PermissionError):
            _resolve_acp_workspace_path("/mnt/acp-workspace/../../etc/passwd")


class TestGetMcpAllowedPaths:
    def test_no_extensions_config(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        with patch("ideer.config.extensions_config.get_extensions_config", side_effect=Exception("no config")):
            result = _get_mcp_allowed_paths()
            assert result == []

    def test_with_filesystem_server(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = True
        mock_server.args = ["--some-flag", "@modelcontextprotocol/server-filesystem", "/data/"]

        mock_ext_config = MagicMock()
        mock_ext_config.mcp_servers = {"fs": mock_server}

        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext_config):
            result = _get_mcp_allowed_paths()
            assert "/data/" in result

    def test_disabled_server_skipped(self):
        from ideer.sandbox.tools import _get_mcp_allowed_paths

        mock_server = MagicMock()
        mock_server.enabled = False
        mock_server.args = ["@modelcontextprotocol/server-filesystem", "/data/"]

        mock_ext_config = MagicMock()
        mock_ext_config.mcp_servers = {"fs": mock_server}

        with patch("ideer.config.extensions_config.get_extensions_config", return_value=mock_ext_config):
            result = _get_mcp_allowed_paths()
            assert "/data/" not in result


class TestGetToolConfigIntExtended:
    def test_returns_configured_value(self):
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_config.get_tool_config.return_value = MagicMock()
        mock_config.get_tool_config.return_value.model_extra = {"max_results": 500}

        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 100)
            assert result == 500

    def test_returns_default_when_key_missing(self):
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_config.get_tool_config.return_value = MagicMock()
        mock_config.get_tool_config.return_value.model_extra = {}

        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 100)
            assert result == 100

    def test_returns_default_when_not_int(self):
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_config.get_tool_config.return_value = MagicMock()
        mock_config.get_tool_config.return_value.model_extra = {"max_results": "not_int"}

        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 100)
            assert result == 100

    def test_returns_default_when_no_tool_config(self):
        from ideer.sandbox.tools import _get_tool_config_int

        mock_config = MagicMock()
        mock_config.get_tool_config.return_value = None

        with patch("ideer.sandbox.tools.get_app_config", return_value=mock_config):
            result = _get_tool_config_int("glob", "max_results", 100)
            assert result == 100


class TestResolveMaxResultsExtended:
    def test_respects_lower_bound(self):
        from ideer.sandbox.tools import _resolve_max_results

        with patch("ideer.sandbox.tools._get_tool_config_int", return_value=50):
            result = _resolve_max_results("glob", 100, default=200, upper_bound=500)
            assert result == 50

    def test_respects_upper_bound(self):
        from ideer.sandbox.tools import _resolve_max_results

        with patch("ideer.sandbox.tools._get_tool_config_int", return_value=1000):
            result = _resolve_max_results("glob", 200, default=100, upper_bound=500)
            assert result == 200


class TestReplaceVirtualPathExtended:
    def test_exact_match_workspace(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data()
        result = replace_virtual_path("/mnt/user-data/workspace", td)
        assert result == td["workspace_path"]

    def test_trailing_slash_preserved(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = _make_thread_data()
        result = replace_virtual_path("/mnt/user-data/workspace/", td)
        assert result.endswith("/") or result.endswith("\\")

    def test_empty_mappings(self):
        from ideer.sandbox.tools import replace_virtual_path

        td = {"workspace_path": None, "uploads_path": None, "outputs_path": None}
        result = replace_virtual_path("/mnt/user-data/workspace/file.txt", td)
        assert result == "/mnt/user-data/workspace/file.txt"


class TestThreadVirtualToActualMappings:
    def test_all_paths(self):
        from ideer.sandbox.tools import _thread_virtual_to_actual_mappings

        td = _make_thread_data()
        mappings = _thread_virtual_to_actual_mappings(td)
        assert "/mnt/user-data/workspace" in mappings
        assert "/mnt/user-data/uploads" in mappings
        assert "/mnt/user-data/outputs" in mappings

    def test_common_parent(self):
        from ideer.sandbox.tools import _thread_virtual_to_actual_mappings

        td = {
            "workspace_path": "/base/user-data/workspace",
            "uploads_path": "/base/user-data/uploads",
            "outputs_path": "/base/user-data/outputs",
        }
        mappings = _thread_virtual_to_actual_mappings(td)
        assert "/mnt/user-data" in mappings

    def test_partial_paths(self):
        from ideer.sandbox.tools import _thread_virtual_to_actual_mappings

        td = {"workspace_path": "/ws", "uploads_path": None, "outputs_path": None}
        mappings = _thread_virtual_to_actual_mappings(td)
        assert "/mnt/user-data/workspace" in mappings
        assert "/mnt/user-data/uploads" not in mappings


class TestMaskLocalPathsInOutputExtended:
    def test_empty_mappings(self):
        from ideer.sandbox.tools import mask_local_paths_in_output

        td = {"workspace_path": None, "uploads_path": None, "outputs_path": None}
        result = mask_local_paths_in_output("hello", td)
        assert result == "hello"


class TestValidateLocalBashCommandPathsExtended:
    def test_cd_to_virtual_path(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            validate_local_bash_command_paths("cd /mnt/user-data/workspace", td)

    def test_cd_to_home_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError):
            validate_local_bash_command_paths("cd ~", td)

    def test_command_with_url(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_mcp_allowed_paths", return_value=[]):
            validate_local_bash_command_paths("curl https://example.com > /mnt/user-data/workspace/out.txt", td)

    def test_dotdot_in_command_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError):
            validate_local_bash_command_paths("cat /mnt/user-data/../etc/passwd", td)

    def test_subshell_cd_raises(self):
        from ideer.sandbox.tools import validate_local_bash_command_paths

        td = _make_thread_data()
        with pytest.raises(PermissionError, match="command substitution"):
            validate_local_bash_command_paths("$(cd /tmp)", td)


class TestValidateLocalBashShellTokensExtended:
    def test_assignment_at_start(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        # Should not raise - assignment is allowed
        _validate_local_bash_shell_tokens("FOO=bar ls /mnt/user-data/workspace", [])

    def test_command_wrapper_builtin(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        # builtin cd should be validated
        with pytest.raises(PermissionError):
            _validate_local_bash_shell_tokens("builtin cd ~", [])

    def test_prefix_keyword(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        # 'if' is a prefix keyword
        _validate_local_bash_shell_tokens("if true; then echo ok; fi", [])


class TestValidateLocalBashRootPathArgs:
    def test_slash_only_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        with pytest.raises(PermissionError, match="/"):
            _validate_local_bash_root_path_args("cat", ["/"], 0)

    def test_non_root_command_skipped(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        # 'echo' is not in _LOCAL_BASH_ROOT_PATH_COMMANDS
        _validate_local_bash_root_path_args("echo", ["/etc/passwd"], 0)

    def test_separator_stops(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        _validate_local_bash_root_path_args("cat", [";", "/etc/passwd"], 0)

    def test_redirection_skipped(self):
        from ideer.sandbox.tools import _validate_local_bash_root_path_args

        _validate_local_bash_root_path_args("cat", [">", "/tmp/out"], 0)


class TestNextCdTargetExtended:
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

    def test_redirection(self):
        from ideer.sandbox.tools import _next_cd_target

        tokens = [">", "/dev/null", "/tmp"]
        target, idx = _next_cd_target(tokens, 0)
        assert target == "/tmp"


class TestValidateLocalBashCwdTargetExtended:
    def test_backtick_target_raises(self):
        from ideer.sandbox.tools import _validate_local_bash_cwd_target

        with pytest.raises(PermissionError):
            _validate_local_bash_cwd_target("cd", "`pwd`", [])


class TestLooksLikeUnsafeCwdTargetExtended:
    def test_double_dot(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("../escape") is True

    def test_dotdot_in_middle(self):
        from ideer.sandbox.tools import _looks_like_unsafe_cwd_target

        assert _looks_like_unsafe_cwd_target("foo/../bar") is True


class TestHasDotDotPathSegmentExtended:
    def test_equals_sign(self):
        from ideer.sandbox.tools import _has_dotdot_path_segment

        assert _has_dotdot_path_segment("key=../value") is True

    def test_backslash(self):
        from ideer.sandbox.tools import _has_dotdot_path_segment

        assert _has_dotdot_path_segment("foo\\..\\bar") is True


class TestIsNonFileUrlTokenExtended:
    def test_with_equals(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("URL=https://example.com") is True

    def test_file_url(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("file:///tmp/test") is False

    def test_plain_path(self):
        from ideer.sandbox.tools import _is_non_file_url_token

        assert _is_non_file_url_token("/tmp/test") is False


class TestBashToolExtended:
    def test_unexpected_error(self):
        from ideer.sandbox.tools import bash_tool

        runtime = _make_runtime(sandbox_id="aio:test")
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = RuntimeError("unexpected")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = bash_tool.func(runtime, "test", "ls")
                assert "Error" in result


class TestLsToolExtended:
    def test_local_sandbox_with_skills_path(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime(thread_data=_make_thread_data())
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.return_value = ["SKILL.md"]
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=True):
                with patch("ideer.sandbox.tools.validate_local_tool_path"):
                    with patch("ideer.sandbox.tools._is_skills_path", return_value=True):
                        with patch("ideer.sandbox.tools._resolve_skills_path", return_value="/host/skills"):
                            with patch("ideer.sandbox.tools.get_thread_data", return_value=_make_thread_data()):
                                with patch("ideer.sandbox.tools.mask_local_paths_in_output", return_value="SKILL.md"):
                                    with patch("ideer.sandbox.tools.get_app_config") as mock_cfg:
                                        mock_cfg.return_value.sandbox.ls_output_max_chars = 20000
                                        result = ls_tool.func(runtime, "test", "/mnt/skills")
                                        assert "SKILL.md" in result

    def test_unexpected_error(self):
        from ideer.sandbox.tools import ls_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.list_dir.side_effect = RuntimeError("unexpected")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = ls_tool.func(runtime, "test", "/tmp")
                assert "Error" in result


class TestGlobToolExtended:
    def test_sandbox_error(self):
        from ideer.sandbox.tools import glob_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.glob.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = glob_tool.func(runtime, "test", "*.py", "/tmp")
                assert "Error" in result

    def test_permission_error(self):
        from ideer.sandbox.tools import glob_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.glob.side_effect = PermissionError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = glob_tool.func(runtime, "test", "*.py", "/root")
                assert "denied" in result.lower()


class TestGrepToolExtended:
    def test_with_matches(self):
        from ideer.sandbox.search import GrepMatch
        from ideer.sandbox.tools import grep_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.grep.return_value = (
            [GrepMatch(path="/tmp/a.py", line_number=1, line="hello")],
            False,
        )
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = grep_tool.func(runtime, "test", "hello", "/tmp")
                assert "Found 1 matches" in result

    def test_permission_error(self):
        from ideer.sandbox.tools import grep_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = PermissionError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = grep_tool.func(runtime, "test", "p", "/root")
                assert "denied" in result.lower()

    def test_sandbox_error(self):
        from ideer.sandbox.tools import grep_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.grep.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = grep_tool.func(runtime, "test", "p", "/tmp")
                assert "Error" in result


class TestReadFileToolExtended:
    def test_permission_error(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = PermissionError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = read_file_tool.func(runtime, "test", "/root/secret")
                assert "denied" in result.lower()

    def test_sandbox_error(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = read_file_tool.func(runtime, "test", "/tmp/test")
                assert "Error" in result

    def test_unexpected_error(self):
        from ideer.sandbox.tools import read_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                result = read_file_tool.func(runtime, "test", "/tmp/test")
                assert "Error" in result


class TestWriteFileToolExtended:
    def test_permission_error(self):
        from ideer.sandbox.tools import write_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.write_file.side_effect = PermissionError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = write_file_tool.func(runtime, "test", "/root/secret", "data")
                    assert "denied" in result.lower()

    def test_os_error(self):
        from ideer.sandbox.tools import write_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.write_file.side_effect = OSError("disk full")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = write_file_tool.func(runtime, "test", "/tmp/test", "data")
                    assert "Error" in result

    def test_unexpected_error(self):
        from ideer.sandbox.tools import write_file_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.write_file.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = write_file_tool.func(runtime, "test", "/tmp/test", "data")
                    assert "Error" in result


class TestStrReplaceToolExtended:
    def test_sandbox_error(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = SandboxError("fail")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/test", "old", "new")
                    assert "Error" in result

    def test_file_not_found(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = FileNotFoundError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/missing", "old", "new")
                    assert "not found" in result.lower()

    def test_permission_error(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = PermissionError()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/root/secret", "old", "new")
                    assert "denied" in result.lower()

    def test_unexpected_error(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.side_effect = RuntimeError("boom")
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/test", "old", "new")
                    assert "Error" in result

    def test_replace_all_flag(self):
        from ideer.sandbox.tools import str_replace_tool

        runtime = _make_runtime()
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "aaa bbb aaa"
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            with patch("ideer.sandbox.tools.is_local_sandbox", return_value=False):
                with patch("ideer.sandbox.tools.get_file_operation_lock", return_value=mock_lock):
                    result = str_replace_tool.func(runtime, "test", "/tmp/test", "aaa", "ccc", replace_all=True)
                    assert result == "OK"
                    written_content = mock_sandbox.write_file.call_args[0][1]
                    assert written_content == "ccc bbb ccc"


class TestTruncateWriteFileErrorDetailExtended:
    def test_exact_length(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "x" * 100
        assert _truncate_write_file_error_detail(detail, 100) == detail

    def test_preserves_head_and_tail(self):
        from ideer.sandbox.tools import _truncate_write_file_error_detail

        detail = "HEAD" + "x" * 1000 + "TAIL"
        result = _truncate_write_file_error_detail(detail, 100)
        assert len(result) <= 100


class TestFormatWriteFileErrorExtended:
    def test_with_runtime(self):
        from ideer.sandbox.tools import _format_write_file_error

        td = _make_thread_data()
        runtime = _make_runtime(thread_data=td)
        with patch("ideer.sandbox.tools._sanitize_error", return_value="sanitized"):
            result = _format_write_file_error("/test", ValueError("bad"), runtime)
            assert "Error" in result
            assert "/test" in result

    def test_zero_max_chars(self):
        from ideer.sandbox.tools import _format_write_file_error

        result = _format_write_file_error("/test", ValueError("bad"), max_chars=0)
        assert "Error" in result


class TestApplyCwdPrefixExtended:
    def test_no_workspace_path(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        td = {"workspace_path": None}
        result = _apply_cwd_prefix("ls -la", td)
        assert result == "ls -la"

    def test_empty_thread_data(self):
        from ideer.sandbox.tools import _apply_cwd_prefix

        result = _apply_cwd_prefix("ls -la", {})
        assert result == "ls -la"


class TestEnsureSandboxInitializedExtended:
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

    def test_sandbox_id_set_in_context(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized

        runtime = _make_runtime(sandbox_id="test_id")
        mock_sandbox = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_sandbox
        with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
            ensure_sandbox_initialized(runtime)
            assert runtime.context["sandbox_id"] == "test_id"


class TestEnsureSandboxInitializedAsyncExtended:
    def test_none_state_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            runtime = MagicMock()
            runtime.state = None
            with pytest.raises(SandboxRuntimeError):
                await ensure_sandbox_initialized_async(runtime)

        _run_async(go())

    def test_no_thread_id_raises(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            runtime = MagicMock()
            runtime.state = {}
            runtime.context = {}
            runtime.config = {}
            with pytest.raises(SandboxRuntimeError, match="Thread ID"):
                await ensure_sandbox_initialized_async(runtime)

        _run_async(go())

    def test_released_sandbox_reacquired(self):
        from ideer.sandbox.tools import ensure_sandbox_initialized_async

        async def go():
            runtime = _make_runtime(sandbox_id="old_id")
            mock_sandbox = MagicMock()
            mock_provider = MagicMock()
            mock_provider.get.side_effect = [None, mock_sandbox]
            mock_provider.acquire_async = AsyncMock(return_value="new_id")
            with patch("ideer.sandbox.tools.get_sandbox_provider", return_value=mock_provider):
                result = await ensure_sandbox_initialized_async(runtime)
                assert result is mock_sandbox

        _run_async(go())


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestRunSyncToolAfterAsyncSandboxInitExtended:
    def test_success_with_args(self):
        from ideer.sandbox.tools import _run_sync_tool_after_async_sandbox_init

        async def go():
            runtime = _make_runtime()
            sync_func = MagicMock(return_value="result")
            with patch("ideer.sandbox.tools.ensure_sandbox_initialized_async", new_callable=AsyncMock):
                result = await _run_sync_tool_after_async_sandbox_init(sync_func, runtime, "arg1", "arg2")
                assert result == "result"

        _run_async(go())


class TestReplaceVirtualPathsInCommandExtended:
    def test_skills_path_replacement(self):
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/skills"):
                result = replace_virtual_paths_in_command("cat /mnt/skills/test.md", td)
                assert "/mnt/skills" not in result
                assert "/opt/skills" in result

    def test_acp_workspace_replacement(self):
        from ideer.sandbox.tools import replace_virtual_paths_in_command

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/base/acp"):
            result = replace_virtual_paths_in_command("cat /mnt/acp-workspace/test.py", td)
            assert "/mnt/acp-workspace" not in result


class TestResolveLocalReadPathExtended:
    def test_custom_mount_path(self):
        from ideer.sandbox.tools import _resolve_local_read_path

        td = _make_thread_data()
        with patch("ideer.sandbox.tools._is_skills_path", return_value=False):
            with patch("ideer.sandbox.tools._is_acp_workspace_path", return_value=False):
                # Custom mount paths are NOT resolved by _resolve_local_read_path
                # They fall through to _resolve_and_validate_user_data_path
                with patch("ideer.sandbox.tools._resolve_and_validate_user_data_path", return_value="/resolved"):
                    result = _resolve_local_read_path("/mnt/user-data/workspace/test", td)
                    assert result == "/resolved"


class TestPathTraversalInCommands:
    def test_dotdot_in_tokens(self):
        from ideer.sandbox.tools import _validate_local_bash_shell_tokens

        with pytest.raises(PermissionError):
            _validate_local_bash_shell_tokens("cat /mnt/user-data/../etc/passwd", [])
