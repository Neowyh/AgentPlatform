"""Image search import handling and DDGS filter forwarding.

The existing test file patches 'ideer.community.image_search.tools.DDGS' but
DDGS is imported locally inside _search_images, so that attribute doesn't exist.
This file patches the import correctly using patch.dict("sys.modules", ...).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ideer.community.image_search.tools import _search_images

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_ddgs(results=None, side_effect=None):
    """Create a mock ddgs module with a DDGS class."""
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.images.return_value = results if results is not None else []
    if side_effect is not None:
        mock_ddgs_instance.images.side_effect = side_effect
    mock_ddgs_module = MagicMock()
    mock_ddgs_module.DDGS.return_value = mock_ddgs_instance
    return mock_ddgs_module, mock_ddgs_instance


def _sample_ddgs_results():
    return [
        {"title": "Image 1", "thumbnail": "http://img1.jpg", "url": "http://page1"},
        {"title": "Image 2", "thumbnail": "http://img2.jpg", "url": "http://page2"},
    ]


# ===================================================================
# _search_images — using sys.modules patching
# ===================================================================


class TestSearchImages:
    def test_successful_search(self):
        mock_module, mock_ddgs = _make_mock_ddgs(_sample_ddgs_results())

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            results = _search_images("cats", max_results=5)

        assert len(results) == 2
        assert results[0]["title"] == "Image 1"
        mock_ddgs.images.assert_called_once_with(
            "cats",
            region="wt-wt",
            safesearch="moderate",
            max_results=5,
        )

    def test_search_with_all_filters(self):
        mock_module, mock_ddgs = _make_mock_ddgs(_sample_ddgs_results())

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            results = _search_images(
                "dogs",
                max_results=3,
                region="us-en",
                safesearch="strict",
                size="Large",
                color="red",
                type_image="photo",
                layout="Wide",
                license_image="CreativeCommons",
            )

        assert len(results) == 2
        mock_ddgs.images.assert_called_once_with(
            "dogs",
            region="us-en",
            safesearch="strict",
            max_results=3,
            size="Large",
            color="red",
            type_image="photo",
            layout="Wide",
            license_image="CreativeCommons",
        )

    def test_search_no_optional_filters(self):
        mock_module, mock_ddgs = _make_mock_ddgs([])

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            results = _search_images("query")

        assert results == []
        call_kwargs = mock_ddgs.images.call_args[1]
        assert "size" not in call_kwargs
        assert "color" not in call_kwargs
        assert "type_image" not in call_kwargs
        assert "layout" not in call_kwargs
        assert "license_image" not in call_kwargs

    def test_search_returns_none(self):
        mock_module, mock_ddgs = _make_mock_ddgs(results=None)
        mock_ddgs.images.return_value = None

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            results = _search_images("query")

        assert results == []

    def test_search_ddgs_import_error(self):
        with patch.dict("sys.modules", {"ddgs": None}):
            results = _search_images("query")
        assert results == []

    def test_search_exception(self):
        mock_module, mock_ddgs = _make_mock_ddgs(side_effect=RuntimeError("network error"))

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            results = _search_images("query")

        assert results == []

    def test_search_with_partial_filters(self):
        mock_module, mock_ddgs = _make_mock_ddgs([])

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            _search_images("query", size="Large", layout="Square")

        call_kwargs = mock_ddgs.images.call_args[1]
        assert call_kwargs["size"] == "Large"
        assert call_kwargs["layout"] == "Square"
        assert "color" not in call_kwargs
        assert "type_image" not in call_kwargs
        assert "license_image" not in call_kwargs

    def test_search_with_only_color_filter(self):
        mock_module, mock_ddgs = _make_mock_ddgs([])

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            _search_images("query", color="blue")

        call_kwargs = mock_ddgs.images.call_args[1]
        assert call_kwargs["color"] == "blue"
        assert "size" not in call_kwargs
        assert "type_image" not in call_kwargs
        assert "layout" not in call_kwargs
        assert "license_image" not in call_kwargs

    def test_search_with_only_license_filter(self):
        mock_module, mock_ddgs = _make_mock_ddgs([])

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            _search_images("query", license_image="ShareCommercially")

        call_kwargs = mock_ddgs.images.call_args[1]
        assert call_kwargs["license_image"] == "ShareCommercially"
        assert "size" not in call_kwargs
        assert "color" not in call_kwargs

    def test_search_with_only_type_filter(self):
        mock_module, mock_ddgs = _make_mock_ddgs([])

        with patch.dict("sys.modules", {"ddgs": mock_module}):
            _search_images("query", type_image="gif")

        call_kwargs = mock_ddgs.images.call_args[1]
        assert call_kwargs["type_image"] == "gif"
        assert "size" not in call_kwargs
        assert "color" not in call_kwargs
        assert "layout" not in call_kwargs
        assert "license_image" not in call_kwargs
