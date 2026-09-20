"""Additional tests for deerflow.runtime.runs.worker — coverage gaps."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from deerflow.runtime.runs.manager import RunStartOutcome
from deerflow.runtime.runs.schemas import RunStatus
from deerflow.runtime.runs.worker import (
    _build_runtime_context,
    _install_runtime_context,
    _unpack_stream_item,
    run_agent,
)

# ---------------------------------------------------------------------------
# Helpers (mocks shaped for the current run_agent contract)
# ---------------------------------------------------------------------------


def _make_record(**overrides):
    record = MagicMock()
    record.run_id = "run_1"
    record.thread_id = "thread_1"
    record.assistant_id = "lead_agent"
    record.model_name = None
    record.abort_event = MagicMock()
    record.abort_event.is_set.return_value = False
    record.abort_action = "interrupt"
    record.status = RunStatus.success
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
    bridge = MagicMock()
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()
    return bridge


def _make_run_manager():
    run_manager = MagicMock()
    run_manager.set_status = AsyncMock()
    run_manager.set_status_if_not_cancelled = AsyncMock(return_value=None)
    run_manager.set_finalizing = AsyncMock()
    run_manager.wait_for_prior_finalizing = AsyncMock()
    run_manager.try_start = AsyncMock(return_value=RunStartOutcome.started)
    run_manager.has_later_started_run = AsyncMock(return_value=False)
    run_manager.persist_current_status = AsyncMock()
    run_manager.persist_current_record = AsyncMock(return_value=True)
    run_manager.update_run_progress = AsyncMock()
    run_manager.update_run_completion = AsyncMock()
    run_manager.update_finalizing_progress = AsyncMock()
    run_manager.update_model_name = AsyncMock()
    run_manager.cleanup = AsyncMock()
    return run_manager


class _EmptyAgent:
    metadata: dict = {}

    async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
        return
        yield  # pragma: no cover


# ---------------------------------------------------------------------------
# _build_runtime_context — additional cases
# ---------------------------------------------------------------------------


class TestBuildRuntimeContextAdditional:
    def test_caller_context_with_existing_thread_id(self):
        caller = {"thread_id": "caller_tid", "run_id": "caller_rid", "extra": "val"}
        result = _build_runtime_context("actual_tid", "actual_rid", caller)
        assert result["thread_id"] == "actual_tid"
        assert result["run_id"] == "actual_rid"
        assert result["extra"] == "val"


# ---------------------------------------------------------------------------
# _install_runtime_context — additional cases
# ---------------------------------------------------------------------------


class TestInstallRuntimeContextAdditional:
    def test_no_existing_context(self):
        config = {}
        runtime_ctx = {"thread_id": "t1", "run_id": "r1", "app_config": "ac"}
        _install_runtime_context(config, runtime_ctx)
        assert config["context"]["app_config"] == "ac"

    def test_existing_context_without_app_config(self):
        config = {"context": {"custom": "val"}}
        runtime_ctx = {"thread_id": "t1", "run_id": "r1"}
        _install_runtime_context(config, runtime_ctx)
        assert config["context"]["custom"] == "val"
        assert "app_config" not in config["context"]


# ---------------------------------------------------------------------------
# _unpack_stream_item — additional cases
# ---------------------------------------------------------------------------


class TestUnpackStreamItemAdditional:
    def test_three_tuple_without_subgraphs(self):
        """Three-tuple without subgraphs falls back to first mode with the raw item."""
        mode, chunk, namespace = _unpack_stream_item(("ns", "values", {"data": 1}), ["values"], False)
        assert mode == "values"
        assert chunk == ("ns", "values", {"data": 1})
        assert namespace == ()

    def test_single_element_list_item(self):
        mode, chunk, namespace = _unpack_stream_item(("values",), ["values"], False)
        assert mode == "values"
        assert chunk == ("values",)
        assert namespace == ()


# ---------------------------------------------------------------------------
# run_agent — additional edge cases
# ---------------------------------------------------------------------------


class TestRunAgentAdditional:
    @pytest.mark.asyncio
    async def test_run_aborted_rollback_action(self):
        """Test run abort with rollback action."""
        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record(abort_action="rollback", status=RunStatus.error)
        record.abort_event.is_set.return_value = True

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
        )

        run_manager.set_status.assert_any_call("run_1", RunStatus.error, error="Rolled back by user")

    @pytest.mark.asyncio
    async def test_run_cancelled_rollback_action(self):
        """Test run cancellation with rollback action."""

        class CancellingAgent:
            metadata: dict = {}

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                raise asyncio.CancelledError()
                yield  # pragma: no cover

        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record(abort_action="rollback", status=RunStatus.error)

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(),
            agent_factory=lambda *, config: CancellingAgent(),
            graph_input={"messages": []},
            config={},
        )

        run_manager.set_status.assert_any_call("run_1", RunStatus.error, error="Rolled back by user")

    @pytest.mark.asyncio
    async def test_run_with_model_name_resolution(self):
        """Test that model name is updated when agent metadata differs."""
        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record(model_name="gpt-4")

        class ModelAgent:
            metadata = {"model_name": "gpt-4-turbo"}

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                return
                yield  # pragma: no cover

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(),
            agent_factory=lambda *, config: ModelAgent(),
            graph_input={"messages": []},
            config={},
        )

        run_manager.update_model_name.assert_called_with("run_1", "gpt-4-turbo")

    @pytest.mark.asyncio
    async def test_run_with_subgraphs(self):
        """Test run with subgraphs enabled."""

        class SubgraphAgent:
            metadata: dict = {}

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                yield ("ns", "values", {"data": 1})

        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(),
            agent_factory=lambda *, config: SubgraphAgent(),
            graph_input={"messages": []},
            config={},
            stream_modes=["values"],
            stream_subgraphs=True,
        )

        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_with_thread_store(self):
        """Test run with thread_store for title sync."""
        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record()

        thread_store = MagicMock()
        thread_store.update_display_name = AsyncMock()
        thread_store.update_status = AsyncMock()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(thread_store=thread_store),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
        )

        thread_store.update_status.assert_called()

    @pytest.mark.asyncio
    async def test_run_messages_tuple_mode(self):
        """Test run with messages-tuple mode maps to 'messages'."""

        class MessagesAgent:
            metadata: dict = {}

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                assert stream_mode == "messages"
                yield ("messages", {"content": "hi"})

        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(),
            agent_factory=lambda *, config: MessagesAgent(),
            graph_input={"messages": []},
            config={},
            stream_modes=["messages-tuple"],
        )

        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_invalid_stream_mode_rejected(self):
        """Invalid stream modes now fail the run instead of silently falling back.

        Upstream replaced the old filtered-fallback behavior with
        normalize_stream_modes raising UnsupportedStreamModeError.
        """
        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
            stream_modes=["invalid_mode"],
        )

        assert record is not None
        run_manager.set_status_if_not_cancelled.assert_any_call(
            "run_1",
            RunStatus.error,
            error="Unsupported stream mode(s): invalid_mode",
        )

    @pytest.mark.asyncio
    async def test_run_abort_during_streaming(self):
        """Test abort during streaming stops processing."""
        bridge = _make_bridge()
        run_manager = _make_run_manager()
        record = _make_record(status=RunStatus.interrupted)
        record.abort_event.is_set.return_value = True  # Always abort

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=_make_ctx(),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
        )

        # When abort is set, no stream chunks are published (only the
        # metadata frame) and the run ends interrupted.
        for pub_call in bridge.publish.await_args_list:
            assert pub_call.args[1] == "metadata"
        run_manager.set_status.assert_any_call("run_1", RunStatus.interrupted)
