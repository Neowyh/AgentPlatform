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
import json
import logging
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server

try:
    import pandas as pd
except ImportError:
    pd = None  # Will be checked at runtime

logger = logging.getLogger(__name__)

server = Server("data-analyzer")

_MAX_OUTPUT_CHARS = 10000


def _check_pandas() -> str | None:
    """Return an error message if pandas is not installed, else None."""
    if pd is None:
        return "pandas is required for data analysis. Install it with: pip install pandas"
    return None


def _read_file(file_path: str):
    """Read a structured data file into a DataFrame.

    Returns (df, error) tuple. On success error is None.
    """
    if not os.path.exists(file_path):
        return None, f"File not found: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        elif ext == ".json":
            try:
                df = pd.read_json(file_path)
            except ValueError:
                # Try line-delimited JSON
                df = pd.read_json(file_path, lines=True)
        else:
            return None, f"Unsupported file format: {ext}. Supported formats: .csv, .xlsx, .xls, .json"
    except Exception as e:
        return None, f"Failed to read file: {e}"

    if df.empty:
        return None, "The file is empty or contains no data rows."

    return df, None


def _analyze_summary(df) -> dict:
    """Return shape, column info, missing values, and first 5 rows."""
    shape = {"rows": df.shape[0], "columns": df.shape[1]}

    columns = [{"name": col, "dtype": str(df[col].dtype)} for col in df.columns]

    missing = {}
    for col in df.columns:
        count = int(df[col].isnull().sum())
        if count > 0:
            missing[col] = count

    try:
        head = df.head(5).to_markdown(index=False)
    except Exception:
        head = df.head(5).to_string(index=False)

    return {
        "shape": shape,
        "columns": columns,
        "missing_values": missing,
        "head": head,
    }


def _analyze_describe(df) -> dict:
    """Return statistical summary for numeric and categorical columns."""
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

    result: dict = {}

    if numeric_cols:
        desc = df[numeric_cols].describe().to_string()
        result["numeric_summary"] = desc

    if categorical_cols:
        cat_summaries = {}
        for col in categorical_cols[:20]:  # Cap to avoid excessive output
            vc = df[col].value_counts().head(5).to_string()
            cat_summaries[col] = vc
        result["categorical_value_counts"] = cat_summaries

    if not numeric_cols and not categorical_cols:
        result["message"] = "No numeric or categorical columns found for analysis."

    return result


def _analyze_correlation(df) -> dict:
    """Return correlation matrix for numeric columns, highlighting strong correlations."""
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] < 2:
        return {"error": "Need at least 2 numeric columns for correlation analysis."}

    corr_matrix = numeric_df.corr()
    corr_text = corr_matrix.to_string()

    # Find strong correlations (|r| > 0.7, excluding diagonal)
    strong = []
    cols = corr_matrix.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr_matrix.iloc[i, j]
            if abs(r) > 0.7:
                strong.append(
                    {
                        "column_1": cols[i],
                        "column_2": cols[j],
                        "correlation": round(r, 4),
                    }
                )

    result: dict = {"correlation_matrix": corr_text}
    if strong:
        result["strong_correlations"] = strong

    return result


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
    # Check pandas availability
    pandas_err = _check_pandas()
    if pandas_err:
        return json.dumps({"error": pandas_err}, ensure_ascii=False)

    # Read file
    df, read_err = _read_file(file_path)
    if read_err:
        return json.dumps({"error": read_err, "file_path": file_path}, ensure_ascii=False)

    # Run requested analysis
    valid_types = {"summary", "describe", "correlation"}
    if analysis_type not in valid_types:
        return json.dumps(
            {"error": f"Unknown analysis_type: {analysis_type}. Valid types: {', '.join(sorted(valid_types))}"},
            ensure_ascii=False,
        )

    try:
        if analysis_type == "summary":
            result = _analyze_summary(df)
        elif analysis_type == "describe":
            result = _analyze_describe(df)
        else:
            result = _analyze_correlation(df)
    except Exception as e:
        logger.error("Analysis failed for %s: %s", file_path, e)
        return json.dumps({"error": f"Analysis failed: {e}"}, ensure_ascii=False)

    output = {
        "file_path": file_path,
        "analysis_type": analysis_type,
        "result": result,
    }

    text = json.dumps(output, indent=2, ensure_ascii=False)
    if len(text) > _MAX_OUTPUT_CHARS:
        logger.warning(
            "Output for %s (%s) truncated from %d to %d chars",
            file_path,
            analysis_type,
            len(text),
            _MAX_OUTPUT_CHARS,
        )
        text = text[:_MAX_OUTPUT_CHARS] + "\n... [truncated]"

    return text


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
