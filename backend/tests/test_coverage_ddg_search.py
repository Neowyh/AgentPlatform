"""Additional coverage tests for ideer.community.ddg_search.tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ideer.community.ddg_search.tools import _search_text, web_search_tool

# ===========================================================================
# _search_text — core search function
# ===========================================================================


class TestSearchText:
    def test_successful_search(self):
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = [
            {"title": "Result 1", "href": "http://r1.com", "body": "body1"},
            {"title": "Result 2", "href": "http://r2.com", "body": "body2"},
        ]
        with patch.dict("sys.modules", {"ddgs": MagicMock(DDGS=MagicMock(return_value=mock_ddgs))}):
            results = _search_text("python tutorial", max_results=5)
        assert len(results) == 2

    def test_empty_results(self):
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        with patch.dict("sys.modules", {"ddgs": MagicMock(DDGS=MagicMock(return_value=mock_ddgs))}):
            results = _search_text("xyznonexistent")
        assert results == []

    def test_none_results(self):
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = None
        with patch.dict("sys.modules", {"ddgs": MagicMock(DDGS=MagicMock(return_value=mock_ddgs))}):
            results = _search_text("query")
        assert results == []

    def test_import_error(self):
        with patch.dict("sys.modules", {"ddgs": None}):
            results = _search_text("query")
        assert results == []

    def test_exception(self):
        mock_ddgs = MagicMock()
        mock_ddgs.text.side_effect = RuntimeError("network error")
        with patch.dict("sys.modules", {"ddgs": MagicMock(DDGS=MagicMock(return_value=mock_ddgs))}):
            results = _search_text("query")
        assert results == []

    def test_search_with_region(self):
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        with patch.dict("sys.modules", {"ddgs": MagicMock(DDGS=MagicMock(return_value=mock_ddgs))}):
            _search_text("query", region="us-en", safesearch="strict")
        mock_ddgs.text.assert_called_once_with(
            "query",
            region="us-en",
            safesearch="strict",
            max_results=5,
        )


# ===========================================================================
# web_search_tool — LangChain tool wrapper
# ===========================================================================


class TestWebSearchTool:
    def test_returns_results_json(self):
        mock_results = [
            {"title": "Title 1", "href": "http://r1.com", "body": "body1"},
        ]
        with (
            patch("ideer.community.ddg_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.ddg_search.tools._search_text", return_value=mock_results),
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            result = web_search_tool.func(query="python", max_results=5)

        data = json.loads(result)
        assert data["query"] == "python"
        assert data["total_results"] == 1
        assert data["results"][0]["title"] == "Title 1"
        assert data["results"][0]["url"] == "http://r1.com"
        assert data["results"][0]["content"] == "body1"

    def test_no_results_returns_error(self):
        with (
            patch("ideer.community.ddg_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.ddg_search.tools._search_text", return_value=[]),
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            result = web_search_tool.func(query="nonexistent")

        data = json.loads(result)
        assert "error" in data
        assert data["query"] == "nonexistent"

    def test_config_override_max_results(self):
        mock_results = [{"title": "T", "href": "http://r.com", "body": "b"}]
        with (
            patch("ideer.community.ddg_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.ddg_search.tools._search_text", return_value=mock_results) as mock_search,
        ):
            config = MagicMock()
            config.model_extra = {"max_results": 10}
            mock_config_fn.return_value.get_tool_config.return_value = config
            web_search_tool.func(query="test", max_results=5)
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["max_results"] == 10

    def test_no_config_override(self):
        mock_results = [{"title": "T", "href": "http://r.com", "body": "b"}]
        with (
            patch("ideer.community.ddg_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.ddg_search.tools._search_text", return_value=mock_results) as mock_search,
        ):
            config = MagicMock()
            config.model_extra = {}
            mock_config_fn.return_value.get_tool_config.return_value = config
            web_search_tool.func(query="test", max_results=7)
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["max_results"] == 7

    def test_result_normalization_missing_fields(self):
        raw = [
            {"title": "Has title"},
            {"href": "http://r2.com"},
            {},
        ]
        with (
            patch("ideer.community.ddg_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.ddg_search.tools._search_text", return_value=raw),
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            result = web_search_tool.func(query="test")

        data = json.loads(result)
        assert data["total_results"] == 3
        assert data["results"][0]["url"] == ""
        assert data["results"][0]["content"] == ""
        assert data["results"][2]["title"] == ""

    def test_link_field_fallback(self):
        raw = [{"title": "T", "link": "http://fallback.com", "snippet": "s"}]
        with (
            patch("ideer.community.ddg_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.ddg_search.tools._search_text", return_value=raw),
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            result = web_search_tool.func(query="test")

        data = json.loads(result)
        assert data["results"][0]["url"] == "http://fallback.com"
        assert data["results"][0]["content"] == "s"

    def test_none_config(self):
        mock_results = [{"title": "T", "href": "http://r.com", "body": "b"}]
        with (
            patch("ideer.community.ddg_search.tools.get_app_config") as mock_config_fn,
            patch("ideer.community.ddg_search.tools._search_text", return_value=mock_results) as mock_search,
        ):
            mock_config_fn.return_value.get_tool_config.return_value = None
            web_search_tool.func(query="test", max_results=3)
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["max_results"] == 3
