"""Tests for ideer.runtime.runs.worker — background agent execution."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.runtime.runs.worker import (
    RunContext,
    _agent_factory_supports_app_config,
    _build_runtime_context,
    _cached_agent_factory_supports_app_config,
    _call_checkpointer_method,
    _compute_agent_factory_supports_app_config,
    _extract_human_message,
    _install_runtime_context,
    _lg_mode_to_sse_event,
    _new_checkpoint_marker,
    _rollback_to_pre_run_checkpoint,
    _unpack_stream_item,
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
# _extract_human_message
# ---------------------------------------------------------------------------


class TestExtractHumanMessage:
    def test_with_human_message_in_list(self):
        from langchain_core.messages import HumanMessage

        graph_input = {"messages": [HumanMessage(content="hello")]}
        result = _extract_human_message(graph_input)
        assert result is not None
        assert result.content == "hello"

    def test_with_string_message(self):
        graph_input = {"messages": ["hello"]}
        result = _extract_human_message(graph_input)
        assert result is not None
        assert result.content == "hello"

    def test_with_dict_message(self):
        graph_input = {"messages": [{"content": "hello"}]}
        result = _extract_human_message(graph_input)
        assert result is not None
        assert result.content == "hello"

    def test_with_object_with_content(self):
        obj = SimpleNamespace(content="hello")
        graph_input = {"messages": [obj]}
        result = _extract_human_message(graph_input)
        assert result is not None
        assert result.content == "hello"

    def test_no_messages(self):
        assert _extract_human_message({}) is None

    def test_empty_string_message(self):
        graph_input = {"messages": [""]}
        assert _extract_human_message(graph_input) is None

    def test_empty_content_dict(self):
        graph_input = {"messages": [{"content": ""}]}
        assert _extract_human_message(graph_input) is None

    def test_single_message_not_list(self):
        from langchain_core.messages import HumanMessage

        graph_input = {"messages": HumanMessage(content="hi")}
        result = _extract_human_message(graph_input)
        assert result is not None


# ---------------------------------------------------------------------------
# _unpack_stream_item
# ---------------------------------------------------------------------------


class TestUnpackStreamItem:
    def test_two_tuple(self):
        mode, chunk = _unpack_stream_item(("values", {"data": 1}), ["values"], False)
        assert mode == "values"
        assert chunk == {"data": 1}

    def test_three_tuple_with_subgraphs(self):
        mode, chunk = _unpack_stream_item(("ns", "updates", {"data": 2}), ["updates"], True)
        assert mode == "updates"
        assert chunk == {"data": 2}

    def test_two_tuple_with_subgraphs(self):
        mode, chunk = _unpack_stream_item(("values", {"data": 3}), ["values"], True)
        assert mode == "values"

    def test_fallback_single_mode(self):
        mode, chunk = _unpack_stream_item({"data": 4}, ["values"], False)
        assert mode == "values"
        assert chunk == {"data": 4}

    def test_fallback_empty_modes(self):
        mode, chunk = _unpack_stream_item({"data": 5}, [], False)
        assert mode is None

    def test_invalid_tuple_subgraphs(self):
        mode, chunk = _unpack_stream_item(("single",), ["values"], True)
        assert mode is None


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


class TestRollbackToPreRunCheckpoint:
    @pytest.mark.asyncio
    async def test_no_checkpointer(self):
        # Should return without error
        await _rollback_to_pre_run_checkpoint(
            checkpointer=None,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=None,
            snapshot_capture_failed=False,
        )

    @pytest.mark.asyncio
    async def test_snapshot_capture_failed(self):
        cp = MagicMock()
        await _rollback_to_pre_run_checkpoint(
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=None,
            snapshot_capture_failed=True,
        )
        # Should not call any checkpointer methods

    @pytest.mark.asyncio
    async def test_no_snapshot_deletes_thread(self):
        cp = MagicMock()
        cp.adelete_thread = AsyncMock()
        await _rollback_to_pre_run_checkpoint(
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=None,
            snapshot_capture_failed=False,
        )
        cp.adelete_thread.assert_called_once_with("t1")

    @pytest.mark.asyncio
    async def test_with_snapshot(self):
        cp = MagicMock()
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "restored_id"}})
        cp.aput_writes = AsyncMock()

        snapshot = {
            "checkpoint": {"id": "ckpt_1", "channel_versions": {"v1": 1}},
            "metadata": {"key": "val"},
            "checkpoint_ns": "",
            "pending_writes": [("task_1", "channel_1", "value_1")],
        }

        await _rollback_to_pre_run_checkpoint(
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="ckpt_1",
            pre_run_snapshot=snapshot,
            snapshot_capture_failed=False,
        )
        cp.aput.assert_called_once()
        cp.aput_writes.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_snapshot_no_pending_writes(self):
        cp = MagicMock()
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "restored_id"}})

        snapshot = {
            "checkpoint": {"id": "ckpt_1"},
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [],
        }

        await _rollback_to_pre_run_checkpoint(
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id="ckpt_1",
            pre_run_snapshot=snapshot,
            snapshot_capture_failed=False,
        )
        cp.aput.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_checkpoint(self):
        cp = MagicMock()
        snapshot = {
            "checkpoint": "not_a_dict",
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [],
        }

        await _rollback_to_pre_run_checkpoint(
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=snapshot,
            snapshot_capture_failed=False,
        )
        # Should not raise, just log warning

    @pytest.mark.asyncio
    async def test_checkpoint_no_id_no_pre_run_id(self):
        cp = MagicMock()
        snapshot = {
            "checkpoint": {"channel_versions": {}},
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [],
        }

        await _rollback_to_pre_run_checkpoint(
            checkpointer=cp,
            thread_id="t1",
            run_id="r1",
            pre_run_checkpoint_id=None,
            pre_run_snapshot=snapshot,
            snapshot_capture_failed=False,
        )
        # Should log warning about no checkpoint id

    @pytest.mark.asyncio
    async def test_invalid_pending_write(self):
        cp = MagicMock()
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "restored_id"}})

        snapshot = {
            "checkpoint": {"id": "ckpt_1", "channel_versions": {}},
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [("not", "a_3_tuple_item")],
        }

        with pytest.raises(RuntimeError, match="pending_write is not a 3-tuple"):
            await _rollback_to_pre_run_checkpoint(
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                pre_run_checkpoint_id="ckpt_1",
                pre_run_snapshot=snapshot,
                snapshot_capture_failed=False,
            )

    @pytest.mark.asyncio
    async def test_invalid_restored_config(self):
        cp = MagicMock()
        cp.aput = AsyncMock(return_value="not_a_dict")

        snapshot = {
            "checkpoint": {"id": "ckpt_1"},
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [],
        }

        with pytest.raises(RuntimeError, match="invalid config"):
            await _rollback_to_pre_run_checkpoint(
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                pre_run_checkpoint_id="ckpt_1",
                pre_run_snapshot=snapshot,
                snapshot_capture_failed=False,
            )

    @pytest.mark.asyncio
    async def test_no_checkpoint_id_returned(self):
        cp = MagicMock()
        cp.aput = AsyncMock(return_value={"configurable": {}})

        snapshot = {
            "checkpoint": {"id": "ckpt_1"},
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [],
        }

        with pytest.raises(RuntimeError, match="did not return checkpoint_id"):
            await _rollback_to_pre_run_checkpoint(
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                pre_run_checkpoint_id="ckpt_1",
                pre_run_snapshot=snapshot,
                snapshot_capture_failed=False,
            )

    @pytest.mark.asyncio
    async def test_non_string_channel_in_pending_write(self):
        cp = MagicMock()
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "restored_id"}})

        snapshot = {
            "checkpoint": {"id": "ckpt_1"},
            "metadata": {},
            "checkpoint_ns": "",
            "pending_writes": [("task_1", 123, "value")],
        }

        with pytest.raises(RuntimeError, match="non-string channel"):
            await _rollback_to_pre_run_checkpoint(
                checkpointer=cp,
                thread_id="t1",
                run_id="r1",
                pre_run_checkpoint_id="ckpt_1",
                pre_run_snapshot=snapshot,
                snapshot_capture_failed=False,
            )


# ---------------------------------------------------------------------------
# run_agent (high-level integration)
# ---------------------------------------------------------------------------


class TestRunAgent:
    @pytest.mark.asyncio
    async def test_successful_run(self):
        """Test a complete successful agent run."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

        # Set up mocks
        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()
        run_manager.update_model_name = AsyncMock()
        run_manager.update_run_completion = AsyncMock()
        run_manager.update_run_progress = MagicMock()

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
        mock_agent.metadata = {"model_name": "gpt-4"}

        async def _empty_astream(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_agent.astream = _empty_astream

        def agent_factory(config=None, app_config=None):
            return mock_agent

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test_run"):
                        await run_agent(
                            bridge,
                            run_manager,
                            record,
                            ctx=ctx,
                            agent_factory=agent_factory,
                            graph_input={"messages": []},
                            config={},
                        )

        run_manager.set_status.assert_any_call("run_1", RunStatus.running)
        run_manager.set_status.assert_any_call("run_1", RunStatus.success)

    @pytest.mark.asyncio
    async def test_run_with_error(self):
        """Test agent run that raises an exception."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = False
        record.status = RunStatus.error

        ctx = RunContext(checkpointer=None, store=None)

        def agent_factory(config=None):
            raise RuntimeError("agent build failed")

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

        run_manager.set_status.assert_any_call("run_1", RunStatus.error, error="agent build failed")
        bridge.publish.assert_any_call("run_1", "error", {"message": "agent build failed", "name": "RuntimeError"})

    @pytest.mark.asyncio
    async def test_run_aborted(self):
        """Test agent run that gets aborted."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_event = MagicMock()
        record.abort_event.is_set.return_value = True
        record.abort_action = "cancel"
        record.status = RunStatus.interrupted

        ctx = RunContext(checkpointer=None, store=None)

        mock_agent = MagicMock()

        async def _empty_astream_abort(*args, **kwargs):
            return
            yield

        mock_agent.astream = _empty_astream_abort

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

        run_manager.set_status.assert_any_call("run_1", RunStatus.interrupted)

    @pytest.mark.asyncio
    async def test_run_cancelled(self):
        """Test agent run that gets cancelled (CancelledError)."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

        bridge = MagicMock()
        bridge.publish = AsyncMock()
        bridge.publish_end = AsyncMock()
        bridge.cleanup = AsyncMock()

        run_manager = MagicMock()
        run_manager.set_status = AsyncMock()

        record = MagicMock()
        record.run_id = "run_1"
        record.thread_id = "thread_1"
        record.assistant_id = "lead_agent"
        record.model_name = None
        record.abort_action = "cancel"
        record.status = RunStatus.interrupted

        ctx = RunContext(checkpointer=None, store=None)

        mock_agent = MagicMock()

        async def cancelling_astream(*args, **kwargs):
            raise asyncio.CancelledError()
            yield  # Make it an async generator

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

        run_manager.set_status.assert_any_call("run_1", RunStatus.interrupted)

    @pytest.mark.asyncio
    async def test_run_with_checkpointer(self):
        """Test run with checkpointer snapshotting."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

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

        mock_ckpt_tuple = MagicMock()
        mock_ckpt_tuple.config = {"configurable": {"checkpoint_id": "ckpt_1", "checkpoint_ns": ""}}
        mock_ckpt_tuple.checkpoint = {"id": "ckpt_1"}
        mock_ckpt_tuple.metadata = {}
        mock_ckpt_tuple.pending_writes = []

        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=mock_ckpt_tuple)

        thread_store = MagicMock()
        thread_store.update_display_name = AsyncMock()
        thread_store.update_status = AsyncMock()

        ctx = RunContext(checkpointer=checkpointer, thread_store=thread_store)

        mock_agent = MagicMock()

        async def _empty_astream_generic(*args, **kwargs):
            return
            yield

        mock_agent.astream = _empty_astream_generic

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

        # Verify checkpoint snapshot was taken
        checkpointer.aget_tuple.assert_called()
        # Verify thread status updated
        thread_store.update_status.assert_called()

    @pytest.mark.asyncio
    async def test_run_with_journal(self):
        """Test run with event store / journal."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

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

        event_store = MagicMock()
        run_events_config = MagicMock()
        run_events_config.track_token_usage = True

        ctx = RunContext(
            checkpointer=None,
            event_store=event_store,
            run_events_config=run_events_config,
        )

        mock_agent = MagicMock()

        async def _empty_astream_generic(*args, **kwargs):
            return
            yield

        mock_agent.astream = _empty_astream_generic

        def agent_factory(config=None):
            return mock_agent

        mock_journal = MagicMock()
        mock_journal.flush = AsyncMock()
        mock_journal.get_completion_data.return_value = {}

        with patch("packages.harness.ideer.runtime.runs.worker.inject_langfuse_metadata"):
            with patch("packages.harness.ideer.runtime.runs.worker.get_effective_user_id", return_value="user_1"):
                with patch("packages.harness.ideer.runtime.runs.worker.os.environ", {}):
                    with patch("packages.harness.ideer.runtime.runs.worker.resolve_root_run_name", return_value="test"):
                        with patch("ideer.runtime.journal.RunJournal", return_value=mock_journal):
                            await run_agent(
                                bridge,
                                run_manager,
                                record,
                                ctx=ctx,
                                agent_factory=agent_factory,
                                graph_input={"messages": []},
                                config={},
                            )

        mock_journal.flush.assert_called()

    @pytest.mark.asyncio
    async def test_run_with_streaming_events(self):
        """Test run that streams events."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

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

        ctx = RunContext(checkpointer=None)

        async def mock_astream(input, config=None, stream_mode="values"):
            yield {"messages": [{"type": "ai", "content": "response"}]}

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
                            graph_input={"messages": [{"role": "human", "content": "hi"}]},
                            config={},
                            stream_modes=["values"],
                        )

        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_with_multiple_modes(self):
        """Test run with multiple stream modes."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

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

        ctx = RunContext(checkpointer=None)

        async def mock_astream(input, config=None, stream_mode=None, subgraphs=False):
            yield ("values", {"messages": []})
            yield ("updates", {"node": {"key": "val"}})

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

        bridge.publish.assert_called()

    @pytest.mark.asyncio
    async def test_run_events_mode_skipped(self):
        """Test that 'events' mode is skipped."""
        from packages.harness.ideer.runtime.runs.schemas import RunStatus
        from packages.harness.ideer.runtime.runs.worker import run_agent

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

        ctx = RunContext(checkpointer=None)

        async def mock_astream(input, config=None, stream_mode="values"):
            yield {"messages": []}

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
                            stream_modes=["events", "values"],
                        )

        # Should still succeed — "events" is skipped, "values" is used
        run_manager.set_status.assert_any_call("run_1", RunStatus.success)
