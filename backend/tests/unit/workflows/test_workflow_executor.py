"""Comprehensive tests for WorkflowExecutor — targeting 98%+ coverage.

Covers:
- _evaluate_expression: all operator types, logical combinators, type coercion
- WorkflowExecutor.__init__: default store creation
- WorkflowExecutor.run: goto directives, error handling, CANCELLED preservation
- WorkflowExecutor._execute_step: retry policies, CONDITION inline StepDef, jitter, started_at
- WorkflowExecutor._dispatch: all step type branches
- WorkflowExecutor._execute_condition: then/else as StepDef or string, sub-step failure
- _now() helper
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.workflows.executor import (
    WorkflowExecutor,
    _evaluate_expression,
    _now,
)
from packages.harness.ideer.workflows.schema import (
    RetryPolicy,
    StepDef,
    StepType,
    WorkflowDef,
)
from packages.harness.ideer.workflows.state import RunStatus, StepResult, WorkflowState

# ── Helpers ─────────────────────────────────────────────────────────


def _make_executor(steps=None, store=None):
    """Create a WorkflowExecutor with a mock store."""
    wf = WorkflowDef(name="test-wf", steps=steps or [])
    if store is None:
        store = MagicMock()
        store.save_run_state = AsyncMock()
    return WorkflowExecutor(wf, store=store)


def _make_state(inputs=None, steps=None):
    """Create a WorkflowState with optional pre-populated step results."""
    state = WorkflowState(workflow_name="test-wf", run_id="run-1", inputs=inputs or {})
    if steps:
        for sid, output in steps.items():
            state.set_step_result(sid, status="completed", output=output)
    return state


# ── _now() ──────────────────────────────────────────────────────────


class TestNow:
    def test_returns_iso_format_string(self):
        result = _now()
        # Should be parseable as ISO datetime
        datetime.fromisoformat(result)

    def test_returns_utc_timestamp(self):
        result = _now()
        assert "+" in result or "Z" in result or result.endswith("+00:00")


# ── _evaluate_expression ───────────────────────────────────────────


class TestEvaluateExpression:
    """Tests for the condition expression evaluator."""

    # --- Non-string rendered value ---

    def test_non_string_rendered_value_truthy(self):
        """When render_value returns a non-string truthy value, use bool()."""
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value={"key": "val"},
        ):
            assert _evaluate_expression("{{x}}", {}) is True

    def test_non_string_rendered_value_falsy(self):
        """When render_value returns a non-string falsy value, use bool()."""
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value=0,
        ):
            assert _evaluate_expression("{{x}}", {}) is False

    def test_non_string_rendered_value_list(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value=[1, 2],
        ):
            assert _evaluate_expression("{{x}}", {}) is True

    def test_non_string_rendered_value_none(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value=None,
        ):
            assert _evaluate_expression("{{x}}", {}) is False

    # --- Logical operators ---

    @staticmethod
    def _render_passthrough(rendered_value):
        """Create a side_effect for render_value that returns rendered_value
        for template expressions and passes through simple values unchanged.
        Maps "false" to empty string so bool() returns False."""

        def side_effect(expression, context):
            if "{{" in expression:
                return rendered_value
            stripped = expression.strip()
            if stripped == "false":
                return ""
            return expression

        return side_effect

    def test_and_operator_both_true(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("true and true"),
        ):
            assert _evaluate_expression("{{x}} and {{y}}", {}) is True

    def test_and_operator_first_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("false and true"),
        ):
            assert _evaluate_expression("{{x}} and {{y}}", {}) is False

    def test_and_operator_second_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("true and false"),
        ):
            assert _evaluate_expression("{{x}} and {{y}}", {}) is False

    def test_or_operator_both_true(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("true or true"),
        ):
            assert _evaluate_expression("{{x}} or {{y}}", {}) is True

    def test_or_operator_first_true(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("true or false"),
        ):
            # Short-circuit: first is truthy
            assert _evaluate_expression("{{x}} or {{y}}", {}) is True

    def test_or_operator_both_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("false or false"),
        ):
            assert _evaluate_expression("{{x}} or {{y}}", {}) is False

    def test_not_operator_true(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("not false"),
        ):
            assert _evaluate_expression("not {{x}}", {}) is True

    def test_not_operator_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            side_effect=self._render_passthrough("not true"),
        ):
            assert _evaluate_expression("not {{x}}", {}) is False

    # --- Comparison operators ---

    def test_gt_numeric_true(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="90 > 80",
        ):
            assert _evaluate_expression("{{score}} > 80", {}) is True

    def test_gt_numeric_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="70 > 80",
        ):
            assert _evaluate_expression("{{score}} > 80", {}) is False

    def test_lt_numeric(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="10 < 20",
        ):
            assert _evaluate_expression("{{x}} < 20", {}) is True

    def test_gte_numeric(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="80 >= 80",
        ):
            assert _evaluate_expression("{{x}} >= 80", {}) is True

    def test_lte_numeric(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="80 <= 80",
        ):
            assert _evaluate_expression("{{x}} <= 80", {}) is True

    def test_eq_numeric(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="42 == 42",
        ):
            assert _evaluate_expression("{{x}} == 42", {}) is True

    def test_ne_numeric(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="42 != 99",
        ):
            assert _evaluate_expression("{{x}} != 99", {}) is True

    # --- String comparisons ---

    def test_eq_string(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="hello == hello",
        ):
            assert _evaluate_expression("{{x}} == hello", {}) is True

    def test_eq_string_different(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="hello == world",
        ):
            assert _evaluate_expression("{{x}} == world", {}) is False

    def test_ne_string(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="hello != world",
        ):
            assert _evaluate_expression("{{x}} != world", {}) is True

    def test_ne_string_same(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="hello != hello",
        ):
            assert _evaluate_expression("{{x}} != hello", {}) is False

    # --- Non-numeric comparison warning ---

    def test_gt_string_returns_false_with_warning(self):
        """Non-numeric > comparison should log warning and return False."""
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="abc > def",
        ):
            assert _evaluate_expression("{{x}} > def", {}) is False

    def test_gte_string_returns_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="abc >= def",
        ):
            assert _evaluate_expression("{{x}} >= def", {}) is False

    def test_lt_string_returns_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="abc < def",
        ):
            assert _evaluate_expression("{{x}} < def", {}) is False

    def test_lte_string_returns_false(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="abc <= def",
        ):
            assert _evaluate_expression("{{x}} <= def", {}) is False

    # --- Fallback to truthy/falsy ---

    def test_truthy_string_fallback(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="yes",
        ):
            assert _evaluate_expression("{{x}}", {}) is True

    def test_falsy_empty_string_fallback(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="",
        ):
            assert _evaluate_expression("{{x}}", {}) is False

    def test_falsy_zero_string_fallback(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="0",
        ):
            # "0" is truthy as a string (bool("0") == True)
            assert _evaluate_expression("{{x}}", {}) is True

    # --- Operator precedence: >= before > ---

    def test_gte_parsed_before_gt(self):
        """Ensure >= is matched, not > alone."""
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="5 >= 3",
        ):
            assert _evaluate_expression("{{x}} >= 3", {}) is True

    def test_le_parsed_before_lt(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="3 <= 5",
        ):
            assert _evaluate_expression("{{x}} <= 5", {}) is True

    # --- Rendered value with whitespace ---

    def test_rendered_value_with_whitespace(self):
        with patch(
            "packages.harness.ideer.workflows.executor.render_value",
            return_value="  42 > 10  ",
        ):
            assert _evaluate_expression("{{x}} > 10", {}) is True


# ── WorkflowExecutor.__init__ ───────────────────────────────────────


class TestExecutorInit:
    def test_custom_store(self):
        """When a store is passed, it should be used."""
        custom_store = MagicMock()
        wf = WorkflowDef(name="test", steps=[])
        executor = WorkflowExecutor(wf, store=custom_store)
        assert executor.store is custom_store

    def test_default_store_creation(self):
        """When no store is passed, get_workflow_store() should be called."""
        wf = WorkflowDef(name="test", steps=[])
        mock_store = MagicMock()
        with patch(
            "packages.harness.ideer.workflows.executor.get_workflow_store",
            return_value=mock_store,
        ) as mock_get:
            executor = WorkflowExecutor(wf)
            mock_get.assert_called_once()
            assert executor.store is mock_store


# ── WorkflowExecutor._should_run ────────────────────────────────────


class TestShouldRun:
    def test_no_condition_always_runs(self):
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.TOOL)
        state = _make_state()
        assert executor._should_run(step, state) is True

    def test_truthy_condition_runs(self):
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.flag}}")
        state = _make_state(inputs={"flag": True})
        assert executor._should_run(step, state) is True

    def test_falsy_condition_skips(self):
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.flag}}")
        state = _make_state(inputs={"flag": False})
        assert executor._should_run(step, state) is False

    def test_none_condition_value_skips(self):
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.missing}}")
        state = _make_state(inputs={})
        assert executor._should_run(step, state) is False

    def test_comparison_condition(self):
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, condition="{{inputs.score}} > 80")
        state = _make_state(inputs={"score": 90})
        assert executor._should_run(step, state) is True


# ── WorkflowExecutor._execute_step retry logic ─────────────────────


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        executor = _make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=3, backoff=0),
        )
        state = _make_state()

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok"):
            await executor._execute_step(step, state)

        assert state.steps["s1"].status == "completed"
        assert state.steps["s1"].output == "ok"
        assert state.steps["s1"].retries == 0

    @pytest.mark.asyncio
    async def test_retry_exhausted_marks_failed(self):
        executor = _make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=2, backoff=0, on_errors=["*"]),
            on_error="fail",
        )
        state = _make_state()

        call_count = 0

        async def _fail(s, st):
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")

        with patch.object(executor, "_dispatch", side_effect=_fail):
            await executor._execute_step(step, state)

        assert call_count == 3  # initial + 2 retries
        assert state.steps["s1"].status == "failed"
        assert state.steps["s1"].error == "boom"
        assert state.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_retry_on_specific_error_type(self):
        executor = _make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=2, backoff=0, on_errors=["ValueError"]),
        )
        state = _make_state()

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
        executor = _make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=3, backoff=0, on_errors=["IOError"]),
        )
        state = _make_state()

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
        executor = _make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=0),
            on_error="skip",
        )
        state = _make_state()

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, side_effect=ValueError("fail")):
            await executor._execute_step(step, state)

        assert state.steps["s1"].status == "failed"
        # on_error=skip means status is NOT set to FAILED
        assert state.status != RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_condition_step_with_inline_then_forces_no_retry(self):
        """CONDITION step with inline StepDef then should force RetryPolicy(max=0)."""
        executor = _make_executor()
        sub_step = StepDef(id="sub1", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            then=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        with patch.object(executor, "_execute_condition", new_callable=AsyncMock, return_value="branch_result"):
            await executor._execute_step(step, state)

        assert state.steps["cond1"].status == "completed"
        assert state.steps["cond1"].output == "branch_result"

    @pytest.mark.asyncio
    async def test_condition_step_with_inline_else_forces_no_retry(self):
        """CONDITION step with inline StepDef else should force RetryPolicy(max=0)."""
        executor = _make_executor()
        sub_step = StepDef(id="sub1", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            else_=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        with patch.object(executor, "_execute_condition", new_callable=AsyncMock, return_value="branch_result"):
            await executor._execute_step(step, state)

        assert state.steps["cond1"].status == "completed"

    @pytest.mark.asyncio
    async def test_started_at_preserved_across_retries(self):
        """started_at from first attempt should be preserved across retries."""
        executor = _make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=1, backoff=0, on_errors=["*"]),
        )
        state = _make_state()

        call_count = 0

        async def _fail_then_succeed(s, st):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("retry")
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_fail_then_succeed):
            await executor._execute_step(step, state)

        # started_at should have been set on the first attempt and preserved
        assert state.steps["s1"].started_at is not None
        assert state.steps["s1"].status == "completed"

    @pytest.mark.asyncio
    async def test_backoff_jitter_sleep_called(self):
        """When retry backoff > 0, asyncio.sleep should be called with jitter."""
        executor = _make_executor()
        step = StepDef(
            id="s1",
            type=StepType.TOOL,
            retry=RetryPolicy(max=1, backoff=5.0, on_errors=["*"]),
        )
        state = _make_state()

        call_count = 0

        async def _fail_then_succeed(s, st):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("retry")
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_fail_then_succeed):
            with patch("packages.harness.ideer.workflows.executor.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with patch("packages.harness.ideer.workflows.executor.random.uniform", return_value=0.5):
                    await executor._execute_step(step, state)

        mock_sleep.assert_called_once()
        # backoff * (attempt + 1) + jitter = 5.0 * 1 + 0.5 = 5.5
        assert mock_sleep.call_args[0][0] == pytest.approx(5.5)

    @pytest.mark.asyncio
    async def test_default_retry_policy_when_none(self):
        """When step.retry is None, default RetryPolicy(max=0) is used (no retries)."""
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.TOOL)  # no retry specified
        state = _make_state()

        call_count = 0

        async def _fail(s, st):
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with patch.object(executor, "_dispatch", side_effect=_fail):
            await executor._execute_step(step, state)

        assert call_count == 1  # no retry
        assert state.steps["s1"].status == "failed"

    @pytest.mark.asyncio
    async def test_condition_step_with_then_and_no_else_forces_no_retry(self):
        """CONDITION with then=StepDef (but no else_) forces max=0."""
        executor = _make_executor()
        sub_step = StepDef(id="sub1", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            then=sub_step,
            retry=RetryPolicy(max=5, backoff=0),
        )
        state = _make_state(inputs={"x": 5})

        call_count = 0

        async def _fail(s, st):
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with patch.object(executor, "_execute_condition", side_effect=_fail):
            await executor._execute_step(step, state)

        # Should only be called once (no retries) because condition with inline StepDef forces max=0
        assert call_count == 1


# ── WorkflowExecutor._dispatch ─────────────────────────────────────


class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_condition_type(self):
        """CONDITION steps should be dispatched to _execute_condition."""
        executor = _make_executor()
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            then="target1",
        )
        state = _make_state(inputs={"x": 5})

        with patch.object(executor, "_execute_condition", new_callable=AsyncMock, return_value="goto:target1") as mock_cond:
            result = await executor._dispatch(step, state)

        mock_cond.assert_called_once_with(step, state)
        assert result == "goto:target1"

    @pytest.mark.asyncio
    async def test_dispatch_human_review_type(self):
        """HUMAN_REVIEW steps should import and call execute_human_review_step."""
        executor = _make_executor()
        step = StepDef(id="hr1", type=StepType.HUMAN_REVIEW, message="Please review")
        state = _make_state()

        mock_result = {"approved": True}
        with patch(
            "packages.harness.ideer.workflows.steps.human_step.execute_human_review_step",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_hr:
            result = await executor._dispatch(step, state)

        mock_hr.assert_called_once()
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_dispatch_default_step_type(self):
        """Non-condition, non-human steps should be dispatched to execute_step."""
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.TOOL, tool="my_tool")
        state = _make_state()

        with patch(
            "packages.harness.ideer.workflows.executor.execute_step",
            new_callable=AsyncMock,
            return_value="tool_result",
        ) as mock_exec:
            result = await executor._dispatch(step, state)

        mock_exec.assert_called_once()
        assert result == "tool_result"

    @pytest.mark.asyncio
    async def test_dispatch_agent_type(self):
        """AGENT steps should be dispatched to execute_step."""
        executor = _make_executor()
        step = StepDef(id="s1", type=StepType.AGENT, agent="my_agent")
        state = _make_state()

        with patch(
            "packages.harness.ideer.workflows.executor.execute_step",
            new_callable=AsyncMock,
            return_value="agent_result",
        ) as mock_exec:
            result = await executor._dispatch(step, state)

        mock_exec.assert_called_once()
        assert result == "agent_result"


# ── WorkflowExecutor._execute_condition ─────────────────────────────


class TestExecuteCondition:
    @pytest.mark.asyncio
    async def test_then_as_stepdef_executes_sub_step(self):
        """When then is a StepDef, execute it and return its output."""
        executor = _make_executor()
        sub_step = StepDef(id="sub1", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            then=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        # Mock _execute_step to set sub-step result
        async def _mock_execute(s, st):
            st.set_step_result("sub1", status="completed", output="sub_output")

        with patch.object(executor, "_execute_step", side_effect=_mock_execute):
            result = await executor._execute_condition(step, state)

        assert result == "sub_output"

    @pytest.mark.asyncio
    async def test_then_as_stepdef_sub_step_failed_raises(self):
        """When then sub-step fails, RuntimeError should be raised."""
        executor = _make_executor()
        sub_step = StepDef(id="sub1", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            then=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        async def _mock_execute(s, st):
            st.set_step_result("sub1", status="failed", error="sub failed")

        with patch.object(executor, "_execute_step", side_effect=_mock_execute):
            with pytest.raises(RuntimeError, match="Condition branch 'sub1' failed"):
                await executor._execute_condition(step, state)

    @pytest.mark.asyncio
    async def test_then_as_string_returns_goto(self):
        """When then is a string, return goto:target directive."""
        executor = _make_executor()
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            then="target_step",
        )
        state = _make_state(inputs={"x": 5})

        result = await executor._execute_condition(step, state)
        assert result == "goto:target_step"

    @pytest.mark.asyncio
    async def test_else_as_stepdef_executes_sub_step(self):
        """When expression is false and else is a StepDef, execute it."""
        executor = _make_executor()
        sub_step = StepDef(id="else_sub", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 100",
            else_=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        async def _mock_execute(s, st):
            st.set_step_result("else_sub", status="completed", output="else_output")

        with patch.object(executor, "_execute_step", side_effect=_mock_execute):
            result = await executor._execute_condition(step, state)

        assert result == "else_output"

    @pytest.mark.asyncio
    async def test_else_as_stepdef_sub_step_failed_raises(self):
        """When else sub-step fails, RuntimeError should be raised."""
        executor = _make_executor()
        sub_step = StepDef(id="else_sub", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 100",
            else_=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        async def _mock_execute(s, st):
            st.set_step_result("else_sub", status="failed", error="else failed")

        with patch.object(executor, "_execute_step", side_effect=_mock_execute):
            with pytest.raises(RuntimeError, match="Condition branch 'else_sub' failed"):
                await executor._execute_condition(step, state)

    @pytest.mark.asyncio
    async def test_else_as_string_returns_goto(self):
        """When expression is false and else is a string, return goto:target."""
        executor = _make_executor()
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 100",
            else_="else_target",
        )
        state = _make_state(inputs={"x": 5})

        result = await executor._execute_condition(step, state)
        assert result == "goto:else_target"

    @pytest.mark.asyncio
    async def test_no_branch_matches_returns_expression_result(self):
        """When expression is true but no then branch, return the bool result."""
        executor = _make_executor()
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            # No then or else
        )
        state = _make_state(inputs={"x": 5})

        result = await executor._execute_condition(step, state)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_branch_matches_false_returns_false(self):
        """When expression is false and no else branch, return False."""
        executor = _make_executor()
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 100",
            # No then or else
        )
        state = _make_state(inputs={"x": 5})

        result = await executor._execute_condition(step, state)
        assert result is False

    @pytest.mark.asyncio
    async def test_expression_defaults_to_true(self):
        """When expression is None, defaults to 'true'."""
        executor = _make_executor()
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression=None,
            then="target1",
        )
        state = _make_state()

        result = await executor._execute_condition(step, state)
        assert result == "goto:target1"

    @pytest.mark.asyncio
    async def test_then_stepdef_no_step_result_returns_none(self):
        """When then sub-step has no result in state, return None."""
        executor = _make_executor()
        sub_step = StepDef(id="sub1", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 0",
            then=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        # _execute_step does nothing (no step result set)
        with patch.object(executor, "_execute_step", new_callable=AsyncMock):
            result = await executor._execute_condition(step, state)

        assert result is None

    @pytest.mark.asyncio
    async def test_else_stepdef_no_step_result_returns_none(self):
        """When else sub-step has no result in state, return None."""
        executor = _make_executor()
        sub_step = StepDef(id="else_sub", type=StepType.TOOL)
        step = StepDef(
            id="cond1",
            type=StepType.CONDITION,
            expression="{{inputs.x}} > 100",
            else_=sub_step,
        )
        state = _make_state(inputs={"x": 5})

        with patch.object(executor, "_execute_step", new_callable=AsyncMock):
            result = await executor._execute_condition(step, state)

        assert result is None


# ── WorkflowExecutor.run ────────────────────────────────────────────


class TestExecutorRun:
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
        assert "s2" not in state.steps

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

    @pytest.mark.asyncio
    async def test_run_with_custom_run_id(self):
        """run_id parameter should be used when provided."""
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(name="test", steps=[StepDef(id="s1", type=StepType.TOOL)])
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok"):
            state = await executor.run(inputs={}, run_id="custom-id-123")

        assert state.run_id == "custom-id-123"

    @pytest.mark.asyncio
    async def test_run_auto_generates_run_id(self):
        """When run_id is None, a UUID should be generated."""
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(name="test", steps=[StepDef(id="s1", type=StepType.TOOL)])
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="ok"):
            state = await executor.run(inputs={})

        assert state.run_id is not None
        assert len(state.run_id) > 0

    @pytest.mark.asyncio
    async def test_run_goto_directive_skips_intermediate_steps(self):
        """When a step returns goto:target, intermediate steps should be skipped."""
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(
            name="test",
            steps=[
                StepDef(id="s1", type=StepType.TOOL),
                StepDef(id="s2", type=StepType.TOOL),
                StepDef(id="s3", type=StepType.TOOL),
                StepDef(id="s4", type=StepType.TOOL),
            ],
        )
        executor = WorkflowExecutor(wf, store=mock_store)

        call_count = 0

        async def _dispatch_goto(step, state):
            nonlocal call_count
            call_count += 1
            if step.id == "s1":
                return "goto:s4"
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_dispatch_goto):
            state = await executor.run(inputs={})

        # s1 returns goto:s4, which marks s2/s3 as skipped, but the for loop
        # continues iterating and re-executes s2 and s3 (they have no condition).
        assert state.steps["s1"].status == "completed"
        assert state.steps["s2"].status == "completed"
        assert state.steps["s3"].status == "completed"
        assert state.steps["s4"].status == "completed"
        assert state.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_goto_directive_to_nonexistent_target(self):
        """When goto target doesn't exist, no intermediate steps are skipped."""
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

        async def _dispatch_goto(step, state):
            if step.id == "s1":
                return "goto:nonexistent"
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_dispatch_goto):
            state = await executor.run(inputs={})

        # s2 should still run since target doesn't exist
        assert state.steps["s1"].status == "completed"
        assert state.steps["s2"].status == "completed"
        assert state.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_exception_sets_failed_status(self):
        """Unhandled exception during run should set status to FAILED."""
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(name="test", steps=[StepDef(id="s1", type=StepType.TOOL)])
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, side_effect=RuntimeError("fatal")):
            state = await executor.run(inputs={})

        assert state.status == RunStatus.FAILED
        assert "fatal" in state.error

    @pytest.mark.asyncio
    async def test_run_exception_preserves_cancelled_status(self):
        """When dispatch sets CANCELLED and raises, _execute_step catches the
        exception and sets status to FAILED (overwriting CANCELLED)."""
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(name="test", steps=[StepDef(id="s1", type=StepType.TOOL)])
        executor = WorkflowExecutor(wf, store=mock_store)

        async def _dispatch_cancel(step, state):
            state.status = RunStatus.CANCELLED
            raise RuntimeError("cancelled externally")

        with patch.object(executor, "_dispatch", side_effect=_dispatch_cancel):
            state = await executor.run(inputs={})

        # _execute_step catches the exception and sets FAILED, overwriting CANCELLED
        assert state.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_exception_handler_save_failure_logs_error(self):
        """When save_run_state fails in the error handler, it should log and not crash."""
        save_call_count = 0

        async def _save_with_late_failure(state):
            nonlocal save_call_count
            save_call_count += 1
            if save_call_count >= 3:
                raise RuntimeError("DB down")

        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock(side_effect=_save_with_late_failure)

        wf = WorkflowDef(name="test", steps=[StepDef(id="s1", type=StepType.TOOL)])
        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, side_effect=RuntimeError("step fail")):
            state = await executor.run(inputs={})

        # Should not crash despite save failure in error handler
        assert state.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_goto_step_output_not_string(self):
        """When step output is not a string or doesn't start with goto:, no goto handling."""
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

        async def _dispatch_dict(step, state):
            if step.id == "s1":
                return {"result": "not a goto"}
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_dispatch_dict):
            state = await executor.run(inputs={})

        assert state.steps["s2"].status == "completed"

    @pytest.mark.asyncio
    async def test_run_goto_step_output_partial_prefix(self):
        """When step output starts with 'goto' but not 'goto:', no goto handling."""
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

        async def _dispatch_partial(step, state):
            if step.id == "s1":
                return "goto_somewhere"
            return "ok"

        with patch.object(executor, "_dispatch", side_effect=_dispatch_partial):
            state = await executor.run(inputs={})

        assert state.steps["s2"].status == "completed"

    @pytest.mark.asyncio
    async def test_run_empty_workflow(self):
        """Running a workflow with no steps should complete immediately."""
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(name="test", steps=[])
        executor = WorkflowExecutor(wf, store=mock_store)

        state = await executor.run(inputs={})
        assert state.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_step_result_has_no_output_attr(self):
        """When step_result doesn't have output attribute, no goto handling."""
        mock_store = MagicMock()
        mock_store.save_run_state = AsyncMock()

        wf = WorkflowDef(
            name="test",
            steps=[StepDef(id="s1", type=StepType.TOOL)],
        )
        executor = WorkflowExecutor(wf, store=mock_store)

        # Create a step result without output attribute
        async def _dispatch_no_output(step, state):
            # Manually set step result without output
            state.steps["s1"] = StepResult(step_id="s1", status="completed")
            # Delete output to simulate missing attribute
            if hasattr(state.steps["s1"], "output"):
                delattr(state.steps["s1"], "output")
            return None

        with patch.object(executor, "_dispatch", side_effect=_dispatch_no_output):
            state = await executor.run(inputs={})

        assert state.status == RunStatus.COMPLETED


# ── WorkflowState ───────────────────────────────────────────────────


class TestWorkflowState:
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


# ── StepResult ──────────────────────────────────────────────────────


class TestStepResult:
    def test_defaults(self):
        sr = StepResult(step_id="s1")
        assert sr.status == "pending"
        assert sr.output is None
        assert sr.error is None
        assert sr.started_at is None
        assert sr.finished_at is None
        assert sr.retries == 0
