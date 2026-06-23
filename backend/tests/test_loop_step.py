"""Tests for ideer.workflows.steps.loop_step — loop step executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ideer.workflows.state import WorkflowState


def _make_state(**kwargs) -> WorkflowState:
    return WorkflowState(workflow_name="test", run_id="run-1", **kwargs)


# ---------------------------------------------------------------------------
# execute_loop_step
# ---------------------------------------------------------------------------


class TestExecuteLoopStep:
    @pytest.mark.asyncio
    async def test_basic_iteration(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": [1, 2, 3]})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "steps": [{"id": "process", "type": "tool"}],
        }

        call_count = 0

        async def _exec(step_type, sub_def, st):
            nonlocal call_count
            call_count += 1
            return f"processed_{st.loop_vars.get('item')}"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert len(results) == 3
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_empty_items(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": []})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        with patch("ideer.workflows.steps.execute_step", new_callable=AsyncMock) as mock_exec:
            results = await execute_loop_step(step_def, state)
            assert results == []
            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_items_skips(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.nonexistent}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        results = await execute_loop_step(step_def, state)
        assert results == []

    @pytest.mark.asyncio
    async def test_scalar_items_wrapped(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"val": "hello"})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.val}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        async def _exec(step_type, sub_def, st):
            return st.loop_vars["item"]

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_string_not_decomposed(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"name": "alice"})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.name}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        async def _exec(step_type, sub_def, st):
            return st.loop_vars["item"]

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert len(results) == 1
            assert results[0]["s"] == "alice"

    @pytest.mark.asyncio
    async def test_max_iterations_truncation(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": list(range(100))})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "max_iterations": 3,
            "steps": [{"id": "s", "type": "tool"}],
        }

        call_count = 0

        async def _exec(step_type, sub_def, st):
            nonlocal call_count
            call_count += 1
            return "ok"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert len(results) == 3
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_sub_step_failure_continues(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": [1, 2, 3]})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        async def _exec(step_type, sub_def, st):
            if st.loop_vars["item"] == 2:
                raise ValueError("bad item")
            return "ok"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert len(results) == 3
            assert results[0]["s"] == "ok"
            assert results[1]["s"] is None  # failed
            assert results[2]["s"] == "ok"

    @pytest.mark.asyncio
    async def test_fail_fast_stops_on_first_failure(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": [1, 2, 3]})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "fail_fast": True,
            "steps": [{"id": "s", "type": "tool"}],
        }

        async def _exec(step_type, sub_def, st):
            if st.loop_vars["item"] == 2:
                raise ValueError("bad item")
            return "ok"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            with pytest.raises(RuntimeError, match="fail_fast"):
                await execute_loop_step(step_def, state)

    @pytest.mark.asyncio
    async def test_loop_vars_restored_after_completion(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": [1, 2]})
        state.loop_vars["outer_var"] = "preserved"
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        async def _exec(step_type, sub_def, st):
            return "ok"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            await execute_loop_step(step_def, state)
            assert state.loop_vars.get("outer_var") == "preserved"
            assert "index" not in state.loop_vars
            assert "item" not in state.loop_vars

    @pytest.mark.asyncio
    async def test_aggregated_results_set_on_state(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": [1, 2]})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        async def _exec(step_type, sub_def, st):
            return f"r_{st.loop_vars['item']}"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            await execute_loop_step(step_def, state)
            assert "s" in state.steps
            assert state.steps["s"].status == "completed"
            assert state.steps["s"].output == ["r_1", "r_2"]

    @pytest.mark.asyncio
    async def test_multiple_sub_steps_per_iteration(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"items": [1]})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.items}}",
            "steps": [
                {"id": "step_a", "type": "tool"},
                {"id": "step_b", "type": "tool"},
            ],
        }

        async def _exec(step_type, sub_def, st):
            return f"{sub_def['id']}_done"

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert results[0]["step_a"] == "step_a_done"
            assert results[0]["step_b"] == "step_b_done"

    @pytest.mark.asyncio
    async def test_default_items_expression(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state()
        step_def = {
            "id": "loop1",
            "type": "loop",
            "steps": [{"id": "s", "type": "tool"}],
        }

        # Default items expr is "[]" which renders as literal string "[]".
        # Since it's a string, the code wraps it in ["[]"], iterating once.
        async def _exec(step_type, sub_def, st):
            return st.loop_vars["item"]

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_iterable_wrapped_in_list(self):
        from ideer.workflows.steps.loop_step import execute_loop_step

        state = _make_state(inputs={"gen": iter([10, 20])})
        step_def = {
            "id": "loop1",
            "type": "loop",
            "items": "{{inputs.gen}}",
            "steps": [{"id": "s", "type": "tool"}],
        }

        async def _exec(step_type, sub_def, st):
            return st.loop_vars["item"]

        with patch("ideer.workflows.steps.execute_step", side_effect=_exec):
            results = await execute_loop_step(step_def, state)
            assert len(results) == 2
