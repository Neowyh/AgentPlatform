"""Tests for app.gateway.auth.credential_file module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from app.gateway.auth.credential_file import _CREDENTIAL_FILENAME, write_initial_credentials


class TestWriteInitialCredentials:
    """Test write_initial_credentials() -- the only public function in the module."""

    def test_creates_file_with_default_label(self, tmp_path: Path) -> None:
        """Happy path: writes email + password with 'initial' label."""
        mock_paths = type("FakePaths", (), {"base_dir": tmp_path})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            result = write_initial_credentials("admin@example.com", "s3cret")

        assert result.exists()
        assert result == (tmp_path / _CREDENTIAL_FILENAME).resolve()

        content = result.read_text(encoding="utf-8")
        assert "email: admin@example.com" in content
        assert "password: s3cret" in content
        assert "iDeer admin initial credentials" in content

    def test_creates_file_with_reset_label(self, tmp_path: Path) -> None:
        """Label='reset' appears in the file header."""
        mock_paths = type("FakePaths", (), {"base_dir": tmp_path})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            result = write_initial_credentials("admin@example.com", "newpw", label="reset")

        content = result.read_text(encoding="utf-8")
        assert "iDeer admin reset credentials" in content
        assert "email: admin@example.com" in content
        assert "password: newpw" in content

    def test_file_permissions_are_0600(self, tmp_path: Path) -> None:
        """The file should be created with mode 0o600 (owner read/write only)."""
        mock_paths = type("FakePaths", (), {"base_dir": tmp_path})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            result = write_initial_credentials("u@e.com", "pw")

        mode = os.stat(result).st_mode & 0o777
        assert mode == 0o600

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """If base_dir does not exist yet, it should be created."""
        nested = tmp_path / "deep" / "nested" / "dir"
        mock_paths = type("FakePaths", (), {"base_dir": nested})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            result = write_initial_credentials("u@e.com", "pw")

        assert result.exists()
        assert nested.is_dir()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """A second call should truncate and overwrite the existing file."""
        mock_paths = type("FakePaths", (), {"base_dir": tmp_path})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            write_initial_credentials("first@example.com", "first_pw")
            result = write_initial_credentials("second@example.com", "second_pw")

        content = result.read_text(encoding="utf-8")
        assert "email: second@example.com" in content
        assert "password: second_pw" in content
        assert "first@example.com" not in content

    def test_returns_resolved_path(self, tmp_path: Path) -> None:
        """Returned path should be absolute and resolved (no symlinks, ..)."""
        mock_paths = type("FakePaths", (), {"base_dir": tmp_path})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            result = write_initial_credentials("u@e.com", "pw")

        assert result.is_absolute()
        assert ".." not in str(result)

    def test_content_contains_instructions(self, tmp_path: Path) -> None:
        """The file content should contain operator instructions."""
        mock_paths = type("FakePaths", (), {"base_dir": tmp_path})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            result = write_initial_credentials("u@e.com", "pw")

        content = result.read_text(encoding="utf-8")
        assert "Change the password after login" in content
        assert "delete this file" in content

    def test_special_characters_in_password(self, tmp_path: Path) -> None:
        """Passwords with special characters should be written verbatim."""
        special_pw = "p@$$w0rd!#%^&*(){}[]|\\:;\"'<>,.?/~`"
        mock_paths = type("FakePaths", (), {"base_dir": tmp_path})()
        with patch("app.gateway.auth.credential_file.get_paths", return_value=mock_paths):
            result = write_initial_credentials("u@e.com", special_pw)

        content = result.read_text(encoding="utf-8")
        assert f"password: {special_pw}" in content

    def test_module_level_constant(self) -> None:
        """_CREDENTIAL_FILENAME should be the expected filename."""
        assert _CREDENTIAL_FILENAME == "admin_initial_credentials.txt"
