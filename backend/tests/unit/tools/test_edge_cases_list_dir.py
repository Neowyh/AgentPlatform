"""Additional coverage tests for ideer.sandbox.local.list_dir."""

from __future__ import annotations

import os

import pytest

from ideer.sandbox.local.list_dir import list_dir

# ===========================================================================
# list_dir
# ===========================================================================


class TestListDir:
    def test_basic(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.py").write_text("y")
        result = list_dir(str(tmp_path))
        assert len(result) == 2

    def test_empty_dir(self, tmp_path):
        result = list_dir(str(tmp_path))
        assert result == []

    def test_nonexistent_dir(self, tmp_path):
        result = list_dir(str(tmp_path / "nonexistent"))
        assert result == []

    def test_max_depth_1(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("y")
        result = list_dir(str(tmp_path), max_depth=1)
        # Should include sub/ and a.txt but not sub/b.txt
        assert any("a.txt" in r for r in result)
        assert any("sub/" in r for r in result)
        assert not any("b.txt" in r for r in result)

    def test_ignores_common_dirs(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x")
        (tmp_path / "keep.txt").write_text("y")
        result = list_dir(str(tmp_path))
        assert not any(".git" in r for r in result)

    def test_ignores_pycache(self, tmp_path):
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.pyc").write_bytes(b"\x00")
        (tmp_path / "keep.txt").write_text("y")
        result = list_dir(str(tmp_path))
        assert not any("__pycache__" in r for r in result)

    def test_symlink_to_inside(self, tmp_path):
        """Symlink whose target is inside the root should appear in results."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "file.txt").write_text("x")
        link = tmp_path / "link"
        link.symlink_to(target, target_is_directory=True)
        result = list_dir(str(tmp_path))
        # The resolved symlink target is inside root, so it should be listed
        assert any("target" in r for r in result)

    def test_symlink_to_outside(self, tmp_path):
        """Symlink whose resolved target is outside root should be filtered out."""
        outside = tmp_path.parent / "outside_dir_for_test"
        outside.mkdir(exist_ok=True)
        try:
            (outside / "secret.txt").write_text("secret")
            link = tmp_path / "link"
            link.symlink_to(outside, target_is_directory=True)
            result = list_dir(str(tmp_path))
            # Should NOT include secret.txt (outside root)
            assert all("secret.txt" not in r for r in result)
        finally:
            import shutil

            shutil.rmtree(outside, ignore_errors=True)

    def test_symlink_broken(self, tmp_path):
        link = tmp_path / "broken_link"
        try:
            link.symlink_to(tmp_path / "nonexistent")
        except (NotImplementedError, OSError):
            pytest.skip("symlinks not supported")
        result = list_dir(str(tmp_path))
        # Broken symlinks are skipped (resolve() raises OSError)
        assert not any("broken_link" in r for r in result)

    def test_permission_error(self, tmp_path):
        # Create a directory that we can't read
        no_access = tmp_path / "no_access"
        no_access.mkdir()
        (no_access / "secret.txt").write_text("secret")
        # Remove read permission
        os.chmod(no_access, 0o000)
        try:
            list_dir(str(tmp_path))
            # Should not crash, may or may not include the dir
        finally:
            os.chmod(no_access, 0o755)

    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x\n")
        result = list_dir(str(f))
        assert result == []

    def test_sorted_output(self, tmp_path):
        (tmp_path / "c.txt").write_text("x")
        (tmp_path / "a.txt").write_text("y")
        (tmp_path / "b.txt").write_text("z")
        result = list_dir(str(tmp_path))
        assert result == sorted(result)

    def test_directories_marked_with_slash(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file.txt").write_text("x")
        result = list_dir(str(tmp_path))
        subdir_entry = [r for r in result if "subdir" in r][0]
        assert subdir_entry.endswith("/")

    def test_files_not_marked(self, tmp_path):
        (tmp_path / "file.txt").write_text("x")
        result = list_dir(str(tmp_path))
        file_entry = [r for r in result if "file.txt" in r][0]
        assert not file_entry.endswith("/")

    def test_symlink_to_outside_not_followed(self, tmp_path):
        """Symlink pointing outside root should not list its children."""
        outside = tmp_path.parent / "outside_not_followed"
        outside.mkdir(exist_ok=True)
        try:
            (outside / "inside_link").mkdir()
            (outside / "inside_link" / "deep.txt").write_text("deep")
            link = tmp_path / "escape"
            link.symlink_to(outside / "inside_link", target_is_directory=True)
            result = list_dir(str(tmp_path))
            # The escape/ link should not be present (resolved outside root)
            assert not any("deep.txt" in r for r in result)
        finally:
            import shutil

            shutil.rmtree(outside, ignore_errors=True)

    def test_max_depth_0_returns_empty(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        result = list_dir(str(tmp_path), max_depth=0)
        assert result == []
