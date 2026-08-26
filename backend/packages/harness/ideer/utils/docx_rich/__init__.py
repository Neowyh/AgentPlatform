"""Rich Word document parsing (ported from only_parser).

High-fidelity ``.docx`` / ``.doc`` -> Markdown conversion built on python-docx,
preserving heading levels, inline formatting, lists, HTML tables, embedded
images, MathType formulas (as LaTeX) and Visio drawings (as PNG, requires
LibreOffice).

Heavy dependencies (MinerU / torch / MFR vision model) are deliberately NOT
included: formulas that MTEF cannot parse degrade to their thumbnail image.

Public API:

- :func:`convert_docx` -- convert one ``.docx`` / ``.doc`` file
- :func:`is_available` -- whether python-docx is installed
- :func:`libreoffice_available` -- whether soffice was found on this host
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "convert_docx",
    "is_available",
    "libreoffice_available",
]


def is_available() -> bool:
    """Return True when python-docx is installed."""
    try:
        import docx  # noqa: F401

        return True
    except ImportError:
        logger.debug("python-docx is not installed; rich docx parsing unavailable")
        return False


def libreoffice_available() -> bool:
    """Return True when a soffice binary was found on this host."""
    from .libreoffice import get_libreoffice_manager

    try:
        return get_libreoffice_manager()._find_soffice() is not None
    except Exception:
        return False


def convert_docx(
    file_path: str | Path,
    output_dir: str | Path,
) -> tuple[str, dict[str, Any]]:
    """Convert a Word document to Markdown.

    Args:
        file_path: Path to the ``.docx`` or ``.doc`` file.
        output_dir: Directory that receives the parsed artifacts. A subdirectory
            named ``<stem>_<ext>`` is created inside it, holding the extracted
            images (``images/``) and an intermediate ``<stem>.md``.

    Returns:
        ``(markdown_content, extra_info)`` where ``extra_info`` contains
        ``image_dir`` and ``output_subdir`` paths.

    Raises:
        RuntimeError: legacy ``.doc`` input without LibreOffice available, or
            LibreOffice conversion failure.
        ValueError: unsupported file extension.
    """
    src = Path(file_path)
    ext = src.suffix.lower()

    if ext == ".doc" and not libreoffice_available():
        raise RuntimeError("LibreOffice (soffice) is required to convert legacy .doc files; please re-save the document as .docx instead.")

    from .parser import DocxDocumentParser

    parser = DocxDocumentParser()
    out_dir = str(output_dir)

    if ext == ".docx":
        markdown_content, _, extra_info = parser.parse_docx(str(src), out_dir)
    elif ext == ".doc":
        markdown_content, _, extra_info = parser.parse_doc(str(src), out_dir)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    extra_info.setdefault("output_subdir", os.path.join(out_dir, f"{src.stem}_{ext.lstrip('.')}"))
    return markdown_content or "", extra_info
