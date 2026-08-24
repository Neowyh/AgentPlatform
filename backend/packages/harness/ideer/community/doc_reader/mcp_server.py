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
import logging

from mcp.server.fastmcp import FastMCP

from ideer.community.doc_reader import tools as _core

logger = logging.getLogger(__name__)

# FastMCP is the high-level server API: its ``.tool`` decorator registers
# handlers directly. The low-level ``mcp.server.Server`` has no such decorator,
# which broke this module at import time (see dev-log findings 2026-08-24).
server = FastMCP("doc-reader")

# Single source of truth: all path validation, conversion, and truncation
# behaviour lives in tools.py; this wrapper only adapts it to MCP transport.
# Re-exported for operators/tests that introspect the validation entry point.
_validate_path = _core._validate_path


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
    return await _core.read_document_async(file_path, page_range=page_range)


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
