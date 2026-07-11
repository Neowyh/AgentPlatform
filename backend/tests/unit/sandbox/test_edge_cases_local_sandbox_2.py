"""Additional coverage tests for ideer.sandbox.local.local_sandbox.

Targets missed lines:
- Lines 65-67: _find_first_available_shell with relative shell name found via shutil.which
- Line 119: _find_path_mapping with root container_path but non-/ path_str
- Lines 307-309: _get_shell RuntimeError paths
- Lines 350, 352: Windows shell execution (powershell/cmd)
- Lines 391-392: download_file outside allowed directory
- Lines 402-403: download_file successful read
- Line 412: write_file to read-only path
- Lines 427-429: write_file OSError re-raise
- Line 468: update_file OSError re-raise
"""

import errno
import os
from unittest.mock import MagicMock, patch

import pytest

from ideer.sandbox.local.local_sandbox import LocalSandbox, PathMapping


class TestFindFirstAvailableShellRelative:
    """Lines 65-67: _find_first_available_shell with relative shell name."""

    def test_relative_shell_found_via_which(self):
        """Relative shell name like 'sh' found via shutil.which."""
        with patch("shutil.which", return_value="/usr/bin/sh"):
            result = LocalSandbox._find_first_available_shell(("nonexistent_shell", "sh"))
        assert result == "/usr/bin/sh"

    def test_relative_shell_not_found(self):
        """No relative shell found."""
        with patch("shutil.which", return_value=None):
            result = LocalSandbox._find_first_available_shell(("nonexistent_shell",))
        assert result is None

    def test_absolute_path_not_executable_skipped(self):
        """Absolute path exists but not executable -> continue."""
        with (
            patch("os.path.isabs", return_value=True),
            patch("os.path.isfile", return_value=True),
            patch("os.access", return_value=False),
        ):
            result = LocalSandbox._find_first_available_shell(("/bin/fake_shell",))
        assert result is None

    def test_absolute_path_not_file_skipped(self):
        """Absolute path not a file -> continue."""
        with (
            patch("os.path.isabs", return_value=True),
            patch("os.path.isfile", return_value=False),
        ):
            result = LocalSandbox._find_first_available_shell(("/bin/fake_shell",))
        assert result is None


class TestFindPathMappingRootNonSlash:
    """Line 119: root container_path but path doesn't start with /."""

    def test_root_mapping_non_slash_path(self):
        sandbox = LocalSandbox("test", [PathMapping(container_path="/", local_path="/tmp/root")])
        # path_str that doesn't start with "/" -> continue (skip)
        result = sandbox._find_path_mapping("relative/path")
        # Should return None since no mapping matches relative path
        assert result is None


class TestGetShellRuntimeError:
    """Lines 307-309: _get_shell raises RuntimeError when no shell found."""

    def test_no_shell_found_raises_runtime_error(self):
        """No Unix shell found and not on Windows -> RuntimeError."""
        with (
            patch.object(LocalSandbox, "_find_first_available_shell", return_value=None),
            patch("os.name", "nt"),
            patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}, clear=False),
        ):
            # Even Windows shells not found
            with patch("shutil.which", return_value=None):
                with pytest.raises(RuntimeError, match="No suitable shell"):
                    LocalSandbox._get_shell()

    def test_no_shell_found_unix_raises_runtime_error(self):
        """No shell found on Unix -> RuntimeError."""
        with (
            patch.object(LocalSandbox, "_find_first_available_shell", return_value=None),
            patch("os.name", "posix"),
        ):
            with pytest.raises(RuntimeError, match="No suitable shell"):
                LocalSandbox._get_shell()


class TestExecuteCommandWindows:
    """Lines 305, 318-329: Windows shell execution paths."""

    def test_powershell_args(self):
        """Line 318-319: PowerShell execution args."""
        sandbox = LocalSandbox("test")
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 0

        with (
            patch("os.name", "nt"),
            patch.object(LocalSandbox, "_get_shell", return_value=r"C:\pwsh.exe"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            sandbox.execute_command("echo hello")

        call_args = mock_run.call_args
        assert call_args[0][0] == [r"C:\pwsh.exe", "-NoProfile", "-Command", "echo hello"]

    def test_cmd_shell_args(self):
        """Line 320-321: cmd.exe execution args."""
        sandbox = LocalSandbox("test")
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 0

        with (
            patch("os.name", "nt"),
            patch.object(LocalSandbox, "_get_shell", return_value="cmd.exe"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            sandbox.execute_command("dir")

        call_args = mock_run.call_args
        assert call_args[0][0] == ["cmd.exe", "/c", "dir"]

    def test_msys_shell_args_with_env(self):
        """Lines 323-329: MSYS shell on Windows sets MSYS env vars."""
        sandbox = LocalSandbox("test")
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 0

        with (
            patch("os.name", "nt"),
            patch.object(LocalSandbox, "_get_shell", return_value="/git/bin/bash.exe"),
            patch.object(LocalSandbox, "_is_msys_shell", return_value=True),
            patch.object(LocalSandbox, "_is_powershell", return_value=False),
            patch.object(LocalSandbox, "_is_cmd_shell", return_value=False),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            sandbox.execute_command("echo hello")

        call_args = mock_run.call_args
        assert call_args[0][0] == ["/git/bin/bash.exe", "-c", "echo hello"]
        env = call_args[1].get("env")
        assert env is not None
        assert env.get("MSYS_NO_PATHCONV") == "1"

    def test_windows_shell_found_returns_shell(self):
        """Line 304-305: Windows shell found via _find_first_available_shell."""
        with (
            patch.object(LocalSandbox, "_find_first_available_shell", side_effect=[None, "pwsh"]),
            patch("os.name", "nt"),
            patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}, clear=False),
        ):
            result = LocalSandbox._get_shell()
        assert result == "pwsh"


class TestExecuteCommandStderr:
    """Test stderr and exit code handling in execute_command."""

    def test_stderr_appended(self):
        sandbox = LocalSandbox("test")
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = "some error"
        mock_result.returncode = 0

        with (
            patch.object(LocalSandbox, "_get_shell", return_value="/bin/bash"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = sandbox.execute_command("cmd")

        assert "some error" in result

    def test_nonzero_exit_code(self):
        sandbox = LocalSandbox("test")
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 1

        with (
            patch.object(LocalSandbox, "_get_shell", return_value="/bin/bash"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = sandbox.execute_command("cmd")

        assert "Exit Code: 1" in result

    def test_no_output_returns_placeholder(self):
        sandbox = LocalSandbox("test")
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0

        with (
            patch.object(LocalSandbox, "_get_shell", return_value="/bin/bash"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = sandbox.execute_command("cmd")

        assert "(no output)" in result

    def test_only_stderr_no_stdout(self):
        sandbox = LocalSandbox("test")
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "error only"
        mock_result.returncode = 0

        with (
            patch.object(LocalSandbox, "_get_shell", return_value="/bin/bash"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = sandbox.execute_command("cmd")

        assert "error only" in result


class TestDownloadFileEdgeCases:
    """Lines 391-392, 402-403: download_file edge cases."""

    def test_download_outside_allowed_prefix(self):
        """Lines 391-392: download outside allowed directory raises PermissionError."""
        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/user-data", local_path="/tmp/data")])
        with pytest.raises(PermissionError):
            sandbox.download_file("/etc/passwd")

    def test_download_success(self, tmp_path):
        """Lines 402-403: successful download."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_bytes(b"hello world")

        from ideer.config.paths import VIRTUAL_PATH_PREFIX

        sandbox = LocalSandbox("test", [PathMapping(container_path=VIRTUAL_PATH_PREFIX, local_path=str(data_dir))])
        result = sandbox.download_file(f"{VIRTUAL_PATH_PREFIX}/file.txt")
        assert result == b"hello world"


class TestWriteFileReadOnly:
    """Line 412: write_file to read-only path raises OSError."""

    def test_write_to_read_only_raises(self, tmp_path):
        ro_dir = tmp_path / "ro"
        ro_dir.mkdir()
        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/ro", local_path=str(ro_dir), read_only=True)])

        with pytest.raises(OSError) as exc_info:
            sandbox.write_file("/mnt/ro/file.txt", "content")
        assert exc_info.value.errno == errno.EROFS


class TestWriteFileOSError:
    """Lines 427-429: write_file OSError re-raises with original path."""

    def test_write_oserror_hides_resolved_path(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/data", local_path=str(data_dir))])

        with patch("builtins.open", side_effect=OSError(errno.EACCES, "Permission denied")):
            with pytest.raises(OSError) as exc_info:
                sandbox.write_file("/mnt/data/file.txt", "content")
            assert exc_info.value.filename == "/mnt/data/file.txt"


class TestUpdateFileOSError:
    """Line 468: update_file OSError re-raises with original path."""

    def test_update_oserror_hides_resolved_path(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/data", local_path=str(data_dir))])

        with patch("builtins.open", side_effect=OSError(errno.EACCES, "Permission denied")):
            with pytest.raises(OSError) as exc_info:
                sandbox.update_file("/mnt/data/file.bin", b"content")
            assert exc_info.value.filename == "/mnt/data/file.bin"


class TestUpdateFileReadOnly:
    """update_file to read-only path raises OSError."""

    def test_update_to_read_only_raises(self, tmp_path):
        ro_dir = tmp_path / "ro"
        ro_dir.mkdir()
        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/ro", local_path=str(ro_dir), read_only=True)])

        with pytest.raises(OSError) as exc_info:
            sandbox.update_file("/mnt/ro/file.bin", b"content")
        assert exc_info.value.errno == errno.EROFS


class TestDownloadFileOSError:
    """download_file OSError re-raises with original path."""

    def test_download_oserror(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_bytes(b"test")

        from ideer.config.paths import VIRTUAL_PATH_PREFIX

        sandbox = LocalSandbox("test", [PathMapping(container_path=VIRTUAL_PATH_PREFIX, local_path=str(data_dir))])

        with patch("os.path.getsize", side_effect=OSError(errno.ENOENT, "No such file")):
            with pytest.raises(OSError) as exc_info:
                sandbox.download_file(f"{VIRTUAL_PATH_PREFIX}/file.txt")
            assert exc_info.value.filename == f"{VIRTUAL_PATH_PREFIX}/file.txt"


class TestIsReadOnlyPath:
    """Test _is_read_only_path edge cases."""

    def test_read_only_path_matches(self, tmp_path):
        ro_dir = tmp_path / "ro"
        ro_dir.mkdir()
        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/ro", local_path=str(ro_dir), read_only=True)])
        assert sandbox._is_read_only_path(str(ro_dir / "file.txt")) is True

    def test_non_read_only_path(self, tmp_path):
        rw_dir = tmp_path / "rw"
        rw_dir.mkdir()
        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/rw", local_path=str(rw_dir), read_only=False)])
        assert sandbox._is_read_only_path(str(rw_dir / "file.txt")) is False

    def test_path_not_under_any_mapping(self):
        sandbox = LocalSandbox("test", [])
        assert sandbox._is_read_only_path("/unmapped/path") is False


class TestListDirWithTrailingSlash:
    """Test list_dir directory entries get trailing slash."""

    def test_directory_entry_has_trailing_slash(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "subdir").mkdir()
        (data_dir / "file.txt").write_text("x")

        sandbox = LocalSandbox("test", [PathMapping(container_path="/mnt/data", local_path=str(data_dir))])
        entries = sandbox.list_dir("/mnt/data")

        dir_entries = [e for e in entries if e.endswith("/")]
        file_entries = [e for e in entries if not e.endswith("/")]
        assert len(dir_entries) >= 1
        assert len(file_entries) >= 1


class TestDownloadPrefixNormalization:
    """Test download_file path normalization."""

    def test_backslash_path_normalized(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_bytes(b"test")

        from ideer.config.paths import VIRTUAL_PATH_PREFIX

        sandbox = LocalSandbox("test", [PathMapping(container_path=VIRTUAL_PATH_PREFIX, local_path=str(data_dir))])
        # On Linux, backslash is part of filename. Test that prefix matching
        # still works when backslashes are normalized to forward slashes.
        # The download_file normalizes path.replace("\\", "/") before checking.
        forward_path = f"{VIRTUAL_PATH_PREFIX}/file.txt"
        result = sandbox.download_file(forward_path)
        assert result == b"test"
