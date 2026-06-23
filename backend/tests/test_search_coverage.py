"""Targeted coverage tests for ideer.sandbox.search uncovered lines.

Each test is named after the specific source line it exercises.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ideer.sandbox.search import (
    find_glob_matches,
    find_grep_matches,
    is_binary_file,
    path_matches,
    truncate_line,
)

# ---------------------------------------------------------------------------
# Line 87 – path_matches: pattern doesn't start with **/ and doesn't match
# ---------------------------------------------------------------------------


class TestPathMatchesLine87:
    def test_no_match_plain_pattern(self):
        """pattern '*.js' does not start with **/ and 'main.py' doesn't match."""
        assert path_matches("*.js", "main.py") is False

    def test_no_match_fixed_prefix(self):
        """Pattern with a fixed prefix that doesn't match the rel_path."""
        assert path_matches("src/*.rs", "lib/main.py") is False


# ---------------------------------------------------------------------------
# Line 94 – truncate_line: line longer than max_chars
# ---------------------------------------------------------------------------


class TestTruncateLineLine94:
    def test_long_line_truncated(self):
        text = "a" * 300
        result = truncate_line(text, 100)
        assert len(result) == 100
        assert result.endswith("...")
        assert result == "a" * 97 + "..."

    def test_exact_boundary_not_truncated(self):
        text = "b" * 50
        result = truncate_line(text, 50)
        assert result == text


# ---------------------------------------------------------------------------
# Lines 101-102 – is_binary_file OSError handling
# ---------------------------------------------------------------------------


class TestIsBinaryFileOSError:
    def test_oserror_returns_true(self, tmp_path):
        f = tmp_path / "unreadable.bin"
        f.write_bytes(b"normal text")
        # Revoke read permissions so open() raises OSError
        os.chmod(f, 0o000)
        try:
            assert is_binary_file(f) is True
        finally:
            os.chmod(f, 0o644)

    def test_permission_denied_on_directory(self, tmp_path):
        """Opening a directory as a file raises OSError."""
        d = tmp_path / "a_dir"
        d.mkdir()
        assert is_binary_file(d) is True


# ---------------------------------------------------------------------------
# Line 111 – find_glob_matches: root doesn't exist → FileNotFoundError
# ---------------------------------------------------------------------------


class TestFindGlobMatchesLine111:
    def test_nonexistent_root(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            find_glob_matches(tmp_path / "does_not_exist", "*.py")


# ---------------------------------------------------------------------------
# Lines 127-128 – find_glob_matches truncation (truncated=True)
# ---------------------------------------------------------------------------


class TestFindGlobMatchesTruncation:
    def test_truncated_when_max_results_reached(self, tmp_path):
        for i in range(10):
            (tmp_path / f"f{i}.txt").write_text("x\n")
        matches, truncated = find_glob_matches(tmp_path, "*.txt", max_results=3)
        assert len(matches) == 3
        assert truncated is True

    def test_truncated_via_dirs(self, tmp_path):
        """include_dirs=True path hitting the truncation branch."""
        for i in range(5):
            d = tmp_path / f"dir{i}"
            d.mkdir()
        matches, truncated = find_glob_matches(tmp_path, "dir*", include_dirs=True, max_results=2)
        assert len(matches) == 2
        assert truncated is True


# ---------------------------------------------------------------------------
# Line 132 – find_glob_matches: file should be ignored
# ---------------------------------------------------------------------------


class TestFindGlobMatchesIgnoredFile:
    def test_ignored_file_skipped(self, tmp_path):
        """A file whose name matches an ignore pattern is skipped."""
        (tmp_path / "keep.py").write_text("a\n")
        (tmp_path / "debug.log").write_text("b\n")  # *.log is ignored
        matches, truncated = find_glob_matches(tmp_path, "*.*")
        names = [Path(m).name for m in matches]
        assert "keep.py" in names
        assert "debug.log" not in names


# ---------------------------------------------------------------------------
# Line 159 – find_grep_matches: root doesn't exist → FileNotFoundError
# ---------------------------------------------------------------------------


class TestFindGrepMatchesLine159:
    def test_nonexistent_root(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            find_grep_matches(tmp_path / "missing", "TODO")


# ---------------------------------------------------------------------------
# Line 176 – find_grep_matches: file should be ignored
# ---------------------------------------------------------------------------


class TestFindGrepMatchesIgnoredFile:
    def test_ignored_file_skipped(self, tmp_path):
        """A file matching an ignore pattern is not searched."""
        (tmp_path / "code.py").write_text("TODO here\n")
        (tmp_path / "debug.log").write_text("TODO in log\n")  # *.log ignored
        matches, _ = find_grep_matches(tmp_path, "TODO")
        assert len(matches) == 1
        assert "code.py" in matches[0].path


# ---------------------------------------------------------------------------
# Line 189 – find_grep_matches: symlink resolves outside root
# ---------------------------------------------------------------------------


class TestFindGrepMatchesSymlinkOutside:
    def test_symlink_to_outside_file(self, tmp_path):
        """A regular file that is a symlink resolving outside the root."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("SECRET data\n")
        link = workspace / "link.txt"
        link.symlink_to(outside)
        # link is a symlink → is_symlink() True → continue at line 186
        matches, _ = find_grep_matches(workspace, "SECRET")
        assert matches == []

    def test_file_resolves_outside_root(self, tmp_path):
        """Mock resolve() so a non-symlink file resolves outside root → line 189."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        target = workspace / "tricky.txt"
        target.write_text("OUTSIDE data\n")
        outside_path = tmp_path / "outside.txt"

        original_resolve = Path.resolve

        def patched_resolve(self, strict=False):
            result = original_resolve(self, strict=strict)
            if self.name == "tricky.txt":
                return outside_path
            return result

        with patch.object(Path, "resolve", patched_resolve):
            matches, _ = find_grep_matches(workspace, "OUTSIDE")
        assert matches == []


# ---------------------------------------------------------------------------
# Line 191 – find_grep_matches: file too large or binary
# ---------------------------------------------------------------------------


class TestFindGrepMatchesLine191:
    def test_oversized_file(self, tmp_path):
        big = tmp_path / "big.py"
        big.write_text("A" * 2_000_000)
        matches, _ = find_grep_matches(tmp_path, "A", max_file_size=1000)
        assert matches == []

    def test_binary_file(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02binary content")
        matches, _ = find_grep_matches(tmp_path, "binary")
        assert matches == []


# ---------------------------------------------------------------------------
# Line 195 – find_grep_matches: line too long
# ---------------------------------------------------------------------------


class TestFindGrepMatchesLine195:
    def test_extremely_long_line_skipped(self, tmp_path):
        f = tmp_path / "minified.js"
        # One line longer than line_summary_length * 10 (200 * 10 = 2000)
        f.write_text("x" * 5000 + "\n")
        matches, _ = find_grep_matches(tmp_path, "x", line_summary_length=200)
        assert matches == []

    def test_long_line_with_match_not_skipped(self, tmp_path):
        """A line within the length limit that matches is still found."""
        f = tmp_path / "ok.py"
        f.write_text("TODO " + "x" * 500 + "\n")
        matches, _ = find_grep_matches(tmp_path, "TODO", line_summary_length=200)
        assert len(matches) == 1


# ---------------------------------------------------------------------------
# Lines 207-208 – find_grep_matches: OSError handling
# ---------------------------------------------------------------------------


class TestFindGrepMatchesOSError:
    def test_oserror_caught_at_try_block(self, tmp_path):
        """Mock Path.stat to raise OSError, hitting the except at lines 207-208.

        The normal permission-denied approach triggers is_binary_file's own
        OSError handler first (lines 101-102), so we need to make stat()
        itself fail.
        """
        target = tmp_path / "target.py"
        target.write_text("TODO target\n")

        original_stat = Path.stat

        def failing_stat(self, *args, **kwargs):
            if self.name == "target.py":
                raise PermissionError("simulated stat failure")
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", failing_stat):
            matches, _ = find_grep_matches(tmp_path, "TODO")
        # OSError caught at line 207 → file silently skipped
        assert matches == []
