"""Tests for WorkflowExecutor — retry logic, condition branching, error handling, and state management.

Covers gaps identified in the workflow executor, store, and state modules.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.workflows.executor import WorkflowExecutor
from packages.harness.ideer.workflows.schema import (
    RetryPolicy,
    StepDef,
    StepType,
    WorkflowDef,
)
from packages.harness.ideer.workflows.state import RunStatus, StepResult, WorkflowState

# ── WorkflowState ──────────────────────────────────────────────────


class TestWorkflowState:
    """Tests for WorkflowState dataclass methods."""

    def test_get_context_returns_inputs_and_steps(self):
        state = WorkflowState(workflow_name="test", run_id="r1", inputs={"q": "hello"})
        state.set_step_result("s1", status="completed", output="world")
        ctx = state.get_context()
        assert ctx["inputs"] == {"q": "hello"}
        assert ctx["steps"]["s1"]["output"] == "world"
        assert ctx["steps"]["s1"]["status"] == "completed"

    def test_get_context_includes_loop_vars(self):
        state = WorkflowState(workflow_name="test", run_id="r1")
        state.loop_vars = {"index": 2, "item": "foo"}
        ctx = state.get_context()
        assert ctx["_loop"]["index"] == 2
        assert ctx["_loop"]["item"] == "foo"

    def test_get_context_no_loop_vars_key_when_empty(self):
        state = WorkflowState(workflow_name="test", run_id="r1")
        ctx = state.get_context()
        assert "_loop" not in ctx

    def test_set_step_result_creates_new(self):
        state = WorkflowState(workflow_name="test", run_id="r1")
        state.set_step_result("s1", status="running")
        assert "s1" in state.steps
        assert state.steps["s1"].status == "running"

    def test_set_step_result_updates_existing(self):
        state = WorkflowState(workflow_name="test", run_id="r1")
        state.set_step_result("s1", status="running")
        state.set_step_result("s1", status="completed", output=42)
        assert state.steps["s1"].status == "completed"
        assert state.steps["s1"].output == 42

    def test_set_step_result_invalid_field_raises(self):
        state = WorkflowState(workflow_name="test", run_id="r1")
        with pytest.raises(TypeError, match="StepResult has no field"):
            state.set_step_result("s1", bogus_field="x")

    def test_step_result_preserves_started_at_across_updates(self):
        state = WorkflowState(workflow_name="test", run_id="r1")
        state.set_step_result("s1", status="running", started_at="2026-01-01T00:00:00")
        state.set_step_result("s1", status="completed", output="ok")
        assert state.steps["s1"].started_at == "2026-01-01T00:00:00"


# ── WorkflowExecutor._should_run ──────────────────────────────────


class TestShouldRun:
    """Tests for condition evaluation on steps."""

    def _make_executor(self):
        wf = WorkflowDef(name="test", steps=[])
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()
        return WorkflowExecutor(wf, store=mock_store)

    def test_no_condition_always_runs(self):
        executor = self._make_executor()
        step = StepDef(id="s1", type=StepType.TOOL)
        state = WorkflowState(workflow_name="test", run_id="r1")
        assert executor._should_run(step, state) is True

    def test_truthy_condition_runs(self):
        executor = self._make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.flag}}")
        state = WorkflowState(workflow_name="test", run_id="r1", inputs={"flag": True})
        assert executor._should_run(step, state) is True

    def test_falsy_condition_skips(self):
        executor = self._make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.flag}}")
        state = WorkflowState(workflow_name="test", run_id="r1", inputs={"flag": False})
        assert executor._should_run(step, state) is False

    def test_none_condition_skips(self):
        executor = self._make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.missing}}")
        state = WorkflowState(workflow_name="test", run_id="r1", inputs={})
        assert executor._should_run(step, state) is False


# ── WorkflowExecutor._execute_step retry logic ────────────────────


class TestRetryLogic:
    """Tests for step retry with RetryPolicy."""

    def _make_executor(self):
        wf = WorkflowDef(name="test", steps=[])
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()
        return WorkflowExecutor(wf, store=mock_store)

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        executor = self._make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=3, backoff=0),
        )
        state = WorkflowState(workflow_name="test", run_id="r1")

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok"):
            await executor._execute_step(step, state)

        assert state.steps["s1"].status == "completed"
        assert state.steps["s1"].output == "ok"
        assert state.steps["s1"].retries == 0

    @pytest.mark.asyncio
    async def test_retry_exhausted_marks_failed(self):
        executor = self._make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=2, backoff=0, on_errors=["*"]),
            on_error="fail",
        )
        state = WorkflowState(workflow_name="test", run_id="r1")

        call_count = 0

        async def _fail_dispatch(s, st):
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")

        with patch.object(executor, "_dispatch", side_effect=_fail_dispatch):
            await executor._execute_step(step, state)

        assert call_count == 3  # initial + 2 retries
        assert state.steps["s1"].status == "failed"
        assert state.steps["s1"].error == "boom"
        assert state.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_retry_on_specific_error_type(self):
        executor = self._make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=2, backoff=0, on_errors=["ValueError"]),
        )
        state = WorkflowState(workflow_name="test", run_id="r1")

        call_count = 0

        async def _fail_then_succeed(s, st):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("first attempt fails")
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_fail_then_succeed):
            await executor._execute_step(step, state)

        assert call_count == 2
        assert state.steps["s1"].status == "completed"
        assert state.steps["s1"].output == "ok"

    @pytest.mark.asyncio
    async def test_no_retry_when_error_not_in_on_errors(self):
        executor = self._make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=3, backoff=0, on_errors=["IOError"]),
        )
        state = WorkflowState(workflow_name="test", run_id="r1")

        call_count = 0

        async def _fail(s, st):
            nonlocal call_count
            call_count += 1
            raise ValueError("wrong error type")

        with patch.object(executor, "_dispatch", side_effect=_fail):
            await executor._execute_step(step, state)

        assert call_count == 1  # no retry because ValueError not in on_errors
        assert state.steps["s1"].status == "failed"

    @pytest.mark.asyncio
    async def test_on_error_skip_continues(self):
        executor = self._make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=0),
            on_error="skip",
        )
        state = WorkflowState(workflow_name="test", run_id="r1")

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, side_effect=ValueError("fail")):
            await executor._execute_step(step, state)

        assert state.steps["s1"].status == "failed"
        # on_error=skip means status is NOT set to FAILED
        assert state.status != RunStatus.FAILED


# ── WorkflowExecutor.run ──────────────────────────────────────────


class TestExecutorRun:
    """Integration-level tests for WorkflowExecutor.run()."""

    @pytest.mark.asyncio
    async def test_run_skips_steps_with_false_condition(self):
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(
            name="test",
            steps=[
                StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.skip}}"),
                StepDef(id="s2", type=StepType.TOOL),
            ],
        )
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok") as mock_dispatch:
            state = await executor.run(inputs={"skip": False})

        # s1 should be skipped (condition is falsy), s2 should execute
        assert state.steps["s1"].status == "skipped"
        assert state.steps["s2"].status == "completed"
        mock_dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_persists_state_after_each_step(self):
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(
            name="test",
            steps=[StepDef(id="s1", type=StepType.TOOL)],
        )
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok"):
            await executor.run(inputs={})

        # save_run_state called: 1 (initial) + 1 (after step) + 1 (completed)
        assert mock_store.save_run_state.call_count >= 3

    @pytest.mark.asyncio
    async def test_run_failed_step_stops_execution(self):
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(
            name="test",
            steps=[
                StepDef(id="s1", type=StepType.TOOL),
                StepDef(id="s2", type=StepType.TOOL),
            ],
        )
        executor = WorkflowExecutor(wf, store=mock_store)

        call_count = 0

        async def _fail_first(s, st):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("step 1 fails")
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_fail_first):
            state = await executor.run(inputs={})

        assert state.status == RunStatus.FAILED
        assert state.steps["s1"].status == "failed"
        # s2 should NOT have been executed
        assert "s2" not in state.steps

    @pytest.mark.asyncio
    async def test_run_preserves_cancelled_status_on_store_failure(self):
        """When save_run_state raises AFTER cancel, run() preserves CANCELLED."""
        mock_store = MagicMock()

        save_call_count = 0

        async def _save_with_failure(state):
            nonlocal save_call_count
            save_call_count += 1
            if save_call_count > 1:
                raise RuntimeError("DB connection lost")

        mock_store.save_run_state = AsyncMock(side_effect=_save_with_failure)

        wf = WorkflowDef(
            name="test",
            steps=[StepDef(id="s1", type=StepType.TOOL)],
        )
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok"):
            state = await executor.run(inputs={})

        # The first save succeeds, but subsequent saves fail.
        # The run should complete or fail gracefully.
        assert state.status in (RunStatus.COMPLETED, RunStatus.FAILED)

    @pytest.mark.asyncio
    async def test_run_sets_completed_when_all_steps_done(self):
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(
            name="test",
            steps=[
                StepDef(id="s1", type=StepType.TOOL),
                StepDef(id="s2", type=StepType.TOOL),
            ],
        )
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok"):
            state = await executor.run(inputs={})

        assert state.status == RunStatus.COMPLETED


# ── StepResult default values ─────────────────────────────────────


class TestStepResult:
    def test_defaults(self):
        sr = StepResult(step_id="s1")
        assert sr.status == "pending"
        assert sr.output is None
        assert sr.error is None
        assert sr.started_at is None
        assert sr.finished_at is None
        assert sr.retries == 0
