"""Additional coverage tests for ideer.sandbox.search."""

from __future__ import annotations

import pytest

from ideer.sandbox.search import (
    find_glob_matches,
    find_grep_matches,
    is_binary_file,
    path_matches,
    should_ignore_name,
    should_ignore_path,
    truncate_line,
)

# ===========================================================================
# should_ignore_name / should_ignore_path
# ===========================================================================


class TestShouldIgnoreName:
    def test_git(self):
        assert should_ignore_name(".git") is True

    def test_pycache(self):
        assert should_ignore_name("__pycache__") is True

    def test_normal_file(self):
        assert should_ignore_name("readme.md") is False

    def test_egg_info(self):
        assert should_ignore_name("pkg.egg-info") is True

    def test_mypy_cache(self):
        assert should_ignore_name(".mypy_cache") is True


class TestShouldIgnorePath:
    def test_normal_path(self):
        assert should_ignore_path("src/main.py") is False

    def test_with_git(self):
        assert should_ignore_path("src/.git/config") is True

    def test_with_backslash(self):
        assert should_ignore_path("src\\__pycache__\\mod.pyc") is True


# ===========================================================================
# path_matches
# ===========================================================================


class TestPathMatches:
    def test_exact_match(self):
        assert path_matches("main.py", "main.py") is True

    def test_star_pattern(self):
        assert path_matches("*.py", "src/main.py") is True

    def test_double_star_pattern(self):
        assert path_matches("**/*.py", "src/deep/main.py") is True

    def test_no_match(self):
        assert path_matches("*.js", "main.py") is False

    def test_non_matching_double_star(self):
        # Test a pattern that doesn't match
        assert path_matches("**/*.js", "src/main.py") is False


# ===========================================================================
# truncate_line
# ===========================================================================


class TestTruncateLine:
    def test_short(self):
        assert truncate_line("hello", 100) == "hello"

    def test_long(self):
        result = truncate_line("a" * 100, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_strips_newlines(self):
        assert truncate_line("hello\n", 100) == "hello"

    def test_exact_length(self):
        text = "a" * 50
        assert truncate_line(text, 50) == text


# ===========================================================================
# is_binary_file
# ===========================================================================


class TestIsBinaryFile:
    def test_text_file(self, tmp_path):
        f = tmp_path / "text.txt"
        f.write_text("hello world\n", encoding="utf-8")
        assert is_binary_file(f) is False

    def test_binary_file(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00binary\x00data")
        assert is_binary_file(f) is True

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "nonexistent.txt"
        assert is_binary_file(f) is True


# ===========================================================================
# find_glob_matches
# ===========================================================================


class TestFindGlobMatches:
    def test_basic(self, tmp_path):
        (tmp_path / "a.py").write_text("x\n")
        (tmp_path / "b.py").write_text("y\n")
        matches, truncated = find_glob_matches(tmp_path, "*.py")
        assert len(matches) == 2
        assert truncated is False

    def test_not_found(self, tmp_path):
        (tmp_path / "a.txt").write_text("x\n")
        matches, truncated = find_glob_matches(tmp_path, "*.py")
        assert matches == []
        assert truncated is False

    def test_truncated(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.py").write_text("x\n")
        matches, truncated = find_glob_matches(tmp_path, "*.py", max_results=2)
        assert len(matches) == 2
        assert truncated is True

    def test_include_dirs(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        matches, truncated = find_glob_matches(tmp_path, "subdir", include_dirs=True)
        assert len(matches) == 1

    def test_nonexistent_root(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            find_glob_matches(tmp_path / "nonexistent", "*.py")

    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x\n")
        with pytest.raises(NotADirectoryError):
            find_glob_matches(f, "*.py")

    def test_ignores_common_dirs(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "skip.py").write_text("x\n")
        (tmp_path / "keep.py").write_text("y\n")
        matches, _ = find_glob_matches(tmp_path, "*.py")
        assert len(matches) == 1

    def test_nested_ignored_dirs(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x\n")
        (tmp_path / "keep.txt").write_text("y\n")
        matches, _ = find_glob_matches(tmp_path, "*.txt")
        assert len(matches) == 1


# ===========================================================================
# find_grep_matches
# ===========================================================================


class TestFindGrepMatches:
    def test_basic(self, tmp_path):
        (tmp_path / "a.py").write_text("TODO: fix this\ndone\n")
        matches, truncated = find_grep_matches(tmp_path, "TODO")
        assert len(matches) == 1
        assert matches[0].line_number == 1
        assert "TODO" in matches[0].line

    def test_no_matches(self, tmp_path):
        (tmp_path / "a.py").write_text("done\n")
        matches, truncated = find_grep_matches(tmp_path, "TODO")
        assert matches == []

    def test_truncated(self, tmp_path):
        (tmp_path / "a.py").write_text("TODO\n" * 10)
        matches, truncated = find_grep_matches(tmp_path, "TODO", max_results=2)
        assert len(matches) == 2
        assert truncated is True

    def test_glob_filter(self, tmp_path):
        (tmp_path / "a.py").write_text("TODO\n")
        (tmp_path / "b.txt").write_text("TODO\n")
        matches, _ = find_grep_matches(tmp_path, "TODO", glob_pattern="*.py")
        assert len(matches) == 1

    def test_literal_mode(self, tmp_path):
        (tmp_path / "a.py").write_text("price (a+b)\nresult a+b\n")
        matches, _ = find_grep_matches(tmp_path, "(a+b)", literal=True)
        assert len(matches) == 1
        assert "price" in matches[0].line

    def test_case_sensitive(self, tmp_path):
        (tmp_path / "a.py").write_text("TODO: fix\ntodo: also\n")
        matches, _ = find_grep_matches(tmp_path, "TODO", case_sensitive=True)
        assert len(matches) == 1

    def test_binary_file_skipped(self, tmp_path):
        (tmp_path / "a.bin").write_bytes(b"\x00binary")
        matches, _ = find_grep_matches(tmp_path, "binary")
        assert matches == []

    def test_nonexistent_root(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            find_grep_matches(tmp_path / "nonexistent", "TODO")

    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("TODO\n")
        with pytest.raises(NotADirectoryError):
            find_grep_matches(f, "TODO")

    def test_symlink_skipped(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("TODO outside\n")
        (workspace / "link.txt").symlink_to(outside)
        matches, _ = find_grep_matches(workspace, "TODO")
        assert matches == []

    def test_max_file_size(self, tmp_path):
        (tmp_path / "a.py").write_text("x" * 2000000)  # > 1MB default
        matches, _ = find_grep_matches(tmp_path, "x", max_file_size=1000)
        assert matches == []

    def test_long_line_skipped(self, tmp_path):
        (tmp_path / "a.py").write_text("x" * 3000 + "\n")
        matches, _ = find_grep_matches(tmp_path, "x", line_summary_length=200)
        assert matches == []
