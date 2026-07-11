"""Additional tests for ideer.runtime.runs.worker — coverage gaps."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.runtime.runs.schemas import RunStatus
from packages.harness.ideer.runtime.runs.worker import (
    RunContext,
    _build_runtime_context,
    _install_runtime_context,
    _unpack_stream_item,
    run_agent,
)

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
        """Three-tuple without subgraphs should fallback to first mode."""
        mode, chunk = _unpack_stream_item(("ns", "values", {"data": 1}), ["values"], False)
        # Without subgraphs, three-tuple is not unpacked as (ns, mode, chunk)
        # Falls back to first mode
        assert mode == "values"

    def test_single_element_list_item(self):
        mode, chunk = _unpack_stream_item(("values",), ["values"], False)
        assert mode == "values"


# ---------------------------------------------------------------------------
# run_agent — additional edge cases
# ---------------------------------------------------------------------------


class TestRunAgentAdditional:
    @pytest.mark.asyncio
    async def test_run_aborted_rollback_action(self):
        """Test run abort with rollback action."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = True
        record.abort_action = "rollback"
        record.status = RunStatus.error

        ctx = RunContext(checkpointer=None, store=None)

        mock_agent = MagicMock()

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

        run_manager.set_status.assert_any_call("run_1", RunStatus.error, error="Rolled back by user")

    @pytest.mark.asyncio
    async def test_run_cancelled_rollback_action(self):
        """Test run cancellation with rollback action."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_action = "rollback"
        record.status = RunStatus.error

        ctx = RunContext(checkpointer=None, store=None)

        mock_agent = MagicMock()

        async def cancelling_astream(*args, **kwargs):
            raise asyncio.CancelledError()
            yield

        mock_agent.astream = cancelling_astream

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

        run_manager.set_status.assert_any_call("run_1", RunStatus.error, error="Rolled back by user")

    @pytest.mark.asyncio
    async def test_run_with_model_name_resolution(self):
        """Test that model name is updated when agent metadata differs."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_model_name = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = "gpt-4"
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        ctx = RunContext(checkpointer=None, store=None)

        mock_agent = MagicMock()
        mock_agent.metadata = {"model_name": "gpt-4-turbo"}

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

        run_manager.update_model_name.assert_called_with("run_1", "gpt-4-turbo")

    @pytest.mark.asyncio
    async def test_run_with_subgraphs(self):
        """Test run with subgraphs enabled."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        ctx = RunContext(checkpointer=None, store=None)

        async def mock_astream(input, config=None, stream_mode=None, subgraphs=False):
            if subgraphs:
                yield ("ns", "values", {"data": 1})
            else:
                yield ("values", {"data": 1})

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
                            stream_modes=["values"],
                            stream_subgraphs=True,
                        )

        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_with_thread_store(self):
        """Test run with thread_store for title sync."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        thread_store = MagicMock()
        thread_store.update_display_name = AsyncMock()
        thread_store.update_status = AsyncMock()

        ctx = RunContext(checkpointer=None, thread_store=thread_store)

        mock_agent = MagicMock()

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

        thread_store.update_status.assert_called()

    @pytest.mark.asyncio
    async def test_run_messages_tuple_mode(self):
        """Test run with messages-tuple mode maps to 'messages'."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        ctx = RunContext(checkpointer=None, store=None)

        async def mock_astream(input, config=None, stream_mode="values"):
            yield ("messages", {"content": "hi"})

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
                            stream_modes=["messages-tuple"],
                        )

        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_invalid_stream_mode_fallback(self):
        """Test that invalid stream modes are filtered out, falling back to values."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.success

        ctx = RunContext(checkpointer=None, store=None)

        async def mock_astream(input, config=None, stream_mode="values"):
            yield {"data": "test"}

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
                            stream_modes=["invalid_mode"],
                        )

        # Invalid mode should be filtered, values fallback used
        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_abort_during_streaming(self):
        """Test abort during streaming stops processing."""
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_run_completion = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = True  # Always abort
        record.abort_action = "interrupt"
        record.status = RunStatus.interrupted

        ctx = RunContext(checkpointer=None, store=None)

        async def mock_astream(input, config=None, stream_mode="values"):
            yield {"chunk": 1}
            yield {"chunk": 2}

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
                        )

        # When abort is set, stream loop breaks immediately (no chunks published)
        run_manager.set_status.assert_any_call("run_1", RunStatus.interrupted)
