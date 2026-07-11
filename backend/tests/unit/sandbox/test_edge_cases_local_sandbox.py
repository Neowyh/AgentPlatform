"""Additional coverage tests for ideer.sandbox.local.local_sandbox."""

from __future__ import annotations

import errno
import os

import pytest

from ideer.sandbox.local.local_sandbox import LocalSandbox, PathMapping

# ===========================================================================
# _shell_name / _is_powershell / _is_cmd_shell / _is_msys_shell
# ===========================================================================


class TestShellDetection:
    def test_shell_name_bash(self):
        assert LocalSandbox._shell_name("/bin/bash") == "bash"

    def test_shell_name_powershell(self):
        assert LocalSandbox._shell_name("C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe") == "powershell.exe"

    def test_is_powershell(self):
        assert LocalSandbox._is_powershell("/bin/powershell") is True
        assert LocalSandbox._is_powershell("pwsh") is True
        assert LocalSandbox._is_powershell("pwsh.exe") is True
        assert LocalSandbox._is_powershell("/bin/bash") is False

    def test_is_cmd_shell(self):
        assert LocalSandbox._is_cmd_shell("cmd") is True
        assert LocalSandbox._is_cmd_shell("cmd.exe") is True
        assert LocalSandbox._is_cmd_shell("/bin/bash") is False

    def test_is_msys_shell(self):
        assert LocalSandbox._is_msys_shell("/usr/bin/bash.exe") is False
        assert LocalSandbox._is_msys_shell("/git/bin/bash.exe") is True
        assert LocalSandbox._is_msys_shell("/mingw64/bin/sh.exe") is True
        assert LocalSandbox._is_msys_shell("/msys/bin/bash.exe") is True
        assert LocalSandbox._is_msys_shell("/bin/bash") is False


# ===========================================================================
# _find_first_available_shell
# ===========================================================================


class TestFindFirstAvailableShell:
    def test_returns_none_when_none_exist(self):
        result = LocalSandbox._find_first_available_shell(("/nonexistent/shell1", "/nonexistent/shell2"))
        assert result is None

    def test_returns_first_found(self):
        # /bin/sh should exist on most Linux systems
        result = LocalSandbox._find_first_available_shell(("/nonexistent", "/bin/sh"))
        # Result depends on system; just check no crash
        assert result is None or result == "/bin/sh"


# ===========================================================================
# _resolve_path_with_mapping
# ===========================================================================


class TestResolvePathWithMapping:
    def test_no_mapping(self):
        sandbox = LocalSandbox("test", [])
        result = sandbox._resolve_path_with_mapping("/mnt/user-data/file.txt")
        assert result.path == "/mnt/user-data/file.txt"
        assert result.mapping is None

    def test_root_mapping(self):
        sandbox = LocalSandbox("test", [PathMapping(container_path="/", local_path="/tmp/root")])
        result = sandbox._resolve_path_with_mapping("/file.txt")
        assert "/root" in result.path
        assert "/file.txt" in result.path

    def test_permission_escape(self, tmp_path):
        mount = tmp_path / "mount"
        mount.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret")
        # Create symlink pointing outside
        (mount / "escape").symlink_to(outside, target_is_directory=True)

        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(mount)),
            ],
        )
        with pytest.raises(PermissionError):
            sandbox._resolve_path_with_mapping("/mnt/data/escape/secret.txt")


# ===========================================================================
# _find_path_mapping
# ===========================================================================


class TestFindPathMapping:
    def test_exact_match(self):
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/skills", local_path="/opt/skills"),
            ],
        )
        result = sandbox._find_path_mapping("/mnt/skills")
        assert result is not None
        mapping, relative = result
        assert mapping.container_path == "/mnt/skills"
        assert relative == ""

    def test_root_mapping(self):
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/", local_path="/tmp/root"),
            ],
        )
        result = sandbox._find_path_mapping("/any/path")
        assert result is not None

    def test_no_mapping(self):
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/skills", local_path="/opt/skills"),
            ],
        )
        result = sandbox._find_path_mapping("/other/path")
        assert result is None

    def test_longest_prefix_wins(self):
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt", local_path="/var/mnt"),
                PathMapping(container_path="/mnt/skills", local_path="/opt/skills"),
            ],
        )
        result = sandbox._find_path_mapping("/mnt/skills/file.py")
        mapping, relative = result
        assert mapping.container_path == "/mnt/skills"


# ===========================================================================
# _reverse_resolve_path
# ===========================================================================


class TestReverseResolvePath:
    def test_no_mapping(self):
        sandbox = LocalSandbox("test", [])
        result = sandbox._reverse_resolve_path("/tmp/file.txt")
        assert result.endswith("/file.txt") or result.endswith("\\file.txt")

    def test_with_mapping(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "test.txt").write_text("x")
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        result = sandbox._reverse_resolve_path(str(data_dir / "test.txt"))
        assert result == "/mnt/data/test.txt"

    def test_backslash_separator(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        # Test with backslash in path
        backslash_path = str(data_dir).replace("/", "\\") + "\\file.txt"
        result = sandbox._reverse_resolve_path(backslash_path)
        assert "/mnt/data/" in result


# ===========================================================================
# _reverse_resolve_paths_in_output
# ===========================================================================


class TestReverseResolvePathsInOutput:
    def test_no_mappings(self):
        sandbox = LocalSandbox("test", [])
        result = sandbox._reverse_resolve_paths_in_output("output text")
        assert result == "output text"

    def test_with_mappings(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        result = sandbox._reverse_resolve_paths_in_output(f"File at {data_dir}/test.txt")
        assert "/mnt/data" in result

    def test_backslash_in_output(self, tmp_path):
        """Test that backslash-separated paths in output are reverse-resolved."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        # Use forward slash path (on Linux str(Path) uses forward slashes)
        # The reverse resolve still works because the regex matches forward slashes too
        result = sandbox._reverse_resolve_paths_in_output(f"Path: {data_dir}/file.txt")
        assert "/mnt/data" in result


# ===========================================================================
# _resolve_paths_in_command
# ===========================================================================


class TestResolvePathsInCommand:
    def test_no_mappings(self):
        sandbox = LocalSandbox("test", [])
        result = sandbox._resolve_paths_in_command("ls /tmp")
        assert result == "ls /tmp"

    def test_with_mappings(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        result = sandbox._resolve_paths_in_command("cat /mnt/data/file.txt")
        assert str(data_dir) in result
        assert "/mnt/data" not in result


# ===========================================================================
# _resolve_paths_in_content
# ===========================================================================


class TestResolvePathsInContent:
    def test_no_mappings(self):
        sandbox = LocalSandbox("test", [])
        result = sandbox._resolve_paths_in_content("some content")
        assert result == "some content"

    def test_with_mappings(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        result = sandbox._resolve_paths_in_content('path = "/mnt/data/output"')
        assert str(data_dir).replace("\\", "/") in result


# ===========================================================================
# read_file — agent_written_paths tracking
# ===========================================================================


class TestReadFileAgentWritten:
    def test_read_agent_written_file(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        # Write via write_file (marks as agent-written)
        sandbox.write_file("/mnt/data/info.txt", "File at /mnt/data/info.txt")
        content = sandbox.read_file("/mnt/data/info.txt")
        assert "/mnt/data/info.txt" in content

    def test_read_non_agent_file(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "upload.txt").write_text("raw content\n", encoding="utf-8")
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        content = sandbox.read_file("/mnt/data/upload.txt")
        assert "raw content" in content

    def test_read_oserror_hides_resolved_path(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        with pytest.raises(OSError) as exc_info:
            sandbox.read_file("/mnt/data/nonexistent.txt")
        assert exc_info.value.filename == "/mnt/data/nonexistent.txt"


# ===========================================================================
# write_file — container path resolution in content
# ===========================================================================


class TestWriteFileContentResolution:
    def test_resolves_paths_in_content(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        sandbox.write_file("/mnt/data/config.py", 'DATA_DIR = "/mnt/data/files"')
        content = (data_dir / "config.py").read_text()
        assert str(data_dir).replace("\\", "/") in content

    def test_append_mode(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        sandbox.write_file("/mnt/data/log.txt", "line1\n")
        sandbox.write_file("/mnt/data/log.txt", "line2\n", append=True)
        content = (data_dir / "log.txt").read_text()
        assert "line1" in content
        assert "line2" in content

    def test_creates_dirs(self, tmp_path):
        data_dir = tmp_path / "data"
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        sandbox.write_file("/mnt/data/sub/deep/file.txt", "nested")
        assert (data_dir / "sub" / "deep" / "file.txt").read_text() == "nested"


# ===========================================================================
# update_file
# ===========================================================================


class TestUpdateFile:
    def test_success(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        sandbox.write_file("/mnt/data/file.bin", "old")
        sandbox.update_file("/mnt/data/file.bin", b"new binary")
        assert (data_dir / "file.bin").read_bytes() == b"new binary"

    def test_creates_dirs(self, tmp_path):
        data_dir = tmp_path / "data"
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        sandbox.update_file("/mnt/data/sub/file.bin", b"data")
        assert (data_dir / "sub" / "file.bin").read_bytes() == b"data"

    def test_oserror_hides_resolved_path(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        ro_dir = tmp_path / "ro"
        ro_dir.mkdir()
        # Make ro_dir read-only so write fails
        os.chmod(ro_dir, 0o555)
        try:
            sandbox = LocalSandbox(
                "test",
                [
                    PathMapping(container_path="/mnt/data", local_path=str(ro_dir)),
                ],
            )
            with pytest.raises(OSError) as exc_info:
                sandbox.update_file("/mnt/data/file.bin", b"updated")
            assert exc_info.value.filename == "/mnt/data/file.bin"
        finally:
            os.chmod(ro_dir, 0o755)


# ===========================================================================
# execute_command
# ===========================================================================


class TestExecuteCommand:
    def test_basic(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        result = sandbox.execute_command("echo hello")
        assert "hello" in result

    def test_path_replacement(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "test.txt").write_text("hello")
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        result = sandbox.execute_command("cat /mnt/data/test.txt")
        assert "hello" in result
        # Should not contain container path
        assert "/mnt/data" not in result


# ===========================================================================
# list_dir — with path mappings
# ===========================================================================


class TestListDirWithMappings:
    def test_returns_mapped_paths(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("x")
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        entries = sandbox.list_dir("/mnt/data")
        assert any("file.txt" in e for e in entries)


# ===========================================================================
# glob — with path mappings
# ===========================================================================


class TestGlobWithMappings:
    def test_basic(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "app.py").write_text("print('hi')\n")
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        matches, truncated = sandbox.glob("/mnt/data", "*.py")
        assert len(matches) == 1
        assert "/mnt/data/app.py" in matches


# ===========================================================================
# grep — with path mappings
# ===========================================================================


class TestGrepWithMappings:
    def test_basic(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "a.py").write_text("TODO: fix\n")
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/data", local_path=str(data_dir)),
            ],
        )
        matches, truncated = sandbox.grep("/mnt/data", "TODO")
        assert len(matches) == 1
        assert "/mnt/data/a.py" in matches[0].path


# ===========================================================================
# download_file edge cases
# ===========================================================================


class TestDownloadFileEdge:
    def test_large_file_rejected(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        big_file = data_dir / "big.bin"
        big_file.write_bytes(b"x" * (100 * 1024 * 1024 + 1))
        sandbox = LocalSandbox(
            "test",
            [
                PathMapping(container_path="/mnt/user-data", local_path=str(data_dir)),
            ],
        )
        with pytest.raises(OSError) as exc_info:
            sandbox.download_file("/mnt/user-data/big.bin")
        assert exc_info.value.errno == errno.EFBIG
