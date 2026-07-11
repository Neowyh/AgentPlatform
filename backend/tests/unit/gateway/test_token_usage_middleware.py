"""Tests for TokenUsageMiddleware and attribution helpers."""

from __future__ import annotations

import importlib
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ideer.agents.middlewares.token_usage_middleware import (
    TOKEN_USAGE_ATTRIBUTION_KEY,
    TokenUsageMiddleware,
    _build_attribution,
    _build_todo_actions,
    _describe_tool_call,
    _has_tool_call,
    _infer_step_kind,
    _normalize_todos,
    _string_arg,
    _todo_action_kind,
)

# ---------------------------------------------------------------------------
# _string_arg
# ---------------------------------------------------------------------------


class TestStringArg:
    def test_returns_stripped_string(self):
        assert _string_arg("  hello  ") == "hello"

    def test_returns_none_for_whitespace_only(self):
        assert _string_arg("   ") is None

    def test_returns_none_for_empty_string(self):
        assert _string_arg("") is None

    def test_returns_none_for_non_string_int(self):
        assert _string_arg(123) is None

    def test_returns_none_for_non_string_none(self):
        assert _string_arg(None) is None

    def test_returns_none_for_non_string_list(self):
        assert _string_arg(["a"]) is None

    def test_returns_clean_string(self):
        assert _string_arg("test") == "test"


# ---------------------------------------------------------------------------
# _normalize_todos
# ---------------------------------------------------------------------------


class TestNormalizeTodos:
    def test_returns_empty_for_non_list_none(self):
        assert _normalize_todos(None) == []

    def test_returns_empty_for_non_list_string(self):
        assert _normalize_todos("not a list") == []

    def test_returns_empty_for_non_list_int(self):
        assert _normalize_todos(42) == []

    def test_skips_non_dict_items(self):
        assert _normalize_todos(["foo", 123, None]) == []

    def test_normalizes_valid_todo(self):
        result = _normalize_todos([{"content": "  buy milk  ", "status": "pending"}])
        assert len(result) == 1
        assert result[0]["content"] == "buy milk"
        assert result[0]["status"] == "pending"

    def test_ignores_invalid_status(self):
        result = _normalize_todos([{"content": "task", "status": "invalid"}])
        assert len(result) == 1
        assert "status" not in result[0]

    def test_content_whitespace_only_drops_content_key(self):
        result = _normalize_todos([{"content": "   ", "status": "completed"}])
        assert len(result) == 1
        assert "content" not in result[0]
        assert result[0]["status"] == "completed"

    def test_valid_statuses_all_accepted(self):
        for status in ("pending", "in_progress", "completed"):
            result = _normalize_todos([{"content": "c", "status": status}])
            assert result[0]["status"] == status

    def test_empty_dict_item(self):
        result = _normalize_todos([{}])
        assert len(result) == 1
        assert result[0] == {}


# ---------------------------------------------------------------------------
# _todo_action_kind
# ---------------------------------------------------------------------------


class TestTodoActionKind:
    def test_no_previous_completed(self):
        assert _todo_action_kind(None, {"status": "completed"}) == "todo_complete"

    def test_no_previous_in_progress(self):
        assert _todo_action_kind(None, {"status": "in_progress"}) == "todo_start"

    def test_no_previous_pending(self):
        assert _todo_action_kind(None, {"status": "pending"}) == "todo_update"

    def test_no_previous_no_status(self):
        assert _todo_action_kind(None, {}) == "todo_update"

    def test_content_changed(self):
        prev = {"content": "old"}
        curr = {"content": "new", "status": "in_progress"}
        assert _todo_action_kind(prev, curr) == "todo_update"

    def test_same_content_completed(self):
        prev = {"content": "task"}
        curr = {"content": "task", "status": "completed"}
        assert _todo_action_kind(prev, curr) == "todo_complete"

    def test_same_content_in_progress(self):
        prev = {"content": "task"}
        curr = {"content": "task", "status": "in_progress"}
        assert _todo_action_kind(prev, curr) == "todo_start"

    def test_same_content_other_status(self):
        prev = {"content": "task"}
        curr = {"content": "task", "status": "pending"}
        assert _todo_action_kind(prev, curr) == "todo_update"


# ---------------------------------------------------------------------------
# _build_todo_actions
# ---------------------------------------------------------------------------


class TestBuildTodoActions:
    def test_empty_lists(self):
        assert _build_todo_actions([], []) == []

    def test_new_todo_added(self):
        actions = _build_todo_actions([], [{"content": "task1", "status": "in_progress"}])
        assert len(actions) == 1
        assert actions[0]["kind"] == "todo_start"
        assert actions[0]["content"] == "task1"

    def test_todo_removed(self):
        actions = _build_todo_actions([{"content": "task1"}], [])
        assert len(actions) == 1
        assert actions[0]["kind"] == "todo_remove"
        assert actions[0]["content"] == "task1"

    def test_todo_status_change(self):
        prev = [{"content": "task1", "status": "pending"}]
        curr = [{"content": "task1", "status": "completed"}]
        actions = _build_todo_actions(prev, curr)
        assert len(actions) == 1
        assert actions[0]["kind"] == "todo_complete"

    def test_unchanged_todo_skipped(self):
        prev = [{"content": "task1", "status": "pending"}]
        curr = [{"content": "task1", "status": "pending"}]
        actions = _build_todo_actions(prev, curr)
        assert actions == []

    def test_content_change_detected(self):
        prev = [{"content": "old", "status": "pending"}]
        curr = [{"content": "new", "status": "pending"}]
        actions = _build_todo_actions(prev, curr)
        # "old" positionally matched to "new" but content differs -> todo_update
        assert any(a["content"] == "new" for a in actions)
        # "old" was matched positionally so it's NOT removed
        assert not any(a.get("content") == "old" and a["kind"] == "todo_remove" for a in actions)

    def test_previous_todo_without_content_skipped_in_removal(self):
        prev = [{"status": "pending"}]
        curr = []
        actions = _build_todo_actions(prev, curr)
        assert actions == []

    def test_next_todo_without_content_skipped(self):
        prev = []
        curr = [{"status": "pending"}]
        actions = _build_todo_actions(prev, curr)
        assert actions == []

    def test_positional_fallback_matching(self):
        prev = [{"content": "taskA", "status": "pending"}]
        curr = [{"content": "taskB", "status": "completed"}]
        actions = _build_todo_actions(prev, curr)
        # taskA positionally matched to taskB (content differs) -> todo_update for taskB
        # taskA is matched so NOT removed
        assert any(a["content"] == "taskB" for a in actions)
        assert not any(a.get("content") == "taskA" and a["kind"] == "todo_remove" for a in actions)

    def test_multiple_todos_mixed(self):
        prev = [
            {"content": "a", "status": "pending"},
            {"content": "b", "status": "in_progress"},
        ]
        curr = [
            {"content": "a", "status": "completed"},
            {"content": "c", "status": "pending"},
        ]
        actions = _build_todo_actions(prev, curr)
        # "a" matched by content, status changed -> todo_complete
        assert any(a["kind"] == "todo_complete" and a["content"] == "a" for a in actions)
        # "c" matched positionally to "b" (content differs) -> todo_update
        assert any(a["content"] == "c" for a in actions)
        # "b" was positionally matched to "c" so it's NOT removed
        assert not any(a.get("content") == "b" and a["kind"] == "todo_remove" for a in actions)

    def test_previous_empty_content_skipped_in_removal(self):
        prev = [{"content": ""}]
        curr = []
        actions = _build_todo_actions(prev, curr)
        assert actions == []


# ---------------------------------------------------------------------------
# _describe_tool_call
# ---------------------------------------------------------------------------


class TestDescribeToolCall:
    def test_write_todos_with_actions(self):
        tc = {
            "name": "write_todos",
            "id": "tc1",
            "args": {"todos": [{"content": "task1", "status": "pending"}]},
        }
        result = _describe_tool_call(tc, [])
        assert len(result) >= 1
        assert result[0]["tool_call_id"] == "tc1"

    def test_write_todos_no_actions_returns_generic(self):
        tc = {
            "name": "write_todos",
            "id": "tc1",
            "args": {"todos": []},
        }
        result = _describe_tool_call(tc, [])
        assert len(result) == 1
        assert result[0]["kind"] == "tool"
        assert result[0]["tool_name"] == "write_todos"

    def test_task_tool(self):
        tc = {
            "name": "task",
            "id": "tc2",
            "args": {"description": "do stuff", "subagent_type": "general"},
        }
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "subagent"
        assert result[0]["description"] == "do stuff"
        assert result[0]["subagent_type"] == "general"

    def test_web_search(self):
        tc = {"name": "web_search", "id": "tc3", "args": {"query": "python"}}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "search"
        assert result[0]["query"] == "python"

    def test_image_search(self):
        tc = {"name": "image_search", "id": "tc4", "args": {"query": "cat"}}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "search"
        assert result[0]["tool_name"] == "image_search"

    def test_present_files(self):
        tc = {"name": "present_files", "id": "tc5", "args": {}}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "present_files"

    def test_ask_clarification(self):
        tc = {"name": "ask_clarification", "id": "tc6", "args": {}}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "clarification"

    def test_generic_tool(self):
        tc = {"name": "read_file", "id": "tc7", "args": {"description": "read it"}}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "tool"
        assert result[0]["tool_name"] == "read_file"
        assert result[0]["description"] == "read it"

    def test_missing_name_defaults_to_unknown(self):
        tc = {"id": "tc8", "args": {}}
        result = _describe_tool_call(tc, [])
        assert result[0]["tool_name"] == "unknown"

    def test_non_dict_args_handled(self):
        tc = {"name": "foo", "id": "tc9", "args": "invalid"}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "tool"

    def test_missing_id_returns_none(self):
        tc = {"name": "foo", "args": {}}
        result = _describe_tool_call(tc, [])
        assert result[0]["tool_call_id"] is None

    def test_task_with_none_description_and_subagent_type(self):
        tc = {"name": "task", "id": "tc10", "args": {}}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "subagent"
        assert result[0]["description"] is None
        assert result[0]["subagent_type"] is None

    def test_search_with_none_query(self):
        tc = {"name": "web_search", "id": "tc11", "args": {}}
        result = _describe_tool_call(tc, [])
        assert result[0]["kind"] == "search"
        assert result[0]["query"] is None


# ---------------------------------------------------------------------------
# _infer_step_kind
# ---------------------------------------------------------------------------


class TestInferStepKind:
    def test_single_todo_action(self):
        msg = AIMessage(content="")
        actions = [{"kind": "todo_start", "content": "task"}]
        assert _infer_step_kind(msg, actions) == "todo_update"

    def test_single_subagent_action(self):
        msg = AIMessage(content="")
        actions = [{"kind": "subagent"}]
        assert _infer_step_kind(msg, actions) == "subagent_dispatch"

    def test_multiple_actions(self):
        msg = AIMessage(content="")
        actions = [{"kind": "tool"}, {"kind": "search"}]
        assert _infer_step_kind(msg, actions) == "tool_batch"

    def test_no_actions_with_content(self):
        msg = AIMessage(content="Hello!")
        assert _infer_step_kind(msg, []) == "final_answer"

    def test_no_actions_no_content(self):
        msg = AIMessage(content="")
        assert _infer_step_kind(msg, []) == "thinking"

    def test_single_todo_complete(self):
        msg = AIMessage(content="")
        actions = [{"kind": "todo_complete"}]
        assert _infer_step_kind(msg, actions) == "todo_update"

    def test_single_todo_update(self):
        msg = AIMessage(content="")
        actions = [{"kind": "todo_update"}]
        assert _infer_step_kind(msg, actions) == "todo_update"

    def test_single_todo_remove(self):
        msg = AIMessage(content="")
        actions = [{"kind": "todo_remove"}]
        assert _infer_step_kind(msg, actions) == "todo_update"


# ---------------------------------------------------------------------------
# _has_tool_call
# ---------------------------------------------------------------------------


class TestHasToolCall:
    def test_finds_tool_call_by_id(self):
        msg = AIMessage(content="", tool_calls=[{"id": "tc1", "name": "foo", "args": {}}])
        assert _has_tool_call(msg, "tc1") is True

    def test_returns_false_when_not_found(self):
        msg = AIMessage(content="", tool_calls=[{"id": "tc1", "name": "foo", "args": {}}])
        assert _has_tool_call(msg, "tc2") is False

    def test_handles_none_tool_calls(self):
        msg = AIMessage(content="")
        msg.tool_calls = None
        assert _has_tool_call(msg, "tc1") is False

    def test_handles_object_with_id_attr(self):
        tc = SimpleNamespace(id="tc_obj")
        msg = AIMessage(content="")
        # Manually set tool_calls to bypass langchain validation
        msg.tool_calls = [tc]
        assert _has_tool_call(msg, "tc_obj") is True
        assert _has_tool_call(msg, "other") is False

    def test_empty_tool_calls(self):
        msg = AIMessage(content="", tool_calls=[])
        assert _has_tool_call(msg, "tc1") is False


# ---------------------------------------------------------------------------
# _build_attribution
# ---------------------------------------------------------------------------


class TestBuildAttribution:
    def test_no_tool_calls_final_answer(self):
        msg = AIMessage(content="Hello")
        result = _build_attribution(msg, [])
        assert result["version"] == 1
        assert result["kind"] == "final_answer"
        assert result["shared_attribution"] is False
        assert result["tool_call_ids"] == []
        assert result["actions"] == []

    def test_no_tool_calls_thinking(self):
        msg = AIMessage(content="")
        result = _build_attribution(msg, [])
        assert result["kind"] == "thinking"

    def test_single_tool_call(self):
        msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc1", "name": "read_file", "args": {"description": "read"}}],
        )
        result = _build_attribution(msg, [])
        assert result["kind"] == "tool_batch"
        assert result["tool_call_ids"] == ["tc1"]
        assert len(result["actions"]) == 1

    def test_multiple_tool_calls_shared(self):
        msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "tc1", "name": "read_file", "args": {}},
                {"id": "tc2", "name": "web_search", "args": {"query": "q"}},
            ],
        )
        result = _build_attribution(msg, [])
        assert result["shared_attribution"] is True
        assert len(result["tool_call_ids"]) == 2

    def test_write_todos_updates_current_todos(self):
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "write_todos",
                    "args": {"todos": [{"content": "task1", "status": "pending"}]},
                },
                {"id": "tc2", "name": "read_file", "args": {}},
            ],
        )
        result = _build_attribution(msg, [])
        assert len(result["actions"]) >= 2

    def test_non_dict_tool_call_skipped(self):
        msg = AIMessage(content="")
        msg.tool_calls = [MagicMock()]
        result = _build_attribution(msg, [])
        assert result["tool_call_ids"] == []

    def test_version_is_1(self):
        msg = AIMessage(content="")
        result = _build_attribution(msg, [])
        assert result["version"] == 1

    def test_single_todo_action_kind_is_todo_update(self):
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "write_todos",
                    "args": {"todos": [{"content": "task1", "status": "pending"}]},
                }
            ],
        )
        result = _build_attribution(msg, [])
        assert result["kind"] == "todo_update"

    def test_single_subagent_action_kind_is_subagent_dispatch(self):
        msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc1", "name": "task", "args": {"description": "d", "subagent_type": "g"}}],
        )
        result = _build_attribution(msg, [])
        assert result["kind"] == "subagent_dispatch"


# ---------------------------------------------------------------------------
# TokenUsageMiddleware
# ---------------------------------------------------------------------------


class TestTokenUsageMiddleware:
    def _make_state(self, messages, todos=None):
        state = {"messages": messages}
        if todos is not None:
            state["todos"] = todos
        return state

    def test_empty_messages_returns_none(self):
        mw = TokenUsageMiddleware()
        result = mw._apply(self._make_state([]))
        assert result is None

    def test_last_message_not_ai_returns_none(self):
        mw = TokenUsageMiddleware()
        state = self._make_state([HumanMessage(content="hi")])
        result = mw._apply(state)
        assert result is None

    def test_annotates_ai_message_with_usage(self):
        mw = TokenUsageMiddleware()
        msg = AIMessage(
            content="answer",
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )
        state = self._make_state([HumanMessage(content="q"), msg])
        result = mw._apply(state)
        assert result is not None
        updated = result["messages"][0]
        assert TOKEN_USAGE_ATTRIBUTION_KEY in updated.additional_kwargs

    def test_ai_message_without_usage(self):
        mw = TokenUsageMiddleware()
        msg = AIMessage(content="answer")
        state = self._make_state([HumanMessage(content="q"), msg])
        result = mw._apply(state)
        assert result is not None
        updated = result["messages"][0]
        assert TOKEN_USAGE_ATTRIBUTION_KEY in updated.additional_kwargs

    def test_skip_if_attribution_unchanged(self):
        mw = TokenUsageMiddleware()
        msg = AIMessage(content="answer")
        attribution = _build_attribution(msg, [])
        msg_with = msg.model_copy(update={"additional_kwargs": {TOKEN_USAGE_ATTRIBUTION_KEY: attribution}})
        state = self._make_state([HumanMessage(content="q"), msg_with])
        result = mw._apply(state)
        assert result is None

    def test_logs_usage_with_details(self, caplog):
        mw = TokenUsageMiddleware()
        msg = AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "input_token_details": {"cache_read": 3},
                "output_token_details": {"reasoning": 2},
            },
        )
        state = self._make_state([HumanMessage(content="q"), msg])
        with caplog.at_level(
            logging.INFO,
            logger="ideer.agents.middlewares.token_usage_middleware",
        ):
            result = mw._apply(state)
        assert result is not None
        assert "input_token_details" in caplog.text
        assert "output_token_details" in caplog.text

    def test_logs_usage_without_details(self, caplog):
        mw = TokenUsageMiddleware()
        msg = AIMessage(
            content="answer",
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )
        state = self._make_state([HumanMessage(content="q"), msg])
        with caplog.at_level(
            logging.INFO,
            logger="ideer.agents.middlewares.token_usage_middleware",
        ):
            result = mw._apply(state)
        assert result is not None
        assert "LLM token usage: input=10 output=5 total=15" in caplog.text

    def test_logs_usage_with_only_input_token_details(self, caplog):
        mw = TokenUsageMiddleware()
        msg = AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "input_token_details": {"cache_read": 3},
            },
        )
        state = self._make_state([HumanMessage(content="q"), msg])
        with caplog.at_level(
            logging.INFO,
            logger="ideer.agents.middlewares.token_usage_middleware",
        ):
            result = mw._apply(state)
        assert result is not None
        assert "input_token_details" in caplog.text
        assert "output_token_details" not in caplog.text

    def test_logs_usage_with_only_output_token_details(self, caplog):
        mw = TokenUsageMiddleware()
        msg = AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "output_token_details": {"reasoning": 2},
            },
        )
        state = self._make_state([HumanMessage(content="q"), msg])
        with caplog.at_level(
            logging.INFO,
            logger="ideer.agents.middlewares.token_usage_middleware",
        ):
            result = mw._apply(state)
        assert result is not None
        assert "output_token_details" in caplog.text

    def test_after_model_delegates(self):
        mw = TokenUsageMiddleware()
        state = MagicMock()
        runtime = MagicMock()
        with patch.object(mw, "_apply", return_value={"messages": []}) as mock_apply:
            mw.after_model(state, runtime)
            mock_apply.assert_called_once_with(state)

    @pytest.mark.asyncio
    async def test_aafter_model_delegates(self):
        mw = TokenUsageMiddleware()
        state = MagicMock()
        runtime = MagicMock()
        with patch.object(mw, "_apply", return_value={"messages": []}) as mock_apply:
            await mw.aafter_model(state, runtime)
            mock_apply.assert_called_once_with(state)

    def _patch_pop_cached(self, monkeypatch, return_fn):
        """Patch pop_cached_subagent_usage via importlib since sys.modules is overridden."""
        real_module = importlib.import_module("ideer.tools.builtins.task_tool")
        monkeypatch.setattr(real_module, "pop_cached_subagent_usage", return_fn)

    def test_subagent_usage_merging(self, monkeypatch):
        mw = TokenUsageMiddleware()
        dispatch_msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc_sub", "name": "task", "args": {}}],
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        tool_msg = ToolMessage(content="done", tool_call_id="tc_sub")
        last_msg = AIMessage(content="result")

        self._patch_pop_cached(monkeypatch, lambda tcid: {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30} if tcid == "tc_sub" else None)
        state = self._make_state([dispatch_msg, tool_msg, last_msg])
        result = mw._apply(state)

        assert result is not None
        updated_dispatch = result["messages"][0]
        usage = updated_dispatch.usage_metadata
        assert usage["input_tokens"] == 120
        assert usage["output_tokens"] == 60
        assert usage["total_tokens"] == 180

    def test_no_subagent_usage(self, monkeypatch):
        mw = TokenUsageMiddleware()
        dispatch_msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc_sub", "name": "task", "args": {}}],
        )
        tool_msg = ToolMessage(content="done", tool_call_id="tc_sub")
        last_msg = AIMessage(content="result")

        self._patch_pop_cached(monkeypatch, lambda tcid: None)
        state = self._make_state([dispatch_msg, tool_msg, last_msg])
        result = mw._apply(state)

        assert result is not None

    def test_last_message_not_ai_with_state_updates(self, monkeypatch):
        mw = TokenUsageMiddleware()
        dispatch_msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc_sub", "name": "task", "args": {}}],
        )
        tool_msg = ToolMessage(content="done", tool_call_id="tc_sub")
        last_msg = ToolMessage(content="another tool result", tool_call_id="tc_other")

        self._patch_pop_cached(monkeypatch, lambda tcid: {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30} if tcid == "tc_sub" else None)
        state = self._make_state([dispatch_msg, tool_msg, last_msg])
        result = mw._apply(state)

        assert result is not None
        assert len(result["messages"]) == 1

    def test_last_message_not_ai_no_state_updates_returns_none(self, monkeypatch):
        mw = TokenUsageMiddleware()
        dispatch_msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc_sub", "name": "task", "args": {}}],
        )
        tool_msg = ToolMessage(content="done", tool_call_id="tc_sub")
        last_msg = ToolMessage(content="another", tool_call_id="tc_other")

        self._patch_pop_cached(monkeypatch, lambda tcid: None)
        state = self._make_state([dispatch_msg, tool_msg, last_msg])
        result = mw._apply(state)

        assert result is None

    def test_todos_passed_to_attribution(self):
        mw = TokenUsageMiddleware()
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "tc1",
                    "name": "write_todos",
                    "args": {"todos": [{"content": "task1", "status": "pending"}]},
                }
            ],
        )
        state = self._make_state(
            [HumanMessage(content="q"), msg],
            todos=[{"content": "old_task", "status": "completed"}],
        )
        result = mw._apply(state)
        assert result is not None

    def test_todos_non_list_treated_as_empty(self):
        mw = TokenUsageMiddleware()
        msg = AIMessage(content="answer")
        state = self._make_state([HumanMessage(content="q"), msg], todos="not a list")
        result = mw._apply(state)
        assert result is not None

    def test_no_messages_returns_none(self):
        mw = TokenUsageMiddleware()
        result = mw._apply({})
        assert result is None

    def test_multiple_task_tool_calls_merged_into_same_dispatch(self, monkeypatch):
        """Multiple ToolMessages for different task calls all merge into one AIMessage."""
        mw = TokenUsageMiddleware()
        dispatch_msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "tc_a", "name": "task", "args": {}},
                {"id": "tc_b", "name": "task", "args": {}},
            ],
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        tool_a = ToolMessage(content="a done", tool_call_id="tc_a")
        tool_b = ToolMessage(content="b done", tool_call_id="tc_b")
        last_msg = AIMessage(content="result")

        usage_map = {
            "tc_a": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "tc_b": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
        }

        self._patch_pop_cached(monkeypatch, lambda tcid: usage_map.pop(tcid, None))
        state = self._make_state([dispatch_msg, tool_a, tool_b, last_msg])
        result = mw._apply(state)

        assert result is not None
        updated_dispatch = result["messages"][0]
        usage = updated_dispatch.usage_metadata
        assert usage["input_tokens"] == 130
        assert usage["output_tokens"] == 65
        assert usage["total_tokens"] == 195

    def test_non_tool_message_breaks_tool_message_walk(self, monkeypatch):
        """A non-ToolMessage before the AIMessage stops the backward walk."""
        mw = TokenUsageMiddleware()
        human = HumanMessage(content="interrupt")
        tool_msg = ToolMessage(content="done", tool_call_id="tc_sub")
        last_msg = AIMessage(content="result")

        self._patch_pop_cached(monkeypatch, lambda tcid: {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15} if tcid == "tc_sub" else None)
        state = self._make_state([human, tool_msg, last_msg])
        result = mw._apply(state)

        assert result is not None

    def test_dispatch_message_without_matching_tool_call(self, monkeypatch):
        """When tool_call_id is not found on any preceding AIMessage, no merge happens."""
        mw = TokenUsageMiddleware()
        dispatch_msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc_other", "name": "task", "args": {}}],
        )
        tool_msg = ToolMessage(content="done", tool_call_id="tc_sub")
        last_msg = AIMessage(content="result")

        self._patch_pop_cached(monkeypatch, lambda tcid: {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15} if tcid == "tc_sub" else None)
        state = self._make_state([dispatch_msg, tool_msg, last_msg])
        result = mw._apply(state)

        assert result is not None

    def test_existing_usage_metadata_merged(self, monkeypatch):
        """When dispatch message already has usage_metadata from a prior merge."""
        mw = TokenUsageMiddleware()
        dispatch_msg = AIMessage(
            content="",
            tool_calls=[{"id": "tc_sub", "name": "task", "args": {}}],
        )
        tool_msg = ToolMessage(content="done", tool_call_id="tc_sub")
        last_msg = AIMessage(content="result")

        self._patch_pop_cached(monkeypatch, lambda tcid: {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15} if tcid == "tc_sub" else None)
        state = self._make_state([dispatch_msg, tool_msg, last_msg])
        result = mw._apply(state)

        assert result is not None
