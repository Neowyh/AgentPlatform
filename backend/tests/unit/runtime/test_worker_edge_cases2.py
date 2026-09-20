"""Tests targeting edge cases and uncovered paths in the run_agent worker.

Covers:
- pre-run checkpoint snapshot capture failure
- agent_factory with/without app_config support
- interrupt_before/after nodes
- multi-mode stream with unparseable items
- rollback exception logging during abort / cancellation
- journal flush / completion persist failures
- thread title sync and status update failures
- _new_checkpoint_marker
- _rollback_to_pre_run_checkpoint error paths (current keyword-only contract)
- _unpack_stream_item namespace tuple handling
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deerflow.runtime.checkpoint_state import CheckpointStateAccessor
from deerflow.runtime.runs.manager import RunStartOutcome
from deerflow.runtime.runs.schemas import RunStatus
from deerflow.runtime.runs.worker import (
    RollbackPoint,
    _extract_llm_error_fallback_message,
    _lg_mode_to_sse_event,
    _new_checkpoint_marker,
    _rollback_to_pre_run_checkpoint,
    _unpack_stream_item,
    run_agent,
)

# Logger used by the worker module (must match worker.py's __name__)
_worker_logger_name = "deerflow.runtime.runs.worker"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(**overrides):
    """RunRecord stand-in matching the fields the current worker reads.

    ``ownership_lost`` and ``finalizing`` must be real False values: on a bare
    MagicMock every attribute is truthy and the worker would skip all durable
    finalization (status updates, journal flush, cleanup).
    """
    record = MagicMock()
    record.run_id = "run-1"
    record.thread_id = "thread-1"
    record.assistant_id = "default"
    record.model_name = "gpt-4"
    record.status = RunStatus.running
    record.abort_event = MagicMock()
    record.abort_event.is_set.return_value = False
    record.abort_action = "interrupt"
    record.ownership_lost = False
    record.finalizing = False
    record.task = None
    record.user_id = None
    record.metadata = {}
    record.error = None
    record.stop_reason = None
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
    ctx.mcp_task_repo = None
    ctx.checkpoint_channel_mode = "full"
    ctx.on_run_completed = None
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
    """RunManager stand-in configured for the current run_agent contract."""
    rm = MagicMock()
    rm.set_status = AsyncMock()
    rm.set_status_if_not_cancelled = AsyncMock(return_value=None)
    rm.set_finalizing = AsyncMock()
    rm.wait_for_prior_finalizing = AsyncMock()
    rm.try_start = AsyncMock(return_value=RunStartOutcome.started)
    rm.has_later_started_run = AsyncMock(return_value=False)
    rm.persist_current_status = AsyncMock()
    rm.persist_current_record = AsyncMock(return_value=True)
    rm.update_run_progress = AsyncMock()
    rm.update_run_completion = AsyncMock()
    rm.update_finalizing_progress = AsyncMock()
    rm.update_model_name = AsyncMock()
    rm.cleanup = AsyncMock()
    return rm


# ---------------------------------------------------------------------------
# _new_checkpoint_marker
# ---------------------------------------------------------------------------


def test_new_checkpoint_marker():
    """_new_checkpoint_marker returns dict with id and ts from empty_checkpoint."""
    marker = _new_checkpoint_marker()
    assert "id" in marker
    assert "ts" in marker
    assert isinstance(marker["id"], str)
    assert isinstance(marker["ts"], str)


# ---------------------------------------------------------------------------
# _extract_llm_error_fallback_message: non-message payloads
# ---------------------------------------------------------------------------


def test_extract_llm_error_fallback_message_returns_none_for_unknown_type():
    """Non-message payloads never match the fallback marker."""
    result = _extract_llm_error_fallback_message({"messages": [42]})
    assert result is None


def test_extract_llm_error_fallback_message_empty_content_dict():
    """A dict message without the fallback marker returns None."""
    result = _extract_llm_error_fallback_message({"messages": [{"content": ""}]})
    assert result is None


# ---------------------------------------------------------------------------
# checkpoint snapshot capture failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_checkpoint_snapshot_failure(caplog):
    """run_agent handles checkpoint snapshot capture failure gracefully."""
    checkpointer = AsyncMock()
    # Mode compatibility gate passes; the rollback capture itself fails below.
    checkpointer.aget_tuple = AsyncMock(
        return_value=SimpleNamespace(
            config={"configurable": {"thread_id": "thread-1", "checkpoint_ns": "", "checkpoint_id": "ckpt-1"}},
            checkpoint={"id": "ckpt-1"},
            metadata={},
            pending_writes=[],
        )
    )

    class SnapshotFailureAgent:
        metadata: dict = {}

        async def aget_state(self, config):
            raise RuntimeError("snapshot error")

        async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
            return
            yield  # pragma: no cover

    ctx = _make_ctx(checkpointer=checkpointer)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    with caplog.at_level(logging.WARNING):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=lambda *, config: SnapshotFailureAgent(),
            graph_input={"messages": []},
            config={},
        )

    assert "Could not capture pre-run checkpoint snapshot" in caplog.text
    # Capture failure only disables rollback; the run itself still succeeds.
    run_manager.set_status_if_not_cancelled.assert_any_call("run-1", RunStatus.success, error=None, stop_reason=None)


# ---------------------------------------------------------------------------
# agent_factory without app_config support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_factory_without_app_config():
    """run_agent calls agent_factory(config=...) when app_config is None."""
    ctx = _make_ctx(app_config=None)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=lambda *, config: agent,
        graph_input={"messages": []},
        config={},
    )

    run_manager.set_status_if_not_cancelled.assert_any_call("run-1", RunStatus.success, error=None, stop_reason=None)


# ---------------------------------------------------------------------------
# interrupt_before/after nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_sets_interrupt_nodes():
    """run_agent sets interrupt_before_nodes and interrupt_after_nodes."""
    ctx = _make_ctx()
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=lambda *, config: agent,
        graph_input={"messages": []},
        config={},
        interrupt_before=["node_a"],
        interrupt_after=["node_b"],
    )

    assert agent.interrupt_before_nodes == ["node_a"]
    assert agent.interrupt_after_nodes == ["node_b"]


# ---------------------------------------------------------------------------
# multi-mode stream with unparseable items
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

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=lambda *, config: agent,
        graph_input={"messages": []},
        config={},
        stream_modes=["values", "updates"],  # multi-mode
    )

    # Should have published at least the valid items
    assert bridge.publish.call_count >= 1


@pytest.mark.asyncio
async def test_run_agent_subgraph_stream_skips_none_mode():
    """run_agent skips items where _unpack_stream_item returns (None, None, ()) in subgraph mode.

    With stream_subgraphs=True an unparseable item (e.g. a bare string) must be
    skipped instead of published.
    """
    ctx = _make_ctx()
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    items = [
        ("ns", "values", {"key": "val1"}),  # valid 3-tuple subgraph item
        "not_a_tuple_at_all",  # unparseable: _unpack_stream_item returns (None, None, ())
        ("updates", {"key": "val2"}),  # valid 2-tuple subgraph item
    ]

    async def fake_astream(*args, **kwargs):
        for item in items:
            yield item

    agent = MagicMock()
    agent.astream = fake_astream
    agent.metadata = {}

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=lambda *, config: agent,
        graph_input={"messages": []},
        config={},
        stream_modes=["values", "updates"],
        stream_subgraphs=True,
    )

    # Two valid items should be published (the non-tuple one is skipped)
    assert bridge.publish.call_count >= 2


# ---------------------------------------------------------------------------
# rollback exception during abort
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_abort_rollback_exception(caplog):
    """run_agent logs a warning when rollback fails during abort handling."""
    ctx = _make_ctx()
    record = _make_record()
    record.abort_event.is_set.return_value = True
    record.abort_action = "rollback"
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    with patch(
        "deerflow.runtime.runs.worker._rollback_to_pre_run_checkpoint",
        side_effect=RuntimeError("rollback failed"),
    ):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=lambda *, config: agent,
                graph_input={"messages": []},
                config={},
            )

    assert "cancellation rollback failed" in caplog.text


# ---------------------------------------------------------------------------
# CancelledError with rollback failure
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
        yield  # pragma: no cover - make it an async generator

    agent.astream = cancelling_astream
    agent.metadata = {}

    with patch(
        "deerflow.runtime.runs.worker._rollback_to_pre_run_checkpoint",
        side_effect=RuntimeError("rollback boom"),
    ):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=lambda *, config: agent,
                graph_input={"messages": []},
                config={},
            )

    assert "cancellation rollback failed" in caplog.text


# ---------------------------------------------------------------------------
# journal flush exception in finally
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_journal_flush_exception(caplog):
    """run_agent logs a warning when journal flush fails in finally."""
    event_store = AsyncMock()
    ctx = _make_ctx(event_store=event_store)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    agent = MagicMock()
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    # Patch RunJournal to return a mock that fails on flush
    mock_journal = AsyncMock()
    mock_journal.flush = AsyncMock(side_effect=RuntimeError("flush error"))
    mock_journal.get_completion_data = MagicMock(return_value={})

    with patch("deerflow.runtime.journal.RunJournal", return_value=mock_journal):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=lambda *, config: agent,
                graph_input={"messages": []},
                config={},
            )

    assert "Failed to flush journal" in caplog.text


# ---------------------------------------------------------------------------
# journal completion persist exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_journal_completion_exception(caplog):
    """run_agent logs a warning when journal completion persist fails."""
    event_store = AsyncMock()
    ctx = _make_ctx(event_store=event_store)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()
    run_manager.update_run_completion = AsyncMock(side_effect=RuntimeError("completion error"))

    agent = MagicMock()
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    mock_journal = AsyncMock()
    mock_journal.flush = AsyncMock()
    mock_journal.get_completion_data = MagicMock(return_value={})

    with patch("deerflow.runtime.journal.RunJournal", return_value=mock_journal):
        with caplog.at_level(logging.WARNING):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                ctx=ctx,
                agent_factory=lambda *, config: agent,
                graph_input={"messages": []},
                config={},
            )

    assert "Failed to persist run completion" in caplog.text


# ---------------------------------------------------------------------------
# thread title sync failure
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
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    with caplog.at_level(logging.DEBUG, logger=_worker_logger_name):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=lambda *, config: agent,
            graph_input={"messages": []},
            config={},
        )

    assert "Failed to sync title" in caplog.text


# ---------------------------------------------------------------------------
# thread status update failure
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
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    with caplog.at_level(logging.DEBUG, logger=_worker_logger_name):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=lambda *, config: agent,
            graph_input={"messages": []},
            config={},
        )

    assert "Failed to update thread_meta status" in caplog.text


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint: current keyword-only contract
# ---------------------------------------------------------------------------


class _RollbackFakeCheckpointer:
    def __init__(self):
        self.adelete_thread = AsyncMock()
        self.aget_tuple = AsyncMock(return_value=None)
        self.aput_writes = AsyncMock()


def _rollback_accessor(checkpointer):
    return CheckpointStateAccessor(graph=SimpleNamespace(), checkpointer=checkpointer, mode="full")


def _make_rollback_point(*, checkpoint_id="ckpt-1", messages=("before",), pending_writes=()):
    return RollbackPoint(
        config={
            "configurable": {
                "thread_id": "t1",
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id,
            }
        },
        state_values={},
        messages=tuple(messages),
        metadata={"source": "input"},
        pending_writes=tuple(pending_writes),
    )


def _stub_mutation_graph(monkeypatch, *, restored_config):
    """Replace the rollback mutation graph with a stub returning ``restored_config``."""
    mock_graph = SimpleNamespace()
    mock_graph.aupdate_state = AsyncMock(return_value=restored_config)
    monkeypatch.setattr(
        "deerflow.runtime.runs.worker.build_state_mutation_graph",
        lambda *args, **kwargs: mock_graph,
    )
    return mock_graph


_RESTORED_CONFIG = {"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": "new-ckpt"}}


@pytest.mark.asyncio
async def test_rollback_restored_configurable_not_dict(monkeypatch):
    """_rollback raises when the restored config payload is not a dict."""
    checkpointer = _RollbackFakeCheckpointer()
    _stub_mutation_graph(monkeypatch, restored_config={"configurable": "not_a_dict"})

    with pytest.raises(RuntimeError, match="invalid config payload"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(),
            snapshot_capture_failed=False,
        )


@pytest.mark.asyncio
async def test_rollback_no_checkpointer(caplog):
    """_rollback logs info when checkpointer is None."""
    with caplog.at_level(logging.INFO):
        completed = await _rollback_to_pre_run_checkpoint(
            accessor=None,
            checkpointer=None,
            thread_id="t1",
            run_id="r1",
            rollback_point=None,
            snapshot_capture_failed=False,
        )

    assert completed is False
    assert "no checkpointer is configured" in caplog.text


@pytest.mark.asyncio
async def test_rollback_snapshot_capture_failed(caplog):
    """_rollback skips when snapshot capture failed."""
    checkpointer = _RollbackFakeCheckpointer()
    with caplog.at_level(logging.WARNING):
        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(),
            snapshot_capture_failed=True,
        )

    assert completed is False
    assert "capture failed" in caplog.text


@pytest.mark.asyncio
async def test_rollback_no_snapshot_deletes_thread(caplog):
    """_rollback deletes thread when there is no rollback point (reset contract)."""
    checkpointer = _RollbackFakeCheckpointer()

    with caplog.at_level(logging.INFO):
        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=None,
            snapshot_capture_failed=False,
        )

    assert completed is True
    checkpointer.adelete_thread.assert_awaited_once_with("t1")
    assert "reset thread" in caplog.text


@pytest.mark.asyncio
async def test_rollback_checkpoint_no_id(caplog):
    """_rollback skips when the rollback point has no checkpoint id to anchor a fork."""
    checkpointer = _RollbackFakeCheckpointer()
    with caplog.at_level(logging.WARNING):
        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(checkpoint_id=None),
            snapshot_capture_failed=False,
        )

    assert completed is False
    assert "no checkpoint id" in caplog.text


@pytest.mark.asyncio
async def test_rollback_invalid_pending_write(monkeypatch):
    """_rollback raises when pending_write is not a 3-tuple."""
    checkpointer = _RollbackFakeCheckpointer()
    _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)

    with pytest.raises(RuntimeError, match="not a 3-tuple"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(pending_writes=[("task1", "channel1")]),  # only 2 elements
            snapshot_capture_failed=False,
        )


@pytest.mark.asyncio
async def test_rollback_non_string_channel(monkeypatch):
    """_rollback raises when pending_write channel is not a string."""
    checkpointer = _RollbackFakeCheckpointer()
    _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)

    with pytest.raises(RuntimeError, match="non-string channel"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(pending_writes=[("task1", 123, "value")]),  # channel is int
            snapshot_capture_failed=False,
        )


@pytest.mark.asyncio
async def test_rollback_success_with_pending_writes(monkeypatch):
    """_rollback forks the pre-run checkpoint and replays pending writes by task."""
    checkpointer = _RollbackFakeCheckpointer()
    mock_graph = _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)

    completed = await _rollback_to_pre_run_checkpoint(
        accessor=_rollback_accessor(checkpointer),
        checkpointer=checkpointer,
        thread_id="t1",
        run_id="r1",
        rollback_point=_make_rollback_point(pending_writes=[("task1", "channel1", "value1")]),
        snapshot_capture_failed=False,
    )

    assert completed is True
    mock_graph.aupdate_state.assert_awaited_once()
    checkpointer.aput_writes.assert_awaited_once()


@pytest.mark.asyncio
async def test_rollback_restore_returns_non_dict(monkeypatch):
    """_rollback raises when the mutation write returns a non-dict config."""
    checkpointer = _RollbackFakeCheckpointer()
    _stub_mutation_graph(monkeypatch, restored_config="not_a_dict")

    with pytest.raises(RuntimeError, match="invalid config"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(),
            snapshot_capture_failed=False,
        )


@pytest.mark.asyncio
async def test_rollback_restore_no_checkpoint_id(monkeypatch):
    """_rollback raises when the mutation write does not return checkpoint_id."""
    checkpointer = _RollbackFakeCheckpointer()
    _stub_mutation_graph(monkeypatch, restored_config={"configurable": {}})

    with pytest.raises(RuntimeError, match="did not return checkpoint_id"):
        await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(checkpointer),
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(),
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
# _unpack_stream_item: subgraph namespace handling
# ---------------------------------------------------------------------------


def test_unpack_stream_item_subgraph_3tuple():
    """_unpack_stream_item handles 3-tuple with subgraphs."""
    mode, chunk, namespace = _unpack_stream_item(("ns", "values", {"a": 1}), ["values"], True)
    assert mode == "values"
    assert chunk == {"a": 1}
    assert namespace == ("ns",)


def test_unpack_stream_item_subgraph_2tuple():
    """_unpack_stream_item handles 2-tuple with subgraphs as a root frame."""
    mode, chunk, namespace = _unpack_stream_item(("updates", {"b": 2}), ["values", "updates"], True)
    assert mode == "updates"
    assert chunk == {"b": 2}
    assert namespace == ()


def test_unpack_stream_item_subgraph_unknown():
    """_unpack_stream_item returns (None, None, ()) for unknown subgraph item."""
    mode, chunk, namespace = _unpack_stream_item("garbage", ["values"], True)
    assert mode is None
    assert chunk is None
    assert namespace == ()


def test_unpack_stream_item_non_tuple_fallback():
    """_unpack_stream_item falls back to first mode for non-tuple items."""
    mode, chunk, namespace = _unpack_stream_item({"data": 1}, ["values", "updates"], False)
    assert mode == "values"
    assert chunk == {"data": 1}
    assert namespace == ()


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
        yield  # pragma: no cover

    agent.astream = cancelling_astream
    agent.metadata = {}

    with caplog.at_level(logging.INFO):
        await run_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            ctx=ctx,
            agent_factory=lambda *, config: agent,
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
    agent.metadata = {"model_name": "gpt-4o"}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=lambda *, config: agent,
        graph_input={"messages": []},
        config={},
    )

    run_manager.update_model_name.assert_called_once_with("run-1", "gpt-4o")


# ---------------------------------------------------------------------------
# agent_factory with app_config support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_factory_with_app_config():
    """run_agent calls agent_factory(config=..., app_config=...) when app_config is set."""
    from deerflow.config.app_config import AppConfig

    mock_app_config = MagicMock(spec=AppConfig)
    ctx = _make_ctx(app_config=mock_app_config)
    record = _make_record()
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    seen_kwargs: dict = {}

    agent = MagicMock()
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    def agent_factory(config, app_config):
        seen_kwargs["app_config"] = app_config
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

    assert seen_kwargs["app_config"] is mock_app_config
    run_manager.set_status_if_not_cancelled.assert_any_call("run-1", RunStatus.success, error=None, stop_reason=None)


# ---------------------------------------------------------------------------
# store is not None
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
    agent.metadata = {}

    async def _empty_astream(*args, **kwargs):
        return
        yield  # pragma: no cover

    agent.astream = _empty_astream

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=lambda *, config: agent,
        graph_input={"messages": []},
        config={},
    )

    assert agent.store == mock_store
    run_manager.set_status_if_not_cancelled.assert_any_call("run-1", RunStatus.success, error=None, stop_reason=None)


# ---------------------------------------------------------------------------
# abort during multi-mode stream (subgraph mode)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_abort_during_subgraph_stream():
    """run_agent stops streaming on abort in subgraph multi-mode stream."""
    ctx = _make_ctx()
    record = _make_record()
    record.abort_event = asyncio.Event()
    record.abort_action = "interrupt"
    bridge = _make_bridge()
    run_manager = _make_run_manager()

    async def fake_astream(*args, **kwargs):
        yield ("ns", "values", {"key": "val1"})
        # Request abort mid-stream; the worker must stop before the next frame.
        record.abort_event.set()
        yield ("ns", "updates", {"key": "val2"})

    agent = MagicMock()
    agent.astream = fake_astream
    agent.metadata = {}

    await run_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        ctx=ctx,
        agent_factory=lambda *, config: agent,
        graph_input={"messages": []},
        config={},
        stream_modes=["values", "updates"],
        stream_subgraphs=True,
    )

    run_manager.set_status.assert_any_call("run-1", RunStatus.interrupted)
