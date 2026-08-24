"""MCP Server for read_document tool.

Run standalone:
    python -m ideer.community.doc_reader.mcp_server

Register in extensions_config.json:
  "doc-reader": {
    "enabled": true,
    "type": "stdio",
    "command": "python",
    "args": ["-m", "ideer.community.doc_reader.mcp_server"]
  }
"""

import asyncio
import json
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server

from ideer.utils.file_conversion import convert_file_to_markdown

logger = logging.getLogger(__name__)

server = Server("doc-reader")

_DEFAULT_MAX_CHARS = 50_000
_MAX_FILE_SIZE = 100_000_000  # 100 MB
_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt"}

# Security: only allow reading files under these prefixes
_ALLOWED_PATH_PREFIXES = ["/mnt/user-data", "/tmp"]


def _validate_path(file_path: str) -> Path:
    """Validate and resolve file path, ensuring it is within allowed directories."""
    path = Path(file_path).resolve()
    if not any(str(path).startswith(prefix) for prefix in _ALLOWED_PATH_PREFIXES):
        raise PermissionError(f"Access denied: file must be under one of {_ALLOWED_PATH_PREFIXES}, got: {file_path}")
    return path


def _truncate_output(text: str, max_chars: int) -> str:
    """Head-truncate output, preserving the beginning of the document."""
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

        with pymupdf.open(str(file_path)) as doc:
            return len(doc)
    except Exception as e:
        logger.warning("Failed to get page count for %s: %s", file_path.name, e)
        return None


def _parse_page_range(page_range: str) -> list[int] | None:
    """Parse a human-readable page range into 0-indexed page numbers.

    Accepts formats like "1-5", "3", "1-3,7,10-12".
    Returns None if the format is invalid.
    """
    _MAX_PAGES = 10000  # hard cap to prevent memory exhaustion
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
                if (end - start + 1) > _MAX_PAGES:
                    return None
                pages.extend(range(start - 1, end))  # convert to 0-indexed
            else:
                num = int(part)
                if num < 1:
                    return None
                pages.append(num - 1)  # convert to 0-indexed
        if len(pages) > _MAX_PAGES:
            return None
    except (ValueError, AttributeError):
        return None
    return pages if pages else None


def _extract_pdf_pages(file_path: Path, page_range: str) -> str | None:
    """Extract text from a specific page range using pymupdf4llm."""
    try:
        import pymupdf4llm
    except ImportError:
        return None

    try:
        pages = _parse_page_range(page_range)
        if pages is None:
            return None
        return pymupdf4llm.to_markdown(str(file_path), pages=pages)
    except Exception as e:
        logger.warning(
            "pymupdf4llm page-range extraction failed for %s (range=%s): %s: %s; falling back to full document",
            file_path.name,
            page_range,
            type(e).__name__,
            e,
        )
        return None


@server.tool("read_document")
async def read_document(file_path: str, page_range: str | None = None) -> str:
    """Read and extract text content from documents (PDF, Word, Excel, PowerPoint).

    Converts documents to Markdown format for easy reading. Supports .pdf, .docx,
    .xlsx, .pptx and other common office formats. Legacy binary .doc files are
    not supported — convert them to .docx first.

    Args:
        file_path: Path to the document file. Supports virtual paths like /mnt/user-data/uploads/xxx.
        page_range: Page range for PDF files, e.g. "1-5" or "3". If not specified, reads all pages.
    """
    try:
        path = _validate_path(file_path)
    except PermissionError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

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

    # --- File size guard ---
    if file_size > _MAX_FILE_SIZE:
        return json.dumps(
            {"error": f"File too large: {file_size} bytes (max {_MAX_FILE_SIZE} bytes)"},
            ensure_ascii=False,
        )

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
        safe_name = path.name.replace("-->", "-- >")
        header = f"<!-- file: {safe_name} | size: {file_size} bytes"
        if page_count is not None:
            header += f" | pages: {page_count} (showing {page_range})"
        header += " -->\n\n"
        result = header + pdf_page_range_text
        return _truncate_output(result, _DEFAULT_MAX_CHARS)

    # --- Full document conversion ---
    try:
        md_path = await convert_file_to_markdown(path)
    except Exception as e:
        logger.error("Document conversion failed for %s: %s", path.name, e)
        return json.dumps(
            {"error": f"Failed to convert document: {path.name}"},
            ensure_ascii=False,
        )

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
            {"error": "Failed to read converted file"},
            ensure_ascii=False,
        )
    finally:
        # Clean up temporary markdown sidecar file
        try:
            md_path.unlink(missing_ok=True)
        except OSError:
            pass

    if not content.strip():
        return json.dumps(
            {"error": "Document conversion produced empty output", "file": path.name},
            ensure_ascii=False,
        )

    # --- Build metadata header ---
    page_count = _get_page_count(path)
    safe_name = path.name.replace("-->", "-- >")
    header = f"<!-- file: {safe_name} | size: {file_size} bytes"
    if page_count is not None:
        header += f" | pages: {page_count}"
    header += " -->\n\n"

    result = header + content
    return _truncate_output(result, _DEFAULT_MAX_CHARS)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
