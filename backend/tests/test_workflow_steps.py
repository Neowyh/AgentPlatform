"""Tests for workflow step executors.

Covers:
- parallel_step: concurrent execution, error handling, empty steps
- loop_step: iteration, template rendering, sub-step failure
- condition_step: expression evaluation, template rendering
- tool_step: parameter rendering, tool lookup, error handling
- human_step: pause/resume, timeout (via mock)
- execute_step dispatch routing
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.workflows.schema import StepType
from packages.harness.ideer.workflows.state import RunStatus, WorkflowState
from packages.harness.ideer.workflows.steps import execute_step

# ── Helpers ──────────────────────────────────────────────────────────


def _make_state(**inputs) -> WorkflowState:
    return WorkflowState(
        workflow_name="test-wf",
        run_id="test-run-001",
        inputs=inputs,
    )


# ── execute_step dispatch ────────────────────────────────────────────


class TestExecuteStepDispatch:
    """Tests for execute_step routing to the correct executor."""

    @pytest.mark.asyncio
    async def test_dispatch_agent(self):
        state = _make_state()
        with patch(
            "packages.harness.ideer.workflows.steps.agent_step.execute_agent_step",
            new_callable=AsyncMock,
            return_value="agent_result",
        ):
            result = await execute_step(StepType.AGENT, {"id": "a1", "agent": "researcher"}, state)
        assert result == "agent_result"

    @pytest.mark.asyncio
    async def test_dispatch_tool(self):
        state = _make_state()
        with patch(
            "packages.harness.ideer.workflows.steps.tool_step.execute_tool_step",
            new_callable=AsyncMock,
            return_value="tool_result",
        ):
            result = await execute_step(StepType.TOOL, {"id": "t1", "tool": "search"}, state)
        assert result == "tool_result"

    @pytest.mark.asyncio
    async def test_dispatch_condition(self):
        state = _make_state()
        with patch(
            "packages.harness.ideer.workflows.steps.condition_step.execute_condition_step",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await execute_step(StepType.CONDITION, {"id": "c1", "expression": "true"}, state)
        assert result is True

    @pytest.mark.asyncio
    async def test_dispatch_parallel(self):
        state = _make_state()
        with patch(
            "packages.harness.ideer.workflows.steps.parallel_step.execute_parallel_step",
            new_callable=AsyncMock,
            return_value={"p1": "ok"},
        ):
            result = await execute_step(StepType.PARALLEL, {"id": "p1", "steps": []}, state)
        assert result == {"p1": "ok"}

    @pytest.mark.asyncio
    async def test_dispatch_loop(self):
        state = _make_state()
        with patch(
            "packages.harness.ideer.workflows.steps.loop_step.execute_loop_step",
            new_callable=AsyncMock,
            return_value=[{"s1": "ok"}],
        ):
            result = await execute_step(StepType.LOOP, {"id": "l1", "items": "[]", "steps": []}, state)
        assert result == [{"s1": "ok"}]

    @pytest.mark.asyncio
    async def test_dispatch_retry(self):
        state = _make_state()
        with patch(
            "packages.harness.ideer.workflows.steps.retry_step.execute_retry_step",
            new_callable=AsyncMock,
            return_value="retry_ok",
        ):
            result = await execute_step(
                StepType.RETRY,
                {"id": "r1", "steps": [{"id": "s1", "type": "tool", "tool": "t1"}]},
                state,
            )
        assert result == "retry_ok"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_type_raises(self):
        state = _make_state()
        with pytest.raises(ValueError, match="Unknown step type"):
            await execute_step("unknown_type", {"id": "x"}, state)


# ── parallel_step ────────────────────────────────────────────────────


class TestParallelStep:
    """Tests for execute_parallel_step."""

    @pytest.mark.asyncio
    async def test_empty_steps_returns_empty_dict(self):
        from packages.harness.ideer.workflows.steps.parallel_step import execute_parallel_step

        state = _make_state()
        result = await execute_parallel_step({"id": "p1", "steps": []}, state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_missing_steps_returns_empty_dict(self):
        from packages.harness.ideer.workflows.steps.parallel_step import execute_parallel_step

        state = _make_state()
        result = await execute_parallel_step({"id": "p1"}, state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_runs_sub_steps_concurrently(self):
        from packages.harness.ideer.workflows.steps.parallel_step import execute_parallel_step

        state = _make_state()
        sub_steps = [
            {"id": "s1", "type": "tool", "tool": "t1"},
            {"id": "s2", "type": "tool", "tool": "t2"},
            {"id": "s3", "type": "tool", "tool": "t3"},
        ]

        async def fake_execute(step_type, step_def_dict, st):
            return f"{step_def_dict['id']}_result"

        # Patch the execute_step at the steps.__init__ module level,
        # which is what `from . import execute_step` resolves to at runtime
        with patch("packages.harness.ideer.workflows.steps.execute_step", side_effect=fake_execute):
            result = await execute_parallel_step({"id": "p1", "steps": sub_steps}, state)

        assert result == {"s1": "s1_result", "s2": "s2_result", "s3": "s3_result"}
        # P2-WF-01: Parallel sub-step IDs are now namespaced with parent prefix
        assert state.steps["p1.s1"].status == "completed"
        assert state.steps["p1.s2"].status == "completed"
        assert state.steps["p1.s3"].status == "completed"

    @pytest.mark.asyncio
    async def test_sub_step_failure_returns_none_for_that_step(self):
        from packages.harness.ideer.workflows.steps.parallel_step import execute_parallel_step

        state = _make_state()
        sub_steps = [
            {"id": "s1", "type": "tool", "tool": "t1"},
            {"id": "s2", "type": "tool", "tool": "t2"},
        ]

        async def fake_execute(step_type, step_def_dict, st):
            if step_def_dict["id"] == "s2":
                raise ValueError("s2 failed")
            return "ok"

        with patch("packages.harness.ideer.workflows.steps.execute_step", side_effect=fake_execute):
            result = await execute_parallel_step({"id": "p1", "steps": sub_steps}, state)

        assert result["s1"] == "ok"
        # BUG-13: Error results now use sentinel key to distinguish from normal output
        assert result["s2"]["__parallel_sub_step_error__"] is True
        assert result["s2"]["error"] == "s2 failed"
        assert result["s2"]["sub_step_id"] == "s2"
        # P2-WF-01: Parallel sub-step IDs are now namespaced with parent prefix
        assert state.steps["p1.s2"].status == "failed"


# ── loop_step ────────────────────────────────────────────────────────


class TestLoopStep:
    """Tests for execute_loop_step."""

    @pytest.mark.asyncio
    async def test_iterates_over_items(self):
        from packages.harness.ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(items=["a", "b", "c"])
        sub_steps = [{"id": "process", "type": "tool", "tool": "t1"}]

        async def fake_execute(step_type, step_def_dict, st):
            return f"processed_{st.loop_vars.get('item', '?')}"

        with patch("packages.harness.ideer.workflows.steps.execute_step", side_effect=fake_execute):
            result = await execute_loop_step(
                {"id": "l1", "items": "{{inputs.items}}", "steps": sub_steps},
                state,
            )

        assert len(result) == 3
        assert result[0]["process"] == "processed_a"
        assert result[1]["process"] == "processed_b"
        assert result[2]["process"] == "processed_c"

    @pytest.mark.asyncio
    async def test_cleans_up_loop_context(self):
        from packages.harness.ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(items=[1])
        sub_steps = [{"id": "s1", "type": "tool", "tool": "t1"}]

        async def fake_execute(step_type, step_def_dict, st):
            return "ok"

        with patch("packages.harness.ideer.workflows.steps.execute_step", side_effect=fake_execute):
            await execute_loop_step(
                {"id": "l1", "items": "{{inputs.items}}", "steps": sub_steps},
                state,
            )

        assert "_loop_index" not in state.inputs
        assert "_loop_item" not in state.inputs

    @pytest.mark.asyncio
    async def test_sub_step_failure_returns_none_for_item(self):
        from packages.harness.ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(items=[1, 2])
        sub_steps = [{"id": "s1", "type": "tool", "tool": "t1"}]

        call_count = 0

        async def fake_execute(step_type, step_def_dict, st):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("first item fails")
            return "ok"

        with patch("packages.harness.ideer.workflows.steps.execute_step", side_effect=fake_execute):
            result = await execute_loop_step(
                {"id": "l1", "items": "{{inputs.items}}", "steps": sub_steps},
                state,
            )

        assert result[0]["s1"] is None
        assert result[1]["s1"] == "ok"

    @pytest.mark.asyncio
    async def test_empty_items_returns_empty_list(self):
        from packages.harness.ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(items=[])
        result = await execute_loop_step(
            {"id": "l1", "items": "{{inputs.items}}", "steps": []},
            state,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_iterates_over_generator(self):
        """Items that are not a list should be converted to list."""
        from packages.harness.ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(items=iter([]))
        sub_steps = [{"id": "s1", "type": "tool", "tool": "t1"}]

        async def fake_execute(step_type, step_def_dict, st):
            return "ok"

        with patch("packages.harness.ideer.workflows.steps.execute_step", side_effect=fake_execute):
            result = await execute_loop_step(
                {"id": "l1", "items": "{{inputs.items}}", "steps": sub_steps},
                state,
            )

        # Empty items → empty result
        assert result == []


# ── condition_step ───────────────────────────────────────────────────


class TestConditionStep:
    """Tests for execute_condition_step."""

    @pytest.mark.asyncio
    async def test_evaluates_truthy_expression(self):
        from packages.harness.ideer.workflows.steps.condition_step import execute_condition_step

        state = _make_state(flag=True)
        result = await execute_condition_step(
            {"id": "c1", "expression": "{{inputs.flag}}"},
            state,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluates_falsy_expression(self):
        from packages.harness.ideer.workflows.steps.condition_step import execute_condition_step

        state = _make_state(flag=False)
        result = await execute_condition_step(
            {"id": "c1", "expression": "{{inputs.flag}}"},
            state,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_default_expression_is_true(self):
        from packages.harness.ideer.workflows.steps.condition_step import execute_condition_step

        state = _make_state()
        result = await execute_condition_step({"id": "c1"}, state)
        assert result is True

    @pytest.mark.asyncio
    async def test_none_expression_returns_false(self):
        """When expression resolves to None, bool(None) = False."""
        from packages.harness.ideer.workflows.steps.condition_step import execute_condition_step

        state = _make_state()
        result = await execute_condition_step(
            {"id": "c1", "expression": "{{inputs.missing}}"},
            state,
        )
        assert result is False


# ── tool_step ────────────────────────────────────────────────────────


class TestToolStep:
    """Tests for execute_tool_step."""

    @pytest.mark.asyncio
    async def test_invokes_tool_ainvoke(self):
        from packages.harness.ideer.workflows.steps.tool_step import execute_tool_step

        state = _make_state(query="hello")
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.ainvoke = AsyncMock(return_value="search_result")

        mock_config = MagicMock()

        with (
            patch("ideer.config.app_config.get_app_config", return_value=mock_config),
            patch("ideer.tools.tools.get_available_tools", return_value=[mock_tool]),
        ):
            result = await execute_tool_step(
                {"id": "t1", "tool": "search", "params": {"q": "{{inputs.query}}"}},
                state,
            )

        assert result == "search_result"
        mock_tool.ainvoke.assert_called_once_with({"q": "hello"})

    @pytest.mark.asyncio
    async def test_invokes_tool_sync_invoke(self):
        """When tool has no ainvoke, falls back to invoke via asyncio.to_thread."""
        from packages.harness.ideer.workflows.steps.tool_step import execute_tool_step

        state = _make_state()
        mock_tool = MagicMock()
        mock_tool.name = "search"
        # No ainvoke attribute
        del mock_tool.ainvoke
        mock_tool.invoke = MagicMock(return_value="sync_result")

        mock_config = MagicMock()

        with (
            patch("ideer.config.app_config.get_app_config", return_value=mock_config),
            patch("ideer.tools.tools.get_available_tools", return_value=[mock_tool]),
        ):
            result = await execute_tool_step(
                {"id": "t1", "tool": "search", "params": {}},
                state,
            )

        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_raises_when_tool_not_found(self):
        from packages.harness.ideer.workflows.steps.tool_step import execute_tool_step

        state = _make_state()
        mock_config = MagicMock()

        with (
            patch("ideer.config.app_config.get_app_config", return_value=mock_config),
            patch("ideer.tools.tools.get_available_tools", return_value=[]),
        ):
            with pytest.raises(ValueError, match="Tool 'nonexistent' not available"):
                await execute_tool_step(
                    {"id": "t1", "tool": "nonexistent", "params": {}},
                    state,
                )

    @pytest.mark.asyncio
    async def test_empty_params(self):
        from packages.harness.ideer.workflows.steps.tool_step import execute_tool_step

        state = _make_state()
        mock_tool = MagicMock()
        mock_tool.name = "t1"
        mock_tool.ainvoke = AsyncMock(return_value="ok")

        mock_config = MagicMock()

        with (
            patch("ideer.config.app_config.get_app_config", return_value=mock_config),
            patch("ideer.tools.tools.get_available_tools", return_value=[mock_tool]),
        ):
            result = await execute_tool_step(
                {"id": "t1", "tool": "t1"},
                state,
            )

        assert result == "ok"
        mock_tool.ainvoke.assert_called_once_with({})


# ── human_step ───────────────────────────────────────────────────────


class TestHumanStep:
    """Tests for execute_human_review_step."""

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """When no review is submitted within timeout, raises TimeoutError."""
        from packages.harness.ideer.workflows.steps.human_step import execute_human_review_step

        state = _make_state()
        mock_store = AsyncMock()
        waiting_state = _make_state(status=RunStatus.RUNNING)
        waiting_state.review_result = None
        mock_store.load_run_state = AsyncMock(return_value=waiting_state)

        import asyncio as _asyncio

        original_sleep = _asyncio.sleep
        _asyncio.sleep = AsyncMock()
        try:
            with pytest.raises(TimeoutError, match="timed out"):
                await execute_human_review_step(
                    {"id": "review1", "timeout": 4},
                    state,
                    mock_store,
                )
        finally:
            _asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_run_disappeared_raises(self):
        """When run disappears from DB during review, raises RuntimeError."""
        from packages.harness.ideer.workflows.steps.human_step import execute_human_review_step

        state = _make_state()
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=None)

        import asyncio as _asyncio

        original_sleep = _asyncio.sleep
        _asyncio.sleep = AsyncMock()
        try:
            with pytest.raises(RuntimeError, match="disappeared"):
                await execute_human_review_step(
                    {"id": "review1", "timeout": 4},
                    state,
                    mock_store,
                )
        finally:
            _asyncio.sleep = original_sleep
