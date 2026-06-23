"""Tests for ideer.workflows.steps.tool_step — tool step executor."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.workflows.state import WorkflowState


def _make_state(**kwargs) -> WorkflowState:
    return WorkflowState(workflow_name="test", run_id="run-1", **kwargs)


def _make_tool(name: str, result: str = "ok"):
    tool = SimpleNamespace(name=name)
    tool.ainvoke = AsyncMock(return_value=result)
    tool.invoke = MagicMock(return_value=result)
    return tool


# ---------------------------------------------------------------------------
# execute_tool_step
# ---------------------------------------------------------------------------


class TestExecuteToolStep:
    @pytest.mark.asyncio
    async def test_success_with_ainvoke(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = _make_tool("search", result="found it")
        step_def = {"id": "t1", "tool": "search", "params": {"query": "hello"}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
        ):
            result = await execute_tool_step(step_def, _make_state())
            assert result == "found it"
            tool.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        step_def = {"id": "t1", "tool": "nonexistent", "params": {}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
        ):
            with pytest.raises(ValueError, match="Tool 'nonexistent' not available"):
                await execute_tool_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_default_timeout(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = _make_tool("t")
        step_def = {"id": "t1", "tool": "t", "params": {}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
            patch("asyncio.wait_for", new_callable=AsyncMock, return_value="result") as mock_wait,
        ):
            await execute_tool_step(step_def, _make_state())
            _, kwargs = mock_wait.call_args
            assert kwargs.get("timeout") == 300.0

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = _make_tool("t")
        step_def = {"id": "t1", "tool": "t", "params": {}, "timeout": 60}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
            patch("asyncio.wait_for", new_callable=AsyncMock, return_value="result") as mock_wait,
        ):
            await execute_tool_step(step_def, _make_state())
            _, kwargs = mock_wait.call_args
            assert kwargs.get("timeout") == 60.0

    @pytest.mark.asyncio
    async def test_invalid_timeout_string(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        step_def = {"id": "t1", "tool": "t", "params": {}, "timeout": "abc"}
        with pytest.raises(ValueError, match="Invalid timeout"):
            await execute_tool_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_negative_timeout(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        step_def = {"id": "t1", "tool": "t", "params": {}, "timeout": -5}
        with pytest.raises(ValueError, match="Invalid timeout|timeout must be positive"):
            await execute_tool_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_zero_timeout(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        step_def = {"id": "t1", "tool": "t", "params": {}, "timeout": 0}
        with pytest.raises(ValueError, match="Invalid timeout|timeout must be positive"):
            await execute_tool_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = SimpleNamespace(name="t")
        tool.ainvoke = AsyncMock(side_effect=TimeoutError())
        step_def = {"id": "t1", "tool": "t", "params": {}, "timeout": 1}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
        ):
            with pytest.raises(TimeoutError, match="timed out"):
                await execute_tool_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_type_error_param_format_retry(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = SimpleNamespace(name="t")
        tool.ainvoke = AsyncMock(side_effect=[TypeError("unexpected argument 'query'"), "retried_ok"])

        step_def = {"id": "t1", "tool": "t", "params": {"query": "test"}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
        ):
            result = await execute_tool_step(step_def, _make_state())
            assert result == "retried_ok"
            assert tool.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_type_error_non_param_reraised(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = SimpleNamespace(name="t")
        tool.ainvoke = AsyncMock(side_effect=TypeError("some other error"))

        step_def = {"id": "t1", "tool": "t", "params": {"query": "test"}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
        ):
            with pytest.raises(TypeError, match="some other error"):
                await execute_tool_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_type_error_on_retry_gives_up(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = SimpleNamespace(name="t")
        tool.ainvoke = AsyncMock(
            side_effect=[
                TypeError("unexpected argument 'x'"),
                TypeError("still broken"),
            ]
        )

        step_def = {"id": "t1", "tool": "t", "params": {"x": 1}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
        ):
            with pytest.raises(TypeError, match="still broken"):
                await execute_tool_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_template_rendered_params(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = _make_tool("t")
        step_def = {"id": "t1", "tool": "t", "params": {"q": "{{inputs.query}}"}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool]),
        ):
            state = _make_state(inputs={"query": "deep learning"})
            await execute_tool_step(step_def, state)
            call_args = tool.ainvoke.call_args[0][0]
            assert call_args["q"] == "deep learning"

    @pytest.mark.asyncio
    async def test_tool_without_ainvoke_falls_back_to_invoke(self):
        from ideer.workflows.steps.tool_step import execute_tool_step

        tool = SimpleNamespace(name="sync_tool")
        tool.invoke = MagicMock(return_value="sync_result")
        # Remove ainvoke
        tool_dict = {"name": "sync_tool", "invoke": MagicMock(return_value="sync_result")}
        tool_no_ainvoke = SimpleNamespace(**tool_dict)

        step_def = {"id": "t1", "tool": "sync_tool", "params": {}}

        with (
            patch("ideer.config.app_config.get_app_config", return_value=SimpleNamespace()),
            patch("ideer.tools.tools.get_available_tools", return_value=[tool_no_ainvoke]),
        ):
            result = await execute_tool_step(step_def, _make_state())
            assert result == "sync_result"
