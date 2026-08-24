"""Document Reader Tool - Read and extract text from office documents.

Converts PDF, Word, Excel, and PowerPoint files to Markdown for easy reading
by agents.  Leverages the existing file-conversion infrastructure in
``ideer.utils.file_conversion``.
"""

import json
import logging
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime, tool

from ideer.utils.file_conversion import convert_file_to_markdown

logger = logging.getLogger(__name__)

_DEFAULT_MAX_CHARS = 50_000
_MAX_FILE_SIZE = 100_000_000  # 100 MB

# Legacy binary ``.doc`` is deliberately unsupported: MarkItDown ships no .doc
# converter, so conversion would fail (or emit garbage) at runtime. Callers are
# told to re-upload as .docx instead.
_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt"}

_LEGACY_DOC_ERROR = {
    "error": "Unsupported file format: legacy .doc is not supported. Please convert the document to .docx (open it in Word/WPS and save as .docx), then upload again.",
}

# Security: only allow reading files under these prefixes
_ALLOWED_PATH_PREFIXES = ["/mnt/user-data", "/tmp"]


def _resolve_virtual_path(file_path: str, runtime: Any) -> str:
    """Resolve a ``/mnt/user-data`` virtual path to its host path.

    Agent runs expose uploads/outputs under the virtual ``/mnt/user-data``
    prefix; the actual location is per-thread and only known through the
    injected runtime state (``thread_data``). Sandbox tools share the same
    mapping via :func:`ideer.sandbox.tools.replace_virtual_path`.

    Returns the input unchanged when there is no runtime, no thread_data, or
    the path is not a ``/mnt/user-data`` path.
    """
    if runtime is None or not file_path.startswith("/mnt/user-data"):
        return file_path
    try:
        from ideer.sandbox.tools import get_thread_data, replace_virtual_path

        resolved = replace_virtual_path(file_path, get_thread_data(runtime))
    except Exception as exc:  # pragma: no cover - defensive, mapping must exist
        logger.warning("Virtual path resolution failed for %s: %s", file_path, exc)
        return file_path
    if resolved != file_path:
        logger.debug("Resolved virtual path %s -> %s", file_path, resolved)
    return resolved


def _resolve_mounted_path(file_path: str) -> str | None:
    """Resolve a configured custom-mount container path to its host path.

    Custom mounts are declared in config.yaml under ``sandbox.mounts``
    (``host_path`` ↔ ``container_path``) and are already honoured by sandbox
    tools and the workflow engine's artifact resolver. This reuses the exact
    same registration source (:func:`ideer.sandbox.tools._get_custom_mount_for_path`,
    longest container_path prefix first) so all three surfaces agree on what
    is readable.

    Returns the host path, or ``None`` when the path is not under any
    registered mount visible to this process.
    """
    try:
        from ideer.sandbox.tools import _get_custom_mount_for_path, _is_custom_mount_path

        if not _is_custom_mount_path(file_path):
            return None
        mount = _get_custom_mount_for_path(file_path)
    except Exception as exc:  # pragma: no cover - defensive, config must exist
        logger.warning("Custom mount lookup failed for %s: %s", file_path, exc)
        return None
    if mount is None or not mount.host_path:
        return None
    rest = file_path[len(mount.container_path) :].lstrip("/")
    host = mount.host_path.rstrip("/")
    resolved = f"{host}/{rest}" if rest else host
    logger.debug("Resolved mounted path %s -> %s", file_path, resolved)
    return resolved


def _invisible_mount_hint(file_path: str) -> str | None:
    """Explain rejections caused by mounts whose host path this process cannot see.

    ``_get_custom_mounts()`` filters configured mounts by
    ``Path(host_path).exists()``, so a mount declared in config.yaml but not
    visible to the gateway/worker process silently disappears from resolution.
    When a rejected path matches such a declaration, surface an actionable
    deployment hint instead of the generic whitelist message.
    """
    try:
        from ideer.config import get_app_config

        config = get_app_config()
        mounts = getattr(config.sandbox, "mounts", None) if config.sandbox else None
    except Exception:  # pragma: no cover - config unavailable, skip hinting
        return None
    for mount in mounts or []:
        container = mount.container_path.rstrip("/")
        if file_path == container or file_path.startswith(f"{container}/"):
            if not Path(mount.host_path).exists():
                return (
                    f"Access denied: {file_path} belongs to a configured mount "
                    f"({mount.container_path} -> {mount.host_path}), but the host "
                    "path is not visible to this process. Mount the same host_path "
                    "into the gateway/worker container to enable document reading."
                )
            return None
    return None


def _validate_path(file_path: str) -> Path:
    """Validate and resolve file path, ensuring it is within allowed directories.

    Raises PermissionError if the path escapes the allowed prefix.
    """
    path = Path(file_path).resolve()
    if not any(str(path).startswith(prefix) for prefix in _ALLOWED_PATH_PREFIXES):
        raise PermissionError(f"Access denied: file must be under one of {_ALLOWED_PATH_PREFIXES}, got: {file_path}")
    return path


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

        with pymupdf.open(str(file_path)) as doc:
            return len(doc)
    except Exception as e:
        logger.warning("Failed to get page count for %s: %s", file_path.name, e)
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
    except Exception as e:
        logger.warning(
            "pymupdf4llm page-range extraction failed for %s (range=%s): %s: %s; falling back to full document",
            file_path.name,
            page_range,
            type(e).__name__,
            e,
        )
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


async def read_document_async(
    file_path: str,
    page_range: str | None = None,
    runtime: ToolRuntime[dict[str, Any], Any] | None = None,
) -> str:
    """Single-source implementation of the read_document capability.

    Both the in-process langchain tool (:func:`read_document_tool`) and the
    standalone FastMCP server (``mcp_server.py``) delegate here so validation,
    conversion, and truncation behaviour cannot drift apart.
    """
    # Path resolution order:
    #   1. /mnt/user-data virtual paths -> host paths via injected thread_data
    #   2. configured custom mounts (sandbox.mounts) -> declared host_path
    #   3. literal whitelist (/mnt/user-data, /tmp) — unchanged fallback
    resolved_input = _resolve_virtual_path(file_path, runtime)
    if resolved_input != file_path:
        path = Path(resolved_input).resolve()
    else:
        mounted = _resolve_mounted_path(file_path)
        if mounted is not None:
            path = Path(mounted).resolve()
        else:
            try:
                path = _validate_path(file_path)
            except PermissionError as e:
                hint = _invisible_mount_hint(file_path)
                if hint is not None:
                    return json.dumps({"error": hint}, ensure_ascii=False)
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
    if suffix == ".doc":
        return json.dumps(dict(_LEGACY_DOC_ERROR), ensure_ascii=False)
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


@tool("read_document", parse_docstring=True)
async def read_document_tool(
    runtime: ToolRuntime[dict[str, Any], Any] = None,
    file_path: str = "",
    page_range: str | None = None,
) -> str:
    """Read and extract text content from documents (PDF, Word, Excel, PowerPoint).

    Converts documents to Markdown format for easy reading. Supports .pdf, .docx,
    .xlsx, .pptx and other common office formats. Legacy binary .doc files are
    not supported — convert them to .docx first.

    Args:
        file_path: Path to the document file. Supports virtual paths like /mnt/user-data/uploads/xxx.
        page_range: Page range for PDF files, e.g. "1-5" or "3". If not specified, reads all pages.
    """
    return await read_document_async(file_path, page_range=page_range, runtime=runtime)
