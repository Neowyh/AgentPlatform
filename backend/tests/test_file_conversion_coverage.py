"""Tests for uncovered lines in file_conversion.py.

Covers:
- Lines 71-72: doc.close() raising exception in finally block
- Lines 85-94: _convert_pdf_with_pymupdf4llm function logic
- Lines 99-102: _convert_with_markitdown function logic
- Lines 313-315: _get_pdf_converter exception handling
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from ideer.utils.file_conversion import (
    _convert_pdf_with_pymupdf4llm,
    _convert_with_markitdown,
    _get_pdf_converter,
    _pymupdf_output_too_sparse,
)

# ---------------------------------------------------------------------------
# Lines 71-72: doc.close() raises exception in finally block
# ---------------------------------------------------------------------------


class TestPymupdfDocCloseException:
    """Cover the except block when doc.close() raises an exception (lines 71-72)."""

    def test_doc_close_raises_exception_is_swallowed(self, tmp_path):
        """When doc.close() raises, the exception is caught and sparsity check still works."""
        pdf = tmp_path / "close_err.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)
        mock_doc.close.side_effect = RuntimeError("close failed")

        fake_pymupdf = ModuleType("pymupdf")
        fake_pymupdf.open = MagicMock(return_value=mock_doc)  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"pymupdf": fake_pymupdf}):
            # 500 chars / 5 pages = 100/page > 50 threshold -> not sparse
            result = _pymupdf_output_too_sparse("x" * 500, pdf)

        assert result is False
        # Verify close was attempted
        mock_doc.close.assert_called_once()


# ---------------------------------------------------------------------------
# Lines 85-94: _convert_pdf_with_pymupdf4llm function
# ---------------------------------------------------------------------------


class TestConvertPdfWithPymupdf4llm:
    """Cover _convert_pdf_with_pymupdf4llm function logic (lines 85-94)."""

    def test_returns_none_when_pymupdf4llm_not_installed(self, tmp_path):
        """When pymupdf4llm is not installed, return None (lines 85-88)."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        # Ensure pymupdf4llm is not importable
        with patch.dict(sys.modules, {"pymupdf4llm": None}):
            result = _convert_pdf_with_pymupdf4llm(pdf)

        assert result is None

    def test_returns_markdown_on_successful_conversion(self, tmp_path):
        """When pymupdf4llm is installed and succeeds, return the markdown (lines 90-91)."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_pymupdf4llm = ModuleType("pymupdf4llm")
        mock_pymupdf4llm.to_markdown = MagicMock(return_value="# Converted PDF\n\nContent here.")  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"pymupdf4llm": mock_pymupdf4llm}):
            result = _convert_pdf_with_pymupdf4llm(pdf)

        assert result == "# Converted PDF\n\nContent here."
        mock_pymupdf4llm.to_markdown.assert_called_once_with(str(pdf))

    def test_returns_none_when_conversion_raises_exception(self, tmp_path):
        """When pymupdf4llm.to_markdown raises, return None (lines 92-94)."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_pymupdf4llm = ModuleType("pymupdf4llm")
        mock_pymupdf4llm.to_markdown = MagicMock(side_effect=RuntimeError("conversion failed"))  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"pymupdf4llm": mock_pymupdf4llm}):
            result = _convert_pdf_with_pymupdf4llm(pdf)

        assert result is None


# ---------------------------------------------------------------------------
# Lines 99-102: _convert_with_markitdown function
# ---------------------------------------------------------------------------


class TestConvertWithMarkitdown:
    """Cover _convert_with_markitdown function logic (lines 99-102)."""

    def test_converts_file_to_markdown(self, tmp_path):
        """MarkItDown is instantiated and converts the file (lines 99-102)."""
        docx = tmp_path / "report.docx"
        docx.write_bytes(b"PK fake docx content")

        mock_markitdown_instance = MagicMock()
        mock_markitdown_instance.convert.return_value.text_content = "# Converted\n\nDocument content."

        mock_markitdown_class = MagicMock(return_value=mock_markitdown_instance)

        mock_markitdown_module = ModuleType("markitdown")
        mock_markitdown_module.MarkItDown = mock_markitdown_class  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"markitdown": mock_markitdown_module}):
            result = _convert_with_markitdown(docx)

        assert result == "# Converted\n\nDocument content."
        mock_markitdown_class.assert_called_once()
        mock_markitdown_instance.convert.assert_called_once_with(str(docx))


# ---------------------------------------------------------------------------
# Lines 313-315: _get_pdf_converter exception handling
# ---------------------------------------------------------------------------


class TestGetPdfConverterException:
    """Cover _get_pdf_converter exception handling (lines 313-315)."""

    def test_returns_auto_when_config_raises_exception(self):
        """When _get_uploads_config_value raises an exception, return 'auto' (lines 313-315)."""
        with patch(
            "ideer.utils.file_conversion._get_uploads_config_value",
            side_effect=RuntimeError("config unavailable"),
        ):
            result = _get_pdf_converter()

        assert result == "auto"

    def test_returns_auto_when_get_app_config_raises(self):
        """When get_app_config itself raises, return 'auto'."""
        with patch(
            "ideer.utils.file_conversion.get_app_config",
            side_effect=RuntimeError("no config"),
        ):
            result = _get_pdf_converter()

        assert result == "auto"
