"""Tests for the code interpreter community tool."""

from __future__ import annotations

import json
import shutil

import pytest

from packages.harness.ideer.community.code_interpreter.tools import code_interpreter_tool

# ── Tool function basics ─────────────────────────────────────────────


def test_code_interpreter_tool_is_invocable():
    assert hasattr(code_interpreter_tool, "invoke")


# ── Python execution ────────────────────────────────────────────────


def test_python_print_expression():
    result = code_interpreter_tool.invoke({"code": "print(2+2)"})
    data = json.loads(result)
    assert data["exit_code"] == 0
    assert "4" in data["stdout"]


# ── Error handling ───────────────────────────────────────────────────


def test_invalid_language_returns_error():
    result = code_interpreter_tool.invoke({"code": "x = 1", "language": "ruby"})
    data = json.loads(result)
    assert "error" in data
    assert "unsupported" in data["error"].lower() or "Unsupported" in data["error"]


# ── Timeout clamping ─────────────────────────────────────────────────


def test_timeout_clamped_to_max():
    """The tool should clamp timeout values above 300 down to 300.

    We verify this indirectly: the call should succeed (not raise) and
    produce valid JSON output rather than erroring on a huge timeout.
    """
    result = code_interpreter_tool.invoke({"code": 'print("ok")', "timeout": 999})
    data = json.loads(result)
    assert data["exit_code"] == 0
    assert "ok" in data["stdout"]


# ── JavaScript execution (skipped if node unavailable) ──────────────


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not installed",
)
def test_javascript_hello():
    result = code_interpreter_tool.invoke({"code": 'console.log("hello")', "language": "javascript"})
    data = json.loads(result)
    assert data["exit_code"] == 0
    assert "hello" in data["stdout"]
