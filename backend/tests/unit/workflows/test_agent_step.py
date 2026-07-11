"""Tests for ideer.workflows.steps.agent_step — agent step executor."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ideer.workflows.state import WorkflowState


def _make_state(**kwargs) -> WorkflowState:
    return WorkflowState(workflow_name="test", run_id="run-1", **kwargs)


def _mock_result(status="completed", result="ok", error=None):
    return SimpleNamespace(status=status, result=result, error=error)


def _run_agent_step(step_def, state, result=None, agent_config=None, soul=""):
    """Helper that patches all local imports inside execute_agent_step."""
    if result is None:
        result = _mock_result()
    if agent_config is None:
        agent_config = SimpleNamespace(tool_groups=[], skills=[], model="default")

    mock_executor_instance = AsyncMock()
    mock_executor_instance._aexecute = AsyncMock(return_value=result)

    with (
        patch("ideer.config.agents_config.load_agent_config", return_value=agent_config),
        patch("ideer.config.agents_config.load_agent_soul", return_value=soul),
        patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
        patch("ideer.tools.tools.get_available_tools", return_value=[]),
        patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor_instance),
        patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
    ):
        import asyncio

        from ideer.workflows.steps.agent_step import execute_agent_step

        return asyncio.run_coroutine_threadsafe(
            execute_agent_step(step_def, state),
            asyncio.new_event_loop(),
        ).result(timeout=5)


# ---------------------------------------------------------------------------
# execute_agent_step
# ---------------------------------------------------------------------------


class TestExecuteAgentStep:
    @pytest.mark.asyncio
    async def test_success(self):
        step_def = {"id": "s1", "agent": "researcher", "prompt": "Do research"}
        mock_result = _mock_result("completed", "Research done")
        agent_config = SimpleNamespace(tool_groups=["search"], skills=["web"], model="gpt-4")

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=agent_config),
            patch("ideer.config.agents_config.load_agent_soul", return_value="You are a researcher."),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            result = await execute_agent_step(step_def, _make_state())
            assert result == "Research done"

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        step_def = {"id": "s1", "agent": "nonexistent", "prompt": "test"}

        with patch("ideer.config.agents_config.load_agent_config", side_effect=FileNotFoundError("not found")):
            from ideer.workflows.steps.agent_step import execute_agent_step

            with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
                await execute_agent_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_agent_failed_with_error(self):
        step_def = {"id": "s1", "agent": "failing", "prompt": "test"}
        mock_result = _mock_result("failed", None, "OOM killed")

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=[], skills=[], model=None)),
            patch("ideer.config.agents_config.load_agent_soul", return_value=""),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            with pytest.raises(RuntimeError, match="failed: OOM killed"):
                await execute_agent_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_agent_unexpected_status(self):
        step_def = {"id": "s1", "agent": "weird", "prompt": "test"}
        mock_result = _mock_result("timeout", None, None)

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=[], skills=[], model=None)),
            patch("ideer.config.agents_config.load_agent_soul", return_value=""),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            with pytest.raises(RuntimeError, match="unexpected status"):
                await execute_agent_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_agent_completed_with_none_result(self):
        step_def = {"id": "s1", "agent": "empty", "prompt": "test"}
        mock_result = _mock_result("completed", None, None)

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=[], skills=[], model=None)),
            patch("ideer.config.agents_config.load_agent_soul", return_value=""),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            result = await execute_agent_step(step_def, _make_state())
            assert result == ""

    @pytest.mark.asyncio
    async def test_template_rendering(self):
        step_def = {"id": "s1", "agent": "r", "prompt": "{{inputs.topic}}"}
        mock_result = _mock_result("completed", "ok", None)

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=[], skills=[], model=None)),
            patch("ideer.config.agents_config.load_agent_soul", return_value=""),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            state = _make_state(inputs={"topic": "AI safety"})
            result = await execute_agent_step(step_def, state)
            assert result == "ok"
            call_args = mock_executor._aexecute.call_args
            assert call_args[0][0] == "AI safety"

    @pytest.mark.asyncio
    async def test_model_inherits_when_none(self):
        """When agent_config.model is None, SubagentConfig should get 'inherit'."""
        step_def = {"id": "s1", "agent": "r", "prompt": "test"}
        mock_result = _mock_result("completed", "done", None)

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=["t"], skills=["s"], model=None)),
            patch("ideer.config.agents_config.load_agent_soul", return_value="soul"),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            result = await execute_agent_step(step_def, _make_state())
            assert result == "done"

    @pytest.mark.asyncio
    async def test_no_prompt_key_defaults_to_empty_string(self):
        """When step_def has no 'prompt' key, empty string is used."""
        step_def = {"id": "s1", "agent": "writer"}
        mock_result = _mock_result("completed", "output", None)

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=[], skills=[], model="test-model")),
            patch("ideer.config.agents_config.load_agent_soul", return_value="soul"),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            result = await execute_agent_step(step_def, _make_state())
            assert result == "output"
            call_args = mock_executor._aexecute.call_args
            assert call_args[0][0] == ""

    @pytest.mark.asyncio
    async def test_completed_with_non_string_result(self):
        """Non-string result is returned as-is when result is not None."""
        step_def = {"id": "s1", "agent": "r", "prompt": "test"}
        mock_result = _mock_result("completed", 42, None)

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=[], skills=[], model=None)),
            patch("ideer.config.agents_config.load_agent_soul", return_value=""),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            result = await execute_agent_step(step_def, _make_state())
            # The code returns result.result directly when not None
            assert result == 42

    @pytest.mark.asyncio
    async def test_failed_with_no_error_message(self):
        """When error is None but status is not completed, generic message used."""
        step_def = {"id": "s1", "agent": "r", "prompt": "test"}
        mock_result = _mock_result("cancelled", None, None)

        mock_executor = AsyncMock()
        mock_executor._aexecute = AsyncMock(return_value=mock_result)

        with (
            patch("ideer.config.agents_config.load_agent_config", return_value=SimpleNamespace(tool_groups=[], skills=[], model=None)),
            patch("ideer.config.agents_config.load_agent_soul", return_value=""),
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
            patch("ideer.subagents.executor.SubagentExecutor", return_value=mock_executor),
            patch("ideer.subagents.executor.SubagentStatus", SimpleNamespace(COMPLETED="completed")),
        ):
            from ideer.workflows.steps.agent_step import execute_agent_step

            with pytest.raises(RuntimeError, match="unexpected status"):
                await execute_agent_step(step_def, _make_state())
