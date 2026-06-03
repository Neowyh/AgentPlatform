"""Document Reader Tool - Read and extract text from office documents.

Converts PDF, Word, Excel, and PowerPoint files to Markdown for easy reading
by agents.  Leverages the existing file-conversion infrastructure in
``ideer.utils.file_conversion``.
"""

import json
import logging
from pathlib import Path

from langchain.tools import tool

from ideer.utils.file_conversion import convert_file_to_markdown

logger = logging.getLogger(__name__)

_DEFAULT_MAX_CHARS = 50_000

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}


def _truncate_output(text: str, max_chars: int) -> str:
    """Head-truncate output, preserving the beginning of the document.

    Follows the same pattern as sandbox ``_truncate_read_file_output``.
    """
    if max_chars == 0:
        return text
    if len(text) <= max_chars:
        return text
    total = len(text)
    marker = f"\n... [truncated: showing first {max_chars} of {total} chars] ..."
    kept = max(0, max_chars - len(marker))
    if kept == 0:
        return text[:max_chars]
    return f"{text[:kept]}{marker}"


def _get_page_count(file_path: Path) -> int | None:
    """Return the number of pages for PDF files, or None for other formats."""
    if file_path.suffix.lower() != ".pdf":
        return None
    try:
        import pymupdf

        doc = pymupdf.open(str(file_path))
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return None


def _extract_pdf_pages(file_path: Path, page_range: str) -> str | None:
    """Extract text from a specific page range using pymupdf4llm.

    Returns the markdown text, or None if pymupdf4llm is not installed or
    the page-range feature is unavailable.
    """
    try:
        import pymupdf4llm
    except ImportError:
        return None

    try:
        # pymupdf4llm.to_markdown supports pages parameter as a list of
        # page numbers (0-indexed).
        pages = _parse_page_range(page_range)
        if pages is None:
            return None
        return pymupdf4llm.to_markdown(str(file_path), pages=pages)
    except Exception:
        logger.warning(
            "pymupdf4llm page-range extraction failed for %s (range=%s); falling back to full document",
            file_path.name,
            page_range,
        )
        return None


def _parse_page_range(page_range: str) -> list[int] | None:
    """Parse a human-readable page range into 0-indexed page numbers.

    Accepts formats like "1-5", "3", "1-3,7,10-12".
    Returns None if the format is invalid.
    """
    pages: list[int] = []
    try:
        for part in page_range.split(","):
            part = part.strip()
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start = int(start_s.strip())
                end = int(end_s.strip())
                if start < 1 or end < start:
                    return None
                pages.extend(range(start - 1, end))  # convert to 0-indexed
            else:
                num = int(part)
                if num < 1:
                    return None
                pages.append(num - 1)  # convert to 0-indexed
    except (ValueError, AttributeError):
        return None
    return pages if pages else None


@tool("read_document", parse_docstring=True)
def read_document_tool(file_path: str, page_range: str | None = None) -> str:
    """Read and extract text content from documents (PDF, Word, Excel, PowerPoint).

    Converts documents to Markdown format for easy reading. Supports .pdf, .docx,
    .xlsx, .pptx and other common office formats.

    Args:
        file_path: Path to the document file. Supports virtual paths like /mnt/user-data/uploads/xxx.
        page_range: Page range for PDF files, e.g. "1-5" or "3". If not specified, reads all pages.
    """
    path = Path(file_path)

    # --- Validate path existence ---
    if not path.exists():
        return json.dumps(
            {"error": f"File not found: {file_path}"},
            ensure_ascii=False,
        )

    if not path.is_file():
        return json.dumps(
            {"error": f"Path is not a file: {file_path}"},
            ensure_ascii=False,
        )

    # --- Validate extension ---
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        return json.dumps(
            {
                "error": f"Unsupported file format: {suffix}",
                "supported": sorted(_SUPPORTED_EXTENSIONS),
            },
            ensure_ascii=False,
        )

    file_size = path.stat().st_size

    # --- Handle PDF page-range extraction ---
    pdf_page_range_text = None
    if page_range and suffix == ".pdf":
        pdf_page_range_text = _extract_pdf_pages(path, page_range)
        if pdf_page_range_text is None:
            logger.warning(
                "Page-range extraction not available; reading full document for %s",
                path.name,
            )

    # --- If page-range extraction succeeded, use that directly ---
    if pdf_page_range_text is not None:
        page_count = _get_page_count(path)
        header = f"<!-- file: {path.name} | size: {file_size} bytes"
        if page_count is not None:
            header += f" | pages: {page_count} (showing {page_range})"
        header += " -->\n\n"
        result = header + pdf_page_range_text
        return _truncate_output(result, _DEFAULT_MAX_CHARS)

    # --- Full document conversion ---
    import asyncio

    try:
        md_path = asyncio.get_event_loop().run_until_complete(convert_file_to_markdown(path))
    except RuntimeError:
        # No running event loop — create a new one
        md_path = asyncio.run(convert_file_to_markdown(path))

    if md_path is None:
        return json.dumps(
            {"error": f"Failed to convert document: {path.name}"},
            ensure_ascii=False,
        )

    if not md_path.exists():
        return json.dumps(
            {"error": f"Converted file not found: {md_path.name}"},
            ensure_ascii=False,
        )

    try:
        content = md_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read converted file %s: %s", md_path.name, e)
        return json.dumps(
            {"error": f"Failed to read converted file: {e}"},
            ensure_ascii=False,
        )

    if not content.strip():
        return json.dumps(
            {"error": "Document conversion produced empty output", "file": path.name},
            ensure_ascii=False,
        )

    # --- Build metadata header ---
    page_count = _get_page_count(path)
    header = f"<!-- file: {path.name} | size: {file_size} bytes"
    if page_count is not None:
        header += f" | pages: {page_count}"
    header += " -->\n\n"

    result = header + content
    return _truncate_output(result, _DEFAULT_MAX_CHARS)
