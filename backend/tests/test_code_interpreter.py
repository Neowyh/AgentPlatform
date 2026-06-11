"""Tests for the code interpreter community tool."""

from __future__ import annotations

import json
import shutil
import subprocess
from unittest.mock import patch

import pytest

from packages.harness.ideer.community.code_interpreter import tools as ci_tools
from packages.harness.ideer.community.code_interpreter.tools import code_interpreter_tool

# ── Mock sandbox for testing ──────────────────────────────────────────


class _MockSandbox:
    """A minimal sandbox that executes commands directly via subprocess.

    Used only in tests — production code must use a real sandbox.
    """

    def execute_command(self, command: str) -> str:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout
            if result.stderr:
                output += f"\nStd Error:\n{result.stderr}"
            if result.returncode != 0:
                output += f"\nExit Code: {result.returncode}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out"

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        with open(path, "w" if not append else "a") as f:
            f.write(content)


@pytest.fixture(autouse=True)
def _mock_sandbox():
    """Patch ensure_sandbox_initialized to return a mock sandbox for all tests."""
    with patch.object(ci_tools, "ensure_sandbox_initialized", return_value=_MockSandbox()):
        yield


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


# ── Sandbox requirement ──────────────────────────────────────────────


def test_no_sandbox_returns_error():
    """Without a sandbox, the tool should return an error."""
    with patch.object(ci_tools, "ensure_sandbox_initialized", side_effect=RuntimeError("no sandbox")):
        result = code_interpreter_tool.invoke({"code": "print(1)"})
        data = json.loads(result)
        assert "error" in data
        assert "sandbox" in data["error"].lower()


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
