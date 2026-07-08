"""Comprehensive unit tests for tool_call_metadata.py helpers.

Tests:
  - _raw_tool_call_id: extracts string id from raw provider tool-call dicts
  - clone_ai_message_with_tool_calls: clones AIMessage while keeping
    additional_kwargs, response_metadata, and content in sync
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from ideer.agents.middlewares.tool_call_metadata import (
    _raw_tool_call_id,
    clone_ai_message_with_tool_calls,
)

# ============================================================================
# Helpers — build test data with minimal repetition
# ============================================================================


def _tc(
    name: str = "test_tool",
    tc_id: str = "call_1",
    args: dict | None = None,
) -> dict:
    return {"name": name, "id": tc_id, "args": args or {}}


def _raw_tc(
    name: str = "test_tool",
    tc_id: str = "call_1",
) -> dict:
    return {
        "name": name,
        "id": tc_id,
        "type": "function",
        "function": {"arguments": "{}"},
    }


def _make_msg(
    tool_calls: list[dict] | None = None,
    additional_kwargs: dict | None = None,
    response_metadata: dict | None = None,
    content: str = "",
    msg_id: str = "msg_1",
) -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=tool_calls or [],
        additional_kwargs=additional_kwargs or {},
        response_metadata=response_metadata or {},
        id=msg_id,
    )


# ============================================================================
# _raw_tool_call_id
# ============================================================================


class TestRawToolCallId:
    def test_none_returns_none(self):
        assert _raw_tool_call_id(None) is None

    def test_non_dict_returns_none(self):
        assert _raw_tool_call_id("not a dict") is None
        assert _raw_tool_call_id(42) is None
        assert _raw_tool_call_id(["list"]) is None

    def test_empty_dict_returns_none(self):
        assert _raw_tool_call_id({}) is None

    def test_empty_string_id_returns_none(self):
        assert _raw_tool_call_id({"id": ""}) is None

    def test_non_string_id_returns_none(self):
        assert _raw_tool_call_id({"id": 123}) is None
        assert _raw_tool_call_id({"id": True}) is None
        assert _raw_tool_call_id({"id": ["nested"]}) is None

    def test_valid_string_id_returns_id(self):
        assert _raw_tool_call_id({"id": "call_abc"}) == "call_abc"

    def test_valid_id_with_extra_keys(self):
        assert _raw_tool_call_id({"id": "call_xyz", "type": "function", "function": {}}) == "call_xyz"

    def test_missing_id_key_returns_none(self):
        assert _raw_tool_call_id({"name": "foo", "type": "function"}) is None


# ============================================================================
# clone_ai_message_with_tool_calls — core cloning
# ============================================================================


class TestCloneCore:
    def test_creates_new_message_with_updated_tool_calls(self):
        original = _make_msg(tool_calls=[_tc("old")], content="hello")
        new_tcs = [_tc("new", "call_2")]
        cloned = clone_ai_message_with_tool_calls(original, new_tcs)
        assert cloned.tool_calls == new_tcs
        assert cloned.tool_calls != original.tool_calls

    def test_preserves_original_message_content(self):
        original = _make_msg(content="original content")
        cloned = clone_ai_message_with_tool_calls(original, [_tc()])
        assert cloned.content == "original content"

    def test_preserves_original_message_id(self):
        original = _make_msg(msg_id="my-unique-id")
        cloned = clone_ai_message_with_tool_calls(original, [_tc()])
        assert cloned.id == "my-unique-id"

    def test_returns_new_instance_does_not_mutate_original(self):
        original = _make_msg(tool_calls=[_tc("original", "call_1")])
        original_tool_calls = list(original.tool_calls)
        new_tcs = [_tc("replacement", "call_2")]
        clone_ai_message_with_tool_calls(original, new_tcs)
        assert original.tool_calls == original_tool_calls


# ============================================================================
# clone_ai_message_with_tool_calls — additional_kwargs sync
# ============================================================================


class TestCloneAdditionalKwargs:
    def test_matching_raw_calls_are_preserved(self):
        original = _make_msg(
            tool_calls=[_tc("a", "call_keep")],
            additional_kwargs={
                "tool_calls": [
                    _raw_tc("a", "call_keep"),
                    _raw_tc("b", "call_drop"),
                ]
            },
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc("a", "call_keep")])
        assert len(cloned.additional_kwargs["tool_calls"]) == 1
        assert cloned.additional_kwargs["tool_calls"][0]["id"] == "call_keep"

    def test_non_matching_raw_calls_are_filtered_out(self):
        original = _make_msg(
            tool_calls=[_tc("old")],
            additional_kwargs={"tool_calls": [_raw_tc("old", "call_drop")]},
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc("new", "call_new")])
        assert "tool_calls" not in cloned.additional_kwargs

    def test_no_matching_raw_calls_removes_key(self):
        original = _make_msg(
            tool_calls=[_tc("a", "call_a")],
            additional_kwargs={"tool_calls": [_raw_tc("b", "call_b")]},
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc("c", "call_c")])
        assert "tool_calls" not in cloned.additional_kwargs

    def test_empty_additional_kwargs_works(self):
        original = _make_msg(additional_kwargs={})
        cloned = clone_ai_message_with_tool_calls(original, [_tc()])
        assert cloned.additional_kwargs == {}

    def test_additional_kwargs_is_none(self):
        msg = AIMessage(content="", tool_calls=[_tc()])
        msg.additional_kwargs = None
        cloned = clone_ai_message_with_tool_calls(msg, [_tc("a", "call_1")])
        assert cloned.additional_kwargs == {}

    def test_non_list_tool_calls_in_additional_kwargs_ignored(self):
        original = _make_msg(
            additional_kwargs={"tool_calls": "not-a-list"},
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc()])
        assert cloned.additional_kwargs == {"tool_calls": "not-a-list"}

    def test_empty_tool_calls_removes_function_call(self):
        original = _make_msg(
            tool_calls=[_tc()],
            additional_kwargs={"function_call": {"name": "foo"}},
        )
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert "function_call" not in cloned.additional_kwargs

    def test_non_empty_tool_calls_keeps_function_call(self):
        original = _make_msg(
            additional_kwargs={"function_call": {"name": "foo"}},
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc()])
        assert cloned.additional_kwargs["function_call"] == {"name": "foo"}

    def test_mixed_match_partial_filter(self):
        original = _make_msg(
            tool_calls=[_tc("a", "keep"), _tc("b", "keep_too")],
            additional_kwargs={
                "tool_calls": [
                    _raw_tc("a", "keep"),
                    _raw_tc("b", "keep_too"),
                    _raw_tc("c", "drop"),
                ]
            },
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc("a", "keep"), _tc("b", "keep_too")])
        assert len(cloned.additional_kwargs["tool_calls"]) == 2

    def test_populated_additional_kwargs_other_keys_preserved(self):
        original = _make_msg(
            tool_calls=[_tc("a", "keep")],
            additional_kwargs={
                "tool_calls": [_raw_tc("a", "keep")],
                "other_key": "still-here",
            },
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc("a", "keep")])
        assert cloned.additional_kwargs["other_key"] == "still-here"

    def test_empty_tool_calls_no_function_call_key(self):
        original = _make_msg(additional_kwargs={"tool_calls": [_raw_tc()]})
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert "function_call" not in cloned.additional_kwargs
        assert "tool_calls" not in cloned.additional_kwargs


# ============================================================================
# clone_ai_message_with_tool_calls — response_metadata sync
# ============================================================================


class TestCloneResponseMetadata:
    def test_empty_tool_calls_changes_finish_reason_tool_calls_to_stop(self):
        original = _make_msg(
            response_metadata={"finish_reason": "tool_calls"},
        )
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert cloned.response_metadata["finish_reason"] == "stop"

    def test_non_empty_tool_calls_keeps_finish_reason_unchanged(self):
        original = _make_msg(
            tool_calls=[_tc()],
            response_metadata={"finish_reason": "tool_calls"},
        )
        cloned = clone_ai_message_with_tool_calls(original, [_tc()])
        assert cloned.response_metadata["finish_reason"] == "tool_calls"

    def test_finish_reason_not_tool_calls_unchanged(self):
        original = _make_msg(
            response_metadata={"finish_reason": "stop"},
        )
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert cloned.response_metadata["finish_reason"] == "stop"

        original2 = _make_msg(
            response_metadata={"finish_reason": "length"},
        )
        cloned2 = clone_ai_message_with_tool_calls(original2, [_tc()])
        assert cloned2.response_metadata["finish_reason"] == "length"

    def test_empty_response_metadata_works(self):
        original = _make_msg(response_metadata={})
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert cloned.response_metadata == {}

    def test_response_metadata_is_none(self):
        msg = AIMessage(content="", tool_calls=[])
        msg.response_metadata = None
        cloned = clone_ai_message_with_tool_calls(msg, [])
        assert cloned.response_metadata == {}

    def test_empty_tool_calls_preserves_other_metadata_keys(self):
        original = _make_msg(
            tool_calls=[_tc()],
            response_metadata={
                "finish_reason": "tool_calls",
                "model_name": "gpt-4",
                "token_usage": {"total": 100},
            },
        )
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert cloned.response_metadata["finish_reason"] == "stop"
        assert cloned.response_metadata["model_name"] == "gpt-4"
        assert cloned.response_metadata["token_usage"] == {"total": 100}


# ============================================================================
# clone_ai_message_with_tool_calls — content handling
# ============================================================================


class TestCloneContent:
    def test_provided_content_is_set(self):
        original = _make_msg(content="original")
        cloned = clone_ai_message_with_tool_calls(original, [_tc()], content="overridden")
        assert cloned.content == "overridden"

    def test_provided_content_empty_string(self):
        original = _make_msg(content="original")
        cloned = clone_ai_message_with_tool_calls(original, [_tc()], content="")
        assert cloned.content == ""

    def test_content_is_none_preserves_original(self):
        original = _make_msg(content="original content")
        cloned = clone_ai_message_with_tool_calls(original, [_tc()], content=None)
        assert cloned.content == "original content"

    def test_preserves_list_content_when_no_content_arg(self):
        original = _make_msg(content="hello")
        cloned = clone_ai_message_with_tool_calls(original, [_tc()])
        assert cloned.content == "hello"


# ============================================================================
# clone_ai_message_with_tool_calls — edge cases / integration
# ============================================================================


class TestCloneEdgeCases:
    def test_empty_tool_calls_list(self):
        original = _make_msg(tool_calls=[_tc()])
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert cloned.tool_calls == []

    def test_tool_call_without_id_in_new_list_kept_metadata_unchanged(self):
        """A tool call without 'id' won't be in kept_ids, so raw calls are all dropped."""
        original = _make_msg(
            tool_calls=[_tc("a", "call_1")],
            additional_kwargs={"tool_calls": [_raw_tc("a", "call_1")]},
        )
        cloned = clone_ai_message_with_tool_calls(original, [{"name": "no_id", "args": {}}])
        assert "tool_calls" not in cloned.additional_kwargs

    def test_original_message_unchanged_after_clone(self):
        original = _make_msg(
            tool_calls=[_tc("a", "call_1")],
            additional_kwargs={"tool_calls": [_raw_tc("a", "call_1")]},
            response_metadata={"finish_reason": "tool_calls"},
            content="before",
        )
        original_tool_calls = list(original.tool_calls)
        clone_ai_message_with_tool_calls(original, [], content="after")
        assert original.tool_calls == original_tool_calls
        assert "tool_calls" in original.additional_kwargs
        assert original.response_metadata["finish_reason"] == "tool_calls"
        assert original.content == "before"

    def test_type_and_constructor_are_aimessage(self):
        cloned = clone_ai_message_with_tool_calls(_make_msg(), [_tc()])
        assert isinstance(cloned, AIMessage)

    def test_name_is_preserved(self):
        original = AIMessage(content="", tool_calls=[], name="assistant")
        cloned = clone_ai_message_with_tool_calls(original, [])
        assert cloned.name == "assistant"

    def test_none_tool_calls_raises_type_error(self):
        with pytest.raises(TypeError):
            clone_ai_message_with_tool_calls(_make_msg(), None)

    def test_non_dict_item_in_tool_calls_raises_attribute_error(self):
        with pytest.raises(AttributeError):
            clone_ai_message_with_tool_calls(_make_msg(), ["not_a_dict"])

    def test_clone_is_independent_from_input_list(self):
        original = _make_msg()
        new_tcs = [_tc("a", "call_1")]
        cloned = clone_ai_message_with_tool_calls(original, new_tcs)
        new_tcs.append(_tc("b", "call_2"))
        assert len(cloned.tool_calls) == 1
        assert cloned.tool_calls[0]["id"] == "call_1"
