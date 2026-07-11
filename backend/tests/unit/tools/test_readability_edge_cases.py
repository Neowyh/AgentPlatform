"""Tests targeting uncovered lines in readability.py.

Covered uncovered lines:
- Line 25: to_markdown() when html_content is None or empty
- Lines 32-55: to_message() method with images, empty content, fallback
- Line 65: exception handler when stderr is bytes
- Line 77: extract_article() when html_content is empty/missing
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from ideer.utils.readability import Article, ReadabilityExtractor

# ---------------------------------------------------------------------------
# Article.to_markdown  --  line 25 (html_content is None / empty)
# ---------------------------------------------------------------------------


class TestToMarkdownNoContent:
    """Cover line 25: markdown fallback when html_content is falsy."""

    def test_to_markdown_none_content(self):
        article = Article(title="T", html_content=None)
        result = article.to_markdown()
        assert "# T" in result
        assert "*No content available*" in result

    def test_to_markdown_empty_string_content(self):
        article = Article(title="T", html_content="   ")
        result = article.to_markdown()
        assert "# T" in result
        assert "*No content available*" in result

    def test_to_markdown_without_title(self):
        article = Article(title="T", html_content=None)
        result = article.to_markdown(including_title=False)
        assert result.startswith("*No content available*")
        assert "# T" not in result


# ---------------------------------------------------------------------------
# Article.to_message  --  lines 32-55
# ---------------------------------------------------------------------------


class TestToMessage:
    """Cover lines 32-55: the entire to_message() method."""

    def test_to_message_returns_text_when_no_images(self):
        """Plain text content, no images -- single text item returned."""
        article = Article(title="T", html_content="<p>Hello world</p>")
        article.url = "https://example.com"
        messages = article.to_message()
        assert messages
        assert all(m["type"] == "text" for m in messages)

    def test_to_message_with_image(self):
        """Markdown with an image should produce image_url entries."""
        article = Article(
            title="T",
            html_content='<p>Before</p><img src="photo.png" alt="pic"><p>After</p>',
        )
        article.url = "https://example.com/page"
        messages = article.to_message()
        image_msgs = [m for m in messages if m["type"] == "image_url"]
        assert len(image_msgs) >= 1
        # The URL should be resolved relative to article.url
        assert image_msgs[0]["image_url"]["url"].startswith("https://example.com/")

    def test_to_message_empty_content_fallback(self):
        """When html_content is empty, to_markdown produces '*No content available*'
        which is NOT empty, so to_message returns it as text (line 37 check passes)."""
        article = Article(title="", html_content="")
        article.url = "https://example.com"
        messages = article.to_message()
        assert len(messages) == 1
        assert "No content available" in messages[0]["text"]

    def test_to_message_only_whitespace_content(self):
        """Whitespace-only html produces '*No content available*' text."""
        article = Article(title="", html_content="   ")
        article.url = "https://example.com"
        messages = article.to_message()
        assert "No content available" in messages[0]["text"]

    def test_to_message_empty_title_no_content(self):
        """Article with empty title and None html_content."""
        article = Article(title="", html_content=None)
        article.url = "https://example.com"
        messages = article.to_message()
        assert len(messages) >= 1
        all_text = " ".join(m.get("text", "") for m in messages if m["type"] == "text")
        assert "No content available" in all_text

    def test_to_message_mixed_images_and_text(self):
        """Multiple images interleaved with text."""
        html = '<p>Part1</p><img src="a.png"><p>Part2</p><img src="b.png"><p>Part3</p>'
        article = Article(title="T", html_content=html)
        article.url = "https://example.com"
        messages = article.to_message()
        types = [m["type"] for m in messages]
        assert "image_url" in types
        assert "text" in types

    def test_to_message_includes_title(self):
        """Title should appear as text in the message list."""
        article = Article(title="My Title", html_content="<p>body</p>")
        article.url = "https://example.com"
        messages = article.to_message()
        all_text = " ".join(m.get("text", "") for m in messages if m["type"] == "text")
        assert "My Title" in all_text

    def test_to_message_early_return_when_markdown_empty(self):
        """Cover lines 37-38: to_markdown returns empty string."""
        article = Article(title="T", html_content="<p>x</p>")
        article.url = "https://example.com"
        # Force to_markdown to return empty string to hit the early return
        with patch.object(article, "to_markdown", return_value=""):
            messages = article.to_message()
        assert len(messages) == 1
        assert messages[0] == {"type": "text", "text": "No content available"}

    def test_to_message_fallback_after_processing(self):
        """Cover lines 52-53: content list is empty after processing all parts.
        Mock re.split so that even though to_markdown returns a non-empty
        string (passing line 37), the split produces only empty text parts
        with no images, leaving content empty."""
        article = Article(title="", html_content="x")
        article.url = "https://example.com"
        with patch.object(article, "to_markdown", return_value="nonempty"), patch("ideer.utils.readability.re.split", return_value=[""]):
            messages = article.to_message()
        # Both parts are empty strings; text parts are stripped to "" and skipped;
        # no odd-index parts exist (all indices are even), so content stays []
        # -> fallback at line 52-53 triggers
        assert len(messages) == 1
        assert messages[0] == {"type": "text", "text": "No content available"}


# ---------------------------------------------------------------------------
# ReadabilityExtractor.extract_article  --  line 65 (bytes stderr)
# ---------------------------------------------------------------------------


class TestExtractArticleBytesStderr:
    """Cover line 65: exception handler receives bytes stderr."""

    def test_extract_article_fallback_with_bytes_stderr(self, monkeypatch):
        """When CalledProcessError has bytes stderr, it should be decoded."""
        calls: list[bool] = []

        def _fake_simple_json(html: str, use_readability: bool = False):
            calls.append(use_readability)
            if use_readability:
                exc = subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["node"],
                )
                exc.stderr = b"binary error \xff\xfe output"
                raise exc
            return {"title": "FB", "content": "<p>ok</p>"}

        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            _fake_simple_json,
        )

        extractor = ReadabilityExtractor()
        article = extractor.extract_article("<html><body>x</body></html>")
        assert calls == [True, False]
        assert article.title == "FB"

    def test_extract_article_fallback_with_none_stderr(self, monkeypatch):
        """When CalledProcessError has no stderr attribute, logger still works."""

        def _fake_simple_json(html: str, use_readability: bool = False):
            if use_readability:
                exc = subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["node"],
                )
                exc.stderr = None
                raise exc
            return {"title": "T", "content": "<p>ok</p>"}

        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            _fake_simple_json,
        )

        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.title == "T"

    def test_extract_article_fallback_with_empty_bytes_stderr(self, monkeypatch):
        """When stderr is empty bytes, no stderr info is appended."""

        def _fake_simple_json(html: str, use_readability: bool = False):
            if use_readability:
                exc = subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["node"],
                )
                exc.stderr = b""
                raise exc
            return {"title": "T", "content": "<p>ok</p>"}

        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            _fake_simple_json,
        )

        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.title == "T"


# ---------------------------------------------------------------------------
# ReadabilityExtractor.extract_article  --  line 77 (empty html_content)
# ---------------------------------------------------------------------------


class TestExtractArticleEmptyContent:
    """Cover line 77: html_content is empty or missing -> default string."""

    def test_extract_article_no_content_key(self, monkeypatch):
        """When article dict has no 'content' key, fallback is used."""
        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            lambda html, use_readability=False: {"title": "T"},
        )
        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.html_content == "No content could be extracted from this page"

    def test_extract_article_empty_content_string(self, monkeypatch):
        """When content is empty string, fallback is used."""
        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            lambda html, use_readability=False: {"title": "T", "content": ""},
        )
        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.html_content == "No content could be extracted from this page"

    def test_extract_article_whitespace_content(self, monkeypatch):
        """When content is whitespace-only, fallback is used."""
        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            lambda html, use_readability=False: {"title": "T", "content": "   "},
        )
        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.html_content == "No content could be extracted from this page"

    def test_extract_article_no_title_key(self, monkeypatch):
        """When title is missing, default 'Untitled' is used (line 81)."""
        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            lambda html, use_readability=False: {"content": "<p>text</p>"},
        )
        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.title == "Untitled"
        assert article.html_content == "<p>text</p>"

    def test_extract_article_empty_title(self, monkeypatch):
        """When title is empty string, default 'Untitled' is used."""
        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            lambda html, use_readability=False: {"title": "", "content": "<p>ok</p>"},
        )
        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.title == "Untitled"

    def test_extract_article_happy_path(self, monkeypatch):
        """Normal extraction returns title and content."""
        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            lambda html, use_readability=False: {
                "title": "Real Title",
                "content": "<p>Real content</p>",
            },
        )
        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.title == "Real Title"
        assert article.html_content == "<p>Real content</p>"


# ---------------------------------------------------------------------------
# FileNotFoundError fallback  --  another path to line 65
# ---------------------------------------------------------------------------


class TestExtractArticleFileNotFoundError:
    """FileNotFoundError is also caught and triggers fallback."""

    def test_extract_article_file_not_found(self, monkeypatch):
        def _fake_simple_json(html: str, use_readability: bool = False):
            if use_readability:
                raise FileNotFoundError("node binary not found")
            return {"title": "FB", "content": "<p>fallback</p>"}

        monkeypatch.setattr(
            "ideer.utils.readability.simple_json_from_html_string",
            _fake_simple_json,
        )

        article = ReadabilityExtractor().extract_article("<html></html>")
        assert article.title == "FB"
        assert article.html_content == "<p>fallback</p>"
