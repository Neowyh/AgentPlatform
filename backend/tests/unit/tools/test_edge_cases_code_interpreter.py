"""Additional coverage tests for ideer.community.code_interpreter.tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ideer.community.code_interpreter import tools as ci_tools
from ideer.community.code_interpreter.tools import (
    _MAX_CODE_SIZE,
    _truncate_output,
    code_interpreter_tool,
)

# ===========================================================================
# _truncate_output
# ===========================================================================


class TestTruncateOutput:
    def test_disabled(self):
        output = "x" * 10000
        assert _truncate_output(output, 0) == output

    def test_short(self):
        assert _truncate_output("short", 100) == "short"

    def test_long(self):
        output = "x" * 50000
        result = _truncate_output(output, 200)
        assert len(result) <= 200
        assert "middle truncated" in result

    def test_preserves_head_and_tail(self):
        output = "HEAD" + "x" * 1000 + "TAIL"
        result = _truncate_output(output, 200)
        assert "HEAD" in result
        assert "TAIL" in result

    def test_kept_zero(self):
        output = "x" * 100
        result = _truncate_output(output, 1)
        assert len(result) <= 1

    def test_exact_length(self):
        output = "x" * 200
        assert _truncate_output(output, 200) == output


# ===========================================================================
# code_interpreter_tool — code too large
# ===========================================================================


class TestCodeInterpreterToolEdge:
    def test_code_too_large(self):
        result = code_interpreter_tool.invoke(
            {
                "code": "x = 1\n" * (_MAX_CODE_SIZE // 5 + 1),
            }
        )
        data = json.loads(result)
        assert "error" in data
        assert "too large" in data["error"].lower()

    def test_unsupported_language(self):
        result = code_interpreter_tool.invoke(
            {
                "code": "puts 'hello'",
                "language": "ruby",
            }
        )
        data = json.loads(result)
        assert "error" in data
        assert "unsupported" in data["error"].lower()

    def test_timeout_clamped_low(self):
        with patch.object(ci_tools, "ensure_sandbox_initialized", side_effect=RuntimeError("no sandbox")):
            result = code_interpreter_tool.invoke(
                {
                    "code": "print(1)",
                    "timeout": 0,
                }
            )
            data = json.loads(result)
            assert "error" in data

    def test_timeout_clamped_high(self):
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "ok"
        with patch.object(ci_tools, "ensure_sandbox_initialized", return_value=mock_sandbox):
            result = code_interpreter_tool.invoke(
                {
                    "code": 'print("ok")',
                    "timeout": 9999,
                }
            )
            data = json.loads(result)
            # Should succeed (timeout clamped to 300)
            assert data["exit_code"] == 0

    def test_sandbox_init_exception(self):
        with patch.object(ci_tools, "ensure_sandbox_initialized", side_effect=RuntimeError("no sandbox")):
            result = code_interpreter_tool.invoke({"code": "print(1)"})
            data = json.loads(result)
            assert "error" in data
            assert "sandbox" in data["error"].lower()

    def test_sandbox_execute_exception(self):
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = RuntimeError("execution failed")
        mock_sandbox.write_file = MagicMock()
        with patch.object(ci_tools, "ensure_sandbox_initialized", return_value=mock_sandbox):
            result = code_interpreter_tool.invoke({"code": "print(1)"})
            data = json.loads(result)
            assert "error" in data

    def test_timeout_exception(self):
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = RuntimeError("timed out after 60 seconds")
        mock_sandbox.write_file = MagicMock()
        with patch.object(ci_tools, "ensure_sandbox_initialized", return_value=mock_sandbox):
            result = code_interpreter_tool.invoke({"code": "print(1)", "timeout": 30})
            data = json.loads(result)
            assert "error" in data
            assert "timed out" in data["error"].lower()

    def test_cleanup_on_success(self):
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.return_value = "ok"
        with patch.object(ci_tools, "ensure_sandbox_initialized", return_value=mock_sandbox):
            result = code_interpreter_tool.invoke({"code": "print(1)"})
            data = json.loads(result)
            assert data["exit_code"] == 0
            # Cleanup should have been called
            assert mock_sandbox.execute_command.call_count == 2  # run + rm

    def test_cleanup_on_error(self):
        mock_sandbox = MagicMock()
        mock_sandbox.execute_command.side_effect = [RuntimeError("fail"), None]
        mock_sandbox.write_file = MagicMock()
        with patch.object(ci_tools, "ensure_sandbox_initialized", return_value=mock_sandbox):
            result = code_interpreter_tool.invoke({"code": "print(1)"})
            data = json.loads(result)
            assert "error" in data
            # Cleanup rm -f should have been attempted
