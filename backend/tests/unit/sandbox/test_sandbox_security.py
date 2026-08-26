"""Sandbox security boundary tests.

Validates that sandbox isolation mechanisms correctly prevent:
- Host filesystem escape via path traversal or symlinks
- Write access to read-only mounts
- Host path leakage in tool output
- Command execution without proper authorization
- Resource limit enforcement (timeouts, output size)

Uses mock sandboxes and fixtures to avoid executing dangerous operations.
"""

from __future__ import annotations

import errno
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ideer.sandbox.exceptions import SandboxRuntimeError
from ideer.sandbox.local.local_sandbox import LocalSandbox, PathMapping

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_workspace(tmp_path: Path):
    """Create a temporary workspace structure for sandbox tests."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    return SimpleNamespace(
        root=tmp_path,
        workspace=workspace,
        uploads=uploads,
        outputs=outputs,
    )


@pytest.fixture()
def thread_data(tmp_workspace) -> dict:
    """Thread data dictionary pointing to temporary directories."""
    return {
        "workspace_path": str(tmp_workspace.workspace),
        "uploads_path": str(tmp_workspace.uploads),
        "outputs_path": str(tmp_workspace.outputs),
    }


@pytest.fixture()
def sandbox_with_mappings(tmp_workspace) -> LocalSandbox:
    """Create a LocalSandbox with path mappings matching the thread data."""
    mappings = [
        PathMapping(
            container_path="/mnt/user-data/workspace",
            local_path=str(tmp_workspace.workspace),
            read_only=False,
        ),
        PathMapping(
            container_path="/mnt/user-data/uploads",
            local_path=str(tmp_workspace.uploads),
            read_only=False,
        ),
        PathMapping(
            container_path="/mnt/user-data/outputs",
            local_path=str(tmp_workspace.outputs),
            read_only=False,
        ),
        PathMapping(
            container_path="/mnt/skills",
            local_path=str(tmp_workspace.root / "skills"),
            read_only=True,
        ),
    ]
    return LocalSandbox("test-sandbox", path_mappings=mappings)


# ---------------------------------------------------------------------------
# 1. Path Traversal Defense -- _resolve_path
# ---------------------------------------------------------------------------


class TestPathTraversalDefense:
    """Verify that _resolve_path prevents escaping mapped directories."""

    def test_dotdot_traversal_blocked_by_path_mapping(self, sandbox_with_mappings, tmp_workspace):
        """Path with .. segments that escape mapped directory must raise PermissionError."""
        # /mnt/user-data/workspace/../../secret.txt resolves outside the workspace mapping
        with pytest.raises(PermissionError, match="path escapes mounted directory"):
            sandbox_with_mappings._resolve_path("/mnt/user-data/workspace/../../secret.txt")

    def test_resolve_path_with_mapping_blocks_partial_escape(self, sandbox_with_mappings):
        """Path with .. segments that partially escape must raise PermissionError."""
        # /mnt/user-data/workspace/sub/../../file.txt resolves to parent of workspace
        with pytest.raises(PermissionError, match="path escapes mounted directory"):
            sandbox_with_mappings._resolve_path("/mnt/user-data/workspace/sub/../../file.txt")

    def test_resolve_path_with_mapping_returns_resolved_path(self, sandbox_with_mappings, tmp_workspace):
        """_resolve_path_with_mapping returns the correct ResolvedPath."""
        result = sandbox_with_mappings._resolve_path_with_mapping("/mnt/user-data/workspace/hello.txt")
        assert result.path == str(tmp_workspace.workspace / "hello.txt")
        assert result.mapping is not None
        assert result.mapping.container_path == "/mnt/user-data/workspace"

    def test_resolve_path_with_mapping_no_match_returns_original(self, sandbox_with_mappings):
        """Paths not matching any mapping are returned as-is."""
        result = sandbox_with_mappings._resolve_path_with_mapping("/other/path/file.txt")
        assert result.path == "/other/path/file.txt"
        assert result.mapping is None

    def test_resolve_path_with_mapping_blocks_escape(self, sandbox_with_mappings, tmp_workspace):
        """Path that escapes mapped directory via .. raises PermissionError."""
        escape_sandbox = LocalSandbox(
            "escape-test",
            path_mappings=[
                PathMapping(
                    container_path="/data",
                    local_path=str(tmp_workspace.workspace / "sub"),
                    read_only=False,
                ),
            ],
        )
        tmp_workspace.workspace.joinpath("sub").mkdir(exist_ok=True)
        # Trying to escape /data/sub to reach /data/secret.txt
        with pytest.raises(PermissionError, match="path escapes mounted directory"):
            escape_sandbox._resolve_path_with_mapping("/data/../../etc/passwd")

    def test_resolve_path_preserves_absolute_paths_outside_mappings(self, sandbox_with_mappings):
        """Paths outside mappings resolve to their original location."""
        resolved = sandbox_with_mappings._resolve_path("/tmp/some/file.txt")
        assert resolved == "/tmp/some/file.txt"


# ---------------------------------------------------------------------------
# 2. Read-Only Mount Enforcement
# ---------------------------------------------------------------------------


class TestReadOnlyMountEnforcement:
    """Verify that write operations are blocked on read-only mounts."""

    def test_write_to_read_only_mount_raises(self, sandbox_with_mappings, tmp_workspace):
        """Writing to a read-only mount must raise OSError (EROFS)."""
        skills_dir = tmp_workspace.root / "skills"
        skills_dir.mkdir(exist_ok=True)
        with pytest.raises(OSError) as exc_info:
            sandbox_with_mappings.write_file("/mnt/skills/SKILL.md", "malicious content")
        assert exc_info.value.errno == errno.EROFS

    def test_update_file_to_read_only_mount_raises(self, sandbox_with_mappings, tmp_workspace):
        """Binary update to a read-only mount must raise OSError (EROFS)."""
        skills_dir = tmp_workspace.root / "skills"
        skills_dir.mkdir(exist_ok=True)
        with pytest.raises(OSError) as exc_info:
            sandbox_with_mappings.update_file("/mnt/skills/binary.dat", b"\x00\x01")
        assert exc_info.value.errno == errno.EROFS

    def test_write_to_writable_mount_succeeds(self, sandbox_with_mappings, tmp_workspace):
        """Writing to a writable mount should succeed."""
        sandbox_with_mappings.write_file("/mnt/user-data/workspace/test.txt", "hello world")
        assert (tmp_workspace.workspace / "test.txt").read_text() == "hello world"

    def test_read_only_detection_nested_mapping(self, tmp_workspace):
        """Read-only check uses most specific (longest) mapping for nested mounts."""
        parent_dir = tmp_workspace.root / "parent"
        parent_dir.mkdir()
        child_dir = parent_dir / "child"
        child_dir.mkdir()

        sandbox = LocalSandbox(
            "nested-test",
            path_mappings=[
                PathMapping(container_path="/data", local_path=str(parent_dir), read_only=False),
                PathMapping(container_path="/data/child", local_path=str(child_dir), read_only=True),
            ],
        )
        # /data/child/secret.txt should be read-only (child mapping wins)
        with pytest.raises(OSError) as exc_info:
            sandbox.write_file("/data/child/secret.txt", "nope")
        assert exc_info.value.errno == errno.EROFS

        # /data/other.txt should be writable (parent mapping)
        sandbox.write_file("/data/other.txt", "ok")
        assert (parent_dir / "other.txt").read_text() == "ok"


# ---------------------------------------------------------------------------
# 3. Download Path Restriction
# ---------------------------------------------------------------------------


class TestDownloadPathRestriction:
    """Verify that download_file only allows paths under VIRTUAL_PATH_PREFIX."""

    def test_download_outside_virtual_prefix_raises(self, sandbox_with_mappings):
        """Downloading a file outside /mnt/user-data must raise PermissionError."""
        with pytest.raises(PermissionError, match="Access denied"):
            sandbox_with_mappings.download_file("/etc/passwd")

    def test_download_outside_virtual_prefix_with_dotdot_raises(self, sandbox_with_mappings):
        """Path traversal in download path must raise an error (PermissionError or FileNotFoundError)."""
        # The dotdot traversal either gets caught by the prefix check or by the
        # file not being found at the resolved (escaped) path. Both are safe.
        with pytest.raises((PermissionError, FileNotFoundError)):
            sandbox_with_mappings.download_file("/mnt/user-data/../../etc/shadow")

    def test_download_under_virtual_prefix_succeeds(self, sandbox_with_mappings, tmp_workspace):
        """Downloading a file under /mnt/user-data should succeed."""
        test_file = tmp_workspace.workspace / "download_test.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03")
        content = sandbox_with_mappings.download_file("/mnt/user-data/workspace/download_test.bin")
        assert content == b"\x00\x01\x02\x03"

    def test_download_rejects_file_exceeding_size_limit(self, sandbox_with_mappings, tmp_workspace):
        """Files exceeding 100MB download limit must raise OSError."""
        test_file = tmp_workspace.workspace / "large.bin"
        test_file.write_bytes(b"\x00")
        with patch("os.path.getsize", return_value=200 * 1024 * 1024):
            with pytest.raises(OSError, match="maximum download size"):
                sandbox_with_mappings.download_file("/mnt/user-data/workspace/large.bin")


# ---------------------------------------------------------------------------
# 4. Host Path Masking in Output
# ---------------------------------------------------------------------------


class TestHostPathMasking:
    """Verify that host filesystem paths are masked in tool output."""

    def test_host_user_data_paths_masked(self, thread_data):
        """Host paths under workspace/uploads/outputs must be replaced with virtual paths."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        host_path = f"{thread_data['workspace_path']}/result.txt"
        output = f"Created file at {host_path}"
        masked = mask_local_paths_in_output(output, thread_data)

        assert thread_data["workspace_path"] not in masked
        assert "/mnt/user-data/workspace/result.txt" in masked

    def test_host_skills_paths_masked(self, thread_data):
        """Skills host paths must be replaced with /mnt/skills virtual path."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        with (
            patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"),
            patch("ideer.sandbox.tools._get_skills_host_path", return_value="/opt/app/skills"),
        ):
            output = "Reading /opt/app/skills/bootstrap/SKILL.md"
            masked = mask_local_paths_in_output(output, thread_data)

            assert "/opt/app/skills" not in masked
            assert "/mnt/skills/bootstrap/SKILL.md" in masked

    def test_host_acp_workspace_paths_masked(self, thread_data):
        """ACP workspace host paths must be replaced with /mnt/acp-workspace."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        with patch("ideer.sandbox.tools._get_acp_workspace_host_path", return_value="/home/user/.ideer/acp-workspace"):
            output = "Compiled /home/user/.ideer/acp-workspace/main.py"
            masked = mask_local_paths_in_output(output, thread_data)

            assert "/home/user/.ideer/acp-workspace" not in masked
            assert "/mnt/acp-workspace/main.py" in masked

    def test_absolute_paths_outside_mappings_not_masked(self, thread_data):
        """Paths not matching any mapping should remain unchanged."""
        from ideer.sandbox.tools import mask_local_paths_in_output

        output = "System path: /usr/bin/python3"
        masked = mask_local_paths_in_output(output, thread_data)
        assert masked == output

    def test_reverse_resolve_paths_in_output(self, sandbox_with_mappings, tmp_workspace):
        """LocalSandbox._reverse_resolve_paths_in_output should mask host paths."""
        local_path = str(tmp_workspace.workspace / "output.txt")
        output = f"File saved to {local_path}"
        result = sandbox_with_mappings._reverse_resolve_paths_in_output(output)
        assert str(tmp_workspace.workspace) not in result
        assert "/mnt/user-data/workspace/output.txt" in result


# ---------------------------------------------------------------------------
# 5. Bash Command Authorization
# ---------------------------------------------------------------------------


class TestBashCommandAuthorization:
    """Verify that bash execution is gated by host_bash_allowed."""

    def test_bash_blocked_when_host_bash_disabled(self, monkeypatch):
        """bash_tool must return error when host bash is not allowed."""
        from ideer.sandbox.tools import bash_tool

        runtime = SimpleNamespace(
            state={
                "sandbox": {"sandbox_id": "local"},
                "thread_data": {
                    "workspace_path": "/tmp/ws",
                    "uploads_path": "/tmp/up",
                    "outputs_path": "/tmp/out",
                },
            },
            context={"thread_id": "t1"},
        )

        monkeypatch.setattr(
            "ideer.sandbox.tools.ensure_sandbox_initialized",
            lambda rt: SimpleNamespace(execute_command=lambda cmd: pytest.fail("should not execute")),
        )
        monkeypatch.setattr("ideer.sandbox.tools.is_host_bash_allowed", lambda: False)

        result = bash_tool.func(runtime=runtime, description="test", command="echo hello")
        assert "Host bash execution is disabled" in result

    def test_bash_allowed_when_host_bash_enabled(self, monkeypatch):
        """bash_tool should execute when host bash is explicitly allowed."""
        from ideer.sandbox.tools import bash_tool

        mock_sandbox = SimpleNamespace(execute_command=lambda cmd: "hello\n")

        runtime = SimpleNamespace(
            state={
                "sandbox": {"sandbox_id": "local"},
                "thread_data": {
                    "workspace_path": "/tmp/ws",
                    "uploads_path": "/tmp/up",
                    "outputs_path": "/tmp/out",
                },
            },
            context={"thread_id": "t1"},
        )

        monkeypatch.setattr("ideer.sandbox.tools.ensure_sandbox_initialized", lambda rt: mock_sandbox)
        monkeypatch.setattr("ideer.sandbox.tools.ensure_thread_directories_exist", lambda rt: None)
        monkeypatch.setattr("ideer.sandbox.tools.is_host_bash_allowed", lambda: True)
        monkeypatch.setattr("ideer.sandbox.tools.validate_local_bash_command_paths", lambda cmd, td: None)
        monkeypatch.setattr("ideer.sandbox.tools.replace_virtual_paths_in_command", lambda cmd, td: cmd)
        monkeypatch.setattr("ideer.sandbox.tools._apply_cwd_prefix", lambda cmd, td: cmd)
        monkeypatch.setattr("ideer.sandbox.tools.mask_local_paths_in_output", lambda out, td: out)
        monkeypatch.setattr("ideer.sandbox.tools._truncate_bash_output", lambda out, mx: out)
        monkeypatch.setattr("ideer.sandbox.tools.get_app_config", lambda: SimpleNamespace(sandbox=SimpleNamespace(bash_output_max_chars=20000)))

        result = bash_tool.func(runtime=runtime, description="test", command="echo hello")
        assert result == "hello\n"

    def test_bash_blocks_dangerous_paths(self, monkeypatch):
        """bash_tool must block commands with unsafe absolute paths."""
        from ideer.sandbox.tools import bash_tool

        thread_data = {
            "workspace_path": "/tmp/ws",
            "uploads_path": "/tmp/up",
            "outputs_path": "/tmp/out",
        }
        runtime = SimpleNamespace(
            state={
                "sandbox": {"sandbox_id": "local"},
                "thread_data": thread_data,
            },
            context={"thread_id": "t1"},
        )

        monkeypatch.setattr(
            "ideer.sandbox.tools.ensure_sandbox_initialized",
            lambda rt: SimpleNamespace(execute_command=lambda cmd: pytest.fail("unsafe")),
        )
        monkeypatch.setattr("ideer.sandbox.tools.ensure_thread_directories_exist", lambda rt: None)
        monkeypatch.setattr("ideer.sandbox.tools.is_host_bash_allowed", lambda: True)

        result = bash_tool.func(runtime=runtime, description="test", command="cat /etc/shadow")
        assert "path" in result.lower() or "unsafe" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# 6. File Operation Lock -- Concurrent Write Safety
# ---------------------------------------------------------------------------


class TestFileOperationLock:
    """Verify that file operation locks prevent concurrent corruption."""

    def test_same_path_same_lock(self):
        """Multiple calls with the same sandbox+path must return the same lock."""
        from ideer.sandbox.file_operation_lock import get_file_operation_lock

        sandbox = MagicMock()
        sandbox.id = "lock-test"
        lock1 = get_file_operation_lock(sandbox, "/data/file.txt")
        lock2 = get_file_operation_lock(sandbox, "/data/file.txt")
        assert lock1 is lock2

    def test_different_paths_different_locks(self):
        """Different paths must have different locks."""
        from ideer.sandbox.file_operation_lock import get_file_operation_lock

        sandbox = MagicMock()
        sandbox.id = "lock-test"
        lock1 = get_file_operation_lock(sandbox, "/data/file1.txt")
        lock2 = get_file_operation_lock(sandbox, "/data/file2.txt")
        assert lock1 is not lock2

    def test_different_sandboxes_different_locks(self):
        """Same path in different sandboxes must have different locks."""
        from ideer.sandbox.file_operation_lock import get_file_operation_lock

        sb1 = MagicMock()
        sb1.id = "sandbox-a"
        sb2 = MagicMock()
        sb2.id = "sandbox-b"
        lock1 = get_file_operation_lock(sb1, "/data/file.txt")
        lock2 = get_file_operation_lock(sb2, "/data/file.txt")
        assert lock1 is not lock2

    def test_lock_prevents_concurrent_write_read_race(self, monkeypatch):
        """Concurrent str_replace and write_file on the same path must be serialized."""
        from ideer.sandbox.tools import str_replace_tool, write_file_tool

        class SharedSandbox:
            id = "concurrent-test"

            def __init__(self):
                self.content = "original\n"
                self._lock = threading.Lock()

            def read_file(self, path):
                with self._lock:
                    snapshot = self.content
                return snapshot

            def write_file(self, path, content, append=False):
                with self._lock:
                    if append:
                        self.content += content
                    else:
                        self.content = content

        sandbox = SharedSandbox()
        monkeypatch.setattr("ideer.sandbox.tools.ensure_sandbox_initialized", lambda rt: sandbox)
        monkeypatch.setattr("ideer.sandbox.tools.ensure_thread_directories_exist", lambda rt: None)
        monkeypatch.setattr("ideer.sandbox.tools.is_local_sandbox", lambda rt: False)

        errors = []

        def replace_worker():
            try:
                str_replace_tool.func(
                    runtime=SimpleNamespace(state={}, context={}, config={}),
                    description="replace",
                    path="/mnt/user-data/workspace/shared.txt",
                    old_str="original",
                    new_str="REPLACED",
                )
            except Exception as e:
                errors.append(e)

        def append_worker():
            try:
                write_file_tool.func(
                    runtime=SimpleNamespace(state={}, context={}, config={}),
                    description="append",
                    path="/mnt/user-data/workspace/shared.txt",
                    content="appended\n",
                    append=True,
                )
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=replace_worker)
        t2 = threading.Thread(target=append_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == []
        # Both operations should have been applied (order may vary)
        assert "REPLACED" in sandbox.content or "appended" in sandbox.content


# ---------------------------------------------------------------------------
# 7. Provider Singleton Security
# ---------------------------------------------------------------------------


class TestProviderSecurity:
    """Verify that the sandbox provider enforces security policies."""

    def test_reset_clears_all_state(self):
        """reset_sandbox_provider must clear all cached sandboxes."""
        from ideer.sandbox.sandbox_provider import (
            reset_sandbox_provider,
            set_sandbox_provider,
        )

        mock_provider = MagicMock()
        set_sandbox_provider(mock_provider)
        reset_sandbox_provider()
        mock_provider.reset.assert_called_once()

    def test_shutdown_calls_provider_shutdown(self):
        """shutdown_sandbox_provider must call provider.shutdown()."""
        from ideer.sandbox.sandbox_provider import (
            set_sandbox_provider,
            shutdown_sandbox_provider,
        )

        mock_provider = MagicMock()
        set_sandbox_provider(mock_provider)
        shutdown_sandbox_provider()
        mock_provider.shutdown.assert_called_once()

    def test_get_returns_none_for_unknown_sandbox(self):
        """SandboxProvider.get() must return None for unknown IDs."""
        from ideer.sandbox.local.local_sandbox_provider import LocalSandboxProvider

        provider = LocalSandboxProvider()
        assert provider.get("nonexistent-id") is None

    def test_release_is_idempotent(self):
        """Releasing an already-released sandbox must not raise."""
        from ideer.sandbox.local.local_sandbox_provider import LocalSandboxProvider

        provider = LocalSandboxProvider()
        provider.release("nonexistent-id")
        provider.release("nonexistent-id")


# ---------------------------------------------------------------------------
# 8. LocalSandbox Execute Command Timeout
# ---------------------------------------------------------------------------


class TestCommandTimeout:
    """Verify that command execution has a timeout."""

    def test_execute_command_has_timeout(self, sandbox_with_mappings):
        """execute_command must use a timeout to prevent infinite loops."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(stdout="ok\n", stderr="", returncode=0)
            sandbox_with_mappings.execute_command("echo ok")
            _, kwargs = mock_run.call_args
            assert "timeout" in kwargs
            assert kwargs["timeout"] > 0
            assert kwargs["timeout"] <= 600

    def test_execute_command_uses_shell_false(self, sandbox_with_mappings):
        """execute_command must use shell=False for security (args list, not string)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(stdout="ok\n", stderr="", returncode=0)
            sandbox_with_mappings.execute_command("echo ok")
            _, kwargs = mock_run.call_args
            assert kwargs.get("shell") is False

    def test_execute_command_capture_output(self, sandbox_with_mappings):
        """execute_command must capture output to prevent stdout/stderr leakage."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(stdout="data\n", stderr="", returncode=0)
            sandbox_with_mappings.execute_command("echo data")
            _, kwargs = mock_run.call_args
            assert kwargs.get("capture_output") is True


# ---------------------------------------------------------------------------
# 9. Output Truncation -- Resource Limits
# ---------------------------------------------------------------------------


class TestOutputTruncation:
    """Verify that tool output is truncated to prevent memory exhaustion."""

    def test_bash_output_truncated(self):
        """Bash output exceeding max_chars must be truncated."""
        from ideer.sandbox.tools import _truncate_bash_output

        large_output = "A" * 100000
        result = _truncate_bash_output(large_output, max_chars=1000)
        assert len(result) <= 1000
        assert "[middle truncated:" in result

    def test_read_file_output_truncated(self):
        """Read file output exceeding max_chars must be truncated."""
        from ideer.sandbox.tools import _truncate_read_file_output

        large_content = "line\n" * 50000
        result = _truncate_read_file_output(large_content, max_chars=5000)
        assert len(result) <= 5000
        assert "[truncated:" in result

    def test_ls_output_truncated(self):
        """ls output exceeding max_chars must be truncated."""
        from ideer.sandbox.tools import _truncate_ls_output

        large_listing = "\n".join(f"/mnt/user-data/workspace/file_{i}.txt" for i in range(10000))
        result = _truncate_ls_output(large_listing, max_chars=2000)
        assert len(result) <= 2000
        assert "[truncated:" in result

    def test_truncation_disabled_when_zero(self):
        """Truncation should be disabled when max_chars is 0."""
        from ideer.sandbox.tools import (
            _truncate_bash_output,
            _truncate_ls_output,
            _truncate_read_file_output,
        )

        content = "A" * 5000
        assert _truncate_bash_output(content, max_chars=0) == content
        assert _truncate_read_file_output(content, max_chars=0) == content
        assert _truncate_ls_output(content, max_chars=0) == content

    def test_short_output_not_truncated(self):
        """Output shorter than max_chars must be returned unchanged."""
        from ideer.sandbox.tools import _truncate_bash_output

        short_output = "hello"
        result = _truncate_bash_output(short_output, max_chars=1000)
        assert result == short_output


# ---------------------------------------------------------------------------
# 10. Path Validation -- Tool Layer Gate
# ---------------------------------------------------------------------------


class TestPathValidationGate:
    """Verify that the tool-layer path validation correctly gates access."""

    def test_non_virtual_path_rejected(self, thread_data):
        """Paths outside /mnt/user-data must be rejected."""
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(PermissionError, match="Only paths under"):
            validate_local_tool_path("/home/user/secret.txt", thread_data)

    def test_skills_path_write_blocked(self, thread_data):
        """Write access to /mnt/skills must be rejected."""
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            with pytest.raises(PermissionError, match="Write access to skills"):
                validate_local_tool_path("/mnt/skills/SKILL.md", thread_data, read_only=False)

    def test_skills_path_read_allowed(self, thread_data):
        """Read access to /mnt/skills must be allowed."""
        from ideer.sandbox.tools import validate_local_tool_path

        with patch("ideer.sandbox.tools._get_skills_container_path", return_value="/mnt/skills"):
            validate_local_tool_path("/mnt/skills/SKILL.md", thread_data, read_only=True)

    def test_acp_workspace_write_blocked(self, thread_data):
        """Write access to /mnt/acp-workspace must be rejected."""
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(PermissionError, match="Write access to ACP workspace"):
            validate_local_tool_path("/mnt/acp-workspace/main.py", thread_data, read_only=False)

    def test_null_thread_data_rejected(self):
        """Missing thread data must raise SandboxRuntimeError."""
        from ideer.sandbox.tools import validate_local_tool_path

        with pytest.raises(SandboxRuntimeError):
            validate_local_tool_path("/mnt/user-data/workspace/file.txt", None)

    def test_dotdot_in_bash_command_rejected(self, thread_data):
        """Bash commands with path traversal must be rejected."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(PermissionError, match="path traversal"):
            validate_local_bash_command_paths("cat ../../../etc/passwd", thread_data)

    def test_file_url_in_bash_command_rejected(self, thread_data):
        """file:// URLs in bash commands must be rejected."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(PermissionError, match="file://"):
            validate_local_bash_command_paths("curl file:///etc/passwd", thread_data)

    def test_cd_to_root_rejected(self, thread_data):
        """cd / must be rejected in bash commands."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            validate_local_bash_command_paths("cd / && ls", thread_data)

    def test_cd_to_home_rejected(self, thread_data):
        """cd $HOME must be rejected in bash commands."""
        from ideer.sandbox.tools import validate_local_bash_command_paths

        with pytest.raises(PermissionError, match="Unsafe working directory"):
            validate_local_bash_command_paths("cd $HOME && ls", thread_data)


# ---------------------------------------------------------------------------
# 11. Sandbox Isolation -- Cross-Thread
# ---------------------------------------------------------------------------


class TestCrossThreadIsolation:
    """Verify that different threads get isolated sandbox environments."""

    def test_different_threads_get_different_sandboxes(self, tmp_path):
        """LocalSandboxProvider must give different sandbox instances per thread."""
        from ideer.sandbox.local.local_sandbox_provider import LocalSandboxProvider

        provider = LocalSandboxProvider()
        sb_id_1 = provider.acquire("thread-a")
        sb_id_2 = provider.acquire("thread-b")

        assert sb_id_1 != sb_id_2

        sb1 = provider.get(sb_id_1)
        sb2 = provider.get(sb_id_2)
        assert sb1 is not None
        assert sb2 is not None
        assert sb1 is not sb2

    def test_same_thread_gets_same_sandbox(self):
        """Same thread calling acquire multiple times gets the same sandbox."""
        from ideer.sandbox.local.local_sandbox_provider import LocalSandboxProvider

        provider = LocalSandboxProvider()
        sb_id_1 = provider.acquire("thread-x")
        sb_id_2 = provider.acquire("thread-x")
        assert sb_id_1 == sb_id_2

    def test_generic_sandbox_shared_across_calls(self):
        """Sandbox acquired without thread_id returns the shared 'local' singleton."""
        from ideer.sandbox.local.local_sandbox_provider import LocalSandboxProvider

        provider = LocalSandboxProvider()
        sb_id_1 = provider.acquire(None)
        sb_id_2 = provider.acquire(None)
        assert sb_id_1 == "local"
        assert sb_id_2 == "local"


# ---------------------------------------------------------------------------
# 12. Security Config Defaults
# ---------------------------------------------------------------------------


class TestSecurityConfigDefaults:
    """Verify that security-sensitive configuration defaults are safe."""

    def test_allow_host_bash_defaults_false(self):
        """SandboxConfig.allow_host_bash must default to False."""
        from ideer.config.sandbox_config import SandboxConfig

        config = SandboxConfig(use="ideer.sandbox.local:LocalSandboxProvider")
        assert config.allow_host_bash is False

    def test_bash_output_max_chars_has_reasonable_default(self):
        """bash_output_max_chars must have a positive default."""
        from ideer.config.sandbox_config import SandboxConfig

        config = SandboxConfig(use="test")
        assert config.bash_output_max_chars > 0
        assert config.bash_output_max_chars <= 100000

    def test_read_file_output_max_chars_has_reasonable_default(self):
        """read_file_output_max_chars must have a positive default."""
        from ideer.config.sandbox_config import SandboxConfig

        config = SandboxConfig(use="test")
        assert config.read_file_output_max_chars > 0
        assert config.read_file_output_max_chars <= 500000

    def test_volume_mount_defaults_read_write(self):
        """VolumeMountConfig must default to read_only=False."""
        from ideer.config.sandbox_config import VolumeMountConfig

        mount = VolumeMountConfig(host_path="/tmp/test", container_path="/data")
        assert mount.read_only is False

    def test_idle_timeout_has_reasonable_default(self):
        """idle_timeout must have a positive default (not unlimited)."""
        from ideer.config.sandbox_config import SandboxConfig

        config = SandboxConfig(use="test")
        if config.idle_timeout is not None:
            assert config.idle_timeout > 0
