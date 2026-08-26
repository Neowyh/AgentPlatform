"""MCP Server for data_analyzer tool.

Run standalone:
    python -m ideer.community.data_analyzer.mcp_server

Register in extensions_config.json:
  "data-analyzer": {
    "enabled": true,
    "type": "stdio",
    "command": "python",
    "args": ["-m", "ideer.community.data_analyzer.mcp_server"]
  }
"""

import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from ideer.community.data_analyzer import tools as _core

logger = logging.getLogger(__name__)

# FastMCP exposes the ``.tool`` decorator; the low-level Server does not.
server = FastMCP("data-analyzer")

# Single source of truth: pandas checks, file reading, analysis, and output
# truncation all live in tools.py; this wrapper only adapts them to MCP
# transport. Re-exported for operators/tests introspecting validation.
_validate_path = _core._validate_path


@server.tool("data_analyzer")
async def data_analyzer(file_path: str, analysis_type: str = "summary") -> str:
    """Analyze structured data files and generate statistical insights.

    Supports CSV, Excel (.xlsx/.xls), and JSON files. Provides statistical
    summaries, data quality reports, and correlation analysis.

    Args:
        file_path: Path to the data file. Supports virtual paths like /mnt/user-data/uploads/data.csv.
        analysis_type: Type of analysis — "summary" (overview + data types + missing values),
            "describe" (statistical summary of numeric columns),
            "correlation" (correlation matrix for numeric columns).
    """
    return await asyncio.to_thread(_core.data_analyzer_sync, file_path, analysis_type)


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
