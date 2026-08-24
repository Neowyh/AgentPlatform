"""Comprehensive tests for doc_reader/tools.py targeting 98%+ coverage.

Covers every function and branch in
``packages/harness/ideer/community/doc_reader/tools.py``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.community.doc_reader.tools import (
    _ALLOWED_PATH_PREFIXES,
    _DEFAULT_MAX_CHARS,
    _MAX_FILE_SIZE,
    _SUPPORTED_EXTENSIONS,
    _extract_pdf_pages,
    _get_page_count,
    _parse_page_range,
    _resolve_mounted_path,
    _resolve_virtual_path,
    _truncate_output,
    _validate_path,
    read_document_tool,
)

# ============================================================================
# Helpers
# ============================================================================

_TMP_PREFIX = "/tmp/test_doc_reader_"


def _make_tmp_file(suffix: str = ".pdf", content: bytes = b"x" * 10) -> str:
    """Create a temporary file under /tmp and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix, dir="/tmp", prefix="test_doc_reader_")
    os.write(fd, content)
    os.close(fd)
    return path


def _cleanup(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# ============================================================================
# _validate_path
# ============================================================================


class TestValidatePath:
    """Tests for _validate_path."""

    def test_allowed_prefix_tmp(self):
        result = _validate_path("/tmp/somefile.pdf")
        assert isinstance(result, Path)
        assert str(result).startswith("/tmp")

    def test_allowed_prefix_mnt(self):
        result = _validate_path("/mnt/user-data/uploads/test.pdf")
        assert isinstance(result, Path)

    def test_disallowed_prefix_raises(self):
        with pytest.raises(PermissionError, match="Access denied"):
            _validate_path("/etc/passwd")

    def test_disallowed_root_raises(self):
        with pytest.raises(PermissionError, match="Access denied"):
            _validate_path("/home/user/doc.pdf")

    def test_path_is_resolved(self):
        result = _validate_path("/tmp/../tmp/test.pdf")
        assert ".." not in str(result)


# ============================================================================
# _truncate_output
# ============================================================================


class TestTruncateOutput:
    """Tests for _truncate_output."""

    def test_max_chars_zero_returns_full_text(self):
        text = "a" * 1000
        assert _truncate_output(text, 0) == text

    def test_text_shorter_than_max(self):
        text = "hello"
        assert _truncate_output(text, 100) == "hello"

    def test_text_equal_to_max(self):
        text = "a" * 50
        assert _truncate_output(text, 50) == text

    def test_text_longer_than_max_truncates(self):
        text = "a" * 1000
        result = _truncate_output(text, 100)
        assert len(result) <= 100
        assert result.startswith("a")
        assert "truncated" in result

    def test_truncation_marker_format(self):
        text = "x" * 200
        result = _truncate_output(text, 80)
        assert "showing first" in result
        assert "of 200 chars" in result

    def test_very_small_max_chars_with_marker(self):
        """When marker itself exceeds max_chars, returns text[:max_chars]."""
        text = "a" * 10000
        # Use a very small max_chars so that kept <= 0
        result = _truncate_output(text, 5)
        # If kept <= 0, returns text[:max_chars]
        assert len(result) == 5

    def test_max_chars_exactly_marker_length(self):
        """Edge case where max_chars barely fits the marker."""
        text = "a" * 200
        marker = f"\n... [truncated: showing first {50} of {200} chars] ..."
        # Set max_chars equal to marker length
        result = _truncate_output(text, len(marker))
        # kept = max_chars - len(marker) = 0, so text[:max_chars]
        assert len(result) == len(marker)


# ============================================================================
# _get_page_count
# ============================================================================


class TestGetPageCount:
    """Tests for _get_page_count."""

    def test_non_pdf_returns_none(self):
        path = Path("/tmp/test.docx")
        assert _get_page_count(path) is None

    def test_pdf_with_pymupdf_installed(self):
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=42)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_pymupdf = ModuleType("pymupdf")
        mock_pymupdf.open = MagicMock(return_value=mock_doc)

        with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
            result = _get_page_count(Path("/tmp/test.pdf"))

        assert result == 42

    def test_pdf_pymupdf_not_installed(self):

        with patch.dict("sys.modules", {"pymupdf": None}):
            result = _get_page_count(Path("/tmp/test.pdf"))

        assert result is None

    def test_pdf_pymupdf_raises_exception(self):
        mock_pymupdf = ModuleType("pymupdf")
        mock_pymupdf.open = MagicMock(side_effect=RuntimeError("corrupt"))

        with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
            result = _get_page_count(Path("/tmp/test.pdf"))

        assert result is None


# ============================================================================
# _parse_page_range
# ============================================================================


class TestParsePageRange:
    """Tests for _parse_page_range."""

    def test_single_page(self):
        assert _parse_page_range("3") == [2]

    def test_range(self):
        assert _parse_page_range("1-5") == [0, 1, 2, 3, 4]

    def test_mixed_range_and_single(self):
        assert _parse_page_range("1-3,7") == [0, 1, 2, 6]

    def test_complex_range(self):
        assert _parse_page_range("1-3,7,10-12") == [0, 1, 2, 6, 9, 10, 11]

    def test_invalid_format(self):
        assert _parse_page_range("abc") is None

    def test_zero_page_returns_none(self):
        assert _parse_page_range("0") is None

    def test_reversed_range_returns_none(self):
        assert _parse_page_range("5-2") is None

    def test_empty_string_returns_none(self):
        assert _parse_page_range("") is None

    def test_negative_number_returns_none(self):
        assert _parse_page_range("-1") is None

    def test_whitespace_handling(self):
        assert _parse_page_range(" 1 - 3 , 7 ") == [0, 1, 2, 6]

    def test_range_exceeding_max_pages(self):
        # _MAX_PAGES = 10000, so 1-10001 should be None
        assert _parse_page_range("1-10001") is None

    def test_total_pages_exceeding_max(self):
        # Many individual pages exceeding _MAX_PAGES
        pages = ",".join(str(i) for i in range(1, 10002))
        assert _parse_page_range(pages) is None

    def test_single_page_zero_in_range(self):
        # start=0 is invalid
        assert _parse_page_range("0-5") is None

    def test_non_string_input_returns_none(self):
        # AttributeError branch
        assert _parse_page_range(None) is None

    def test_float_input_returns_none(self):
        # ValueError branch
        assert _parse_page_range("1.5") is None


# ============================================================================
# _extract_pdf_pages
# ============================================================================


class TestExtractPdfPages:
    """Tests for _extract_pdf_pages."""

    def test_pymupdf4llm_not_installed(self):

        with patch.dict("sys.modules", {"pymupdf4llm": None}):
            result = _extract_pdf_pages(Path("/tmp/test.pdf"), "1-5")

        assert result is None

    def test_invalid_page_range_returns_none(self):
        mock_pymupdf4llm = ModuleType("pymupdf4llm")
        mock_pymupdf4llm.to_markdown = MagicMock()

        with patch.dict("sys.modules", {"pymupdf4llm": mock_pymupdf4llm}):
            result = _extract_pdf_pages(Path("/tmp/test.pdf"), "abc")

        assert result is None
        mock_pymupdf4llm.to_markdown.assert_not_called()

    def test_successful_extraction(self):
        mock_pymupdf4llm = ModuleType("pymupdf4llm")
        mock_pymupdf4llm.to_markdown = MagicMock(return_value="# Page Content")

        with patch.dict("sys.modules", {"pymupdf4llm": mock_pymupdf4llm}):
            result = _extract_pdf_pages(Path("/tmp/test.pdf"), "1-3")

        assert result == "# Page Content"
        mock_pymupdf4llm.to_markdown.assert_called_once()

    def test_extraction_raises_exception(self):
        mock_pymupdf4llm = ModuleType("pymupdf4llm")
        mock_pymupdf4llm.to_markdown = MagicMock(side_effect=RuntimeError("bad pdf"))

        with patch.dict("sys.modules", {"pymupdf4llm": mock_pymupdf4llm}):
            result = _extract_pdf_pages(Path("/tmp/test.pdf"), "1-5")

        assert result is None


# ============================================================================
# read_document_tool — error paths
# ============================================================================


class TestReadDocumentToolErrors:
    """Tests for error branches in read_document_tool."""

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        result = await read_document_tool.ainvoke({"file_path": "/etc/passwd"})
        data = json.loads(result)
        assert "error" in data
        assert "access denied" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_path_traversal_rejected(self):
        result = await read_document_tool.ainvoke({"file_path": "/mnt/user-data/../../../etc/passwd"})
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        result = await read_document_tool.ainvoke({"file_path": "/tmp/definitely_does_not_exist_99999.pdf"})
        data = json.loads(result)
        assert "error" in data
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_path_is_directory(self):
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="test_doc_reader_") as d:
            result = await read_document_tool.ainvoke({"file_path": d})
            data = json.loads(result)
            assert "error" in data
            assert "not a file" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_unsupported_extension(self):
        path = _make_tmp_file(suffix=".xyz")
        try:
            result = await read_document_tool.ainvoke({"file_path": path})
            data = json.loads(result)
            assert "error" in data
            assert "unsupported" in data["error"].lower()
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        path = _make_tmp_file(suffix=".pdf", content=b"x")
        try:
            import stat as stat_mod

            with patch("packages.harness.ideer.community.doc_reader.tools.Path.stat") as mock_stat:
                mock_stat_result = MagicMock()
                mock_stat_result.st_size = _MAX_FILE_SIZE + 1
                # is_file() also calls stat() and checks S_ISREG(st_mode)
                mock_stat_result.st_mode = stat_mod.S_IFREG
                mock_stat.return_value = mock_stat_result

                result = await read_document_tool.ainvoke({"file_path": path})
                data = json.loads(result)
                assert "error" in data
                assert "too large" in data["error"].lower()
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_conversion_raises_exception(self):
        path = _make_tmp_file(suffix=".docx")
        try:
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                side_effect=RuntimeError("boom"),
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                data = json.loads(result)
                assert "error" in data
                assert "failed to convert" in data["error"].lower()
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_conversion_returns_none(self):
        path = _make_tmp_file(suffix=".docx")
        try:
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                data = json.loads(result)
                assert "error" in data
                assert "failed to convert" in data["error"].lower()
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_converted_file_not_found(self):
        path = _make_tmp_file(suffix=".docx")
        try:
            fake_md_path = Path("/tmp/nonexistent_output.md")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=fake_md_path,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                data = json.loads(result)
                assert "error" in data
                assert "not found" in data["error"].lower()
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_converted_file_read_error(self):
        path = _make_tmp_file(suffix=".docx")
        md_path = Path(path).with_suffix(".md")
        try:
            # Create the md file so md_path.exists() passes
            md_path.write_text("placeholder", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
                patch.object(Path, "read_text", side_effect=PermissionError("no read access")),
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                data = json.loads(result)
                assert "error" in data
                assert "failed to read" in data["error"].lower()
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_empty_conversion_output(self):
        path = _make_tmp_file(suffix=".docx")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("   \n  ", encoding="utf-8")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                data = json.loads(result)
                assert "error" in data
                assert "empty" in data["error"].lower()
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass


# ============================================================================
# read_document_tool — success paths
# ============================================================================


class TestReadDocumentToolSuccess:
    """Tests for successful document reading."""

    @pytest.mark.asyncio
    async def test_successful_non_pdf_conversion(self):
        """Non-PDF file: full doc conversion with header, no page count."""
        path = _make_tmp_file(suffix=".docx")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("# Hello World\n\nSome content.", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=None,
                ),
            ):
                # The tool returns markdown with an HTML comment header, not JSON
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "file:" in result
                assert "Hello World" in result
                assert "Some content" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_successful_pdf_with_page_count(self):
        """PDF file: full doc conversion with page count in header."""
        path = _make_tmp_file(suffix=".pdf")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("# PDF Content\n\nSome text.", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=10,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "file:" in result
                assert "pages: 10" in result
                assert "PDF Content" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_successful_xlsx_conversion(self):
        """Excel file converted successfully."""
        path = _make_tmp_file(suffix=".xlsx")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("| Col1 | Col2 |\n|---|---|\n| A | B |", encoding="utf-8")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "Col1" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_successful_pptx_conversion(self):
        """PowerPoint file converted successfully."""
        path = _make_tmp_file(suffix=".pptx")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("# Slide 1\n\nContent here.", encoding="utf-8")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "Slide 1" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_metadata_header_contains_file_info(self):
        """Header includes file name and size."""
        path = _make_tmp_file(suffix=".docx", content=b"test content here")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("Body text.", encoding="utf-8")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "<!-- file:" in result
                assert "size:" in result
                assert "bytes" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_safe_name_replaces_arrow(self):
        """File name with --> gets sanitized to -- > in header."""
        # Create a file with --> in the name
        dir_path = tempfile.mkdtemp(dir="/tmp", prefix="test_doc_reader_")
        dangerous_name = "test-->file.docx"
        path = os.path.join(dir_path, dangerous_name)
        with open(path, "wb") as f:
            f.write(b"content")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("Body.", encoding="utf-8")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "-- >" in result
                assert "-->" not in result.split("file:")[1].split("|")[0]
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass
            try:
                os.rmdir(dir_path)
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_output_truncation_for_large_content(self):
        """Content exceeding _DEFAULT_MAX_CHARS gets truncated."""
        path = _make_tmp_file(suffix=".docx")
        md_path = Path(path).with_suffix(".md")
        try:
            large_content = "x" * (_DEFAULT_MAX_CHARS + 10000)
            md_path.write_text(large_content, encoding="utf-8")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "truncated" in result
                assert len(result) <= _DEFAULT_MAX_CHARS
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_cleanup_md_file_on_success(self):
        """Temporary .md sidecar file is cleaned up after reading."""
        path = _make_tmp_file(suffix=".docx")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("Content.", encoding="utf-8")
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ):
                await read_document_tool.ainvoke({"file_path": path})
                # md_path should have been deleted
                assert not md_path.exists()
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass


# ============================================================================
# read_document_tool — PDF page-range extraction
# ============================================================================


class TestReadDocumentToolPdfPageRange:
    """Tests for PDF page-range extraction path."""

    @pytest.mark.asyncio
    async def test_pdf_page_range_success(self):
        """Page-range extraction succeeds: uses extracted text directly."""
        path = _make_tmp_file(suffix=".pdf")
        try:
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._extract_pdf_pages",
                    return_value="# Pages 1-3 content",
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=10,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path, "page_range": "1-3"})
                assert "Pages 1-3 content" in result
                assert "pages: 10 (showing 1-3)" in result
                assert "<!-- file:" in result
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_pdf_page_range_no_page_count(self):
        """Page-range extraction succeeds but _get_page_count returns None."""
        path = _make_tmp_file(suffix=".pdf")
        try:
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._extract_pdf_pages",
                    return_value="# Extracted pages",
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=None,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path, "page_range": "1-5"})
                assert "Extracted pages" in result
                assert "pages:" not in result
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_pdf_page_range_fails_falls_back_to_full_doc(self):
        """Page-range extraction returns None -> falls back to full conversion."""
        path = _make_tmp_file(suffix=".pdf")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("# Full Document Content", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._extract_pdf_pages",
                    return_value=None,
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=5,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path, "page_range": "1-3"})
                assert "Full Document Content" in result
                assert "pages: 5" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_pdf_page_range_truncation(self):
        """Page-range output exceeding max chars gets truncated."""
        path = _make_tmp_file(suffix=".pdf")
        try:
            large_text = "x" * (_DEFAULT_MAX_CHARS + 5000)
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._extract_pdf_pages",
                    return_value=large_text,
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=100,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path, "page_range": "1-50"})
                assert "truncated" in result
                assert len(result) <= _DEFAULT_MAX_CHARS
        finally:
            _cleanup(path)

    @pytest.mark.asyncio
    async def test_non_pdf_with_page_range_ignores_range(self):
        """page_range on non-PDF file is ignored; uses full conversion."""
        path = _make_tmp_file(suffix=".docx")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("Word content.", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._extract_pdf_pages",
                ) as mock_extract,
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path, "page_range": "1-5"})
                mock_extract.assert_not_called()
                assert "Word content" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_pdf_no_page_range_uses_full_conversion(self):
        """PDF without page_range uses full document conversion."""
        path = _make_tmp_file(suffix=".pdf")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("# Full PDF Content", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=20,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "Full PDF Content" in result
                assert "pages: 20" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink()
            except OSError:
                pass


# ============================================================================
# read_document_tool — finally block / unlink
# ============================================================================


class TestReadDocumentToolCleanup:
    """Tests for the finally block cleanup of .md sidecar files."""

    @pytest.mark.asyncio
    async def test_unlink_os_error_caught(self):
        """OSError during md_path.unlink is silently caught."""
        path = _make_tmp_file(suffix=".docx")
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("Content.", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
                patch.object(Path, "unlink", side_effect=OSError("permission denied")),
            ):
                # Should not raise even though unlink fails
                result = await read_document_tool.ainvoke({"file_path": path})
                assert "Content" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink(missing_ok=True)
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_unlink_called_on_conversion_exception(self):
        """When conversion raises, there is no md_path to unlink (None returned)."""
        path = _make_tmp_file(suffix=".docx")
        try:
            with patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                data = json.loads(result)
                assert "error" in data
        finally:
            _cleanup(path)


# ============================================================================
# read_document_tool — all supported extensions
# ============================================================================


class TestSupportedExtensions:
    """Verify all declared supported extensions are accepted."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "suffix",
        [".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt"],
    )
    async def test_each_supported_extension(self, suffix: str):
        path = _make_tmp_file(suffix=suffix)
        md_path = Path(path).with_suffix(".md")
        try:
            md_path.write_text("Content.", encoding="utf-8")
            with (
                patch(
                    "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                    new_callable=AsyncMock,
                    return_value=md_path,
                ),
                patch(
                    "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                    return_value=None,
                ),
            ):
                result = await read_document_tool.ainvoke({"file_path": path})
                # Should NOT contain "unsupported" error
                data = json.loads(result) if result.startswith("{") else None
                if data is not None:
                    assert "error" not in data or "unsupported" not in data.get("error", "").lower()
                assert "Content" in result
        finally:
            _cleanup(path)
            try:
                md_path.unlink(missing_ok=True)
            except OSError:
                pass

    def test_supported_extensions_set(self):
        """Module constant contains expected extensions (legacy .doc excluded)."""
        expected = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt"}
        assert _SUPPORTED_EXTENSIONS == expected

    @pytest.mark.asyncio
    async def test_legacy_doc_rejected_with_conversion_hint(self):
        """Legacy .doc files get a dedicated error telling users to convert."""
        path = _make_tmp_file(suffix=".doc")
        try:
            result = await read_document_tool.ainvoke({"file_path": path})
            data = json.loads(result)
            assert "error" in data
            assert ".docx" in data["error"]
            assert "convert" in data["error"].lower()
        finally:
            _cleanup(path)

    def test_allowed_path_prefixes(self):
        """Module constant for allowed prefixes."""
        assert "/tmp" in _ALLOWED_PATH_PREFIXES
        assert "/mnt/user-data" in _ALLOWED_PATH_PREFIXES

    def test_default_max_chars(self):
        assert _DEFAULT_MAX_CHARS == 50_000

    def test_max_file_size(self):
        assert _MAX_FILE_SIZE == 100_000_000


# ============================================================================
# read_document_tool — virtual /mnt/user-data path resolution
# ============================================================================


class TestVirtualPathResolution:
    """Virtual /mnt/user-data paths resolve to host paths via runtime thread_data.

    Regression coverage for the workflow gap: agent nodes receive sandbox
    virtual paths (``/mnt/user-data/uploads/<case>/x.docx``) which previously
    failed with "File not found" because read_document never resolved them.
    """

    @pytest.fixture()
    def thread_env(self, tmp_path: Path):
        """Create a host uploads dir + a real ToolRuntime carrying thread_data."""
        from langchain.tools import ToolRuntime

        uploads = tmp_path / "user-data" / "uploads"
        uploads.mkdir(parents=True)
        runtime = ToolRuntime(
            state={
                "thread_data": {
                    "workspace_path": str(tmp_path / "user-data" / "workspace"),
                    "uploads_path": str(uploads),
                    "outputs_path": str(tmp_path / "user-data" / "outputs"),
                }
            },
            context={"thread_id": "probe-thread"},
            config={"configurable": {"thread_id": "probe-thread"}},
            stream_writer=lambda _update: None,
            tools=[],
            tool_call_id=None,
            store=None,
        )
        return runtime, uploads

    @pytest.mark.asyncio
    async def test_virtual_upload_path_resolves_and_reads(self, thread_env, tmp_path: Path):
        runtime, uploads = thread_env
        doc = uploads / "case" / "report.docx"
        doc.parent.mkdir(parents=True)
        doc.write_bytes(b"fake-docx")
        md_path = tmp_path / "report.md"
        md_path.write_text("# 转换后的内容", encoding="utf-8")

        with (
            patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ),
            patch(
                "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                return_value=None,
            ),
        ):
            result = await read_document_tool.ainvoke({"runtime": runtime, "file_path": "/mnt/user-data/uploads/case/report.docx"})
        assert "转换后的内容" in result

    @pytest.mark.asyncio
    async def test_virtual_output_path_reads(self, thread_env):
        runtime, _uploads = thread_env
        outputs = Path(runtime.state["thread_data"]["outputs_path"])
        outputs.mkdir(parents=True, exist_ok=True)
        doc = outputs / "brief.pdf"
        doc.write_bytes(b"%PDF-1.4 fake")
        # page-range extraction path avoids convert_file_to_markdown entirely.
        with patch(
            "packages.harness.ideer.community.doc_reader.tools._extract_pdf_pages",
            return_value="# 页面内容",
        ):
            result = await read_document_tool.ainvoke(
                {
                    "runtime": runtime,
                    "file_path": "/mnt/user-data/outputs/brief.pdf",
                    "page_range": "1",
                }
            )
        assert "# 页面内容" in result

    @pytest.mark.asyncio
    async def test_virtual_path_missing_file_reports_original_name(self, thread_env):
        runtime, _uploads = thread_env
        result = await read_document_tool.ainvoke({"runtime": runtime, "file_path": "/mnt/user-data/uploads/nope.docx"})
        data = json.loads(result)
        assert data["error"] == "File not found: /mnt/user-data/uploads/nope.docx"

    @pytest.mark.asyncio
    async def test_no_runtime_keeps_literal_prefix_whitelist(self):
        """Without a runtime, literal /mnt/user-data paths behave as before."""
        result = await read_document_tool.ainvoke({"file_path": "/mnt/user-data/uploads/definitely_missing_12345.docx"})
        assert json.loads(result)["error"].startswith("File not found")

    def test_unresolved_escape_still_blocked(self):
        with pytest.raises(PermissionError):
            _validate_path("/mnt/user-data/../../../etc/passwd")

    def test_resolve_virtual_path_noop_cases(self):
        assert _resolve_virtual_path("/tmp/x.pdf", None) == "/tmp/x.pdf"
        from langchain.tools import ToolRuntime

        runtime = ToolRuntime(
            state={"thread_data": {"uploads_path": "/host/uploads"}},
            context={},
            config={},
            stream_writer=lambda _update: None,
            tools=[],
            tool_call_id=None,
            store=None,
        )
        assert _resolve_virtual_path("/tmp/x.pdf", runtime) == "/tmp/x.pdf"
        assert _resolve_virtual_path("/mnt/user-data/uploads/a.pdf", None) == "/mnt/user-data/uploads/a.pdf"
        assert _resolve_virtual_path("/mnt/user-data/uploads/a.pdf", runtime) == "/host/uploads/a.pdf"


# ============================================================================
# read_document_tool — configured sandbox.mounts (custom mount) resolution
# ============================================================================


class TestCustomMountResolution:
    """Paths under configured ``sandbox.mounts`` resolve container_path -> host_path.

    The resolution chain is: thread_data virtual paths, then registered custom
    mounts (shared source of truth with sandbox tools and the workflow engine),
    then the literal whitelist fallback.
    """

    @pytest.fixture()
    def mounted_env(self, tmp_path: Path, monkeypatch):
        """Register a real tmp-dir mount via the shared _get_custom_mounts cache.

        The ideer package is importable under two module identities
        (``ideer.*`` used by production code and ``packages.harness.ideer.*``
        used by tests), so both module objects must be patched.
        """
        host_dir = tmp_path / "eval-host"
        host_dir.mkdir()
        mounts = [SimpleNamespace(host_path=str(host_dir), container_path="/mnt/eval-case", read_only=True)]
        import packages.harness.ideer.sandbox.tools as _sbx_alt

        for sbx in {_get_sandbox_tools_module(), _sbx_alt}:
            monkeypatch.setattr(sbx, "_get_custom_mounts", lambda mounts=mounts: mounts)
        yield host_dir

    def _patch_conversion(self, md_path: Path):
        return (
            patch(
                "packages.harness.ideer.community.doc_reader.tools.convert_file_to_markdown",
                new_callable=AsyncMock,
                return_value=md_path,
            ),
            patch(
                "packages.harness.ideer.community.doc_reader.tools._get_page_count",
                return_value=None,
            ),
        )

    @pytest.mark.asyncio
    async def test_mounted_docx_resolves_and_reads(self, mounted_env, tmp_path: Path):
        doc = mounted_env / "case-01" / "report.docx"
        doc.parent.mkdir(parents=True)
        doc.write_bytes(b"fake-docx")
        md_path = tmp_path / "report.md"
        md_path.write_text("# 挂载目录内容", encoding="utf-8")
        conv, page = self._patch_conversion(md_path)
        with conv, page:
            result = await read_document_tool.ainvoke({"file_path": "/mnt/eval-case/case-01/report.docx"})
        assert "挂载目录内容" in result

    @pytest.mark.asyncio
    async def test_unregistered_mount_prefix_still_rejected(self):
        result = await read_document_tool.ainvoke({"file_path": "/mnt/not-registered/secret.pdf"})
        data = json.loads(result)
        assert data["error"].startswith("Access denied")

    @pytest.mark.asyncio
    async def test_invisible_mount_gets_deployment_hint(self, tmp_path: Path):
        """A declared mount whose host_path is invisible to this process gets an
        actionable error instead of the generic whitelist message."""
        from ideer.config import get_app_config as _real  # noqa: F401

        fake_config = SimpleNamespace(
            sandbox=SimpleNamespace(
                mounts=[
                    SimpleNamespace(
                        host_path="/nonexistent/host/eval",
                        container_path="/mnt/invisible-case",
                        read_only=True,
                    )
                ]
            )
        )
        # Ensure the shared cache does not know this mount either.
        with (
            patch(
                "packages.harness.ideer.sandbox.tools._get_custom_mounts",
                return_value=[],
            ),
            patch(
                "ideer.config.get_app_config",
                return_value=fake_config,
            ),
        ):
            result = await read_document_tool.ainvoke({"file_path": "/mnt/invisible-case/report.pdf"})
        data = json.loads(result)
        assert "/mnt/invisible-case" in data["error"]
        assert "gateway/worker" in data["error"]

    @pytest.mark.asyncio
    async def test_nested_mount_longest_prefix_wins(self, tmp_path: Path, monkeypatch):
        parent_host = tmp_path / "parent-host"
        child_host = tmp_path / "child-host"
        parent_host.mkdir()
        child_host.mkdir()
        mounts = [
            SimpleNamespace(host_path=str(parent_host), container_path="/mnt/data", read_only=True),
            SimpleNamespace(host_path=str(child_host), container_path="/mnt/data/sub", read_only=True),
        ]
        import packages.harness.ideer.sandbox.tools as _sbx_alt

        for sbx in {_get_sandbox_tools_module(), _sbx_alt}:
            monkeypatch.setattr(sbx, "_get_custom_mounts", lambda mounts=mounts: mounts)
        resolved_child = _resolve_mounted_path("/mnt/data/sub/a.pdf")
        resolved_parent = _resolve_mounted_path("/mnt/data/other/b.pdf")
        assert str(child_host / "a.pdf") == resolved_child
        assert str(parent_host / "other/b.pdf") == resolved_parent


def _get_sandbox_tools_module():
    """Return the ``ideer.sandbox.tools`` module object production code uses."""
    import ideer.sandbox.tools as sbx

    return sbx


class TestMcpServerMountWhitelist:
    """The MCP variant accepts configured mount container paths too.

    Skipped when the module cannot be imported: the installed ``mcp`` library
    lacks ``Server.tool``, which breaks this module at decoration time — a
    pre-existing incompatibility unrelated to the whitelist change.
    """

    def _import_mcp_server(self):
        try:
            from packages.harness.ideer.community.doc_reader import mcp_server
        except AttributeError as exc:
            pytest.skip(f"installed mcp library incompatible with this module: {exc}")
        return mcp_server

    def test_validate_path_accepts_registered_mount(self, tmp_path: Path, monkeypatch):
        mcp_server = self._import_mcp_server()

        host_dir = tmp_path / "mcp-host"
        host_dir.mkdir()
        mounts = [SimpleNamespace(host_path=str(host_dir), container_path="/mnt/mcp-case", read_only=True)]
        import packages.harness.ideer.sandbox.tools as _sbx_alt

        for sbx in {_get_sandbox_tools_module(), _sbx_alt}:
            monkeypatch.setattr(sbx, "_get_custom_mounts", lambda mounts=mounts: mounts)
        resolved = mcp_server._validate_path("/mnt/mcp-case/doc.pdf")
        assert isinstance(resolved, Path)

    def test_validate_path_rejects_unknown_prefix(self):
        mcp_server = self._import_mcp_server()

        with pytest.raises(PermissionError):
            mcp_server._validate_path("/mnt/nowhere/doc.pdf")


# ============================================================================
# read_document_tool — invoke interface
# ============================================================================


class TestToolInterface:
    """Test that the tool is properly registered."""

    def test_tool_has_invoke(self):
        assert hasattr(read_document_tool, "invoke")

    def test_tool_has_ainvoke(self):
        assert hasattr(read_document_tool, "ainvoke")

    def test_tool_name(self):
        assert read_document_tool.name == "read_document"
