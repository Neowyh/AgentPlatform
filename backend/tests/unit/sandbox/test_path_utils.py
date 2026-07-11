"""Tests for app.gateway.path_utils module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.gateway.path_utils import resolve_thread_virtual_path


class TestResolveThreadVirtualPath:
    """Test resolve_thread_virtual_path() -- the only public function."""

    def test_valid_virtual_path_outputs(self, tmp_path: Path) -> None:
        """Standard /mnt/user-data/outputs/ path resolves correctly."""
        user_data_dir = tmp_path / "user-data"
        user_data_dir.mkdir(parents=True)
        expected = user_data_dir / "outputs" / "report.pdf"

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = expected.resolve()

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="user-1"),
        ):
            result = resolve_thread_virtual_path("thread-123", "/mnt/user-data/outputs/report.pdf")

        assert result == expected.resolve()
        mock_paths.resolve_virtual_path.assert_called_once_with("thread-123", "/mnt/user-data/outputs/report.pdf", user_id="user-1")

    def test_valid_virtual_path_workspace(self, tmp_path: Path) -> None:
        """Standard /mnt/user-data/workspace/ path resolves correctly."""
        user_data_dir = tmp_path / "user-data"
        user_data_dir.mkdir(parents=True)
        expected = user_data_dir / "workspace" / "main.py"

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = expected.resolve()

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="user-1"),
        ):
            result = resolve_thread_virtual_path("t-1", "/mnt/user-data/workspace/main.py")

        assert result == expected.resolve()

    def test_valid_virtual_path_uploads(self, tmp_path: Path) -> None:
        """Standard /mnt/user-data/uploads/ path resolves correctly."""
        user_data_dir = tmp_path / "user-data"
        user_data_dir.mkdir(parents=True)
        expected = user_data_dir / "uploads" / "data.csv"

        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = expected.resolve()

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="user-1"),
        ):
            result = resolve_thread_virtual_path("t-1", "/mnt/user-data/uploads/data.csv")

        assert result == expected.resolve()

    def test_path_traversal_raises_403(self) -> None:
        """A ValueError containing 'traversal' should raise HTTPException 403."""
        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.side_effect = ValueError("Access denied: path traversal detected")

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="user-1"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                resolve_thread_virtual_path("t-1", "/mnt/user-data/../../etc/passwd")

        assert exc_info.value.status_code == 403
        assert "traversal" in exc_info.value.detail

    def test_invalid_path_prefix_raises_400(self) -> None:
        """A ValueError without 'traversal' should raise HTTPException 400."""
        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.side_effect = ValueError("Path must start with /mnt/user-data")

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="user-1"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                resolve_thread_virtual_path("t-1", "/tmp/evil.txt")

        assert exc_info.value.status_code == 400
        assert "Path must start with" in exc_info.value.detail

    def test_traversal_keyword_in_different_positions(self) -> None:
        """Verify the 403 vs 400 distinction based on 'traversal' substring."""
        # Case 1: 'traversal' at the start
        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.side_effect = ValueError("traversal attempt blocked")

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="u"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                resolve_thread_virtual_path("t-1", "/mnt/user-data/../../x")
            assert exc_info.value.status_code == 403

        # Case 2: 'traversal' embedded in message
        mock_paths.resolve_virtual_path.side_effect = ValueError("detected path traversal in request")

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="u"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                resolve_thread_virtual_path("t-1", "/mnt/user-data/../../x")
            assert exc_info.value.status_code == 403

    def test_passes_user_id_from_context(self) -> None:
        """The function should pass get_effective_user_id() as user_id."""
        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = Path("/resolved")

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="ctx-user-99"),
        ):
            resolve_thread_virtual_path("t-abc", "/mnt/user-data/outputs/f.txt")

        mock_paths.resolve_virtual_path.assert_called_once_with("t-abc", "/mnt/user-data/outputs/f.txt", user_id="ctx-user-99")

    def test_passes_thread_id_correctly(self) -> None:
        """thread_id is forwarded as the first positional argument."""
        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.return_value = Path("/resolved")

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="u1"),
        ):
            resolve_thread_virtual_path("my-thread-id", "/mnt/user-data/workspace/x.py")

        args = mock_paths.resolve_virtual_path.call_args
        assert args[0][0] == "my-thread-id"

    def test_no_traversal_in_generic_error_message(self) -> None:
        """An error message without 'traversal' gives 400, not 403."""
        mock_paths = MagicMock()
        mock_paths.resolve_virtual_path.side_effect = ValueError("some other error")

        with (
            patch("app.gateway.path_utils.get_paths", return_value=mock_paths),
            patch("app.gateway.path_utils.get_effective_user_id", return_value="u"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                resolve_thread_virtual_path("t-1", "/bad/path")

        assert exc_info.value.status_code == 400
