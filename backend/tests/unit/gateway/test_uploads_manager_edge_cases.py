"""Tests for uncovered error paths in ideer.uploads.manager.

Covers the specific lines identified as missing coverage:
- Line 37: validate_thread_id error path
- Line 75: normalize_filename backslash rejection
- Line 77: normalize_filename too-long rejection
- Line 156: POSIX open_upload_file_no_symlink re-raise OSError
- Lines 176, 180, 188, 190, 194-197, 202, 208: Windows branch paths
"""

import errno
import os
import stat
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_original_ofollow = getattr(os, "O_NOFOLLOW", None)


def _hide_o_nofollow():
    """Remove os.O_NOFOLLOW so hasattr(os, 'O_NOFOLLOW') returns False."""
    if _original_ofollow is not None:
        delattr(os, "O_NOFOLLOW")


def _restore_o_nofollow():
    """Restore os.O_NOFOLLOW after a test."""
    if _original_ofollow is not None:
        os.O_NOFOLLOW = _original_ofollow


@pytest.fixture(autouse=True)
def _restore_o_nofollow_fixture():
    """Ensure O_NOFOLLOW is always restored after every test."""
    yield
    _restore_o_nofollow()


# ---------------------------------------------------------------------------
# validate_thread_id  (line 37)
# ---------------------------------------------------------------------------


class TestValidateThreadId:
    """validate_thread_id raises ValueError for invalid input."""

    def test_empty_string_raises(self):
        from ideer.uploads.manager import validate_thread_id

        with pytest.raises(ValueError, match="Invalid thread_id"):
            validate_thread_id("")

    def test_unsafe_characters_raise(self):
        from ideer.uploads.manager import validate_thread_id

        with pytest.raises(ValueError, match="Invalid thread_id"):
            validate_thread_id("../../etc/passwd")

    def test_spaces_raise(self):
        from ideer.uploads.manager import validate_thread_id

        with pytest.raises(ValueError, match="Invalid thread_id"):
            validate_thread_id("thread 123")

    def test_slash_raises(self):
        from ideer.uploads.manager import validate_thread_id

        with pytest.raises(ValueError, match="Invalid thread_id"):
            validate_thread_id("thread/123")


# ---------------------------------------------------------------------------
# normalize_filename  (lines 75, 77)
# ---------------------------------------------------------------------------


class TestNormalizeFilename:
    """normalize_filename error paths for backslash and length."""

    def test_backslash_in_basename_raises(self):
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="Filename contains backslash"):
            normalize_filename("report\\file.pdf")

    def test_backslash_in_name_only_raises(self):
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="Filename contains backslash"):
            normalize_filename("file\\name.txt")

    def test_filename_too_long_raises(self):
        from ideer.uploads.manager import normalize_filename

        # Each Chinese character is 3 bytes in UTF-8, so 86 chars = 258 bytes
        long_name = "中" * 86 + ".txt"
        with pytest.raises(ValueError, match="Filename too long"):
            normalize_filename(long_name)

    def test_filename_exactly_255_bytes_ok(self):
        from ideer.uploads.manager import normalize_filename

        # 251 ASCII chars + ".txt" = 255 bytes — should pass
        name = "a" * 251 + ".txt"
        result = normalize_filename(name)
        assert result == name

    def test_empty_filename_raises(self):
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="Filename is empty"):
            normalize_filename("")

    def test_dotdot_basename_raises(self):
        """Line 71: basename resolving to '..' should be rejected."""
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="Filename is unsafe"):
            normalize_filename("/tmp/..")

    def test_dot_basename_raises(self):
        """Line 71: basename resolving to '.' should be rejected."""
        from ideer.uploads.manager import normalize_filename

        with pytest.raises(ValueError, match="Filename is unsafe"):
            normalize_filename(".")


# ---------------------------------------------------------------------------
# open_upload_file_no_symlink  — POSIX branch, line 156 (re-raise OSError)
# ---------------------------------------------------------------------------


class TestOpenUploadPosixOSErrorReRaise:
    """POSIX branch error paths (lines 155-156)."""

    def test_eloop_raises_unsafe_upload(self, tmp_path):
        """Line 155: OSError with ELOOP is caught and converted to UnsafeUploadPathError."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        with patch("os.open", side_effect=OSError(errno.ELOOP, "Too many levels of symbolic links")):
            with pytest.raises(UnsafeUploadPathError, match="Unsafe upload destination"):
                open_upload_file_no_symlink(tmp_path, "test.txt")

    def test_eisdir_raises_unsafe_upload(self, tmp_path):
        """Line 155: EISDIR in POSIX branch."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        with patch("os.open", side_effect=OSError(errno.EISDIR, "Is a directory")):
            with pytest.raises(UnsafeUploadPathError, match="Unsafe upload destination"):
                open_upload_file_no_symlink(tmp_path, "test.txt")

    def test_oserror_with_unexpected_errno_is_reraised(self, tmp_path):
        """Line 156: OSError with errno NOT in {ELOOP,EISDIR,ENOTDIR,ENXIO,EAGAIN}
        should be re-raised as-is."""
        from ideer.uploads.manager import open_upload_file_no_symlink

        with patch("os.open", side_effect=OSError(errno.EACCES, "Permission denied")):
            with pytest.raises(OSError) as exc_info:
                open_upload_file_no_symlink(tmp_path, "test.txt")
            assert exc_info.value.errno == errno.EACCES

    def test_oserror_eperm_is_reraised(self, tmp_path):
        """Line 156: EPERM also not in the handled set — should re-raise."""
        from ideer.uploads.manager import open_upload_file_no_symlink

        with patch("os.open", side_effect=OSError(errno.EPERM, "Operation not permitted")):
            with pytest.raises(OSError) as exc_info:
                open_upload_file_no_symlink(tmp_path, "test.txt")
            assert exc_info.value.errno == errno.EPERM


# ---------------------------------------------------------------------------
# open_upload_file_no_symlink  — Windows branch (no O_NOFOLLOW)
# ---------------------------------------------------------------------------


class TestOpenUploadWindowsBranch:
    """Tests for the Windows (no O_NOFOLLOW) branch of open_upload_file_no_symlink.

    We remove os.O_NOFOLLOW so hasattr(os, 'O_NOFOLLOW') returns False,
    forcing the function into the else branch. We use real filesystem objects
    wherever possible to avoid interfering with Path.resolve().
    """

    @pytest.fixture(autouse=True)
    def _mock_user_context(self):
        """Mock get_effective_user_id to avoid context var issues."""
        with patch("ideer.uploads.manager.get_effective_user_id", return_value="testuser"):
            yield

    def test_nlink_gt_1_raises(self, tmp_path):
        """Line 176: st.nlink > 1 on initial lstat raises UnsafeUploadPathError."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        # Create a real file, then a hard link to it so nlink == 2
        original = tmp_path / "original.txt"
        original.write_bytes(b"content")
        link = tmp_path / "test.txt"
        os.link(str(original), str(link))

        _hide_o_nofollow()
        try:
            with pytest.raises(UnsafeUploadPathError, match="multiple links"):
                open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_pre_open_lstat_not_regular_raises(self, tmp_path):
        """Line 188: pre_open_st is not a regular file.

        We need a TOCTOU simulation: the first lstat returns a regular file
        (so line 138 passes), but the second lstat (line 183) returns a
        directory.  We use a selective lstat wrapper that only intercepts
        calls to the target file path, passing all others through to the
        real os.lstat (which Path.resolve() also uses).
        """
        import os as _os

        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        target = str(tmp_path / "test.txt")
        (tmp_path / "test.txt").write_bytes(b"x")

        real_lstat = _os.lstat
        call_count = [0]

        def selective_lstat(path, *args, **kwargs):
            if str(path) == target:
                call_count[0] += 1
                # Call #1: line 134 (first lstat)
                # Call #2: dest.resolve() in validate_path_traversal
                # Call #3: line 183 (second lstat) — this is the one we fake
                if call_count[0] == 3:
                    return SimpleNamespace(
                        st_mode=stat.S_IFDIR,
                        st_nlink=1,
                        st_size=4096,
                    )
            return real_lstat(path, *args, **kwargs)

        _hide_o_nofollow()
        try:
            with patch("os.lstat", side_effect=selective_lstat):
                with pytest.raises(UnsafeUploadPathError, match="not a regular file"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_pre_open_lstat_nlink_gt_1_raises(self, tmp_path):
        """Line 190: pre_open_st.nlink > 1 on the second lstat.

        We need a TOCTOU simulation: the first lstat returns a regular file
        with nlink=1 (so line 175 passes), but the second lstat (line 183)
        returns nlink > 1.  We use a selective lstat wrapper that only
        intercepts calls to the target file path.
        """
        import os as _os

        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        target = str(tmp_path / "test.txt")
        (tmp_path / "test.txt").write_bytes(b"x")

        real_lstat = _os.lstat
        call_count = [0]

        def selective_lstat(path, *args, **kwargs):
            if str(path) == target:
                call_count[0] += 1
                # Call #1: line 134 (first lstat)
                # Call #2: dest.resolve() in validate_path_traversal
                # Call #3: line 183 (second lstat) — this is the one we fake
                if call_count[0] == 3:
                    real = real_lstat(path, *args, **kwargs)
                    return SimpleNamespace(
                        st_mode=real.st_mode,
                        st_nlink=3,
                        st_size=real.st_size,
                    )
            return real_lstat(path, *args, **kwargs)

        _hide_o_nofollow()
        try:
            with patch("os.lstat", side_effect=selective_lstat):
                with pytest.raises(UnsafeUploadPathError, match="multiple links"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_os_open_oserror_eisdir_raises(self, tmp_path):
        """Lines 194-197: OSError with EISDIR is caught and converted."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        # Create a file so the first lstat succeeds (nlink=1)
        (tmp_path / "test.txt").write_bytes(b"x")

        _hide_o_nofollow()
        try:
            with patch("os.open", side_effect=OSError(errno.EISDIR, "Is a directory")):
                with pytest.raises(UnsafeUploadPathError, match="Unsafe upload destination"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_os_open_oserror_enotdir_raises(self, tmp_path):
        """Lines 194-197: ENOTDIR."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")

        _hide_o_nofollow()
        try:
            with patch("os.open", side_effect=OSError(errno.ENOTDIR, "Not a directory")):
                with pytest.raises(UnsafeUploadPathError, match="Unsafe upload destination"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_os_open_oserror_enxio_raises(self, tmp_path):
        """Lines 194-197: ENXIO."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")

        _hide_o_nofollow()
        try:
            with patch("os.open", side_effect=OSError(errno.ENXIO, "No such device")):
                with pytest.raises(UnsafeUploadPathError, match="Unsafe upload destination"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_os_open_oserror_eagain_raises(self, tmp_path):
        """Lines 194-197: EAGAIN."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")

        _hide_o_nofollow()
        try:
            with patch("os.open", side_effect=OSError(errno.EAGAIN, "Try again")):
                with pytest.raises(UnsafeUploadPathError, match="Unsafe upload destination"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_os_open_oserror_unexpected_errno_reraises(self, tmp_path):
        """Lines 194-197: OSError with unhandled errno is re-raised."""
        from ideer.uploads.manager import open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")

        _hide_o_nofollow()
        try:
            with patch("os.open", side_effect=OSError(errno.EACCES, "Permission denied")):
                with pytest.raises(OSError) as exc_info:
                    open_upload_file_no_symlink(tmp_path, "test.txt")
                assert exc_info.value.errno == errno.EACCES
        finally:
            _restore_o_nofollow()

    def test_fstat_not_regular_raises(self, tmp_path):
        """Line 202: opened_stat is not a regular file."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")
        opened_stat = SimpleNamespace(st_mode=stat.S_IFDIR, st_nlink=1)

        _hide_o_nofollow()
        try:
            with (
                patch("os.open", return_value=42),
                patch("os.fstat", return_value=opened_stat),
                patch("os.close"),
            ):
                with pytest.raises(UnsafeUploadPathError, match="not an exclusive regular file"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_fstat_nlink_gt_1_raises(self, tmp_path):
        """Line 202: opened_stat.nlink > 1."""
        from ideer.uploads.manager import UnsafeUploadPathError, open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")
        opened_stat = SimpleNamespace(st_mode=stat.S_IFREG, st_nlink=2)

        _hide_o_nofollow()
        try:
            with (
                patch("os.open", return_value=42),
                patch("os.fstat", return_value=opened_stat),
                patch("os.close"),
            ):
                with pytest.raises(UnsafeUploadPathError, match="not an exclusive regular file"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
        finally:
            _restore_o_nofollow()

    def test_fd_closed_in_finally_on_fstat_error(self, tmp_path):
        """Line 208: fd is closed in the finally block when fstat raises."""
        from ideer.uploads.manager import open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")
        fd = 99

        _hide_o_nofollow()
        try:
            with (
                patch("os.open", return_value=fd),
                patch("os.fstat", side_effect=OSError("fstat failed")),
                patch("os.close") as mock_close,
                patch("os.fdopen", side_effect=OSError("should not reach fdopen")),
            ):
                with pytest.raises(OSError, match="fstat failed"):
                    open_upload_file_no_symlink(tmp_path, "test.txt")
                # Verify os.close was called in the finally block
                mock_close.assert_called_once_with(fd)
        finally:
            _restore_o_nofollow()

    def test_successful_open_on_windows_path(self, tmp_path):
        """Happy path on Windows branch: file is opened and returned."""
        from ideer.uploads.manager import open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")
        opened_stat = SimpleNamespace(st_mode=stat.S_IFREG, st_nlink=1)
        mock_fh = MagicMock()

        _hide_o_nofollow()
        try:
            with (
                patch("os.open", return_value=42),
                patch("os.fstat", return_value=opened_stat),
                patch("os.ftruncate"),
                patch("os.fdopen", return_value=mock_fh),
            ):
                dest, fh = open_upload_file_no_symlink(tmp_path, "test.txt")
                assert dest == tmp_path / "test.txt"
                assert fh is mock_fh
        finally:
            _restore_o_nofollow()

    def test_o_binary_flag_added_when_available(self, tmp_path):
        """Line 180: O_BINARY flag is included when the attribute exists."""
        from ideer.uploads.manager import open_upload_file_no_symlink

        (tmp_path / "test.txt").write_bytes(b"x")
        opened_stat = SimpleNamespace(st_mode=stat.S_IFREG, st_nlink=1)
        mock_fh = MagicMock()
        O_BINARY_VALUE = 0x8000

        _hide_o_nofollow()
        try:
            with (
                patch("os.open", return_value=42) as mock_open,
                patch("os.fstat", return_value=opened_stat),
                patch("os.ftruncate"),
                patch("os.fdopen", return_value=mock_fh),
                patch.object(os, "O_BINARY", O_BINARY_VALUE, create=True),
            ):
                dest, fh = open_upload_file_no_symlink(tmp_path, "test.txt")
                # Verify O_BINARY was ORed into the flags
                call_args = mock_open.call_args
                flags = call_args[0][1]
                assert flags & O_BINARY_VALUE != 0
        finally:
            _restore_o_nofollow()
