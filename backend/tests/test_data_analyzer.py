"""Tests for the data analyzer community tool."""

from __future__ import annotations

import json
import os
import tempfile

from packages.harness.ideer.community.data_analyzer.tools import data_analyzer_tool

# ── Tool function basics ─────────────────────────────────────────────


def test_data_analyzer_tool_is_invocable():
    assert hasattr(data_analyzer_tool, "invoke")


# ── Error handling ───────────────────────────────────────────────────


def test_nonexistent_file_returns_error():
    result = data_analyzer_tool.invoke({"file_path": "/tmp/does_not_exist_12345.csv"})
    data = json.loads(result)
    assert "error" in data
    assert "not found" in data["error"].lower() or "File not found" in data["error"]


def test_empty_csv_returns_error():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("col1,col2\n")
        tmp_path = f.name
    try:
        result = data_analyzer_tool.invoke({"file_path": tmp_path})
        data = json.loads(result)
        assert "error" in data
        assert "empty" in data["error"].lower()
    finally:
        os.unlink(tmp_path)


def test_invalid_analysis_type_returns_error():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("a,b\n1,2\n3,4\n")
        tmp_path = f.name
    try:
        result = data_analyzer_tool.invoke({"file_path": tmp_path, "analysis_type": "histogram"})
        data = json.loads(result)
        assert "error" in data
        assert "unknown" in data["error"].lower() or "Unknown" in data["error"]
    finally:
        os.unlink(tmp_path)


# ── Summary analysis ─────────────────────────────────────────────────


def test_summary_contains_expected_keys():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("name,age,city\nAlice,30,NYC\nBob,25,LA\nCharlie,35,Chicago\n")
        tmp_path = f.name
    try:
        result = data_analyzer_tool.invoke({"file_path": tmp_path, "analysis_type": "summary"})
        data = json.loads(result)
        assert "result" in data
        res = data["result"]
        assert "shape" in res
        assert "columns" in res
        assert "missing_values" in res
        assert "head" in res
        assert res["shape"]["rows"] == 3
        assert res["shape"]["columns"] == 3
    finally:
        os.unlink(tmp_path)


# ── Describe analysis ────────────────────────────────────────────────


def test_describe_contains_statistics():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("x,y\n1,10\n2,20\n3,30\n4,40\n5,50\n")
        tmp_path = f.name
    try:
        result = data_analyzer_tool.invoke({"file_path": tmp_path, "analysis_type": "describe"})
        data = json.loads(result)
        assert "result" in data
        res = data["result"]
        assert "numeric_summary" in res
        # The numeric summary should contain standard stats
        assert "mean" in res["numeric_summary"] or "count" in res["numeric_summary"]
    finally:
        os.unlink(tmp_path)


# ── Path security ────────────────────────────────────────────────────


def test_path_outside_allowed_prefix_rejected():
    """Reading /etc/passwd should be rejected by path validation."""
    result = data_analyzer_tool.invoke({"file_path": "/etc/passwd"})
    data = json.loads(result)
    assert "error" in data
    assert "access denied" in data["error"].lower()


def test_path_traversal_rejected():
    """Path traversal attempting to escape allowed prefix should be rejected."""
    result = data_analyzer_tool.invoke({"file_path": "/mnt/user-data/../../../etc/shadow"})
    data = json.loads(result)
    assert "error" in data
