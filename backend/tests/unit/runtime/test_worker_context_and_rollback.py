"""Run worker context propagation, stream filtering, and rollback behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deerflow.runtime.checkpoint_state import CheckpointStateAccessor
from deerflow.runtime.runs.manager import RunStartOutcome
from deerflow.runtime.runs.schemas import RunStatus
from deerflow.runtime.runs.worker import (
    RollbackPoint,
    RunContext,
    _rollback_to_pre_run_checkpoint,
    run_agent,
)


def _make_run_manager() -> MagicMock:
    """Build a RunManager mock exposing every method upstream ``run_agent`` awaits."""
    run_manager = MagicMock()
    run_manager.wait_for_prior_finalizing = AsyncMock()
    run_manager.try_start = AsyncMock(return_value=RunStartOutcome.started)
    run_manager.set_status = AsyncMock()
    run_manager.set_status_if_not_cancelled = AsyncMock(return_value=None)
    run_manager.set_finalizing = AsyncMock()
    run_manager.update_run_completion = AsyncMock()
    run_manager.update_model_name = AsyncMock()
    run_manager.cleanup = AsyncMock()
    return run_manager


# ---------------------------------------------------------------------------
# agent_factory receives app_config
# ---------------------------------------------------------------------------


class TestRunWithAppConfig:
    @pytest.mark.asyncio
    async def test_agent_factory_receives_app_config(self):
        """When ctx.app_config is set and factory supports it, pass app_config."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = _make_run_manager()

        record = MagicMock()
        record.run_id = "run_appcfg"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.ownership_lost = False
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        mock_app_config = MagicMock()
        ctx = RunContext(checkpointer=None, store=None, app_config=mock_app_config)

        mock_agent = MagicMock()
        mock_agent.metadata = {}

        async def _empty_astream(*args, **kwargs):
            return
            yield

        mock_agent.astream = _empty_astream

        factory_calls = {}

        def agent_factory(config=None, app_config=None):
            factory_calls["config"] = config
            factory_calls["app_config"] = app_config
            return mock_agent

        with patch("deerflow.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("deerflow.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("deerflow.runtime.runs.worker.os.environ", {}):
                    with patch("deerflow.runtime.runs.worker.resolve_root_run_name", return_value="test"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                        )

        assert factory_calls["app_config"] is mock_app_config


# ---------------------------------------------------------------------------
# agent.store receives the runtime store
# ---------------------------------------------------------------------------


class TestRunWithStore:
    @pytest.mark.asyncio
    async def test_agent_receives_store(self):
        """When ctx.store is set, agent.store should be assigned."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = _make_run_manager()

        record = MagicMock()
        record.run_id = "run_store"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.ownership_lost = False
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        mock_store = MagicMock()
        ctx = RunContext(checkpointer=None, store=mock_store)

        mock_agent = MagicMock()
        mock_agent.metadata = {}

        async def _empty_astream(*args, **kwargs):
            return
            yield

        mock_agent.astream = _empty_astream

        def agent_factory(config=None):
            return mock_agent

        with patch("deerflow.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("deerflow.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("deerflow.runtime.runs.worker.os.environ", {}):
                    with patch("deerflow.runtime.runs.worker.resolve_root_run_name", return_value="test"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                        )

        assert mock_agent.store is mock_store


# ---------------------------------------------------------------------------
# Multi-mode streams skip items without a usable mode
# ---------------------------------------------------------------------------


class TestMultiModeStreamNoneMode:
    @pytest.mark.asyncio
    async def test_multi_mode_stream_skips_none_mode(self):
        """Multi-mode stream should skip items where mode is None."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = _make_run_manager()

        record = MagicMock()
        record.run_id = "run_multimode"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.ownership_lost = False
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        ctx = RunContext(checkpointer=None, store=None)

        # Create a stream that yields multiple modes
        async def mock_astream(input, config=None, stream_mode=None, subgraphs=False):
            # First item is valid
            yield ("values", {"data": 1})
            # Second item will be an unparseable 3-tuple without subgraphs
            yield ("ns", "values", {"data": 2})

        mock_agent = MagicMock()
        mock_agent.astream = mock_astream
        mock_agent.metadata = {}

        def agent_factory(config=None):
            return mock_agent

        with patch("deerflow.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("deerflow.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("deerflow.runtime.runs.worker.os.environ", {}):
                    with patch("deerflow.runtime.runs.worker.resolve_root_run_name", return_value="test"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                            stream_modes=["values", "updates"],
                        )

        # Should have published events (at least the valid items)
        bridge.publish.assert_called()


# ---------------------------------------------------------------------------
# Rollback restores through the pre-run checkpoint lineage
# ---------------------------------------------------------------------------


class TestRollbackCheckpointIdInjection:
    @pytest.mark.asyncio
    async def test_rollback_restores_from_pre_run_checkpoint_id(self):
        """A valid rollback point forks the pre-run checkpoint via a state mutation write."""
        checkpointer = MagicMock()
        checkpointer.aput_writes = AsyncMock()

        class _StubMutationAccessor:
            mode = "full"

            def __init__(self):
                self.aupdate_calls = []

            async def aupdate(self, config, values, *, as_node=None):
                self.aupdate_calls.append((config, values, as_node))
                return {"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": "restored-id"}}

        stub_mutation_accessor = _StubMutationAccessor()
        rollback_point = RollbackPoint(
            config={"configurable": {"thread_id": "t1", "checkpoint_ns": "", "checkpoint_id": "original-ckpt-id"}},
            state_values={},
            messages=(),
            metadata={},
            pending_writes=(),
        )
        accessor = SimpleNamespace(mode="full", graph=None)

        with patch.object(
            CheckpointStateAccessor,
            "bind",
            classmethod(lambda cls, graph, checkpointer, **kwargs: stub_mutation_accessor),
        ):
            restored = await _rollback_to_pre_run_checkpoint(
                accessor=accessor,
                checkpointer=checkpointer,
                thread_id="t1",
                run_id="r1",
                rollback_point=rollback_point,
                snapshot_capture_failed=False,
            )

        assert restored is True
        assert len(stub_mutation_accessor.aupdate_calls) == 1
        restore_config, _values, as_node = stub_mutation_accessor.aupdate_calls[0]
        # The mutation write is anchored at the pre-run checkpoint id.
        assert restore_config["configurable"]["checkpoint_id"] == "original-ckpt-id"
        assert as_node == "rollback_restore"
        checkpointer.aput_writes.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_no_checkpoint_id_skips(self):
        """When the pre-run checkpoint has no checkpoint id, skip the restore."""
        checkpointer = MagicMock()
        checkpointer.aput_writes = AsyncMock()

        class _StubMutationAccessor:
            mode = "full"

            async def aupdate(self, config, values, *, as_node=None):  # pragma: no cover - must not run
                raise AssertionError("aupdate must not be called without a checkpoint id")

        rollback_point = RollbackPoint(
            config={"configurable": {"thread_id": "t1", "checkpoint_ns": ""}},
            state_values={},
            messages=(),
            metadata={},
            pending_writes=(),
        )
        accessor = SimpleNamespace(mode="full", graph=None)

        with patch.object(
            CheckpointStateAccessor,
            "bind",
            classmethod(lambda cls, graph, checkpointer, **kwargs: _StubMutationAccessor()),
        ):
            restored = await _rollback_to_pre_run_checkpoint(
                accessor=accessor,
                checkpointer=checkpointer,
                thread_id="t1",
                run_id="r1",
                rollback_point=rollback_point,
                snapshot_capture_failed=False,
            )

        assert restored is False
        checkpointer.aput_writes.assert_not_called()


# ---------------------------------------------------------------------------
# Line 254 alternative: agent_factory without app_config support
# ---------------------------------------------------------------------------


class TestAgentFactoryWithoutAppConfig:
    @pytest.mark.asyncio
    async def test_factory_without_app_config_param(self):
        """When factory doesn't support app_config, it's called without it."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = _make_run_manager()

        record = MagicMock()
        record.run_id = "run_noapp"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.ownership_lost = False
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        mock_app_config = MagicMock()
        ctx = RunContext(checkpointer=None, store=None, app_config=mock_app_config)

        mock_agent = MagicMock()
        mock_agent.metadata = {}

        async def _empty_astream(*args, **kwargs):
            return
            yield

        mock_agent.astream = _empty_astream

        # Factory that does NOT accept app_config
        def agent_factory(config=None):
            return mock_agent

        with patch("deerflow.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("deerflow.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("deerflow.runtime.runs.worker.os.environ", {}):
                    with patch("deerflow.runtime.runs.worker.resolve_root_run_name", return_value="test"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                        )

        # Agent should still be created successfully
        run_manager.set_status_if_not_cancelled.assert_any_call("run_noapp", RunStatus.success, error=None, stop_reason=None)


# ---------------------------------------------------------------------------
# Lines 326-327, 331: multi-mode stream abort and None mode handling
# ---------------------------------------------------------------------------


class TestMultiModeStreamAbort:
    @pytest.mark.asyncio
    async def test_multi_mode_abort_during_streaming(self):
        """Lines 326-327: abort during multi-mode stream breaks the loop."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = _make_run_manager()

        record = MagicMock()
        record.run_id = "run_mm_abort"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.ownership_lost = False
        record.abort_event = MagicMock()
        # 1st call: chunk check (continue), 2nd: chunk check (abort → break),
        # then the goal-continuation while-condition and the final status check
        # each poll once more; both must see True.
        record.abort_event.is_set.side_effect = [False, True, True, True]
        record.abort_action = "interrupt"
        record.status = RunStatus.interrupted

        ctx = RunContext(checkpointer=None, store=None)

        chunk_count = 0

        async def mock_astream(input, config=None, stream_mode=None, subgraphs=False):
            nonlocal chunk_count
            chunk_count += 1
            yield ("values", {"data": 1})
            chunk_count += 1
            yield ("values", {"data": 2})

        mock_agent = MagicMock()
        mock_agent.astream = mock_astream
        mock_agent.metadata = {}

        def agent_factory(config=None):
            return mock_agent

        with patch("deerflow.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("deerflow.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("deerflow.runtime.runs.worker.os.environ", {}):
                    with patch("deerflow.runtime.runs.worker.resolve_root_run_name", return_value="test"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                            stream_modes=["values", "updates"],
                        )

        # Abort should have stopped the stream
        run_manager.set_status.assert_any_call("run_mm_abort", RunStatus.interrupted)


class TestMultiModeStreamNoneModeExtra:
    @pytest.mark.asyncio
    async def test_multi_mode_none_mode_continues(self):
        """Lines 330-331: when _unpack_stream_item returns None mode, skip the item."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = _make_run_manager()

        record = MagicMock()
        record.run_id = "run_mm_none"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.ownership_lost = False
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        ctx = RunContext(checkpointer=None, store=None)

        async def mock_astream(input, config=None, stream_mode=None, subgraphs=False):
            # Valid tuple
            yield ("values", {"data": 1})
            # Invalid item that _unpack_stream_item can't parse (3-tuple without subgraphs)
            yield ("ns", "values", {"data": 2})

        mock_agent = MagicMock()
        mock_agent.astream = mock_astream
        mock_agent.metadata = {}

        def agent_factory(config=None):
            return mock_agent

        with patch("deerflow.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("deerflow.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("deerflow.runtime.runs.worker.os.environ", {}):
                    with patch("deerflow.runtime.runs.worker.resolve_root_run_name", return_value="test"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                            stream_modes=["values", "updates"],
                        )

        # Should complete successfully
        run_manager.set_status_if_not_cancelled.assert_any_call("run_mm_none", RunStatus.success, error=None, stop_reason=None)
