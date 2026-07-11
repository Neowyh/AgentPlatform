"""Tests targeting uncovered lines in run_agent worker.

Covers:
- worker.py lines 198-200: checkpoint snapshot capture failure
- worker.py line 254: agent_factory without app_config
- worker.py lines 277, 279: interrupt_before/after nodes
- worker.py lines 326-327, 331: multi-mode stream with mode=None
- worker.py lines 351-352: rollback exception log
- worker.py lines 372-373: CancelledError rollback exception
- worker.py lines 396-397: journal flush exception
- worker.py lines 403-404: journal completion persist exception
- worker.py lines 416-417: thread title sync failure
- worker.py lines 424-425: thread status update failure
- worker.py line 479: _new_checkpoint_marker
- worker.py line 511: _rollback restored_configurable not dict
- worker.py line 579: _extract_human_message returns None
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.runtime.runs.schemas import RunStatus
from ideer.runtime.runs.worker import (
    _extract_human_message,
    _lg_mode_to_sse_event,
    _new_checkpoint_marker,
    _rollback_to_pre_run_checkpoint,
    _unpack_stream_item,
    run_agent,
)

# Logger used by the worker module (must match worker.py's __name__)
_worker_logger_name = "ideer.runtime.runs.worker"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _empty_async_gen():
    """An async generator that yields nothing."""
    return
    yield  # pragma: no cover


def _empty_astream(*args, **kwargs):
    """Mock astream that returns an empty async generator."""
    return _empty_async_gen()


def _make_record(**overrides):
    record = MagicMock()
    record.run_id = "run-1"
    record.thread_id = "thread-1"
    record.assistant_id = "default"
    record.model_name = "gpt-4"
    record.status = RunStatus.running
    record.abort_event = MagicMock()
    record.abort_event.is_set.return_value = False
    record.abort_action = "interrupt"
    for k, v in overrides.items():
        setattr(record, k, v)
    return record


def _make_ctx(**overrides):
    ctx = MagicMock()
    ctx.checkpointer = None
    ctx.store = None
    ctx.event_store = None
    ctx.run_events_config = None
    ctx.thread_store = None
    ctx.app_config = None
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


def _make_bridge():
    bridge = AsyncMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()
    return bridge


def _make_run_manager():
    rm = AsyncMock()
    rm.set_status = AsyncMock()
    rm.update_run_progress = AsyncMock()
    rm.update_run_completion = AsyncMock()
    rm.update_model_name = AsyncMock()
    return rm


# ---------------------------------------------------------------------------
# Line 479: _new_checkpoint_marker
# ---------------------------------------------------------------------------


def test_new_checkpoint_marker():
    """_new_checkpoint_marker returns dict with id and ts from empty_checkpoint."""
    marker = _new_checkpoint_marker()
    assert "id" in marker
    assert "ts" in marker
    assert isinstance(marker["id"], str)
    assert isinstance(marker["ts"], str)


# ---------------------------------------------------------------------------
# Line 579: _extract_human_message returns None for unknown type
# ---------------------------------------------------------------------------


def test_extract_human_message_returns_none_for_unknown_type():
    """_extract_human_message returns None for a last element with unknown type."""
    result = _extract_human_message({"messages": [42]})
    assert result is None


# ---------------------------------------------------------------------------
# Line 579: _extract_human_message returns None for empty content dict
# ---------------------------------------------------------------------------


def test_extract_human_message_empty_content_dict():
    """_extract_human_message returns None when dict has empty content."""
    result = _extract_human_message({"messages": [{"content": ""}]})
    assert result is None


# ---------------------------------------------------------------------------
# Lines 198-200: checkpoint snapshot capture failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_checkpoint_snapshot_failure(caplog):
    """run_agent handles checkpoint snapshot capture failure gracefully."""
    checkpointer = AsyncMock()
    checkpointer.aget_tuple = AsyncMock(side_effect=RuntimeError("ckpt error"))

    ctx = _make_ctx(checkpointer=checkpointer)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    # Agent factory returns a mock agent that yields nothing
    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    with caplog.at_level(logging.WARNING):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=agent_factory,
            graph_input={"messages": []},
            config={},
        )

    assert "Could not capture pre-run checkpoint snapshot" in caplog.text


# ---------------------------------------------------------------------------
# Line 254: agent_factory without app_config support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_factory_without_app_config():
    """run_agent calls agent_factory(config=...) when app_config is None."""
    ctx = _make_ctx(app_config=None)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}

    # Factory that does NOT accept app_config
    def agent_factory(config):
        return agent

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
    )

    run_manager.set_status.assert_any_call("run-1", RunStatus.success)


# ---------------------------------------------------------------------------
# Lines 277, 279: interrupt_before/after nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_sets_interrupt_nodes():
    """run_agent sets interrupt_before_nodes and interrupt_after_nodes."""
    ctx = _make_ctx()
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
        interrupt_before=["node_a"],
        interrupt_after=["node_b"],
    )

    assert agent.interrupt_before_nodes == ["node_a"]
    assert agent.interrupt_after_nodes == ["node_b"]


# ---------------------------------------------------------------------------
# Lines 326-327, 331: multi-mode stream where unpack returns (None, chunk)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_multi_mode_stream_skips_none_mode():
    """run_agent skips items where mode is None in multi-mode stream."""
    ctx = _make_ctx()
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    # Simulate astream yielding items where one has an unparseable shape
    items = [
        ("values", {"key": "val1"}),  # valid
        "not_a_tuple",  # will fallback to first mode
        (None, None),  # edge case
    ]

    async def fake_astream(*args, **kwargs):
        for item in items:
            yield item

    agent = MagicMock()
    agent.astream = fake_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
        stream_modes=["values", "updates"],  # multi-mode
    )

    # Should have published at least the valid items
    assert bridge.publish.call_count >= 1


@pytest.mark.asyncio
async def test_run_agent_subgraph_stream_skips_none_mode():
    """run_agent skips items where _unpack_stream_item returns (None, None) in subgraph mode.

    Line 331: `if mode is None: continue` is hit when stream_subgraphs=True
    and the astream yields a non-tuple item (e.g. a bare value), which causes
    _unpack_stream_item to return (None, None).
    """
    ctx = _make_ctx()
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    items = [
        ("ns", "values", {"key": "val1"}),  # valid 3-tuple subgraph item
        "not_a_tuple_at_all",  # unparseable: _unpack_stream_item returns (None, None)
        ("updates", {"key": "val2"}),  # valid 2-tuple subgraph item
    ]

    async def fake_astream(*args, **kwargs):
        for item in items:
            yield item

    agent = MagicMock()
    agent.astream = fake_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
        stream_modes=["values", "updates"],
        stream_subgraphs=True,
    )

    # Two valid items should be published (the non-tuple one is skipped via line 331)
    assert bridge.publish.call_count >= 2


# ---------------------------------------------------------------------------
# Lines 351-352: rollback exception during abort
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_abort_rollback_exception(caplog):
    """run_agent logs warning when rollback fails after abort."""
    checkpointer = AsyncMock()
    ckpt_tuple = MagicMock()
    ckpt_tuple.config = {"configurable": {"checkpoint_id": "ckpt-1", "checkpoint_ns": ""}}
    ckpt_tuple.checkpoint = {"id": "ckpt-1", "channel_values": {}}
    ckpt_tuple.metadata = {}
    ckpt_tuple.pending_writes = []
    checkpointer.aget_tuple = AsyncMock(return_value=ckpt_tuple)

    ctx = _make_ctx(checkpointer=checkpointer)
    record = _make_record()
    record.abort_event.is_set.return_value = True
    record.abort_action = "rollback"
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    # Make _rollback_to_pre_run_checkpoint fail
    with patch(
        "ideer.runtime.runs.worker._rollback_to_pre_run_checkpoint",
        side_effect=RuntimeError("rollback failed"),
    ):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=agent_factory,
                graph_input={"messages": []},
                config={},
            )

    assert "Failed to rollback checkpoint" in caplog.text


# ---------------------------------------------------------------------------
# Lines 372-373: CancelledError with rollback failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_cancelled_with_rollback_failure(caplog):
    """run_agent handles CancelledError when rollback also fails."""
    ctx = _make_ctx()
    record = _make_record()
    record.abort_action = "rollback"
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()

    async def cancelling_astream(*args, **kwargs):
        raise asyncio.CancelledError()
        yield  # make it an async generator

    agent.astream = cancelling_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    with patch(
        "ideer.runtime.runs.worker._rollback_to_pre_run_checkpoint",
        side_effect=RuntimeError("rollback boom"),
    ):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=agent_factory,
                graph_input={"messages": []},
                config={},
            )

    assert "cancellation rollback failed" in caplog.text


# ---------------------------------------------------------------------------
# Lines 396-397: journal flush exception in finally
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_journal_flush_exception(caplog):
    """run_agent logs warning when journal flush fails in finally."""
    event_store = AsyncMock()
    ctx = _make_ctx(event_store=event_store)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    # Patch RunJournal to return a mock that fails on flush
    mock_journal = AsyncMock()
    mock_journal.flush = AsyncMock(side_effect=RuntimeError("flush error"))
    mock_journal.get_completion_data = MagicMock(return_value={})

    with patch("ideer.runtime.journal.RunJournal", return_value=mock_journal):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=agent_factory,
                graph_input={"messages": []},
                config={},
            )

    assert "Failed to flush journal" in caplog.text


# ---------------------------------------------------------------------------
# Lines 403-404: journal completion persist exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_journal_completion_exception(caplog):
    """run_agent logs warning when journal completion persist fails."""
    event_store = AsyncMock()
    ctx = _make_ctx(event_store=event_store)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()
    run_manager.update_run_completion = AsyncMock(side_effect=RuntimeError("completion error"))

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    mock_journal = AsyncMock()
    mock_journal.flush = AsyncMock()
    mock_journal.get_completion_data = MagicMock(return_value={})

    with patch("ideer.runtime.journal.RunJournal", return_value=mock_journal):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=agent_factory,
                graph_input={"messages": []},
                config={},
            )

    assert "Failed to persist run completion" in caplog.text


# ---------------------------------------------------------------------------
# Lines 416-417: thread title sync failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_thread_title_sync_failure(caplog):
    """run_agent logs debug when thread title sync fails."""
    checkpointer = AsyncMock()
    ckpt_tuple = MagicMock()
    ckpt_tuple.checkpoint = {"channel_values": {"title": "My Title"}}
    checkpointer.aget_tuple = AsyncMock(return_value=ckpt_tuple)

    thread_store = AsyncMock()
    thread_store.update_display_name = AsyncMock(side_effect=RuntimeError("sync error"))
    thread_store.update_status = AsyncMock()

    ctx = _make_ctx(checkpointer=checkpointer, thread_store=thread_store)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    with caplog.at_level(logging.DEBUG, logger=_worker_logger_name):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=agent_factory,
            graph_input={"messages": []},
            config={},
        )

    assert "Failed to sync title" in caplog.text


# ---------------------------------------------------------------------------
# Lines 424-425: thread status update failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_thread_status_update_failure(caplog):
    """run_agent logs debug when thread status update fails."""
    thread_store = AsyncMock()
    thread_store.update_status = AsyncMock(side_effect=RuntimeError("status error"))

    ctx = _make_ctx(thread_store=thread_store)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    with caplog.at_level(logging.DEBUG, logger=_worker_logger_name):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=agent_factory,
            graph_input={"messages": []},
            config={},
        )

    assert "Failed to update thread_meta status" in caplog.text


# ---------------------------------------------------------------------------
# Line 511: _rollback_to_pre_run_checkpoint restored_configurable not dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_restored_configurable_not_dict():
    """_rollback raises when restored_configurable is not a dict."""
    checkpointer = AsyncMock()
    checkpointer.aput = AsyncMock(return_value={"configurable": "not_a_dict"})

    with pytest.raises(RuntimeError, match="invalid config payload"):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="ckpt-1",
            pre_run_snapshot={
                "checkpoint": {"id": "old-ckpt"},
                "metadata": {},
                "checkpoint_ns": "",
                "pending_writes": [],
            },
            snapshot_capture_failed=False,
        )


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: checkpointer is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_no_checkpointer(caplog):
    """_rollback logs info when checkpointer is None."""
    with caplog.at_level(logging.INFO):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=None,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=None,
            snapshot_capture_failed=False,
        )

    assert "no checkpointer is configured" in caplog.text


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: snapshot_capture_failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_snapshot_capture_failed(caplog):
    """_rollback skips when snapshot capture failed."""
    with caplog.at_level(logging.WARNING):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=MagicMock(),
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=None,
            snapshot_capture_failed=True,
        )

    assert "snapshot capture failed" in caplog.text


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: pre_run_snapshot is None (delete thread)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_no_snapshot_deletes_thread(caplog):
    """_rollback deletes thread when pre_run_snapshot is None."""
    checkpointer = AsyncMock()
    checkpointer.adelete_thread = AsyncMock()

    with caplog.at_level(logging.INFO):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=None,
            snapshot_capture_failed=False,
        )

    checkpointer.adelete_thread.assert_called_once_with("t1")
    assert "reset thread" in caplog.text


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: invalid checkpoint (not dict)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_invalid_checkpoint(caplog):
    """_rollback skips when checkpoint is not a dict."""
    with caplog.at_level(logging.WARNING):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=MagicMock(),
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot={"checkpoint": "not_a_dict", "metadata": {}, "checkpoint_ns": "", "pending_writes": []},
            snapshot_capture_failed=False,
        )

    assert "invalid pre-run checkpoint" in caplog.text


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: checkpoint has no id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_checkpoint_no_id(caplog):
    """_rollback skips when checkpoint has no id even after injecting pre_run_checkpoint_id."""
    with caplog.at_level(logging.WARNING):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=MagicMock(),
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot={"checkpoint": {}, "metadata": {}, "checkpoint_ns": "", "pending_writes": []},
            snapshot_capture_failed=False,
        )

    assert "no checkpoint id" in caplog.text


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: invalid pending_write shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_invalid_pending_write():
    """_rollback raises when pending_write is not a 3-tuple."""
    checkpointer = AsyncMock()
    checkpointer.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "new-ckpt"}})

    with pytest.raises(RuntimeError, match="not a 3-tuple"):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="old-ckpt",
            pre_run_snapshot={
                "checkpoint": {"id": "old-ckpt"},
                "metadata": {},
                "checkpoint_ns": "",
                "pending_writes": [("task1", "channel1")],  # only 2 elements
            },
            snapshot_capture_failed=False,
        )


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: non-string channel in pending_write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_non_string_channel():
    """_rollback raises when pending_write channel is not a string."""
    checkpointer = AsyncMock()
    checkpointer.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "new-ckpt"}})

    with pytest.raises(RuntimeError, match="non-string channel"):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="old-ckpt",
            pre_run_snapshot={
                "checkpoint": {"id": "old-ckpt"},
                "metadata": {},
                "checkpoint_ns": "",
                "pending_writes": [("task1", 123, "value")],  # channel is int
            },
            snapshot_capture_failed=False,
        )


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: successful restore with pending writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_success_with_pending_writes():
    """_rollback restores checkpoint and replays pending writes."""
    checkpointer = AsyncMock()
    checkpointer.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "new-ckpt"}})
    checkpointer.aput_writes = AsyncMock()

    await _rollback_to_pre_run_checkpoint(
        checkpointer=checkpointer,
        thread_id="t1",
        run_id="r1",
        pre_run_checkpoint_id="old-ckpt",
        pre_run_snapshot={
            "checkpoint": {"id": "old-ckpt", "channel_values": {}},
            "metadata": {"source": "test"},
            "checkpoint_ns": "",
            "pending_writes": [("task1", "channel1", "value1")],
        },
        snapshot_capture_failed=False,
    )

    checkpointer.aput.assert_called_once()
    checkpointer.aput_writes.assert_called_once()


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: aput returns non-dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_aput_returns_non_dict():
    """_rollback raises when aput returns non-dict."""
    checkpointer = AsyncMock()
    checkpointer.aput = AsyncMock(return_value="not_a_dict")

    with pytest.raises(RuntimeError, match="invalid config"):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="old-ckpt",
            pre_run_snapshot={
                "checkpoint": {"id": "old-ckpt"},
                "metadata": {},
                "checkpoint_ns": "",
                "pending_writes": [],
            },
            snapshot_capture_failed=False,
        )


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: aput returns dict without checkpoint_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_aput_no_checkpoint_id():
    """_rollback raises when aput does not return checkpoint_id."""
    checkpointer = AsyncMock()
    checkpointer.aput = AsyncMock(return_value={"configurable": {}})

    with pytest.raises(RuntimeError, match="did not return checkpoint_id"):
        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="old-ckpt",
            pre_run_snapshot={
                "checkpoint": {"id": "old-ckpt"},
                "metadata": {},
                "checkpoint_ns": "",
                "pending_writes": [],
            },
            snapshot_capture_failed=False,
        )


# ---------------------------------------------------------------------------
# _lg_mode_to_sse_event: identity mapping
# ---------------------------------------------------------------------------


def test_lg_mode_to_sse_event():
    """_lg_mode_to_sse_event returns mode as-is."""
    assert _lg_mode_to_sse_event("values") == "values"
    assert _lg_mode_to_sse_event("messages") == "messages"


# ---------------------------------------------------------------------------
# _unpack_stream_item: subgraph 3-tuple
# ---------------------------------------------------------------------------


def test_unpack_stream_item_subgraph_3tuple():
    """_unpack_stream_item handles 3-tuple with subgraphs."""
    mode, chunk = _unpack_stream_item(("ns", "values", {"a": 1}), ["values"], True)
    assert mode == "values"
    assert chunk == {"a": 1}


# ---------------------------------------------------------------------------
# _unpack_stream_item: subgraph 2-tuple
# ---------------------------------------------------------------------------


def test_unpack_stream_item_subgraph_2tuple():
    """_unpack_stream_item handles 2-tuple with subgraphs."""
    mode, chunk = _unpack_stream_item(("updates", {"b": 2}), ["values", "updates"], True)
    assert mode == "updates"
    assert chunk == {"b": 2}


# ---------------------------------------------------------------------------
# _unpack_stream_item: subgraph unknown shape
# ---------------------------------------------------------------------------


def test_unpack_stream_item_subgraph_unknown():
    """_unpack_stream_item returns (None, None) for unknown subgraph item."""
    mode, chunk = _unpack_stream_item("garbage", ["values"], True)
    assert mode is None
    assert chunk is None


# ---------------------------------------------------------------------------
# _unpack_stream_item: non-tuple fallback
# ---------------------------------------------------------------------------


def test_unpack_stream_item_non_tuple_fallback():
    """_unpack_stream_item falls back to first mode for non-tuple items."""
    mode, chunk = _unpack_stream_item({"data": 1}, ["values", "updates"], False)
    assert mode == "values"
    assert chunk == {"data": 1}


# ---------------------------------------------------------------------------
# run_agent: CancelledError with interrupt action (not rollback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_cancelled_interrupt(caplog):
    """run_agent handles CancelledError with interrupt action."""
    ctx = _make_ctx()
    record = _make_record()
    record.abort_action = "interrupt"
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()

    async def cancelling_astream(*args, **kwargs):
        raise asyncio.CancelledError()
        yield

    agent.astream = cancelling_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    with caplog.at_level(logging.INFO):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=agent_factory,
            graph_input={"messages": []},
            config={},
        )

    assert "was cancelled" in caplog.text
    run_manager.set_status.assert_any_call("run-1", RunStatus.interrupted)


# ---------------------------------------------------------------------------
# run_agent: model_name mismatch triggers update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_updates_model_name_on_mismatch():
    """run_agent updates model_name when agent metadata differs."""
    ctx = _make_ctx()
    record = _make_record(model_name="gpt-4")
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {"model_name": "gpt-4o"}
    agent_factory = MagicMock(return_value=agent)

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
    )

    run_manager.update_model_name.assert_called_once_with("run-1", "gpt-4o")


# ---------------------------------------------------------------------------
# Line 254: agent_factory with app_config support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_factory_with_app_config():
    """run_agent calls agent_factory(config=..., app_config=...) when app_config is set."""
    from ideer.config.app_config import AppConfig

    mock_app_config = MagicMock(spec=AppConfig)
    ctx = _make_ctx(app_config=mock_app_config)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}

    # Factory that accepts app_config
    def agent_factory(config, app_config):
        return agent

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
    )

    run_manager.set_status.assert_any_call("run-1", RunStatus.success)


# ---------------------------------------------------------------------------
# Line 273: store is not None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_with_store():
    """run_agent sets agent.store when store is not None."""
    mock_store = MagicMock()
    ctx = _make_ctx(store=mock_store)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.astream = _empty_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
    )

    assert agent.store == mock_store
    run_manager.set_status.assert_any_call("run-1", RunStatus.success)


# ---------------------------------------------------------------------------
# Lines 326-327: abort during multi-mode stream (subgraph mode)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_abort_during_subgraph_stream():
    """run_agent stops streaming on abort in subgraph multi-mode stream."""
    ctx = _make_ctx()
    call_count = {"n": 0}

    def _is_set():
        call_count["n"] += 1
        # First call is at line 312 (single-mode check) or 325 (multi-mode check).
        # Return True on the second call (inside the multi-mode loop).
        return call_count["n"] > 1

    abort_event = MagicMock()
    abort_event.is_set = MagicMock(side_effect=_is_set)
    record = _make_record(abort_event=abort_event)
    record.abort_action = "interrupt"
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    items = [
        ("ns", "values", {"key": "val1"}),
        ("ns", "updates", {"key": "val2"}),
    ]

    async def fake_astream(*args, **kwargs):
        for item in items:
            yield item

    agent = MagicMock()
    agent.astream = fake_astream
    agent.metadata = {}
    agent_factory = MagicMock(return_value=agent)

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=agent_factory,
        graph_input={"messages": []},
        config={},
        stream_modes=["values", "updates"],
        stream_subgraphs=True,
    )

    run_manager.set_status.assert_any_call("run-1", RunStatus.interrupted)


# ---------------------------------------------------------------------------
# Line 479: _rollback injects pre_run_checkpoint_id when checkpoint has no id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_injects_pre_run_checkpoint_id():
    """_rollback injects pre_run_checkpoint_id when checkpoint has no id."""
    checkpointer = AsyncMock()
    checkpointer.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "new-ckpt"}})

    await _rollback_to_pre_run_checkpoint(
        checkpointer=checkpointer,
        thread_id="t1",
        run_id="r1",
        pre_run_checkpoint_id="injected-id",
        pre_run_snapshot={
            "checkpoint": {"channel_values": {}},  # no "id" key
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [],
        },
        snapshot_capture_failed=False,
    )

    checkpointer.aput.assert_called_once()
