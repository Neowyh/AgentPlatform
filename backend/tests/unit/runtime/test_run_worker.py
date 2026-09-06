"""Tests for deerflow.runtime.runs.worker — background agent execution."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from deerflow.runtime.checkpoint_state import CheckpointStateAccessor
from deerflow.runtime.events.store.memory import MemoryRunEventStore
from deerflow.runtime.runs.manager import RunManager
from deerflow.runtime.runs.schemas import RunStatus
from deerflow.runtime.runs.worker import (
    RollbackPoint,
    RunContext,
    _agent_factory_supports_app_config,
    _build_runtime_context,
    _cached_agent_factory_supports_app_config,
    _call_checkpointer_method,
    _compute_agent_factory_supports_app_config,
    _extract_llm_error_fallback_message,
    _install_runtime_context,
    _lg_mode_to_sse_event,
    _new_checkpoint_marker,
    _rollback_to_pre_run_checkpoint,
    _unpack_stream_item,
    run_agent,
)

# ---------------------------------------------------------------------------
# _build_runtime_context
# ---------------------------------------------------------------------------


class TestBuildRuntimeContext:
    def test_basic(self):
        result = _build_runtime_context("t1", "r1", None)
        assert result["thread_id"] == "t1"
        assert result["run_id"] == "r1"

    def test_with_caller_context(self):
        caller = {"agent_name": "test_agent", "extra": "data"}
        result = _build_runtime_context("t1", "r1", caller)
        assert result["agent_name"] == "test_agent"
        assert result["extra"] == "data"

    def test_caller_does_not_override(self):
        caller = {"thread_id": "override", "run_id": "override"}
        result = _build_runtime_context("t1", "r1", caller)
        assert result["thread_id"] == "t1"
        assert result["run_id"] == "r1"

    def test_with_app_config(self):
        config = MagicMock()
        result = _build_runtime_context("t1", "r1", None, app_config=config)
        assert result["app_config"] is config

    def test_non_dict_caller(self):
        result = _build_runtime_context("t1", "r1", "not_a_dict")
        assert result["thread_id"] == "t1"


# ---------------------------------------------------------------------------
# RunContext dataclass
# ---------------------------------------------------------------------------


class TestRunContext:
    def test_defaults(self):
        ctx = RunContext(checkpointer="cp")
        assert ctx.checkpointer == "cp"
        assert ctx.store is None
        assert ctx.event_store is None
        assert ctx.thread_store is None

    def test_all_fields(self):
        ctx = RunContext(
            checkpointer="cp",
            store="store",
            event_store="es",
            run_events_config="rec",
            thread_store="ts",
            app_config="ac",
        )
        assert ctx.store == "store"
        assert ctx.event_store == "es"


# ---------------------------------------------------------------------------
# _install_runtime_context
# ---------------------------------------------------------------------------


class TestInstallRuntimeContext:
    def test_sets_context(self):
        config = {}
        runtime_ctx = {"thread_id": "t1", "run_id": "r1"}
        _install_runtime_context(config, runtime_ctx)
        assert config["context"] == runtime_ctx

    def test_merges_existing(self):
        config = {"context": {"custom_key": "val"}}
        runtime_ctx = {"thread_id": "t1", "run_id": "r1", "app_config": "ac"}
        _install_runtime_context(config, runtime_ctx)
        assert config["context"]["custom_key"] == "val"
        assert config["context"]["thread_id"] == "t1"
        assert config["context"]["app_config"] == "ac"

    def test_existing_does_not_override(self):
        config = {"context": {"thread_id": "existing"}}
        runtime_ctx = {"thread_id": "t1", "run_id": "r1"}
        _install_runtime_context(config, runtime_ctx)
        assert config["context"]["thread_id"] == "existing"


# ---------------------------------------------------------------------------
# _compute_agent_factory_supports_app_config
# ---------------------------------------------------------------------------


class TestAgentFactorySupportsAppConfig:
    def test_with_app_config_param(self):
        def factory(config, app_config=None):
            pass

        assert _compute_agent_factory_supports_app_config(factory) is True

    def test_without_app_config_param(self):
        def factory(config):
            pass

        assert _compute_agent_factory_supports_app_config(factory) is False

    def test_with_non_callable(self):
        assert _compute_agent_factory_supports_app_config("not_callable") is False


# ---------------------------------------------------------------------------
# _cached_agent_factory_supports_app_config
# ---------------------------------------------------------------------------


class TestCachedAgentFactorySupportsAppConfig:
    def test_caches_result(self):
        def factory(config, app_config=None):
            pass

        # Clear cache
        _cached_agent_factory_supports_app_config.cache_clear()
        result1 = _cached_agent_factory_supports_app_config(factory)
        result2 = _cached_agent_factory_supports_app_config(factory)
        assert result1 is True
        assert result2 is True

    def test_unhashable_fallback(self):
        # Test the _agent_factory_supports_app_config wrapper
        class UnhashableFactory:
            __hash__ = None

            def __call__(self, config, app_config=None):
                pass

        factory = UnhashableFactory()
        # _agent_factory_supports_app_config catches TypeError
        result = _agent_factory_supports_app_config(factory)
        assert result is True


# ---------------------------------------------------------------------------
# _lg_mode_to_sse_event
# ---------------------------------------------------------------------------


class TestLgModeToSseEvent:
    def test_identity_mapping(self):
        assert _lg_mode_to_sse_event("values") == "values"
        assert _lg_mode_to_sse_event("updates") == "updates"
        assert _lg_mode_to_sse_event("messages") == "messages"

    def test_custom_mode(self):
        assert _lg_mode_to_sse_event("custom") == "custom"


# ---------------------------------------------------------------------------
# _extract_llm_error_fallback_message
# ---------------------------------------------------------------------------


class TestExtractLlmErrorFallbackMessage:
    """``_extract_llm_error_fallback_message`` returns the fallback detail string.

    Upstream replaced the old human-message extraction with error-fallback
    marker extraction: only messages carrying the ``deerflow_error_fallback``
    marker in ``additional_kwargs`` match, and the function returns the error
    detail/reason text rather than a message object.
    """

    @staticmethod
    def _marker_message(content="", **extra):
        from langchain_core.messages import AIMessage

        kwargs = {"deerflow_error_fallback": True}
        kwargs.update(extra)
        return AIMessage(content=content, additional_kwargs=kwargs)

    def test_extracts_error_detail_from_object_message(self):
        graph_input = {"messages": [self._marker_message(content="fallback", error_detail="boom")]}
        result = _extract_llm_error_fallback_message(graph_input)
        assert result == "boom"

    def test_extracts_from_dict_message(self):
        graph_input = {
            "messages": [
                {
                    "content": "c",
                    "additional_kwargs": {"deerflow_error_fallback": True, "error_reason": "rate_limited"},
                }
            ]
        }
        result = _extract_llm_error_fallback_message(graph_input)
        assert result == "rate_limited"

    def test_no_messages(self):
        assert _extract_llm_error_fallback_message({}) is None

    def test_message_without_marker(self):
        from langchain_core.messages import AIMessage

        graph_input = {"messages": [AIMessage(content="hello")]}
        assert _extract_llm_error_fallback_message(graph_input) is None

    def test_content_fallback(self):
        msg = {"additional_kwargs": {"deerflow_error_fallback": True}, "content": "fallback text"}
        assert _extract_llm_error_fallback_message({"messages": [msg]}) == "fallback text"

    def test_default_message_when_no_metadata_or_content(self):
        msg = {"additional_kwargs": {"deerflow_error_fallback": True}, "content": ""}
        assert _extract_llm_error_fallback_message({"messages": [msg]}) == "LLM provider failed after retries"

    def test_pre_existing_ids_skipped(self):
        from langchain_core.messages import AIMessage

        msg = AIMessage(
            content="x",
            id="m1",
            additional_kwargs={"deerflow_error_fallback": True, "error_detail": "boom"},
        )
        assert _extract_llm_error_fallback_message({"messages": [msg]}, {"m1"}) is None

    def test_updates_chunk_deep_walk(self):
        msg = {"additional_kwargs": {"deerflow_error_fallback": True, "error_detail": "deep"}}
        graph_input = {"node": {"messages": [msg]}}
        assert _extract_llm_error_fallback_message(graph_input) == "deep"


# ---------------------------------------------------------------------------
# _unpack_stream_item
# ---------------------------------------------------------------------------


class TestUnpackStreamItem:
    def test_two_tuple(self):
        mode, chunk, namespace = _unpack_stream_item(("values", {"data": 1}), ["values"], False)
        assert mode == "values"
        assert chunk == {"data": 1}
        assert namespace == ()

    def test_three_tuple_with_subgraphs(self):
        mode, chunk, namespace = _unpack_stream_item(("ns", "updates", {"data": 2}), ["updates"], True)
        assert mode == "updates"
        assert chunk == {"data": 2}
        assert namespace == ("ns",)

    def test_list_namespace_with_subgraphs(self):
        mode, chunk, namespace = _unpack_stream_item((["a", "b"], "updates", {"data": 7}), ["updates"], True)
        assert mode == "updates"
        assert namespace == ("a", "b")

    def test_two_tuple_with_subgraphs(self):
        mode, chunk, namespace = _unpack_stream_item(("values", {"data": 3}), ["values"], True)
        assert mode == "values"
        assert chunk == {"data": 3}
        assert namespace == ()

    def test_fallback_single_mode(self):
        mode, chunk, namespace = _unpack_stream_item({"data": 4}, ["values"], False)
        assert mode == "values"
        assert chunk == {"data": 4}
        assert namespace == ()

    def test_fallback_empty_modes(self):
        mode, chunk, namespace = _unpack_stream_item({"data": 5}, [], False)
        assert mode is None
        assert chunk == {"data": 5}
        assert namespace == ()

    def test_invalid_tuple_subgraphs(self):
        mode, chunk, namespace = _unpack_stream_item(("single",), ["values"], True)
        assert mode is None
        assert chunk is None
        assert namespace == ()


# ---------------------------------------------------------------------------
# _new_checkpoint_marker
# ---------------------------------------------------------------------------


class TestNewCheckpointMarker:
    def test_returns_id_and_ts(self):
        marker = _new_checkpoint_marker()
        assert "id" in marker
        assert "ts" in marker
        assert isinstance(marker["id"], str)
        assert isinstance(marker["ts"], str)


# ---------------------------------------------------------------------------
# _call_checkpointer_method
# ---------------------------------------------------------------------------


class TestCallCheckpointerMethod:
    @pytest.mark.asyncio
    async def test_async_method(self):
        cp = MagicMock()
        cp.aget_tuple = AsyncMock(return_value="result")
        result = await _call_checkpointer_method(cp, "aget_tuple", "get_tuple", "arg")
        assert result == "result"

    @pytest.mark.asyncio
    async def test_sync_method(self):
        cp = MagicMock()
        cp.get_tuple = MagicMock(return_value="result")
        cp.aget_tuple = None  # no async version
        result = await _call_checkpointer_method(cp, "aget_tuple", "get_tuple", "arg")
        assert result == "result"

    @pytest.mark.asyncio
    async def test_missing_method(self):
        cp = MagicMock(spec=[])  # no methods
        with pytest.raises(AttributeError, match="Missing checkpointer method"):
            await _call_checkpointer_method(cp, "aget_tuple", "get_tuple")


# ---------------------------------------------------------------------------
# _rollback_to_pre_run_checkpoint
# ---------------------------------------------------------------------------


class _RollbackFakeCheckpointer:
    def __init__(self):
        self.adelete_thread = AsyncMock()
        self.aget_tuple = AsyncMock(return_value=None)
        self.aput_writes = AsyncMock()


def _rollback_accessor(checkpointer):
    return CheckpointStateAccessor(graph=SimpleNamespace(), checkpointer=checkpointer, mode="full")


def _make_rollback_point(*, checkpoint_id="ckpt_1", messages=("before",), pending_writes=()):
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


_RESTORED_CONFIG = {"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": "restored_id"}}


class TestRollbackToPreRunCheckpoint:
    @pytest.mark.asyncio
    async def test_no_checkpointer(self):
        # No checkpointer configured: rollback is a no-op returning False.
        completed = await _rollback_to_pre_run_checkpoint(
            accessor=None,
            checkpointer=None,
            thread_id="t1",
            run_id="r1",
            rollback_point=None,
            snapshot_capture_failed=False,
        )
        assert completed is False

    @pytest.mark.asyncio
    async def test_snapshot_capture_failed(self):
        # Capture failure disables rollback: no checkpointer writes at all.
        cp = _RollbackFakeCheckpointer()
        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(cp),
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(),
            snapshot_capture_failed=True,
        )
        assert completed is False
        cp.adelete_thread.assert_not_awaited()
        cp.aput_writes.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_snapshot_deletes_thread(self):
        # No rollback point: reset contract deletes the thread state.
        cp = _RollbackFakeCheckpointer()
        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(cp),
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            rollback_point=None,
            snapshot_capture_failed=False,
        )
        assert completed is True
        cp.adelete_thread.assert_awaited_once_with("t1")

    @pytest.mark.asyncio
    async def test_with_snapshot(self, monkeypatch):
        cp = _RollbackFakeCheckpointer()
        mock_graph = _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)
        rollback_point = _make_rollback_point(
            pending_writes=[
                ("task_1", "channel_1", "value_1"),
                ("task_1", "status", "done"),
                ("task_2", "events", {"type": "tool"}),
            ],
        )

        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(cp),
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            rollback_point=rollback_point,
            snapshot_capture_failed=False,
        )
        assert completed is True
        # Full mode forks the pre-run checkpoint: messages are overwritten on
        # the forked head, no thread deletion.
        cp.adelete_thread.assert_not_awaited()
        mock_graph.aupdate_state.assert_awaited_once()
        update_config, update_values = mock_graph.aupdate_state.await_args.args[:2]
        assert update_config["configurable"]["checkpoint_id"] == "ckpt_1"
        from langgraph.types import Overwrite

        overwrite = update_values["messages"]
        assert isinstance(overwrite, Overwrite)
        assert overwrite.value == ["before"]
        assert mock_graph.aupdate_state.await_args.kwargs["as_node"] == "rollback_restore"
        # Pending writes are re-applied grouped by task id onto the restored head.
        assert cp.aput_writes.await_args_list == [
            call(_RESTORED_CONFIG, [("channel_1", "value_1"), ("status", "done")], task_id="task_1"),
            call(_RESTORED_CONFIG, [("events", {"type": "tool"})], task_id="task_2"),
        ]

    @pytest.mark.asyncio
    async def test_with_snapshot_no_pending_writes(self, monkeypatch):
        cp = _RollbackFakeCheckpointer()
        _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)

        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(cp),
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(pending_writes=[]),
            snapshot_capture_failed=False,
        )
        assert completed is True
        cp.aput_writes.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_checkpoint(self, monkeypatch):
        # A rollback point without a checkpoint id cannot anchor a fork.
        cp = _RollbackFakeCheckpointer()
        mock_graph = _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)

        completed = await _rollback_to_pre_run_checkpoint(
            accessor=_rollback_accessor(cp),
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(checkpoint_id=None),
            snapshot_capture_failed=False,
        )
        assert completed is False
        cp.adelete_thread.assert_not_awaited()
        mock_graph.aupdate_state.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_checkpoint_no_id_no_pre_run_id(self):
        # Missing accessor is fail-closed: rollback cannot proceed.
        cp = _RollbackFakeCheckpointer()

        completed = await _rollback_to_pre_run_checkpoint(
            accessor=None,
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            rollback_point=_make_rollback_point(),
            snapshot_capture_failed=False,
        )
        assert completed is False
        cp.aput_writes.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_pending_write(self, monkeypatch):
        cp = _RollbackFakeCheckpointer()
        _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)

        with pytest.raises(RuntimeError, match="pending_write is not a 3-tuple"):
            await _rollback_to_pre_run_checkpoint(
                accessor=_rollback_accessor(cp),
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                rollback_point=_make_rollback_point(pending_writes=[("not", "a_3_tuple_item")]),
                snapshot_capture_failed=False,
            )

    @pytest.mark.asyncio
    async def test_invalid_restored_config(self, monkeypatch):
        cp = _RollbackFakeCheckpointer()
        _stub_mutation_graph(monkeypatch, restored_config="not_a_dict")

        with pytest.raises(RuntimeError, match="invalid config"):
            await _rollback_to_pre_run_checkpoint(
                accessor=_rollback_accessor(cp),
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                rollback_point=_make_rollback_point(),
                snapshot_capture_failed=False,
            )

    @pytest.mark.asyncio
    async def test_no_checkpoint_id_returned(self, monkeypatch):
        cp = _RollbackFakeCheckpointer()
        _stub_mutation_graph(monkeypatch, restored_config={"configurable": {}})

        with pytest.raises(RuntimeError, match="did not return checkpoint_id"):
            await _rollback_to_pre_run_checkpoint(
                accessor=_rollback_accessor(cp),
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                rollback_point=_make_rollback_point(),
                snapshot_capture_failed=False,
            )

    @pytest.mark.asyncio
    async def test_non_string_channel_in_pending_write(self, monkeypatch):
        cp = _RollbackFakeCheckpointer()
        _stub_mutation_graph(monkeypatch, restored_config=_RESTORED_CONFIG)

        with pytest.raises(RuntimeError, match="non-string channel"):
            await _rollback_to_pre_run_checkpoint(
                accessor=_rollback_accessor(cp),
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                rollback_point=_make_rollback_point(pending_writes=[("task_1", 123, "value")]),
                snapshot_capture_failed=False,
            )


# ---------------------------------------------------------------------------
# run_agent (high-level integration)
# ---------------------------------------------------------------------------


def _worker_bridge():
    """Minimal stream bridge stand-in matching the attributes run_agent uses."""
    return SimpleNamespace(publish=AsyncMock(), publish_end=AsyncMock(), cleanup=AsyncMock())


class _EmptyAgent:
    """Agent stand-in whose stream yields nothing."""

    metadata: dict = {}

    async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
        return
        yield  # pragma: no cover - makes this an async generator


class TestRunAgent:
    @pytest.mark.asyncio
    async def test_successful_run(self):
        """A complete successful agent run reaches the success status."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
        )

        assert record.status == RunStatus.success
        # useStream needs both run_id AND thread_id in the metadata frame.
        bridge.publish.assert_any_call(
            record.run_id,
            "metadata",
            {"run_id": record.run_id, "thread_id": record.thread_id},
        )

    @pytest.mark.asyncio
    async def test_run_with_error(self):
        """Agent build failure marks the run errored and publishes the error frame."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()

        def agent_factory(*, config):
            raise RuntimeError("agent build failed")

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None),
            agent_factory=agent_factory,
            graph_input={"messages": []},
            config={},
        )

        assert record.status == RunStatus.error
        assert record.error == "agent build failed"
        bridge.publish.assert_any_call(
            record.run_id,
            "error",
            {"message": "agent build failed", "name": "RuntimeError"},
        )

    @pytest.mark.asyncio
    async def test_run_aborted(self):
        """A run whose abort event is already set ends interrupted."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        record.abort_event.set()
        bridge = _worker_bridge()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
        )

        assert record.status == RunStatus.interrupted

    @pytest.mark.asyncio
    async def test_run_cancelled(self):
        """A CancelledError escaping the agent stream ends the run interrupted."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()

        class CancellingAgent:
            metadata: dict = {}

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                raise asyncio.CancelledError()
                yield  # pragma: no cover - makes this an async generator

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None),
            agent_factory=lambda *, config: CancellingAgent(),
            graph_input={"messages": []},
            config={},
        )

        assert record.status == RunStatus.interrupted

    @pytest.mark.asyncio
    async def test_run_with_checkpointer(self):
        """A run with a checkpointer reads checkpoint state and drives thread status."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()

        checkpoint_tuple = SimpleNamespace(
            config={"configurable": {"thread_id": "thread_1", "checkpoint_ns": "", "checkpoint_id": "ckpt_1"}},
            checkpoint={"id": "ckpt_1"},
            metadata={},
            pending_writes=[],
        )
        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)

        class SnapshotAgent:
            metadata: dict = {}

            async def aget_state(self, config):
                return SimpleNamespace(
                    values={"messages": []},
                    config=checkpoint_tuple.config,
                    metadata={},
                )

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                return
                yield  # pragma: no cover

        thread_store = SimpleNamespace(update_display_name=AsyncMock(), update_status=AsyncMock())

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=checkpointer, thread_store=thread_store),
            agent_factory=lambda *, config: SnapshotAgent(),
            graph_input={"messages": []},
            config={},
        )

        assert record.status == RunStatus.success
        # The pre-run rollback capture reads the checkpoint tuple.
        checkpointer.aget_tuple.assert_awaited()
        # Thread status goes running on start and back to idle on success.
        thread_store.update_status.assert_any_call("thread_1", "running")
        thread_store.update_status.assert_any_call("thread_1", "idle")

    @pytest.mark.asyncio
    async def test_run_with_journal(self):
        """A run with an event store flushes its journal and persists the delivery receipt."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()
        event_store = MemoryRunEventStore()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None, event_store=event_store),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
        )

        assert record.status == RunStatus.success
        events = await event_store.list_events(record.thread_id, record.run_id)
        assert any(event["event_type"] == "run.delivery" for event in events)

    @pytest.mark.asyncio
    async def test_run_with_streaming_events(self):
        """Values-mode chunks are published on the bridge."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()

        class StreamingAgent:
            metadata: dict = {}

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                yield {"messages": [{"type": "ai", "content": "response"}]}

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None),
            agent_factory=lambda *, config: StreamingAgent(),
            graph_input={"messages": [{"role": "human", "content": "hi"}]},
            config={},
            stream_modes=["values"],
        )

        assert record.status == RunStatus.success
        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_with_multiple_modes(self):
        """Multiple stream modes each publish through the bridge."""
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()

        class MultiModeAgent:
            metadata: dict = {}

            async def astream(self, graph_input, config=None, stream_mode=None, subgraphs=False):
                yield ("values", {"messages": []})
                yield ("updates", {"node": {"key": "val"}})

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None),
            agent_factory=lambda *, config: MultiModeAgent(),
            graph_input={"messages": []},
            config={},
            stream_modes=["values", "updates"],
        )

        assert record.status == RunStatus.success
        published_modes = {call.args[1] for call in bridge.publish.await_args_list}
        assert "values" in published_modes
        assert "updates" in published_modes

    @pytest.mark.asyncio
    async def test_run_events_mode_rejected(self):
        """'events' is no longer a supported stream mode: the run fails closed.

        Upstream replaced the old silently-skipped 'events' handling with
        normalize_stream_modes raising UnsupportedStreamModeError.
        """
        run_manager = RunManager()
        record = await run_manager.create("thread_1")
        bridge = _worker_bridge()

        await run_agent(
            bridge,
            run_manager,
            record,
            ctx=RunContext(checkpointer=None),
            agent_factory=lambda *, config: _EmptyAgent(),
            graph_input={"messages": []},
            config={},
            stream_modes=["events", "values"],
        )

        assert record.status == RunStatus.error
        assert "Unsupported stream mode" in record.error
