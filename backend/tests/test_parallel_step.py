"""Tests for ideer.workflows.steps.parallel_step — parallel step executor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ideer.workflows.state import WorkflowState


def _make_state(**kwargs) -> WorkflowState:
    return WorkflowState(workflow_name="test", run_id="run-1", **kwargs)


# ---------------------------------------------------------------------------
# execute_parallel_step
# ---------------------------------------------------------------------------


class TestExecuteParallelStep:
    @pytest.mark.asyncio
    async def test_empty_sub_steps(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {"id": "p1", "type": "parallel", "steps": []}
        result = await execute_parallel_step(step_def, _make_state())
        assert result == {}

    @pytest.mark.asyncio
    async def test_no_steps_key(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {"id": "p1", "type": "parallel"}
        result = await execute_parallel_step(step_def, _make_state())
        assert result == {}

    @pytest.mark.asyncio
    async def test_single_sub_step_success(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {
            "id": "p1",
            "type": "parallel",
            "steps": [{"id": "a1", "type": "tool"}],
        }

        with patch("ideer.workflows.steps.execute_step", new_callable=AsyncMock, return_value="result_a"):
            result = await execute_parallel_step(step_def, _make_state())
            assert result == {"a1": "result_a"}

    @pytest.mark.asyncio
    async def test_multiple_sub_steps(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {
            "id": "p1",
            "type": "parallel",
            "steps": [
                {"id": "a", "type": "tool"},
                {"id": "b", "type": "tool"},
                {"id": "c", "type": "tool"},
            ],
        }

        async def _execute_step(step_type, sub_def, state):
            return f"result_{sub_def['id']}"

        with patch("ideer.workflows.steps.execute_step", side_effect=_execute_step):
            result = await execute_parallel_step(step_def, _make_state())
            assert set(result.keys()) == {"a", "b", "c"}
            assert result["a"] == "result_a"

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        from ideer.workflows.steps.parallel_step import _ERROR_SENTINEL, execute_parallel_step

        step_def = {
            "id": "p1",
            "type": "parallel",
            "steps": [
                {"id": "ok", "type": "tool"},
                {"id": "fail", "type": "tool"},
            ],
        }

        async def _execute_step(step_type, sub_def, state):
            if sub_def["id"] == "fail":
                raise RuntimeError("boom")
            return "good"

        with patch("ideer.workflows.steps.execute_step", side_effect=_execute_step):
            result = await execute_parallel_step(step_def, _make_state())
            assert result["ok"] == "good"
            assert result["fail"][_ERROR_SENTINEL] is True
            assert "boom" in result["fail"]["error"]

    @pytest.mark.asyncio
    async def test_all_failed_raises(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {
            "id": "p1",
            "type": "parallel",
            "steps": [
                {"id": "a", "type": "tool"},
                {"id": "b", "type": "tool"},
            ],
        }

        async def _execute_step(step_type, sub_def, state):
            raise RuntimeError(f"fail_{sub_def['id']}")

        with patch("ideer.workflows.steps.execute_step", side_effect=_execute_step):
            with pytest.raises(RuntimeError, match="All parallel sub-steps failed"):
                await execute_parallel_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_timeout(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {
            "id": "p1",
            "type": "parallel",
            "timeout": 0.01,
            "steps": [{"id": "slow", "type": "tool"}],
        }

        async def _slow_step(step_type, sub_def, state):
            await asyncio.sleep(100)
            return "done"

        with patch("ideer.workflows.steps.execute_step", side_effect=_slow_step):
            with pytest.raises(TimeoutError, match="timed out"):
                await execute_parallel_step(step_def, _make_state())

    @pytest.mark.asyncio
    async def test_invalid_timeout_ignored(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {
            "id": "p1",
            "type": "parallel",
            "timeout": "not_a_number",
            "steps": [{"id": "a", "type": "tool"}],
        }

        with patch("ideer.workflows.steps.execute_step", new_callable=AsyncMock, return_value="ok"):
            result = await execute_parallel_step(step_def, _make_state())
            assert result == {"a": "ok"}

    @pytest.mark.asyncio
    async def test_negative_timeout_ignored(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        step_def = {
            "id": "p1",
            "type": "parallel",
            "timeout": -5,
            "steps": [{"id": "a", "type": "tool"}],
        }

        with patch("ideer.workflows.steps.execute_step", new_callable=AsyncMock, return_value="ok"):
            result = await execute_parallel_step(step_def, _make_state())
            assert result == {"a": "ok"}

    @pytest.mark.asyncio
    async def test_step_results_set_on_state(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        state = _make_state()
        step_def = {
            "id": "p1",
            "type": "parallel",
            "steps": [{"id": "a", "type": "tool"}],
        }

        with patch("ideer.workflows.steps.execute_step", new_callable=AsyncMock, return_value="out"):
            await execute_parallel_step(step_def, state)
            assert "p1.a" in state.steps
            assert state.steps["p1.a"].status == "completed"
            assert state.steps["p1.a"].output == "out"

    @pytest.mark.asyncio
    async def test_failed_step_result_set_on_state(self):
        from ideer.workflows.steps.parallel_step import execute_parallel_step

        state = _make_state()
        step_def = {
            "id": "p1",
            "type": "parallel",
            "steps": [
                {"id": "ok", "type": "tool"},
                {"id": "bad", "type": "tool"},
            ],
        }

        async def _exec(step_type, sub_def, st):
            if sub_def["id"] == "bad":
                raise ValueError("oops")
            return "fine"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            await execute_parallel_step(step_def, state)
            assert state.steps["p1.bad"].status == "failed"
            assert "oops" in state.steps["p1.bad"].error
