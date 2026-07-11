"""Additional coverage tests for dangling_tool_call_middleware.py.

Targets missed lines:
- Lines 57-75: raw provider tool_calls with function dict format
- Line 85: non-dict invalid_tool_calls entries
- Line 104: invalid tool call with no error string
- Line 140: tool call with no id (tc_id is None)
"""

import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, ToolMessage

from ideer.agents.middlewares.dangling_tool_call_middleware import (
    DanglingToolCallMiddleware,
)


class TestRawProviderToolCalls:
    """Lines 57-75: _message_tool_calls with raw provider payloads."""

    def test_raw_function_dict_name_from_function(self):
        """Line 62-63: name derived from function dict when top-level name absent."""
        mw = DanglingToolCallMiddleware()
        msg = AIMessage(
            content="",
            tool_calls=[],
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_raw_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"q":"test"}'},
                    }
                ]
            },
        )
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["name"] == "search"
        assert calls[0]["id"] == "call_raw_1"
        assert calls[0]["args"] == {"q": "test"}

    def test_raw_function_dict_args_from_function_arguments_json_string(self):
        """Lines 66-73: args parsed from function.arguments JSON string."""
        mw = DanglingToolCallMiddleware()
        msg = AIMessage(
            content="",
            tool_calls=[],
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_raw_2",
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "arguments": json.dumps({"command": "ls -la"}),
                        },
                    }
                ]
            },
        )
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["args"] == {"command": "ls -la"}

    def test_raw_function_dict_malformed_json_arguments(self):
        """Lines 70-72: malformed JSON in function.arguments -> empty args."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                {
                    "id": "call_raw_3",
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "arguments": "not-valid-json{{{",
                    },
                }
            ]
        }
        msg.invalid_tool_calls = None
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["args"] == {}

    def test_raw_function_dict_non_dict_parsed_args(self):
        """Lines 72-73: parsed args is not a dict (e.g., a list) -> empty args."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                {
                    "id": "call_raw_4",
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "arguments": json.dumps(["not", "a", "dict"]),
                    },
                }
            ]
        }
        msg.invalid_tool_calls = None
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["args"] == {}

    def test_raw_top_level_name_used_when_present(self):
        """Lines 61: name from top-level 'name' field when present."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                {
                    "id": "call_raw_5",
                    "name": "top_level_name",
                    "function": {"name": "func_name", "arguments": "{}"},
                }
            ]
        }
        msg.invalid_tool_calls = None
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["name"] == "top_level_name"

    def test_raw_no_name_no_function_falls_to_unknown(self):
        """Line 78: name defaults to 'unknown' when no name and no function dict."""
        mw = DanglingToolCallMiddleware()
        msg = AIMessage(
            content="",
            tool_calls=[],
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_raw_6",
                    }
                ]
            },
        )
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["name"] == "unknown"

    def test_raw_non_dict_entries_skipped(self):
        """Line 57-58: non-dict entries in raw_tool_calls are skipped."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                "not-a-dict",
                42,
                {
                    "id": "call_raw_7",
                    "name": "valid",
                },
            ]
        }
        msg.invalid_tool_calls = None
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["id"] == "call_raw_7"

    def test_raw_args_not_a_dict_fallback(self):
        """Line 79: args is not a dict -> empty dict."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                {
                    "id": "call_raw_8",
                    "name": "tool",
                    "args": "not-a-dict",
                }
            ]
        }
        msg.invalid_tool_calls = None
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["args"] == {}

    def test_raw_top_level_args_used_when_present(self):
        """Line 65: args from top-level 'args' when present."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                {
                    "id": "call_raw_9",
                    "name": "tool",
                    "args": {"key": "val"},
                }
            ]
        }
        msg.invalid_tool_calls = None
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["args"] == {"key": "val"}

    def test_raw_function_arguments_is_not_string(self):
        """Lines 67-73: function.arguments is not a string -> empty args."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                {
                    "id": "call_raw_10",
                    "function": {
                        "name": "bash",
                        "arguments": 12345,
                    },
                }
            ]
        }
        msg.invalid_tool_calls = None
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["args"] == {}


class TestNonDictInvalidToolCalls:
    """Line 85: non-dict entries in invalid_tool_calls are skipped."""

    def test_non_dict_invalid_tool_call_skipped(self):
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {}
        msg.invalid_tool_calls = ["not-a-dict", 42]
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 0

    def test_mixed_valid_and_non_dict_invalid(self):
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {}
        msg.invalid_tool_calls = [
            "not-a-dict",
            {
                "type": "invalid_tool_call",
                "name": "tool",
                "id": "inv_1",
                "args": "{}",
                "error": "bad args",
            },
        ]
        calls = mw._message_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["id"] == "inv_1"


class TestSyntheticContentInvalidNoError:
    """Line 104: invalid tool call with no error string."""

    def test_invalid_with_none_error(self):
        mw = DanglingToolCallMiddleware()
        content = mw._synthetic_tool_message_content({"invalid": True, "error": None})
        assert "could not be executed" in content
        assert "invalid" not in content.lower() or "arguments were invalid" in content

    def test_invalid_with_empty_string_error(self):
        mw = DanglingToolCallMiddleware()
        content = mw._synthetic_tool_message_content({"invalid": True, "error": ""})
        assert "could not be executed" in content

    def test_invalid_with_non_string_error(self):
        mw = DanglingToolCallMiddleware()
        content = mw._synthetic_tool_message_content({"invalid": True, "error": 123})
        assert "could not be executed" in content


class TestToolCallWithNoId:
    """Line 140: tool call where tc_id is None is skipped."""

    def test_tool_call_no_id_skipped(self):
        mw = DanglingToolCallMiddleware()
        msgs = [
            AIMessage(
                content="",
                tool_calls=[{"name": "bash", "id": None, "args": {}}],
            )
        ]
        # The tool call has no id, so no synthetic message is created.
        # _build_patched_messages should return None since there's nothing to patch.
        result = mw._build_patched_messages(msgs)
        assert result is None

    def test_raw_provider_tool_call_patched_in_build(self):
        """Lines 57-75 + 137-155: raw tool calls get patched end-to-end."""
        mw = DanglingToolCallMiddleware()
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "tool_calls": [
                {
                    "id": "raw_tc_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"q":"test"}'},
                }
            ]
        }
        msg.invalid_tool_calls = None
        msg.type = "ai"
        msgs = [msg]
        patched = mw._build_patched_messages(msgs)
        assert patched is not None
        assert len(patched) == 2
        assert isinstance(patched[1], ToolMessage)
        assert patched[1].tool_call_id == "raw_tc_1"
        assert patched[1].name == "search"
        assert patched[1].status == "error"
        assert "interrupted" in patched[1].content.lower()
