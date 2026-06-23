"""Additional tests for ideer.runtime.runs.worker — remaining coverage gaps.

Covers:
  - Line 254: agent_factory called with app_config
  - Line 273: agent.store = store (store is not None)
  - Lines 326-327, 331: multi-mode stream where unpack returns (None, chunk)
  - Line 479: rollback checkpoint id injection from pre_run_checkpoint_id
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.runtime.runs.schemas import RunStatus
from packages.harness.ideer.runtime.runs.worker import (
    RunContext,
    _rollback_to_pre_run_checkpoint,
    run_agent,
)

# ---------------------------------------------------------------------------
# Line 254: agent_factory with app_config
# ---------------------------------------------------------------------------


class TestRunWithAppConfig:
    @pytest.mark.asyncio
    async def test_agent_factory_receives_app_config(self):
        """When ctx.app_config is set and factory supports it, pass app_config."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_appcfg"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
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

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test"):
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
# Line 273: agent.store = store
# ---------------------------------------------------------------------------


class TestRunWithStore:
    @pytest.mark.asyncio
    async def test_agent_receives_store(self):
        """When ctx.store is set, agent.store should be assigned."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_store"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
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

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test"):
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
# Lines 326-327, 331: multi-mode stream with None mode from _unpack_stream_item
# ---------------------------------------------------------------------------


class TestMultiModeStreamNoneMode:
    @pytest.mark.asyncio
    async def test_multi_mode_stream_skips_none_mode(self):
        """Multi-mode stream should skip items where mode is None."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_multimode"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
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

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test"):
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
# Line 479: rollback with checkpoint missing id but pre_run_checkpoint_id set
# ---------------------------------------------------------------------------


class TestRollbackCheckpointIdInjection:
    @pytest.mark.asyncio
    async def test_rollback_injects_checkpoint_id_from_pre_run(self):
        """When checkpoint has no id but pre_run_checkpoint_id is set, inject it."""
        checkpointer = MagicMock()
        checkpointer.aput = AsyncMock(
            return_value={
                "configurable": {
                    "thread_id": "t1",
                    "checkpoint_ns": "",
                    "checkpoint_id": "restored-id",
                }
            }
        )

        # Pre-run snapshot with checkpoint that has NO "id"
        pre_run_snapshot = {
            "checkpoint": {"channel_values": {}, "ts": "2024-01-01"},
            "metadata": {"run_id": "r1"},
            "pending_writes": [],
            "checkpoint_ns": "",
        }

        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="original-ckpt-id",
            pre_run_snapshot=pre_run_snapshot,
            snapshot_capture_failed=False,
        )

        # aput should have been called with a checkpoint that has an id
        checkpointer.aput.assert_called_once()
        call_args = checkpointer.aput.call_args
        restored_ckpt = call_args[0][1]  # second positional arg is checkpoint
        assert "id" in restored_ckpt
        assert restored_ckpt["id"] is not None

    @pytest.mark.asyncio
    async def test_rollback_no_checkpoint_id_skips(self):
        """When checkpoint has no id and no pre_run_checkpoint_id, skip rollback."""
        checkpointer = MagicMock()

        pre_run_snapshot = {
            "checkpoint": {"channel_values": {}, "ts": "2024-01-01"},
            "metadata": {},
            "pending_writes": [],
            "checkpoint_ns": "",
        }

        await _rollback_to_pre_run_checkpoint(
            checkpointer=checkpointer,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=pre_run_snapshot,
            snapshot_capture_failed=False,
        )

        # aput should NOT be called since checkpoint has no id
        checkpointer.aput.assert_not_called()


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

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_noapp"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
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

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test"):
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
        run_manager.set_status.assert_any_call("run_noapp", RunStatus.success)


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

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_mm_abort"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        # First call returns False (continue streaming), second returns True (abort),
        # third returns True (final status check after loop)
        record.abort_event.is_set.side_effect = [False, True, True]
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

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test"):
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

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_mm_none"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
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

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test"):
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
        run_manager.set_status.assert_any_call("run_mm_none", RunStatus.success)
