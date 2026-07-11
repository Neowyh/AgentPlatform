"""Additional coverage tests for sandbox_audit_middleware.py.

Targets missed lines:
- Lines 85-88: escaping in _split_compound_command (backslash in progress)
- Lines 91-94: starting new escape sequence in _split_compound_command
- Lines 151-154: shlex.split fails in _classify_single_command
- Line 223: runtime is None in _get_thread_id
- Lines 227-228: thread_id falls back to config.configurable
- Line 257: _append_warn_to_result with non-ToolMessage result
- Line 260: result.content is a list in _append_warn_to_result
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import ToolMessage

from ideer.agents.middlewares.sandbox_audit_middleware import (
    SandboxAuditMiddleware,
    _classify_single_command,
    _split_compound_command,
)


class TestSplitCompoundCommandEscaping:
    """Lines 85-88, 91-94: backslash escaping in _split_compound_command."""

    def test_escaped_semicolon_not_split(self):
        r"""A backslash-escaped semicolon (\;) should not be treated as a separator."""
        result = _split_compound_command(r"echo hello\;world")
        assert len(result) == 1
        assert "hello" in result[0]

    def test_escaped_and_not_split(self):
        r"""A backslash-escaped && should not split."""
        result = _split_compound_command(r"echo hello\&\&world")
        assert len(result) == 1

    def test_escape_at_end_returns_whole(self):
        """Line 128: dangling backslash at end -> fail-closed, return whole."""
        result = _split_compound_command("echo hello\\")
        assert result == ["echo hello\\"]

    def test_escaped_char_in_middle(self):
        """Escaped character in middle of command."""
        result = _split_compound_command(r"echo a\ b && ls")
        assert len(result) == 2

    def test_escaped_quote_in_single_quotes(self):
        """Backslash inside single quotes is literal (not an escape)."""
        result = _split_compound_command("echo '\\' && ls")
        assert len(result) == 2


class TestSplitCompoundCommandOrOperator:
    """Lines 91-94: || operator splitting (actually this is about `||` not the or)."""

    def test_or_operator_splitting(self):
        """Lines 109-115: || operator splits commands."""
        result = _split_compound_command("cmd1 || cmd2")
        assert result == ["cmd1", "cmd2"]

    def test_or_operator_no_whitespace(self):
        result = _split_compound_command("cmd1||cmd2")
        assert result == ["cmd1", "cmd2"]


class TestClassifySingleCommandShlexFailure:
    """Lines 151-154: shlex.split fails -> classify as block."""

    def test_unclosed_single_quote_blocks(self):
        """shlex.split fails on unclosed quote -> block."""
        result = _classify_single_command("echo 'unclosed")
        assert result == "block"

    def test_unclosed_double_quote_blocks(self):
        result = _classify_single_command('echo "unclosed')
        assert result == "block"

    def test_trailing_backslash_blocks(self):
        result = _classify_single_command("echo hello\\")
        assert result == "block"


class TestClassifySingleCommandShlexHighRisk:
    """Line 151: shlex-normalized tokens match high-risk pattern that raw string didn't."""

    def test_quoted_dangerous_command_blocked(self):
        """Shell-quoted dangerous command -> shlex normalization reveals high-risk pattern."""
        # The raw string 'echo "rm" "-rf" "/"' does NOT match the high-risk
        # regex because quotes break the pattern. But after shlex parsing,
        # it becomes 'echo rm -rf /' which DOES match.
        result = _classify_single_command('echo "rm" "-rf" "/"')
        assert result == "block"

    def test_quoted_dd_command_blocked(self):
        """Shell-quoted dd command blocked via shlex normalization."""
        result = _classify_single_command('"dd" "if=/dev/zero" "of=/dev/sda"')
        assert result == "block"


class TestGetThreadIdEdgeCases:
    """Lines 223, 227-228: _get_thread_id edge cases."""

    def test_runtime_none_returns_none(self):
        """Line 223: runtime is None -> return None."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.runtime = None
        assert mw._get_thread_id(request) is None

    def test_thread_id_from_configurable(self):
        """Lines 227-228: thread_id from config.configurable when not in context."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.runtime = SimpleNamespace(
            context={},
            config={"configurable": {"thread_id": "cfg-thread"}},
        )
        assert mw._get_thread_id(request) == "cfg-thread"

    def test_context_not_dict(self):
        """context is not a dict -> falls back to config."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.runtime = SimpleNamespace(
            context="not-a-dict",
            config={"configurable": {"thread_id": "from-cfg"}},
        )
        assert mw._get_thread_id(request) == "from-cfg"

    def test_context_none_falls_back(self):
        """context is None -> falls back to config."""
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.runtime = SimpleNamespace(
            context=None,
            config={"configurable": {"thread_id": "from-cfg"}},
        )
        assert mw._get_thread_id(request) == "from-cfg"


class TestAppendWarnToResultEdgeCases:
    """Lines 257, 260: _append_warn_to_result edge cases."""

    def test_non_tool_message_returns_unchanged(self):
        """Line 257: result is not a ToolMessage -> return as-is."""
        mw = SandboxAuditMiddleware()
        from langgraph.types import Command

        cmd = Command(update={"key": "value"})
        result = mw._append_warn_to_result(cmd, "pip install foo")
        assert result is cmd

    def test_list_content_gets_appended(self):
        """Line 260: result.content is a list -> append text entry."""
        mw = SandboxAuditMiddleware()
        tool_msg = ToolMessage(
            content=[{"type": "text", "text": "output"}],
            tool_call_id="tc-1",
            name="bash",
        )
        result = mw._append_warn_to_result(tool_msg, "pip install foo")
        assert isinstance(result, ToolMessage)
        assert isinstance(result.content, list)
        assert len(result.content) == 2
        assert "warning" in result.content[1]["text"].lower()

    def test_string_content_gets_appended(self):
        """String content gets warning appended."""
        mw = SandboxAuditMiddleware()
        tool_msg = ToolMessage(
            content="output",
            tool_call_id="tc-1",
            name="bash",
        )
        result = mw._append_warn_to_result(tool_msg, "pip install foo")
        assert isinstance(result, ToolMessage)
        assert isinstance(result.content, str)
        assert "warning" in result.content.lower()


class TestAuditLogTruncation:
    """Test _write_audit with truncate=True for long commands."""

    def test_long_command_truncated_in_audit(self):
        mw = SandboxAuditMiddleware()
        long_cmd = "x" * 300
        # Should not raise
        mw._write_audit("thread-1", long_cmd, "pass", truncate=True)

    def test_short_command_not_truncated(self):
        mw = SandboxAuditMiddleware()
        mw._write_audit("thread-1", "ls", "pass", truncate=False)


class TestBuildBlockMessage:
    """Test _build_block_message."""

    def test_block_message_format(self):
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"id": "call-123", "name": "bash", "args": {}}
        result = mw._build_block_message(request, "security violation detected")
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert "blocked" in result.content.lower()
        assert result.tool_call_id == "call-123"
        assert result.name == "bash"

    def test_block_message_missing_id(self):
        mw = SandboxAuditMiddleware()
        request = MagicMock()
        request.tool_call = {"name": "bash", "args": {}}
        result = mw._build_block_message(request, "danger")
        assert result.tool_call_id == "missing_id"
