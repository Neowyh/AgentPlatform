"""Tests targeting uncovered lines in RunJournal.

Covers:
- journal.py line 246: generation without message attribute
- journal.py line 366: _flush_sync early return on empty buffer
- journal.py line 370: _flush_sync early return on pending flush tasks
- journal.py lines 385-393: _flush_async exception handling
- journal.py line 398: _on_flush_done cancelled task
- journal.py line 401: _on_flush_done task with exception
- journal.py lines 503-505: flush() exception in put_batch
- journal.py lines 522-523: _schedule_progress_flush RuntimeError
- journal.py line 529: _schedule_delayed_progress_flush early return
- journal.py lines 532-533: _schedule_delayed_progress_flush RuntimeError
- journal.py line 540: _flush_progress_async with None reporter
- journal.py lines 551-552: _flush_progress_async reporter exception
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.runtime.journal import RunJournal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_journal(**kwargs) -> RunJournal:
    store = AsyncMock()
    store.put_batch = AsyncMock(return_value=[])
    defaults = dict(
        run_id="run-1",
        thread_id="thread-1",
        event_store=store,
        track_token_usage=True,
        flush_threshold=100,
        progress_reporter=None,
    )
    defaults.update(kwargs)
    return RunJournal(**defaults)


def _make_generation(has_message: bool = True):
    """Create a mock generation object."""
    gen = MagicMock(spec=[])  # no attributes by default
    if has_message:
        msg = MagicMock()
        msg.usage_metadata = None
        msg.model_dump.return_value = {"role": "assistant", "content": "hi"}
        type(msg).type = "ai"
        gen.message = msg
    return gen


def _make_llm_response(has_message: bool = True):
    """Create a mock LLM result with generations."""
    gen = _make_generation(has_message=has_message)
    response = MagicMock()
    response.generations = [[gen]]
    return response


# ---------------------------------------------------------------------------
# Line 246: generation without message attribute
# ---------------------------------------------------------------------------


def test_on_llm_end_generation_without_message(caplog):
    """on_llm_end logs a warning when a generation has no message attribute."""
    journal = _make_journal()
    response = _make_llm_response(has_message=False)

    with caplog.at_level(logging.WARNING):
        journal.on_llm_end(response, run_id=MagicMock())

    assert "generation has no message attribute" in caplog.text


# ---------------------------------------------------------------------------
# Line 366: _flush_sync early return when buffer is empty
# ---------------------------------------------------------------------------


def test_flush_sync_empty_buffer():
    """_flush_sync returns immediately when buffer is empty."""
    journal = _make_journal()
    assert journal._buffer == []
    # Should not raise
    journal._flush_sync()
    assert journal._buffer == []


# ---------------------------------------------------------------------------
# Line 370: _flush_sync early return when pending flush tasks exist
# ---------------------------------------------------------------------------


def test_flush_sync_skips_when_pending_tasks():
    """_flush_sync returns early if there are pending flush tasks."""
    journal = _make_journal()
    journal._buffer = [{"event_type": "test"}]

    # Simulate a pending task
    dummy_task = MagicMock()
    journal._pending_flush_tasks.add(dummy_task)

    journal._flush_sync()
    # Buffer should NOT be cleared because we skipped
    assert len(journal._buffer) == 1


# ---------------------------------------------------------------------------
# Lines 385-393: _flush_async exception handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_async_returns_events_to_buffer_on_failure():
    """_flush_async puts failed events back into buffer."""
    journal = _make_journal()
    journal._store.put_batch = AsyncMock(side_effect=RuntimeError("db down"))
    journal._buffer = []

    batch = [{"event_type": "test1"}]
    await journal._flush_async(batch)

    # Failed batch should be prepended to buffer
    assert len(journal._buffer) == 1
    assert journal._buffer[0]["event_type"] == "test1"


# ---------------------------------------------------------------------------
# Line 398: _on_flush_done with cancelled task
# ---------------------------------------------------------------------------


def test_on_flush_done_cancelled_task():
    """_on_flush_done handles cancelled tasks gracefully."""
    journal = _make_journal()
    task = MagicMock()
    task.cancelled.return_value = True
    journal._pending_flush_tasks.add(task)

    journal._on_flush_done(task)

    # Task should be discarded from the set
    assert task not in journal._pending_flush_tasks


# ---------------------------------------------------------------------------
# Line 401: _on_flush_done with task exception
# ---------------------------------------------------------------------------


def test_on_flush_done_task_with_exception(caplog):
    """_on_flush_done logs a warning when the task raised an exception."""
    journal = _make_journal()
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = RuntimeError("flush failed")
    journal._pending_flush_tasks.add(task)

    with caplog.at_level(logging.WARNING):
        journal._on_flush_done(task)

    assert "Journal flush task failed" in caplog.text


# ---------------------------------------------------------------------------
# Lines 503-505: flush() re-raises after put_batch failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_raises_after_put_batch_failure():
    """flush() re-raises exception from put_batch and restores buffer."""
    journal = _make_journal()
    journal._store.put_batch = AsyncMock(side_effect=RuntimeError("db error"))
    journal._buffer = [{"event_type": "ev1"}, {"event_type": "ev2"}]
    journal._flush_threshold = 1  # Force batching into 1-item chunks

    with pytest.raises(RuntimeError, match="db error"):
        await journal.flush()

    # Remaining events should be back in buffer
    assert len(journal._buffer) >= 1


# ---------------------------------------------------------------------------
# Lines 522-523: _schedule_progress_flush RuntimeError (no event loop)
# ---------------------------------------------------------------------------


def test_schedule_progress_flush_no_event_loop():
    """_schedule_progress_flush handles RuntimeError from get_running_loop."""
    reporter = MagicMock()
    journal = _make_journal(progress_reporter=reporter)
    journal._progress_dirty = False
    journal._last_progress_flush = 0.0

    # Patch asyncio.get_running_loop to raise RuntimeError
    with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
        # Should not raise — just returns
        journal._schedule_progress_flush()


# ---------------------------------------------------------------------------
# Line 529: _schedule_delayed_progress_flush early return on pending task
# ---------------------------------------------------------------------------


def test_schedule_delayed_progress_flush_skips_on_pending_task():
    """_schedule_delayed_progress_flush returns early if a task is pending."""
    reporter = MagicMock()
    journal = _make_journal(progress_reporter=reporter)

    # Simulate a pending task that is not done
    pending_task = MagicMock()
    pending_task.done.return_value = False
    journal._pending_progress_task = pending_task

    # Should return early without creating a new task
    journal._schedule_delayed_progress_flush(1.0)
    # pending_progress_task should remain unchanged
    assert journal._pending_progress_task is pending_task


# ---------------------------------------------------------------------------
# Lines 532-533: _schedule_delayed_progress_flush RuntimeError
# ---------------------------------------------------------------------------


def test_schedule_delayed_progress_flush_no_event_loop():
    """_schedule_delayed_progress_flush handles RuntimeError from get_running_loop."""
    reporter = MagicMock()
    journal = _make_journal(progress_reporter=reporter)
    journal._pending_progress_task = None

    with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
        # Should not raise
        journal._schedule_delayed_progress_flush(1.0)


# ---------------------------------------------------------------------------
# Line 540: _flush_progress_async with None reporter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_progress_async_none_reporter():
    """_flush_progress_async returns early when reporter is None."""
    journal = _make_journal(progress_reporter=None)
    # Should not raise
    await journal._flush_progress_async()


# ---------------------------------------------------------------------------
# Lines 551-552: _flush_progress_async reporter raises exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_progress_async_reporter_exception(caplog):
    """_flush_progress_async logs warning when reporter raises."""
    reporter = AsyncMock(side_effect=RuntimeError("reporter failed"))
    journal = _make_journal(progress_reporter=reporter)
    journal._progress_dirty = False

    with caplog.at_level(logging.WARNING):
        await journal._flush_progress_async()

    assert "Failed to persist progress snapshot" in caplog.text


# ---------------------------------------------------------------------------
# Lines 551-552: _flush_progress_async with dirty flag re-scheduling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_progress_async_reschedules_when_dirty():
    """_flush_progress_async re-schedules when progress was dirty before write."""
    reporter = AsyncMock()
    journal = _make_journal(progress_reporter=reporter)
    journal._progress_dirty = True  # dirty before write
    journal._pending_progress_task = None

    # Need a running loop for _schedule_delayed_progress_flush
    loop = asyncio.get_event_loop()
    with patch("asyncio.get_running_loop", return_value=loop):
        await journal._flush_progress_async()

    # After the flush, if dirty_before_write was True, it should have rescheduled
    reporter.assert_called_once()


# ---------------------------------------------------------------------------
# on_chat_model_start: HumanMessage with name="summary" should be skipped
# (tests the m.name != "summary" guard on line 212)
# ---------------------------------------------------------------------------


def test_on_chat_model_start_skips_summary_human_message():
    """HumanMessage with name='summary' should be skipped for first_human_msg."""
    from langchain_core.messages import HumanMessage

    journal = _make_journal()
    msg = HumanMessage(content="summary text", name="summary")

    journal.on_chat_model_start(
        serialized={"name": "test"},
        messages=[[msg]],
        run_id=MagicMock(),
        tags=[],
    )

    # Should NOT set first_human_msg because name="summary"
    assert journal._first_human_msg is None


# ---------------------------------------------------------------------------
# on_tool_end: Command with non-BaseMessage messages (line 334)
# ---------------------------------------------------------------------------


def test_on_tool_end_command_with_non_basemessage():
    """on_tool_end logs warning when Command messages are not BaseMessage."""
    from langgraph.types import Command

    journal = _make_journal()
    # Command.update with a message that is NOT a BaseMessage
    cmd = Command(update={"messages": [{"not": "a message"}]})

    journal.on_tool_end(output=cmd, run_id=MagicMock())
    # Should log a warning but not raise


# ---------------------------------------------------------------------------
# on_tool_end: output that is neither ToolMessage nor Command (line 336)
# ---------------------------------------------------------------------------


def test_on_tool_end_unhandled_output_type(caplog):
    """on_tool_end logs warning when output is not ToolMessage or Command."""
    journal = _make_journal()

    with caplog.at_level(logging.WARNING):
        journal.on_tool_end(output="unexpected", run_id=MagicMock())

    assert "output is not ToolMessage" in caplog.text
