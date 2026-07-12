"""Tests for MemoryMiddleware — memory queueing after agent execution."""

import asyncio
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ideer.agents.middlewares.memory_middleware import MemoryMiddleware
from ideer.config.memory_config import MemoryConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runtime(thread_id: str = "t1", run_id: str = "r1"):
    runtime = MagicMock()
    runtime.context = {"thread_id": thread_id, "run_id": run_id}
    return runtime


def _make_runtime_no_thread():
    runtime = MagicMock()
    runtime.context = {}
    return runtime


def _make_runtime_context_none():
    runtime = MagicMock()
    runtime.context = None
    return runtime


def _make_config(enabled: bool = True) -> MemoryConfig:
    return MemoryConfig(enabled=enabled, debounce_seconds=30)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestAfterAgentReturnsNone:
    """after_agent returns None in all code paths."""

    def test_returns_none_when_memory_disabled(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config(enabled=False)):
            assert mw.after_agent(state, _make_runtime()) is None

    def test_returns_none_when_no_thread_id(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        runtime = _make_runtime_no_thread()
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.get_config", return_value={"configurable": {}}):
                assert mw.after_agent(state, runtime) is None

    def test_returns_none_when_no_messages(self):
        mw = MemoryMiddleware()
        state: dict = {}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            assert mw.after_agent(state, _make_runtime()) is None

    def test_returns_none_when_empty_messages(self):
        mw = MemoryMiddleware()
        state = {"messages": []}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            assert mw.after_agent(state, _make_runtime()) is None

    def test_returns_none_when_only_user_messages(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory", return_value=[HumanMessage(content="hi")]):
                assert mw.after_agent(state, _make_runtime()) is None

    def test_returns_none_when_only_assistant_messages(self):
        mw = MemoryMiddleware()
        state = {"messages": [AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory", return_value=[AIMessage(content="hello")]):
                assert mw.after_agent(state, _make_runtime()) is None

    def test_returns_none_for_tool_messages_only(self):
        mw = MemoryMiddleware()
        state = {"messages": [ToolMessage(content="tool result", tool_call_id="tc_1")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory", return_value=[]):
                assert mw.after_agent(state, _make_runtime()) is None

    def test_returns_none_when_runtime_context_is_none(self):
        """runtime.context is None — fallback to get_config, then skip if still no thread_id."""
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        runtime = _make_runtime_context_none()
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.get_config", return_value={"configurable": {}}):
                assert mw.after_agent(state, runtime) is None


class TestAfterAgentQueues:
    """after_agent queues to memory when conditions are met."""

    def test_queues_when_user_and_assistant_present(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                        mw.after_agent(state, _make_runtime())
                        mock_queue().add.assert_called_once()

    def test_queues_with_thread_id_from_config(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        runtime = _make_runtime_no_thread()
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.get_config", return_value={"configurable": {"thread_id": "from-config"}}):
                with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                    mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                    with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                        with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                            mw.after_agent(state, runtime)
                            call_kwargs = mock_queue().add.call_args[1]
                            assert call_kwargs["thread_id"] == "from-config"

    def test_passes_agent_name(self):
        mw = MemoryMiddleware(agent_name="my_agent")
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                        mw.after_agent(state, _make_runtime())
                        call_kwargs = mock_queue().add.call_args[1]
                        assert call_kwargs["agent_name"] == "my_agent"

    def test_default_agent_name_is_none(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                        mw.after_agent(state, _make_runtime())
                        call_kwargs = mock_queue().add.call_args[1]
                        assert call_kwargs["agent_name"] is None

    def test_passes_user_id(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="user-42"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                        mw.after_agent(state, _make_runtime())
                        call_kwargs = mock_queue().add.call_args[1]
                        assert call_kwargs["user_id"] == "user-42"

    def test_passes_correction_detected(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.detect_correction", return_value=True) as mock_corr:
                    with patch("ideer.agents.middlewares.memory_middleware.detect_reinforcement") as mock_reinf:
                        with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                            with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                                mw.after_agent(state, _make_runtime())
                                # correction=True → short-circuit: detect_reinforcement NOT called
                                mock_corr.assert_called_once()
                                mock_reinf.assert_not_called()
                                call_kwargs = mock_queue().add.call_args[1]
                                assert call_kwargs["correction_detected"] is True
                                assert call_kwargs["reinforcement_detected"] is False

    def test_reinforcement_not_detected_when_correction_present(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.detect_correction", return_value=True):
                    with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                        with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                            mw.after_agent(state, _make_runtime())
                            call_kwargs = mock_queue().add.call_args[1]
                            assert call_kwargs["correction_detected"] is True
                            assert call_kwargs["reinforcement_detected"] is False

    def test_reinforcement_detected_when_no_correction(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.detect_correction", return_value=False):
                    with patch("ideer.agents.middlewares.memory_middleware.detect_reinforcement", return_value=True):
                        with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                            with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                                mw.after_agent(state, _make_runtime())
                                call_kwargs = mock_queue().add.call_args[1]
                                assert call_kwargs["correction_detected"] is False
                                assert call_kwargs["reinforcement_detected"] is True


class TestAfterAgentFiltering:
    """Messages are properly filtered before queueing."""

    def test_tool_messages_filtered_out(self):
        mw = MemoryMiddleware()
        state = {
            "messages": [
                HumanMessage(content="search"),
                AIMessage(content="", tool_calls=[{"name": "search", "id": "tc1", "args": {}}]),
                ToolMessage(content="results", tool_call_id="tc1"),
                AIMessage(content="done"),
            ]
        }
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="search"), AIMessage(content="done")]
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                        mw.after_agent(state, _make_runtime())
                        call_kwargs = mock_queue().add.call_args[1]
                        assert len(call_kwargs["messages"]) == 2
                        assert call_kwargs["messages"][0].type == "human"
                        assert call_kwargs["messages"][1].type == "ai"

    def test_filter_receives_original_messages(self):
        """filter_messages_for_memory should receive the original state messages."""
        mw = MemoryMiddleware()
        original = [HumanMessage(content="hi"), AIMessage(content="hello")]
        state = {"messages": original}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory", return_value=original) as mock_filter:
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue"):
                        mw.after_agent(state, _make_runtime())
                        mock_filter.assert_called_once_with(original)

    def test_multiple_user_and_assistant_messages_queued(self):
        """Multiple human+ai message pairs are all included in queue."""
        mw = MemoryMiddleware()
        filtered = [
            HumanMessage(content="q1"),
            AIMessage(content="a1"),
            HumanMessage(content="q2"),
            AIMessage(content="a2"),
        ]
        state = {"messages": filtered}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory", return_value=filtered):
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                        mw.after_agent(state, _make_runtime())
                        call_kwargs = mock_queue().add.call_args[1]
                        assert len(call_kwargs["messages"]) == 4


class TestAsyncAfterAgent:
    """async after_agent delegates to sync."""

    def test_async_after_agent_returns_none_when_disabled(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config(enabled=False)):
            result = asyncio.run(mw.aafter_agent(state, _make_runtime()))
            assert result is None

    def test_async_after_agent_base_returns_none(self):
        """Base class aafter_agent returns None; the agent runtime calls
        after_agent (sync) from the async loop, so queuing happens there."""
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        # Verify aafter_agent returns None (base class behavior)
        result = asyncio.run(mw.aafter_agent(state, _make_runtime()))
        assert result is None

    def test_async_path_then_sync_queuing(self):
        """Simulate: async loop calls aafter_agent, then sync after_agent."""
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory") as mock_filter:
                mock_filter.return_value = [HumanMessage(content="hi"), AIMessage(content="hello")]
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                        asyncio.run(mw.aafter_agent(state, _make_runtime()))
                        mw.after_agent(state, _make_runtime())
                        mock_queue().add.assert_called_once()


class TestMemoryConfig:
    """Middleware respects MemoryConfig."""

    def test_uses_explicit_config_when_provided(self):
        explicit = MemoryConfig(enabled=False)
        mw = MemoryMiddleware(memory_config=explicit)
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        # Should not call get_memory_config at all since explicit config is provided
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config") as mock_global:
            assert mw.after_agent(state, _make_runtime()) is None
            mock_global.assert_not_called()

    def test_uses_global_config_when_not_provided(self):
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config(enabled=False)):
            assert mw.after_agent(state, _make_runtime()) is None

    def test_explicit_enabled_config_queues(self):
        """Explicit enabled config should queue successfully."""
        explicit = MemoryConfig(enabled=True, debounce_seconds=30)
        mw = MemoryMiddleware(memory_config=explicit)
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory", return_value=[HumanMessage(content="hi"), AIMessage(content="hello")]):
            with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="u1"):
                with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue") as mock_queue:
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_config") as mock_global:
                        mw.after_agent(state, _make_runtime())
                        mock_queue().add.assert_called_once()
                        mock_global.assert_not_called()

    def test_get_effective_user_id_called(self):
        """get_effective_user_id is called during enqueue."""
        mw = MemoryMiddleware()
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello")]}
        with patch("ideer.agents.middlewares.memory_middleware.get_memory_config", return_value=_make_config()):
            with patch("ideer.agents.middlewares.memory_middleware.filter_messages_for_memory", return_value=[HumanMessage(content="hi"), AIMessage(content="hello")]):
                with patch("ideer.agents.middlewares.memory_middleware.get_effective_user_id", return_value="uid-99") as mock_uid:
                    with patch("ideer.agents.middlewares.memory_middleware.get_memory_queue"):
                        mw.after_agent(state, _make_runtime())
                        mock_uid.assert_called_once()
