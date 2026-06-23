"""Coverage boost tests for app.gateway.services.

Targets missed lines:
- Line 110: normalize_input non-dict/non-BaseMessage passthrough
- Line 167: inject_authenticated_user_context early return (no user_id)
- Line 245: build_run_config invalid assistant_id ValueError
- Line 251: build_run_config fallback to setdefault("configurable", {})
- Lines 282-370: start_run function
- Lines 385-404: sse_consumer function
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Line 110: normalize_input with non-dict, non-BaseMessage messages
# ---------------------------------------------------------------------------


class TestNormalizeInputPassthrough:
    """Cover the else branch at line 110 where message is not dict and not BaseMessage."""

    def test_non_dict_non_basemessage_passthrough(self):
        from app.gateway.services import normalize_input

        # A plain string is neither a dict nor a BaseMessage → else branch
        result = normalize_input({"messages": ["just a string", 42]})
        assert result["messages"][0] == "just a string"
        assert result["messages"][1] == 42

    def test_mixed_message_types(self):
        from app.gateway.services import normalize_input

        result = normalize_input(
            {
                "messages": [
                    {"role": "user", "content": "dict msg"},
                    "plain string",
                    12345,
                ]
            }
        )
        assert len(result["messages"]) == 3
        # first converted, rest passed through
        assert result["messages"][0].content == "dict msg"
        assert result["messages"][1] == "plain string"
        assert result["messages"][2] == 12345

    def test_basemessage_instance_passthrough(self):
        """Line 100: BaseMessage instances are appended directly."""
        from langchain_core.messages import HumanMessage

        from app.gateway.services import normalize_input

        msg = HumanMessage(content="hello")
        result = normalize_input({"messages": [msg]})
        assert result["messages"][0] is msg


# ---------------------------------------------------------------------------
# Line 167: inject_authenticated_user_context with no user_id
# ---------------------------------------------------------------------------


class TestInjectAuthenticatedUserContextNoUser:
    """Cover the early return when user_id is None."""

    def test_no_user_state(self):
        from app.gateway.services import inject_authenticated_user_context

        config = {"configurable": {"thread_id": "t1"}}
        request = SimpleNamespace(state=SimpleNamespace(user=None))
        inject_authenticated_user_context(config, request)
        # Should not have added user_id
        assert "context" not in config

    def test_user_with_no_id(self):
        from app.gateway.services import inject_authenticated_user_context

        config = {"configurable": {"thread_id": "t1"}}
        user_no_id = SimpleNamespace()  # no id attribute
        request = SimpleNamespace(state=SimpleNamespace(user=user_no_id))
        inject_authenticated_user_context(config, request)
        assert "context" not in config

    def test_no_state_user_attr(self):
        from app.gateway.services import inject_authenticated_user_context

        config = {"configurable": {"thread_id": "t1"}}
        request = SimpleNamespace(state=SimpleNamespace())  # no user attr
        inject_authenticated_user_context(config, request)
        assert "context" not in config


# ---------------------------------------------------------------------------
# Line 245: build_run_config invalid assistant_id
# ---------------------------------------------------------------------------


class TestBuildRunConfigInvalidAssistantId:
    """Cover the ValueError raise for invalid assistant_id normalization."""

    def test_invalid_chars_in_assistant_id(self):
        import pytest

        from app.gateway.services import build_run_config

        with pytest.raises(ValueError, match="Invalid assistant_id"):
            build_run_config("thread-1", None, None, assistant_id="bad agent!")

    def test_underscores_normalized_to_hyphens(self):
        from app.gateway.services import build_run_config

        config = build_run_config("thread-1", None, None, assistant_id="my_agent")
        assert config["configurable"]["agent_name"] == "my-agent"


# ---------------------------------------------------------------------------
# Line 251: build_run_config target fallback to setdefault
# ---------------------------------------------------------------------------


class TestBuildRunConfigTargetFallback:
    """Cover the else branch where neither 'configurable' nor 'context' exists."""

    def test_no_configurable_no_context_fallback(self):
        from app.gateway.services import build_run_config

        # When request_config has neither "configurable" nor "context",
        # build_run_config creates "configurable" with thread_id.
        # Then for assistant_id, target is already in "configurable".
        # To hit line 251, we need a config where neither key exists after processing.
        # This happens when request_config is non-null but has no "configurable"/"context".
        config = build_run_config(
            "thread-1",
            {"tags": ["test"]},  # no configurable or context
            None,
            assistant_id="custom-agent",
        )
        assert config["configurable"]["agent_name"] == "custom-agent"


# ---------------------------------------------------------------------------
# Lines 282-370: start_run function
# ---------------------------------------------------------------------------


class TestStartRun:
    """Test the start_run lifecycle function with mocked dependencies."""

    @pytest.fixture()
    def mock_deps(self):
        """Create mock dependencies for start_run."""
        bridge = MagicMock()
        bridge.subscribe = MagicMock()

        run_mgr = MagicMock()
        run_mgr.create_or_reject = AsyncMock()
        run_mgr.cancel = AsyncMock()

        run_ctx = MagicMock()
        run_ctx.thread_store = MagicMock()
        run_ctx.thread_store.get = AsyncMock(return_value=None)
        run_ctx.thread_store.create = AsyncMock()
        run_ctx.thread_store.update_status = AsyncMock()

        request = MagicMock()
        request.state = SimpleNamespace(user=SimpleNamespace(id="user-1"))
        request.headers = {}

        return bridge, run_mgr, run_ctx, request

    @pytest.mark.asyncio
    async def test_start_run_basic(self, mock_deps):
        """Cover the basic flow of start_run."""
        bridge, run_mgr, run_ctx, request = mock_deps

        record = MagicMock()
        record.run_id = "run-123"
        record.task = None
        run_mgr.create_or_reject.return_value = record

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="cancel",
            input={"messages": [{"role": "user", "content": "hi"}]},
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context=None,
        )

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.resolve_agent_factory") as mock_factory,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_factory.return_value = MagicMock()
            mock_app_config.return_value.get_model_config.return_value = None

            from app.gateway.services import start_run

            result = await start_run(body, "thread-1", request)

        assert result == record
        run_mgr.create_or_reject.assert_called_once()
        run_ctx.thread_store.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_run_with_model_name(self, mock_deps):
        """Cover model validation path."""
        bridge, run_mgr, run_ctx, request = mock_deps

        record = MagicMock()
        record.run_id = "run-456"
        record.task = None
        run_mgr.create_or_reject.return_value = record

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="continue",
            input={"messages": [{"role": "user", "content": "hi"}]},
            config=None,
            metadata={"key": "value"},
            multitask_strategy="reject",
            stream_mode=["values"],
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context={"model_name": "gpt-4"},
        )

        mock_model_config = {"name": "gpt-4"}

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.resolve_agent_factory") as mock_factory,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_factory.return_value = MagicMock()
            mock_app_config.return_value.get_model_config.return_value = mock_model_config

            from app.gateway.services import start_run

            result = await start_run(body, "thread-1", request)

        assert result == record

    @pytest.mark.asyncio
    async def test_start_run_rejects_unknown_model(self, mock_deps):
        """Cover the HTTPException(400) for unknown model."""
        bridge, run_mgr, run_ctx, request = mock_deps

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="cancel",
            input=None,
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context={"model_name": "unknown-model"},
        )

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_app_config.return_value.get_model_config.return_value = None

            from app.gateway.services import start_run

            with pytest.raises(Exception) as excinfo:
                await start_run(body, "thread-1", request)
            assert "unknown-model" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_start_run_coerces_non_string_model_name(self, mock_deps):
        """Cover the non-string model_name coercion."""
        bridge, run_mgr, run_ctx, request = mock_deps

        record = MagicMock()
        record.run_id = "run-789"
        record.task = None
        run_mgr.create_or_reject.return_value = record

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="cancel",
            input=None,
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context={"model_name": 12345},  # non-string
        )

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.resolve_agent_factory") as mock_factory,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_factory.return_value = MagicMock()
            mock_app_config.return_value.get_model_config.return_value = {"name": "12345"}

            from app.gateway.services import start_run

            result = await start_run(body, "thread-1", request)
        assert result == record

    @pytest.mark.asyncio
    async def test_start_run_handles_conflict_error(self, mock_deps):
        """Cover the ConflictError -> HTTPException 409 path."""
        bridge, run_mgr, run_ctx, request = mock_deps

        from ideer.runtime import ConflictError

        run_mgr.create_or_reject.side_effect = ConflictError("already running")

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="cancel",
            input=None,
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context=None,
        )

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_app_config.return_value.get_model_config.return_value = None

            from app.gateway.services import start_run

            with pytest.raises(Exception) as excinfo:
                await start_run(body, "thread-1", request)
            assert excinfo.value.status_code == 409

    @pytest.mark.asyncio
    async def test_start_run_handles_unsupported_strategy(self, mock_deps):
        """Cover the UnsupportedStrategyError -> HTTPException 501 path."""
        bridge, run_mgr, run_ctx, request = mock_deps

        from ideer.runtime import UnsupportedStrategyError

        run_mgr.create_or_reject.side_effect = UnsupportedStrategyError("not supported")

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="cancel",
            input=None,
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context=None,
        )

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_app_config.return_value.get_model_config.return_value = None

            from app.gateway.services import start_run

            with pytest.raises(Exception) as excinfo:
                await start_run(body, "thread-1", request)
            assert excinfo.value.status_code == 501

    @pytest.mark.asyncio
    async def test_start_run_thread_already_exists(self, mock_deps):
        """Cover the else branch when thread already exists (update_status)."""
        bridge, run_mgr, run_ctx, request = mock_deps

        record = MagicMock()
        record.run_id = "run-existing"
        record.task = None
        run_mgr.create_or_reject.return_value = record

        # Thread already exists
        run_ctx.thread_store.get = AsyncMock(return_value={"thread_id": "thread-1"})

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="cancel",
            input=None,
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context=None,
        )

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.resolve_agent_factory") as mock_factory,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_factory.return_value = MagicMock()
            mock_app_config.return_value.get_model_config.return_value = None

            from app.gateway.services import start_run

            result = await start_run(body, "thread-1", request)

        assert result == record
        run_ctx.thread_store.update_status.assert_called_once_with("thread-1", "running")
        run_ctx.thread_store.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_run_thread_upsert_exception_is_non_fatal(self, mock_deps):
        """Cover the exception handling for thread_meta upsert (non-fatal)."""
        bridge, run_mgr, run_ctx, request = mock_deps

        record = MagicMock()
        record.run_id = "run-upsert-fail"
        record.task = None
        run_mgr.create_or_reject.return_value = record

        run_ctx.thread_store.get = AsyncMock(side_effect=Exception("DB down"))

        body = SimpleNamespace(
            assistant_id="lead_agent",
            on_disconnect="cancel",
            input=None,
            config=None,
            metadata=None,
            multitask_strategy="reject",
            stream_mode=None,
            stream_subgraphs=False,
            interrupt_before=None,
            interrupt_after=None,
            context=None,
        )

        with (
            patch("app.gateway.services.get_stream_bridge", return_value=bridge),
            patch("app.gateway.services.get_run_manager", return_value=run_mgr),
            patch("app.gateway.services.get_run_context", return_value=run_ctx),
            patch("app.gateway.services.resolve_agent_factory") as mock_factory,
            patch("app.gateway.services.run_agent", new_callable=AsyncMock),
            patch("app.gateway.services.get_app_config") as mock_app_config,
        ):
            mock_factory.return_value = MagicMock()
            mock_app_config.return_value.get_model_config.return_value = None

            from app.gateway.services import start_run

            # Should not raise despite the upsert failure
            result = await start_run(body, "thread-1", request)
        assert result == record


# ---------------------------------------------------------------------------
# Lines 385-404: sse_consumer function
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Lines 75, 100, 104-105, 112, 183-185, 216-229, 248-251:
# Additional coverage from functions tested in test_gateway_services.py
# but not reachable when running test files separately.
# ---------------------------------------------------------------------------


class TestNormalizeStreamModesAdditional:
    def test_string_input(self):
        from app.gateway.services import normalize_stream_modes

        assert normalize_stream_modes("messages-tuple") == ["messages-tuple"]


class TestNormalizeInputAdditional:
    def test_passthrough_without_messages(self):
        from app.gateway.services import normalize_input

        result = normalize_input({"custom_key": "value"})
        assert result == {"custom_key": "value"}

    def test_rejects_malformed_message(self):
        import pytest
        from fastapi import HTTPException

        from app.gateway.services import normalize_input

        with pytest.raises(HTTPException) as excinfo:
            normalize_input({"messages": [{"role": "user", "content": "ok"}, {"oops": "no role here"}]})
        assert excinfo.value.status_code == 400
        assert "input.messages[1]" in excinfo.value.detail


class TestResolveAgentFactoryAdditional:
    def test_returns_make_lead_agent(self):
        from app.gateway.services import resolve_agent_factory
        from ideer.agents.lead_agent.agent import make_lead_agent

        assert resolve_agent_factory(None) is make_lead_agent
        assert resolve_agent_factory("lead_agent") is make_lead_agent
        assert resolve_agent_factory("finalis") is make_lead_agent


class TestBuildRunConfigContextAdditional:
    def test_with_context_preferred(self):
        from app.gateway.services import build_run_config

        config = build_run_config(
            "thread-1",
            {"context": {"user_id": "u-42", "thread_id": "thread-1"}},
            None,
        )
        assert "context" in config
        assert config["context"]["user_id"] == "u-42"
        assert "configurable" not in config

    def test_context_plus_configurable_warns(self, caplog):
        import logging

        from app.gateway.services import build_run_config

        with caplog.at_level(logging.WARNING, logger="app.gateway.services"):
            config = build_run_config(
                "thread-1",
                {"context": {"user_id": "u-42"}, "configurable": {"model_name": "gpt-4"}},
                None,
            )
        assert "context" in config
        assert any("both 'context' and 'configurable'" in r.message for r in caplog.records)

    def test_null_context_becomes_empty(self):
        from app.gateway.services import build_run_config

        config = build_run_config("thread-1", {"context": None}, None)
        assert config["context"] == {}

    def test_rejects_non_mapping_context(self):
        import pytest

        from app.gateway.services import build_run_config

        with pytest.raises(ValueError, match="context"):
            build_run_config("thread-1", {"context": "bad-context"}, None)

    def test_context_custom_agent_injects_agent_name(self):
        from app.gateway.services import build_run_config

        config = build_run_config(
            "thread-1",
            {"context": {"model_name": "deepseek-v3"}},
            None,
            assistant_id="finalis",
        )
        assert config["context"]["agent_name"] == "finalis"
        assert "configurable" not in config

    def test_null_context_custom_agent(self):
        from app.gateway.services import build_run_config

        config = build_run_config("thread-1", {"context": None}, None, assistant_id="finalis")
        assert config["context"] == {"agent_name": "finalis"}


class TestSSEConsumer:
    """Test the sse_consumer async generator."""

    @pytest.mark.asyncio
    async def test_sse_consumer_yields_heartbeat(self):
        from app.gateway.services import HEARTBEAT_SENTINEL, sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-hb"
        record.status = MagicMock()
        record.on_disconnect = MagicMock()

        request = MagicMock()
        request.headers = {}
        request.is_disconnected = AsyncMock(return_value=False)

        run_mgr = MagicMock()

        async def mock_subscribe(*args, **kwargs):
            yield HEARTBEAT_SENTINEL

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        assert len(frames) == 1
        assert frames[0] == ": heartbeat\n\n"

    @pytest.mark.asyncio
    async def test_sse_consumer_yields_end(self):
        from app.gateway.services import END_SENTINEL, sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-end"
        record.status = MagicMock()
        record.on_disconnect = MagicMock()

        request = MagicMock()
        request.headers = {}
        request.is_disconnected = AsyncMock(return_value=False)

        run_mgr = MagicMock()

        end_entry = MagicMock()
        end_entry.id = "evt-end-1"

        async def mock_subscribe(*args, **kwargs):
            yield END_SENTINEL

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        assert len(frames) == 1
        assert "event: end" in frames[0]

    @pytest.mark.asyncio
    async def test_sse_consumer_yields_data_frame(self):
        from app.gateway.services import sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-data"
        record.status = MagicMock()
        record.on_disconnect = MagicMock()

        request = MagicMock()
        request.headers = {}
        request.is_disconnected = AsyncMock(return_value=False)

        run_mgr = MagicMock()

        entry = MagicMock()
        entry.event = "values"
        entry.data = {"messages": [{"content": "hello"}]}
        entry.id = "evt-1"

        end_sentinel = MagicMock()
        end_sentinel.id = "evt-end"

        async def mock_subscribe(*args, **kwargs):
            yield entry

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        assert len(frames) == 1
        assert "event: values" in frames[0]
        assert "hello" in frames[0]

    @pytest.mark.asyncio
    async def test_sse_consumer_breaks_on_disconnect(self):
        from app.gateway.services import sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-dc"
        record.status = MagicMock()
        record.on_disconnect = MagicMock()

        request = MagicMock()
        request.headers = {}

        call_count = 0

        async def mock_is_disconnected():
            nonlocal call_count
            call_count += 1
            return True  # immediately disconnected

        request.is_disconnected = mock_is_disconnected

        run_mgr = MagicMock()

        entry = MagicMock()
        entry.event = "values"
        entry.data = {"x": 1}
        entry.id = "evt-1"

        async def mock_subscribe(*args, **kwargs):
            yield entry

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        # No frames should be yielded since is_disconnected returns True
        assert frames == []

    @pytest.mark.asyncio
    async def test_sse_consumer_cancel_on_disconnect(self):
        """Cover the finally block: cancel run when disconnected + running."""
        from app.gateway.services import DisconnectMode, RunStatus, sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-cancel"
        record.status = RunStatus.running
        record.on_disconnect = DisconnectMode.cancel

        request = MagicMock()
        request.headers = {"Last-Event-ID": "last-evt"}
        request.is_disconnected = AsyncMock(return_value=True)

        run_mgr = MagicMock()
        run_mgr.cancel = AsyncMock()

        async def mock_subscribe(*args, **kwargs):
            # yield nothing - disconnected immediately
            return
            yield  # make it an async generator

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        run_mgr.cancel.assert_called_once_with("run-cancel")

    @pytest.mark.asyncio
    async def test_sse_consumer_no_cancel_when_continue_mode(self):
        """Don't cancel when on_disconnect is continue."""
        from app.gateway.services import DisconnectMode, RunStatus, sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-continue"
        record.status = RunStatus.running
        record.on_disconnect = DisconnectMode.continue_

        request = MagicMock()
        request.headers = {}
        request.is_disconnected = AsyncMock(return_value=True)

        run_mgr = MagicMock()
        run_mgr.cancel = AsyncMock()

        async def mock_subscribe(*args, **kwargs):
            return
            yield

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        run_mgr.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_sse_consumer_no_cancel_when_run_completed(self):
        """Don't cancel when the run has already completed."""
        from app.gateway.services import DisconnectMode, RunStatus, sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-done"
        record.status = RunStatus.success
        record.on_disconnect = DisconnectMode.cancel

        request = MagicMock()
        request.headers = {}
        request.is_disconnected = AsyncMock(return_value=True)

        run_mgr = MagicMock()
        run_mgr.cancel = AsyncMock()

        async def mock_subscribe(*args, **kwargs):
            return
            yield

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        run_mgr.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_sse_consumer_with_last_event_id(self):
        """Cover the Last-Event-ID header being passed to subscribe."""
        from app.gateway.services import sse_consumer

        bridge = MagicMock()
        record = MagicMock()
        record.run_id = "run-replay"
        record.status = MagicMock()
        record.on_disconnect = MagicMock()

        request = MagicMock()
        request.headers = {"Last-Event-ID": "evt-42"}
        request.is_disconnected = AsyncMock(return_value=False)

        run_mgr = MagicMock()

        subscribe_calls = []

        async def mock_subscribe(*args, **kwargs):
            subscribe_calls.append(kwargs)
            return
            yield

        bridge.subscribe = mock_subscribe

        frames = []
        async for frame in sse_consumer(bridge, record, request, run_mgr):
            frames.append(frame)

        assert subscribe_calls[0]["last_event_id"] == "evt-42"
