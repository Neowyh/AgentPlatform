"""Additional tests for ideer.runtime.journal — coverage gaps."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from ideer.runtime.events.store.memory import MemoryRunEventStore
from ideer.runtime.journal import RunJournal


@pytest.fixture
def store():
    return MemoryRunEventStore()


def _make_llm_response(content="Hello", usage=None, tool_calls=None):
    msg = MagicMock()
    msg.type = "ai"
    msg.content = content
    msg.id = f"msg-{id(msg)}"
    msg.tool_calls = tool_calls or []
    msg.invalid_tool_calls = []
    msg.response_metadata = {"model_name": "test"}
    msg.usage_metadata = usage
    msg.additional_kwargs = {}
    msg.name = None
    msg.model_dump.return_value = {
        "content": content,
        "type": "ai",
        "tool_calls": tool_calls or [],
        "usage_metadata": usage,
    }
    gen = MagicMock()
    gen.message = msg
    response = MagicMock()
    response.generations = [[gen]]
    return response


# ---------------------------------------------------------------------------
# on_llm_error
# ---------------------------------------------------------------------------


class TestOnLlmError:
    def test_on_llm_error_clears_start_time(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        run_id = uuid4()
        j._llm_start_times[str(run_id)] = 123.45
        j.on_llm_error(ValueError("boom"), run_id=run_id)
        assert str(run_id) not in j._llm_start_times

    @pytest.mark.anyio
    async def test_on_llm_error_writes_event(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        run_id = uuid4()
        j.on_llm_error(RuntimeError("llm failed"), run_id=run_id)
        await j.flush()
        events = await store.list_events("t1", "r1")
        error_events = [e for e in events if e["event_type"] == "llm.error"]
        assert len(error_events) == 1
        assert "llm failed" in error_events[0]["content"]


# ---------------------------------------------------------------------------
# on_tool_start
# ---------------------------------------------------------------------------


class TestOnToolStart:
    def test_on_tool_start_does_not_crash(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        run_id = uuid4()
        j.on_tool_start({"name": "search"}, "query", run_id=run_id, tags=["lead_agent"])
        # Should not raise — currently a no-op


# ---------------------------------------------------------------------------
# on_tool_end — additional paths
# ---------------------------------------------------------------------------


class TestOnToolEndAdditional:
    def test_tool_end_with_non_tool_non_command_output(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        j.on_tool_end("plain string output", run_id=uuid4())
        # Should not raise

    def test_tool_end_with_command_containing_non_base_message(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        cmd = Command(update={"messages": ["not_a_base_message"]})
        j.on_tool_end(cmd, run_id=uuid4())
        # Should not raise


# ---------------------------------------------------------------------------
# _message_text — additional edge cases
# ---------------------------------------------------------------------------


class TestMessageText:
    def test_mapping_content_with_text(self):
        msg = MagicMock()
        msg.content = {"text": "hello"}
        msg.text = None
        result = RunJournal._message_text(msg)
        assert result == "hello"

    def test_mapping_content_with_content_key(self):
        msg = MagicMock()
        msg.content = {"content": "nested text"}
        msg.text = None
        result = RunJournal._message_text(msg)
        assert result == "nested text"

    def test_mapping_content_no_text_no_content(self):
        msg = MagicMock()
        msg.content = {"other": "key"}
        msg.text = "fallback"
        result = RunJournal._message_text(msg)
        assert result == "fallback"

    def test_text_attr_fallback(self):
        msg = MagicMock()
        msg.content = 123  # not str, list, or Mapping
        msg.text = "from text attr"
        result = RunJournal._message_text(msg)
        assert result == "from text attr"

    def test_no_content_no_text(self):
        msg = MagicMock()
        msg.content = 123
        msg.text = None
        result = RunJournal._message_text(msg)
        assert result == ""

    def test_list_content_with_dict_having_content_key(self):
        msg = MagicMock()
        msg.content = [{"content": "from dict"}]
        result = RunJournal._message_text(msg)
        assert result == "from dict"

    def test_list_content_empty(self):
        msg = MagicMock()
        msg.content = []
        result = RunJournal._message_text(msg)
        assert result == ""


# ---------------------------------------------------------------------------
# set_first_human_message
# ---------------------------------------------------------------------------


class TestSetFirstHumanMessage:
    def test_truncates_long_message(self):
        store = MemoryRunEventStore()
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        long_msg = "x" * 3000
        j.set_first_human_message(long_msg)
        assert len(j._first_human_msg) == 2000

    def test_empty_message_sets_none(self):
        store = MemoryRunEventStore()
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        j.set_first_human_message("")
        assert j._first_human_msg is None


# ---------------------------------------------------------------------------
# flush — additional edge cases
# ---------------------------------------------------------------------------


class TestFlushAdditional:
    @pytest.mark.anyio
    async def test_flush_with_remaining_buffer(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        j._put(event_type="test.event", category="trace", content="data")
        assert len(j._buffer) == 1
        await j.flush()
        assert len(j._buffer) == 0
        events = await store.list_events("t1", "r1")
        assert len(events) == 1

    @pytest.mark.anyio
    async def test_flush_empty_buffer(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        await j.flush()  # Should not raise

    @pytest.mark.anyio
    async def test_flush_with_pending_flush_tasks(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=1)
        j._put(event_type="test.event", category="trace", content="data")
        # Wait for the async flush task
        await asyncio.sleep(0.1)
        await j.flush()


# ---------------------------------------------------------------------------
# on_llm_end — fallback path (no on_chat_model_start)
# ---------------------------------------------------------------------------


class TestOnLlmEndFallback:
    def test_on_llm_end_without_on_chat_model_start(self, store):
        """When on_chat_model_start was not called, on_llm_end should fallback."""
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        run_id = uuid4()
        # Do NOT call on_llm_start — simulating missing start callback
        j.on_llm_end(
            _make_llm_response("answer", usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
            run_id=run_id,
            parent_run_id=None,
            tags=["lead_agent"],
        )
        assert j._llm_call_count == 1
        assert j._total_tokens == 15


# ---------------------------------------------------------------------------
# _record_message_summary — AIMessage with no caller
# ---------------------------------------------------------------------------


class TestRecordMessageSummary:
    def test_ai_message_no_caller_updates_last_ai(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        ai_msg = AIMessage(content="direct answer")
        j._record_message_summary(ai_msg)
        assert j._last_ai_msg == "direct answer"
        assert j._msg_count == 1

    def test_non_ai_message_does_not_update_last_ai(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        human_msg = HumanMessage(content="question")
        j._record_message_summary(human_msg)
        assert j._last_ai_msg is None
        assert j._msg_count == 1

    def test_ai_message_subagent_caller_does_not_update_last_ai(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        ai_msg = AIMessage(content="sub answer")
        j._record_message_summary(ai_msg, caller="subagent:research")
        assert j._last_ai_msg is None
        assert j._msg_count == 1

    def test_ai_message_empty_content_does_not_update(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        ai_msg = AIMessage(content="")
        j._record_message_summary(ai_msg)
        assert j._last_ai_msg is None


# ---------------------------------------------------------------------------
# on_chat_model_start — empty messages
# ---------------------------------------------------------------------------


class TestOnChatModelStart:
    def test_empty_messages_no_crash(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        j.on_chat_model_start({}, [], run_id=uuid4(), tags=["lead_agent"])
        assert j._first_human_msg is None

    def test_no_human_message_in_batch(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        ai_msg = AIMessage(content="only ai")
        j.on_chat_model_start({}, [[ai_msg]], run_id=uuid4(), tags=["lead_agent"])
        assert j._first_human_msg is None


# ---------------------------------------------------------------------------
# on_chain_start — with metadata
# ---------------------------------------------------------------------------


class TestOnChainStart:
    @pytest.mark.anyio
    async def test_chain_start_with_metadata(self, store):
        j = RunJournal("r1", "t1", store, flush_threshold=100)
        j.on_chain_start(
            {"name": "my_chain"},
            {"input": "test"},
            run_id=uuid4(),
            parent_run_id=None,
            metadata={"custom": "data"},
        )
        await j.flush()
        events = await store.list_events("t1", "r1")
        start_events = [e for e in events if e["event_type"] == "run.start"]
        assert len(start_events) == 1
        assert start_events[0]["metadata"]["custom"] == "data"
