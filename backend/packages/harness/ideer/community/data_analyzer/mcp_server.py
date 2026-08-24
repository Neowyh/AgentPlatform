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

from mcp.server.fastmcp import FastMCP

try:
    import pandas as pd
except ImportError:
    pd = None  # Will be checked at runtime

logger = logging.getLogger(__name__)

# FastMCP exposes the ``.tool`` decorator; the low-level Server does not.
server = FastMCP("data-analyzer")

_MAX_OUTPUT_CHARS = 10000
_MAX_FILE_SIZE = 200_000_000  # 200 MB
_MAX_MEMORY_BYTES = 500_000_000  # 500 MB - decompression bomb protection
_MAX_ROWS = 500_000  # row limit to prevent OOM on decompression bombs

# Security: only allow reading files under these prefixes
_ALLOWED_PATH_PREFIXES = ["/mnt/user-data", "/tmp"]


def _validate_path(file_path: str) -> str:
    """Validate file path is within allowed directories. Returns resolved path."""
    resolved = os.path.realpath(file_path)
    if not any(resolved.startswith(prefix) for prefix in _ALLOWED_PATH_PREFIXES):
        raise PermissionError(f"Access denied: file must be under one of {_ALLOWED_PATH_PREFIXES}, got: {file_path}")
    return resolved


def _check_pandas() -> str | None:
    """Return an error message if pandas is not installed, else None."""
    if pd is None:
        return "pandas is required for data analysis. Install it with: pip install pandas"
    return None


def _read_file(file_path: str):
    """Read a structured data file into a DataFrame.

    Returns (df, error) tuple. On success error is None.
    """
    if pd is None:
        return None, "pandas is required for data analysis. Install it with: pip install pandas"

    # Security: validate path is within allowed directories
    try:
        file_path = _validate_path(file_path)
    except PermissionError as e:
        return None, str(e)

    if not os.path.exists(file_path):
        return None, f"File not found: {file_path}"

    file_size = os.path.getsize(file_path)
    if file_size > _MAX_FILE_SIZE:
        return None, f"File too large: {file_size} bytes (max {_MAX_FILE_SIZE} bytes)"

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".csv":
            df = pd.read_csv(file_path, nrows=_MAX_ROWS)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, nrows=_MAX_ROWS)
        elif ext == ".json":
            try:
                df = pd.read_json(file_path, nrows=_MAX_ROWS)
            except (ValueError, TypeError):
                try:
                    df = pd.read_json(file_path, lines=True, nrows=_MAX_ROWS)
                except (ValueError, TypeError):
                    # Fallback: use chunked reading to avoid loading entire file
                    try:
                        chunks = pd.read_json(file_path, chunksize=_MAX_ROWS)
                        df = next(chunks)  # Only take the first chunk
                    except (ValueError, TypeError):
                        return None, f"Failed to parse JSON file: {file_path}"
        else:
            return None, f"Unsupported file format: {ext}. Supported formats: .csv, .xlsx, .xls, .json"
    except Exception as e:
        return None, f"Failed to read file: {e}"

    # Decompression bomb protection: check actual memory usage after loading
    memory_usage = df.memory_usage(deep=True).sum()
    if memory_usage > _MAX_MEMORY_BYTES:
        return None, f"DataFrame too large after decompression: {memory_usage} bytes (max {_MAX_MEMORY_BYTES} bytes)"

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
    return await asyncio.to_thread(_data_analyzer_sync, file_path, analysis_type)


def _data_analyzer_sync(file_path: str, analysis_type: str) -> str:
    """Synchronous implementation of data_analyzer — runs in a thread pool."""
    # Check pandas availability
    pandas_err = _check_pandas()
    if pandas_err:
        return json.dumps({"error": pandas_err}, ensure_ascii=False)

    # Validate analysis_type before reading file (expensive operation)
    valid_types = {"summary", "describe", "correlation"}
    if analysis_type not in valid_types:
        return json.dumps(
            {"error": f"Unknown analysis_type: {analysis_type}. Valid types: {', '.join(sorted(valid_types))}"},
            ensure_ascii=False,
        )

    # Read file
    df, read_err = _read_file(file_path)
    if read_err:
        return json.dumps({"error": read_err, "file_path": file_path}, ensure_ascii=False)

    # Run requested analysis
    try:
        if analysis_type == "summary":
            result = _analyze_summary(df)
        elif analysis_type == "describe":
            result = _analyze_describe(df)
        else:
            result = _analyze_correlation(df)
    except Exception as e:
        logger.error("Analysis failed for %s: %s", file_path, e, exc_info=True)
        return json.dumps({"error": "Analysis failed. Check server logs for details."}, ensure_ascii=False)

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
        # Binary search for the longest result prefix that fits in _MAX_OUTPUT_CHARS
        # after JSON re-escaping. This guarantees the output always fits.
        result_compact = json.dumps(output.get("result", {}), ensure_ascii=False)
        marker = "... [truncated]"
        lo, hi = 0, len(result_compact)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            test_out = json.dumps(
                {"file_path": file_path, "analysis_type": analysis_type, "result_summary": result_compact[:mid] + marker, "truncated": True},
                ensure_ascii=False,
            )
            if len(test_out) <= _MAX_OUTPUT_CHARS:
                lo = mid
            else:
                hi = mid - 1
        return json.dumps(
            {"file_path": file_path, "analysis_type": analysis_type, "result_summary": result_compact[:lo] + marker, "truncated": True},
            ensure_ascii=False,
        )

    return text


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
