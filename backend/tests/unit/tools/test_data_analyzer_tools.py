"""Comprehensive tests for data_analyzer/tools.py targeting 98%+ coverage."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pandas as pd
import pytest

from packages.harness.ideer.community.data_analyzer.tools import (
    _MAX_FILE_SIZE,
    _MAX_MEMORY_BYTES,
    _MAX_OUTPUT_CHARS,
    _MAX_ROWS,
    _analyze_correlation,
    _analyze_describe,
    _analyze_summary,
    _check_pandas,
    _read_file,
    _validate_path,
    data_analyzer_tool,
)

# ── Helpers ──────────────────────────────────────────────────────────────


def _tmp_csv(content: str, suffix: str = ".csv") -> str:
    """Write content to a temp file under /tmp and return its path."""
    f = tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False, dir="/tmp")
    f.write(content)
    f.close()
    return f.name


def _tmp_bytes(content: bytes, suffix: str = ".csv") -> str:
    """Write raw bytes to a temp file under /tmp and return its path."""
    f = tempfile.NamedTemporaryFile(suffix=suffix, mode="wb", delete=False, dir="/tmp")
    f.write(content)
    f.close()
    return f.name


# ── _validate_path ───────────────────────────────────────────────────────


class TestValidatePath:
    def test_allowed_tmp_path(self):
        result = _validate_path("/tmp/somefile.csv")
        assert result.startswith("/tmp")

    def test_allowed_mnt_path(self):
        result = _validate_path("/mnt/user-data/uploads/data.csv")
        assert result.startswith("/mnt/user-data")

    def test_disallowed_path_raises(self):
        with pytest.raises(PermissionError, match="Access denied"):
            _validate_path("/etc/passwd")

    def test_path_traversal_raises(self):
        with pytest.raises(PermissionError, match="Access denied"):
            _validate_path("/mnt/user-data/../../../etc/shadow")

    def test_resolved_path_outside_prefix_raises(self):
        """Symlink or ../ that resolves outside allowed prefix."""
        with pytest.raises(PermissionError):
            _validate_path("/tmp/../etc/hostname")


# ── _check_pandas ────────────────────────────────────────────────────────


class TestCheckPandas:
    def test_returns_none_when_pandas_available(self):
        assert _check_pandas() is None

    def test_returns_error_when_pandas_none(self):
        with patch("packages.harness.ideer.community.data_analyzer.tools.pd", None):
            result = _check_pandas()
            assert result is not None
            assert "pandas" in result.lower()


# ── _read_file ───────────────────────────────────────────────────────────


class TestReadFile:
    def test_pandas_not_installed(self):
        with patch("packages.harness.ideer.community.data_analyzer.tools.pd", None):
            df, err = _read_file("/tmp/test.csv")
            assert df is None
            assert "pandas" in err.lower()

    def test_path_validation_error(self):
        df, err = _read_file("/etc/passwd")
        assert df is None
        assert "access denied" in err.lower()

    def test_file_not_found(self):
        df, err = _read_file("/tmp/_nonexistent_12345.csv")
        assert df is None
        assert "not found" in err.lower()

    def test_file_too_large(self):
        path = _tmp_csv("a,b\n1,2\n")
        try:
            with patch(
                "packages.harness.ideer.community.data_analyzer.tools.os.path.getsize",
                return_value=_MAX_FILE_SIZE + 1,
            ):
                df, err = _read_file(path)
                assert df is None
                assert "too large" in err.lower()
        finally:
            os.unlink(path)

    def test_csv_reading(self):
        path = _tmp_csv("a,b\n1,2\n3,4\n")
        try:
            df, err = _read_file(path)
            assert err is None
            assert df is not None
            assert list(df.columns) == ["a", "b"]
            assert len(df) == 2
        finally:
            os.unlink(path)

    def test_excel_reading(self):
        path = "/tmp/_test_data_analyzer.xlsx"
        try:
            pd.DataFrame({"x": [1, 2]}).to_excel(path, index=False)
            df, err = _read_file(path)
            assert err is None
            assert df is not None
            assert list(df.columns) == ["x"]
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_json_reading(self):
        path = "/tmp/_test_data_analyzer.json"
        try:
            pd.DataFrame({"a": [1, 2]}).to_json(path)
            df, err = _read_file(path)
            assert err is None
            assert df is not None
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_json_lines_fallback(self):
        """JSON that fails normal parse but works with lines=True."""
        # Use .json extension; .jsonl is not a supported format.
        path = "/tmp/_test_data_analyzer.json"
        try:
            with open(path, "w") as f:
                f.write('{"a": 1}\n{"a": 2}\n')
            # First call to pd.read_json will raise ValueError, lines=True succeeds
            df, err = _read_file(path)
            assert err is None
            assert df is not None
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_json_chunked_fallback(self):
        """JSON that fails both normal and lines parse, falls back to chunked."""
        path = "/tmp/_test_data_analyzer.json"
        try:
            # Create a JSON file that requires chunked reading
            with open(path, "w") as f:
                f.write('[{"a": 1}, {"a": 2}]\n')

            # Mock read_json to fail on first two calls, succeed on chunked
            original_read_json = pd.read_json
            call_count = {"n": 0}

            def mock_read_json(*args, **kwargs):
                call_count["n"] += 1
                if kwargs.get("chunksize"):
                    # Return an iterator-like object
                    return iter([pd.DataFrame({"a": [1, 2]})])
                if call_count["n"] == 1:
                    raise ValueError("fail")
                if kwargs.get("lines"):
                    raise ValueError("fail")
                return original_read_json(*args, **kwargs)

            with patch("packages.harness.ideer.community.data_analyzer.tools.pd.read_json", side_effect=mock_read_json):
                with patch("packages.harness.ideer.community.data_analyzer.tools.pd", pd):
                    # Force re-import side effect: just call _read_file with the mock active
                    pass

            # Instead, directly test the chunked fallback path by mocking
            with patch("packages.harness.ideer.community.data_analyzer.tools.pd") as mock_pd:
                mock_pd.read_json.side_effect = [
                    ValueError("fail1"),  # first call
                    ValueError("fail2"),  # lines=True call
                    iter([pd.DataFrame({"a": [1, 2]})]),  # chunked call
                ]
                mock_pd.read_csv = pd.read_csv
                mock_pd.read_excel = pd.read_excel
                df, err = _read_file(path)
                assert err is None
                assert df is not None
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_json_all_parse_fail(self):
        """JSON that fails all parse attempts."""
        path = _tmp_bytes(b"not valid json at all {{{", suffix=".json")
        try:
            df, err = _read_file(path)
            assert df is None
            assert "failed to parse json" in err.lower()
        finally:
            os.unlink(path)

    def test_unsupported_format(self):
        path = _tmp_csv("data", suffix=".xml")
        try:
            df, err = _read_file(path)
            assert df is None
            assert "unsupported" in err.lower()
        finally:
            os.unlink(path)

    def test_generic_exception_during_read(self):
        path = _tmp_csv("a,b\n1,2\n")
        try:
            with patch("packages.harness.ideer.community.data_analyzer.tools.pd.read_csv", side_effect=RuntimeError("boom")):
                df, err = _read_file(path)
                assert df is None
                assert "failed to read file" in err.lower()
        finally:
            os.unlink(path)

    def test_decompression_bomb_protection(self):
        """DataFrame exceeding memory limit is rejected."""
        path = _tmp_csv("a,b\n1,2\n")
        try:
            fake_df = pd.DataFrame({"a": [1], "b": [2]})
            with patch("packages.harness.ideer.community.data_analyzer.tools.pd.read_csv", return_value=fake_df):
                with patch.object(pd.DataFrame, "memory_usage", return_value=pd.Series([_MAX_MEMORY_BYTES + 1])):
                    df, err = _read_file(path)
                    assert df is None
                    assert "too large after decompression" in err.lower()
        finally:
            os.unlink(path)

    def test_row_truncation(self):
        """DataFrame with more rows than _MAX_ROWS gets truncated."""
        path = _tmp_csv("a\n" + "\n".join(str(i) for i in range(_MAX_ROWS + 100)))
        try:
            # Create a mock df that reports more rows than _MAX_ROWS
            big_df = pd.DataFrame({"a": range(_MAX_ROWS + 100)})
            with patch("packages.harness.ideer.community.data_analyzer.tools.pd.read_csv", return_value=big_df):
                with patch.object(pd.DataFrame, "memory_usage", return_value=pd.Series([100])):
                    df, err = _read_file(path)
                    assert err is None
                    assert len(df) == _MAX_ROWS
        finally:
            os.unlink(path)

    def test_empty_file_returns_error(self):
        path = _tmp_csv("col1,col2\n")
        try:
            df, err = _read_file(path)
            assert df is None
            assert "empty" in err.lower()
        finally:
            os.unlink(path)

    def test_xls_extension(self):
        """Test .xls extension triggers Excel reader."""
        pytest.importorskip("xlwt")
        path = "/tmp/_test_data_analyzer.xls"
        try:
            pd.DataFrame({"x": [1]}).to_excel(path, index=False)
            df, err = _read_file(path)
            assert err is None
            assert df is not None
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── _analyze_summary ─────────────────────────────────────────────────────


class TestAnalyzeSummary:
    def test_basic_summary(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = _analyze_summary(df)
        assert result["shape"] == {"rows": 3, "columns": 2}
        assert len(result["columns"]) == 2
        assert result["columns"][0]["name"] == "a"
        assert result["columns"][0]["dtype"] == "int64"
        assert result["missing_values"] == {}
        assert "head" in result

    def test_missing_values_detected(self):
        df = pd.DataFrame({"a": [1, None, 3], "b": [None, None, 3]})
        result = _analyze_summary(df)
        assert result["missing_values"]["a"] == 1
        assert result["missing_values"]["b"] == 2

    def test_to_markdown_fallback(self):
        """When to_markdown raises, falls back to to_string."""
        df = pd.DataFrame({"a": [1, 2]})
        with patch.object(pd.DataFrame, "to_markdown", side_effect=ImportError("no tabulate")):
            result = _analyze_summary(df)
            assert "head" in result
            # to_string output should be present
            assert "a" in result["head"]


# ── _analyze_describe ────────────────────────────────────────────────────


class TestAnalyzeDescribe:
    def test_numeric_columns(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [10, 20, 30, 40, 50]})
        result = _analyze_describe(df)
        assert "numeric_summary" in result
        assert "mean" in result["numeric_summary"]

    def test_categorical_columns(self):
        df = pd.DataFrame({"cat": ["a", "b", "a", "c", "b", "a"]})
        result = _analyze_describe(df)
        assert "categorical_value_counts" in result
        assert "cat" in result["categorical_value_counts"]

    def test_no_numeric_or_categorical(self):
        """DataFrame with only datetime columns (no numeric, no object/category/bool)."""
        df = pd.DataFrame({"dt": pd.to_datetime(["2021-01-01", "2021-01-02"])})
        result = _analyze_describe(df)
        assert "message" in result
        assert "no numeric or categorical" in result["message"].lower()

    def test_mixed_columns(self):
        df = pd.DataFrame(
            {
                "num": [1, 2, 3],
                "cat": ["a", "b", "a"],
            }
        )
        result = _analyze_describe(df)
        assert "numeric_summary" in result
        assert "categorical_value_counts" in result

    def test_categorical_cap_at_20(self):
        """Only first 20 categorical columns are summarized."""
        data = {f"cat{i}": ["a", "b"] for i in range(25)}
        df = pd.DataFrame(data)
        result = _analyze_describe(df)
        assert "categorical_value_counts" in result
        assert len(result["categorical_value_counts"]) == 20


# ── _analyze_correlation ─────────────────────────────────────────────────


class TestAnalyzeCorrelation:
    def test_less_than_two_numeric_columns(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = _analyze_correlation(df)
        assert "error" in result
        assert "at least 2" in result["error"].lower()

    def test_no_numeric_columns(self):
        df = pd.DataFrame({"a": ["x", "y", "z"]})
        result = _analyze_correlation(df)
        assert "error" in result

    def test_basic_correlation(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]})
        result = _analyze_correlation(df)
        assert "correlation_matrix" in result
        # x and y are perfectly correlated
        assert "strong_correlations" in result
        assert len(result["strong_correlations"]) == 1
        assert result["strong_correlations"][0]["correlation"] == 1.0

    def test_no_strong_correlations(self):
        df = pd.DataFrame(
            {
                "x": [1, 2, 3, 4, 5],
                "y": [5, 3, 1, 4, 2],
            }
        )
        result = _analyze_correlation(df)
        assert "correlation_matrix" in result
        # Weak correlation, should not be in strong_correlations
        assert "strong_correlations" not in result

    def test_multiple_strong_correlations(self):
        df = pd.DataFrame(
            {
                "a": [1, 2, 3, 4, 5],
                "b": [2, 4, 6, 8, 10],
                "c": [10, 8, 6, 4, 2],
            }
        )
        result = _analyze_correlation(df)
        assert "strong_correlations" in result
        # a-b and a-c should both be strong
        assert len(result["strong_correlations"]) >= 2


# ── data_analyzer_tool (main entry point) ────────────────────────────────


class TestDataAnalyzerTool:
    def test_tool_is_invocable(self):
        assert hasattr(data_analyzer_tool, "invoke")

    def test_pandas_not_installed(self):
        with patch("packages.harness.ideer.community.data_analyzer.tools.pd", None):
            result = data_analyzer_tool.invoke({"file_path": "/tmp/test.csv"})
            data = json.loads(result)
            assert "error" in data
            assert "pandas" in data["error"].lower()

    def test_invalid_analysis_type(self):
        path = _tmp_csv("a,b\n1,2\n3,4\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "histogram"})
            data = json.loads(result)
            assert "error" in data
            assert "unknown" in data["error"].lower()
        finally:
            os.unlink(path)

    def test_read_error_returns_error(self):
        result = data_analyzer_tool.invoke({"file_path": "/etc/passwd"})
        data = json.loads(result)
        assert "error" in data
        assert "file_path" in data

    def test_summary_analysis(self):
        path = _tmp_csv("name,age\nAlice,30\nBob,25\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "summary"})
            data = json.loads(result)
            assert data["analysis_type"] == "summary"
            assert "result" in data
            assert "shape" in data["result"]
        finally:
            os.unlink(path)

    def test_describe_analysis(self):
        path = _tmp_csv("x,y\n1,10\n2,20\n3,30\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "describe"})
            data = json.loads(result)
            assert data["analysis_type"] == "describe"
            assert "result" in data
        finally:
            os.unlink(path)

    def test_correlation_analysis(self):
        path = _tmp_csv("x,y\n1,2\n3,4\n5,6\n7,8\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "correlation"})
            data = json.loads(result)
            assert data["analysis_type"] == "correlation"
            assert "result" in data
            assert "correlation_matrix" in data["result"]
        finally:
            os.unlink(path)

    def test_analysis_exception_returns_error(self):
        path = _tmp_csv("a,b\n1,2\n3,4\n")
        try:
            with patch(
                "packages.harness.ideer.community.data_analyzer.tools._analyze_summary",
                side_effect=RuntimeError("analysis boom"),
            ):
                result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "summary"})
                data = json.loads(result)
                assert "error" in data
                assert "analysis failed" in data["error"].lower()
        finally:
            os.unlink(path)

    def test_output_truncation(self):
        """When output exceeds _MAX_OUTPUT_CHARS, it gets truncated."""
        path = _tmp_csv("a,b\n1,2\n")
        try:
            # Create a result that would produce very long output
            huge_result = {"data": "x" * (_MAX_OUTPUT_CHARS + 5000)}
            with patch(
                "packages.harness.ideer.community.data_analyzer.tools._analyze_summary",
                return_value=huge_result,
            ):
                result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "summary"})
                data = json.loads(result)
                assert data.get("truncated") is True
                assert "result_summary" in data
                assert "... [truncated]" in data["result_summary"]
                assert len(result) <= _MAX_OUTPUT_CHARS
        finally:
            os.unlink(path)

    def test_output_truncation_binary_search_fits(self):
        """Truncation binary search finds a prefix that fits within limit."""
        path = _tmp_csv("a,b\n1,2\n")
        try:
            # Moderate size result that triggers truncation but binary search finds fit
            huge_result = {"data": "abcdefghij" * 2000}
            with patch(
                "packages.harness.ideer.community.data_analyzer.tools._analyze_summary",
                return_value=huge_result,
            ):
                result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "summary"})
                data = json.loads(result)
                assert data.get("truncated") is True
                assert len(result) <= _MAX_OUTPUT_CHARS
        finally:
            os.unlink(path)

    def test_normal_output_not_truncated(self):
        """Small output is returned as-is, not truncated."""
        path = _tmp_csv("a,b\n1,2\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path, "analysis_type": "summary"})
            data = json.loads(result)
            assert "truncated" not in data
            assert "result" in data
        finally:
            os.unlink(path)

    def test_default_analysis_type_is_summary(self):
        path = _tmp_csv("a,b\n1,2\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path})
            data = json.loads(result)
            assert data["analysis_type"] == "summary"
        finally:
            os.unlink(path)

    def test_file_path_in_output(self):
        path = _tmp_csv("a,b\n1,2\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path})
            data = json.loads(result)
            assert data["file_path"] == path
        finally:
            os.unlink(path)

    def test_path_rejected_returns_error_with_file_path(self):
        result = data_analyzer_tool.invoke({"file_path": "/etc/passwd"})
        data = json.loads(result)
        assert "error" in data
        assert "file_path" in data

    def test_empty_csv_error(self):
        path = _tmp_csv("col1,col2\n")
        try:
            result = data_analyzer_tool.invoke({"file_path": path})
            data = json.loads(result)
            assert "error" in data
            assert "empty" in data["error"].lower()
        finally:
            os.unlink(path)

    def test_unsupported_format_error(self):
        path = _tmp_csv("data", suffix=".xml")
        try:
            result = data_analyzer_tool.invoke({"file_path": path})
            data = json.loads(result)
            assert "error" in data
            assert "unsupported" in data["error"].lower()
        finally:
            os.unlink(path)
