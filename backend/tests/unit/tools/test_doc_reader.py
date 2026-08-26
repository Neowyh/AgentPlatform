"""Tests for the document reader community tool."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from ideer.community.doc_reader.tools import (
    _parse_page_range,
    read_document_tool,
)

# ── Tool function basics ─────────────────────────────────────────────


def test_read_document_tool_is_invocable():
    assert hasattr(read_document_tool, "invoke")


# ── Error handling ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nonexistent_file_returns_error():
    result = await read_document_tool.ainvoke({"file_path": "/tmp/definitely_does_not_exist_12345.pdf"})
    data = json.loads(result)
    assert "error" in data
    assert "not found" in data["error"].lower() or "File not found" in data["error"]


@pytest.mark.asyncio
async def test_unsupported_extension_returns_error():
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"test")
        tmp_path = f.name
    try:
        result = await read_document_tool.ainvoke({"file_path": tmp_path})
        data = json.loads(result)
        assert "error" in data
        assert "unsupported" in data["error"].lower() or "Unsupported" in data["error"]
    finally:
        os.unlink(tmp_path)


# ── _parse_page_range ────────────────────────────────────────────────


def test_parse_page_range_single():
    assert _parse_page_range("3") == [2]


def test_parse_page_range_dash():
    assert _parse_page_range("1-5") == [0, 1, 2, 3, 4]


def test_parse_page_range_mixed():
    assert _parse_page_range("1-3,7") == [0, 1, 2, 6]


def test_parse_page_range_complex():
    assert _parse_page_range("1-3,7,10-12") == [0, 1, 2, 6, 9, 10, 11]


def test_parse_page_range_invalid_format():
    assert _parse_page_range("abc") is None


def test_parse_page_range_zero_returns_none():
    assert _parse_page_range("0") is None


def test_parse_page_range_reversed_range_returns_none():
    assert _parse_page_range("5-2") is None


def test_parse_page_range_empty_string():
    assert _parse_page_range("") is None


# ── Path security ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_path_outside_allowed_prefix_rejected():
    """Reading /etc/passwd should be rejected by path validation."""
    result = await read_document_tool.ainvoke({"file_path": "/etc/passwd"})
    data = json.loads(result)
    assert "error" in data
    assert "access denied" in data["error"].lower()


@pytest.mark.asyncio
async def test_path_traversal_rejected():
    """Path traversal attempting to escape allowed prefix should be rejected."""
    result = await read_document_tool.ainvoke({"file_path": "/mnt/user-data/../../../etc/passwd"})
    data = json.loads(result)
    assert "error" in data
