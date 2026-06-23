"""Tests for ideer.community.image_search.tools — comprehensive coverage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ideer.community.image_search.tools import _search_images, image_search_tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_ddgs_results():
    return [
        {"title": "Image 1", "thumbnail": "http://img1.jpg", "url": "http://page1"},
        {"title": "Image 2", "thumbnail": "http://img2.jpg", "url": "http://page2"},
    ]


def _make_tool_config(max_results: int | None = None):
    cfg = MagicMock()
    if max_results is not None:
        cfg.model_extra = {"max_results": max_results}
    else:
        cfg.model_extra = {}
    return cfg


# ===================================================================
# _search_images — core search function
# ===================================================================


class TestSearchImages:
    def test_successful_search(self):
        mock_ddgs = MagicMock()
        mock_ddgs.images.return_value = _sample_ddgs_results()

        with patch("ddgs.DDGS", return_value=mock_ddgs):
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
        mock_ddgs = MagicMock()
        mock_ddgs.images.return_value = _sample_ddgs_results()

        with patch("ddgs.DDGS", return_value=mock_ddgs):
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
        mock_ddgs = MagicMock()
        mock_ddgs.images.return_value = []

        with patch("ddgs.DDGS", return_value=mock_ddgs):
            results = _search_images("query")

        assert results == []
        call_kwargs = mock_ddgs.images.call_args[1]
        assert "size" not in call_kwargs
        assert "color" not in call_kwargs
        assert "type_image" not in call_kwargs
        assert "layout" not in call_kwargs
        assert "license_image" not in call_kwargs

    def test_search_returns_none(self):
        mock_ddgs = MagicMock()
        mock_ddgs.images.return_value = None

        with patch("ddgs.DDGS", return_value=mock_ddgs):
            results = _search_images("query")

        assert results == []

    def test_search_ddgs_import_error(self):
        with patch.dict("sys.modules", {"ddgs": None}):
            results = _search_images("query")
        assert results == []

    def test_search_exception(self):
        mock_ddgs = MagicMock()
        mock_ddgs.images.side_effect = RuntimeError("network error")

        with patch("ddgs.DDGS", return_value=mock_ddgs):
            results = _search_images("query")

        assert results == []

    def test_search_with_partial_filters(self):
        mock_ddgs = MagicMock()
        mock_ddgs.images.return_value = []

        with patch("ddgs.DDGS", return_value=mock_ddgs):
            _search_images("query", size="Large", layout="Square")

        call_kwargs = mock_ddgs.images.call_args[1]
        assert call_kwargs["size"] == "Large"
        assert call_kwargs["layout"] == "Square"
        assert "color" not in call_kwargs
        assert "type_image" not in call_kwargs
        assert "license_image" not in call_kwargs


# ===================================================================
# image_search_tool — LangChain tool wrapper
# ===================================================================


class TestImageSearchTool:
    def test_returns_results_json(self):
        mock_results = _sample_ddgs_results()

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=mock_results),
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            result = image_search_tool.func(query="cats")

        data = json.loads(result)
        assert data["query"] == "cats"
        assert data["total_results"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["title"] == "Image 1"
        assert data["results"][0]["image_url"] == "http://img1.jpg"
        assert data["results"][0]["thumbnail_url"] == "http://img1.jpg"
        assert "usage_hint" in data

    def test_returns_error_on_no_results(self):
        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=[]),
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            result = image_search_tool.func(query="nonexistent")

        data = json.loads(result)
        assert "error" in data
        assert data["query"] == "nonexistent"

    def test_config_override_max_results(self):
        mock_results = _sample_ddgs_results()

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=mock_results) as mock_search,
        ):
            config = _make_tool_config(max_results=10)
            mock_config_fn.return_value.get_tool_config.return_value = config
            image_search_tool.func(query="cats", max_results=5)

        # Should use config max_results=10 instead of passed 5
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["max_results"] == 10

    def test_no_config_override_when_not_set(self):
        mock_results = _sample_ddgs_results()

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=mock_results) as mock_search,
        ):
            config = _make_tool_config()  # no max_results in model_extra
            mock_config_fn.return_value.get_tool_config.return_value = config
            image_search_tool.func(query="cats", max_results=7)

        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["max_results"] == 7

    def test_none_config_no_override(self):
        mock_results = _sample_ddgs_results()

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=mock_results) as mock_search,
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            image_search_tool.func(query="cats", max_results=3)

        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["max_results"] == 3

    def test_passes_optional_filters(self):
        mock_results = _sample_ddgs_results()

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=mock_results) as mock_search,
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            image_search_tool.func(
                query="cats",
                max_results=5,
                size="Large",
                type_image="photo",
                layout="Wide",
            )

        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["size"] == "Large"
        assert call_kwargs["type_image"] == "photo"
        assert call_kwargs["layout"] == "Wide"

    def test_default_values(self):
        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=[]) as mock_search,
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            image_search_tool.func(query="test")

        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["max_results"] == 5
        assert call_kwargs["size"] is None
        assert call_kwargs["type_image"] is None
        assert call_kwargs["layout"] is None

    def test_result_normalization_missing_fields(self):
        # Results with missing fields
        raw_results = [
            {"title": "Has title"},
            {"thumbnail": "http://thumb.jpg"},
            {},
        ]

        with (
            patch("ideer.community.image_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.image_search.tools._search_images", return_value=raw_results),
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            result = image_search_tool.func(query="test")

        data = json.loads(result)
        assert data["total_results"] == 3
        assert data["results"][0]["image_url"] == ""  # no thumbnail
        assert data["results"][1]["title"] == ""  # no title
        assert data["results"][2]["title"] == ""
        assert data["results"][2]["image_url"] == ""
