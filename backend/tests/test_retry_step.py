"""Tests for the retry step executor and schema integration.

Covers:
- Schema: RetryStep YAML parsing, StepType.RETRY enum
- Executor: retry_step.execute_retry_step happy path, retry on failure,
  max retries exhausted, error filtering, backoff, multiple sub-steps,
  empty sub-steps validation
- Integration: execute_step dispatch to retry, WorkflowExecutor with retry step
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.workflows.parser import parse_workflow_string
from packages.harness.ideer.workflows.schema import StepType
from packages.harness.ideer.workflows.state import RunStatus, WorkflowState

# The retry_step module imports execute_step lazily via `from . import execute_step`
# which resolves to the `steps.__init__` module's execute_step function.
# We must patch the source module, not the retry_step module attribute.
_PATCH_TARGET = "packages.harness.ideer.workflows.steps.execute_step"


# ── Helpers ──────────────────────────────────────────────────────────


def _make_state(**inputs) -> WorkflowState:
    """Create a minimal WorkflowState for testing."""
    return WorkflowState(
        workflow_name="test-wf",
        run_id="test-run-001",
        inputs=inputs,
    )


def _retry_step_def(
    sub_steps: list[dict] | None = None,
    max_retries: int = 3,
    backoff: float = 0.0,
    on_errors: list[str] | None = None,
) -> dict:
    """Build a retry step definition dict."""
    if sub_steps is None:
        sub_steps = [{"id": "sub1", "type": "tool", "tool": "my_tool"}]
    d: dict = {
        "id": "retry1",
        "type": "retry",
        "steps": sub_steps,
        "max": max_retries,
        "backoff": backoff,
    }
    if on_errors is not None:
        d["on_errors"] = on_errors
    return d


# ── Schema: StepType.RETRY ──────────────────────────────────────────


class TestRetryStepType:
    """Tests for RETRY in the StepType enum."""

    def test_retry_enum_value(self):
        assert StepType.RETRY == "retry"

    def test_retry_is_member(self):
        assert "retry" in [s.value for s in StepType]

    def test_step_type_has_seven_members(self):
        assert len(StepType) == 7


# ── Schema: YAML parsing with retry step ────────────────────────────


class TestRetryYAMLParsing:
    """Tests for parsing retry steps from YAML."""

    def test_parse_retry_step_basic(self):
        yaml_content = """
name: with-retry
steps:
  - id: resilient
    type: retry
    max: 2
    backoff: 1.0
    steps:
      - id: call_api
        type: tool
        tool: http_request
"""
        wf = parse_workflow_string(yaml_content)
        assert len(wf.steps) == 1
        step = wf.steps[0]
        assert step.id == "resilient"
        assert step.type == StepType.RETRY
        assert step.steps is not None
        assert len(step.steps) == 1
        assert step.steps[0].id == "call_api"

    def test_parse_retry_step_with_on_errors(self):
        yaml_content = """
name: retry-filtered
steps:
  - id: resilient
    type: retry
    max: 5
    backoff: 2.5
    on_errors:
      - TimeoutError
      - ConnectionError
    steps:
      - id: fetch
        type: tool
        tool: http_get
"""
        wf = parse_workflow_string(yaml_content)
        step = wf.steps[0]
        assert step.type == StepType.RETRY

    def test_parse_retry_step_nested_in_workflow(self):
        yaml_content = """
name: complex-wf
steps:
  - id: prepare
    type: tool
    tool: setup
  - id: resilient_call
    type: retry
    max: 3
    backoff: 1.0
    steps:
      - id: api_call
        type: tool
        tool: fetch_data
        params:
          url: "https://example.com"
  - id: finalize
    type: agent
    agent: writer
"""
        wf = parse_workflow_string(yaml_content)
        assert len(wf.steps) == 3
        assert wf.steps[0].type == StepType.TOOL
        assert wf.steps[1].type == StepType.RETRY
        assert wf.steps[2].type == StepType.AGENT


# ── Executor: execute_retry_step ────────────────────────────────────


class TestRetryStepHappyPath:
    """Happy path — sub-step succeeds on first attempt."""

    @pytest.mark.asyncio
    async def test_single_sub_step_succeeds(self):
        """Retry step with one sub-step that succeeds immediately."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(
            sub_steps=[{"id": "s1", "type": "tool", "tool": "t1"}],
            max_retries=3,
            backoff=0.0,
        )

        with patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_exec:
            result = await execute_retry_step(step_def, state)

        assert result == "ok"
        assert mock_exec.call_count == 1
        mock_exec.assert_called_once_with("tool", {"id": "s1", "type": "tool", "tool": "t1"}, state)

    @pytest.mark.asyncio
    async def test_multiple_sub_steps_all_succeed(self):
        """Multiple sub-steps run sequentially, returns last output."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        sub_steps = [
            {"id": "s1", "type": "tool", "tool": "t1"},
            {"id": "s2", "type": "agent", "agent": "a1"},
            {"id": "s3", "type": "tool", "tool": "t2"},
        ]
        step_def = _retry_step_def(sub_steps=sub_steps, max_retries=2, backoff=0.0)

        call_count = 0

        async def fake_execute(step_type, step_def_dict, st):
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        with patch(
            _PATCH_TARGET,
            side_effect=fake_execute,
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "result_3"
        assert call_count == 3
        # Verify step results were recorded
        assert state.steps["s1"].status == "completed"
        assert state.steps["s1"].output == "result_1"
        assert state.steps["s2"].status == "completed"
        assert state.steps["s2"].output == "result_2"
        assert state.steps["s3"].status == "completed"
        assert state.steps["s3"].output == "result_3"

    @pytest.mark.asyncio
    async def test_returns_none_when_sub_step_returns_none(self):
        """None is a valid return value."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def()

        with patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await execute_retry_step(step_def, state)

        assert result is None


class TestRetryStepRetryOnFailure:
    """Sub-step fails, then succeeds on retry."""

    @pytest.mark.asyncio
    async def test_succeeds_after_one_failure(self):
        """Fails once, succeeds on second attempt."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=3, backoff=0.0)

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")
            return "recovered"

        with patch(
            _PATCH_TARGET,
            side_effect=fail_then_succeed,
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_succeeds_after_two_failures(self):
        """Fails twice, succeeds on third attempt."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=3, backoff=0.0)

        call_count = 0

        async def fail_twice_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError(f"failure {call_count}")
            return "finally_ok"

        with patch(
            _PATCH_TARGET,
            side_effect=fail_twice_then_succeed,
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "finally_ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_sub_step_results_reset_on_retry(self):
        """Failed sub-step results are overwritten when retry succeeds."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=2, backoff=0.0)

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("oops")
            return "fixed"

        with patch(
            _PATCH_TARGET,
            side_effect=fail_then_succeed,
        ):
            await execute_retry_step(step_def, state)

        # After successful retry, step result should be "completed"
        assert state.steps["sub1"].status == "completed"
        assert state.steps["sub1"].output == "fixed"


class TestRetryStepMaxRetriesExhausted:
    """All retry attempts fail."""

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """Raises RuntimeError after all attempts fail."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=2, backoff=0.0)

        with patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=ValueError("always fails"),
        ):
            with pytest.raises(RuntimeError, match="failed after 3 attempts"):
                await execute_retry_step(step_def, state)

    @pytest.mark.asyncio
    async def test_raises_with_original_error_chain(self):
        """The RuntimeError chains the last original error."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=1, backoff=0.0)

        with patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=ConnectionError("network down"),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await execute_retry_step(step_def, state)

            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, ConnectionError)

    @pytest.mark.asyncio
    async def test_sub_steps_marked_failed_after_exhaustion(self):
        """Sub-step results are marked as failed after all retries exhausted."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=1, backoff=0.0)

        with patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=TimeoutError("timed out"),
        ):
            with pytest.raises(RuntimeError):
                await execute_retry_step(step_def, state)

        assert state.steps["sub1"].status == "failed"
        assert "timed out" in state.steps["sub1"].error

    @pytest.mark.asyncio
    async def test_max_retries_zero_fails_immediately(self):
        """max=0 means no retries — fail on first error."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=0, backoff=0.0)

        call_count = 0

        async def count_calls(*args):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with patch(
            _PATCH_TARGET,
            side_effect=count_calls,
        ):
            with pytest.raises(RuntimeError, match="failed after 1 attempts"):
                await execute_retry_step(step_def, state)

        assert call_count == 1


class TestRetryStepErrorFiltering:
    """on_errors filtering — only retry matching error types."""

    @pytest.mark.asyncio
    async def test_retries_on_matching_error_type(self):
        """Retries when error type matches on_errors list."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(
            max_retries=3,
            backoff=0.0,
            on_errors=["TimeoutError"],
        )

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timed out")
            return "ok"

        with patch(
            _PATCH_TARGET,
            side_effect=fail_then_succeed,
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_does_not_retry_on_non_matching_error(self):
        """Does NOT retry when error type is not in on_errors — original error propagates."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(
            max_retries=3,
            backoff=0.0,
            on_errors=["TimeoutError"],
        )

        with patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=ValueError("bad input"),
        ):
            with pytest.raises(ValueError, match="bad input"):
                await execute_retry_step(step_def, state)

    @pytest.mark.asyncio
    async def test_wildcard_retries_all_errors(self):
        """on_errors=['*'] retries any error type."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(
            max_retries=2,
            backoff=0.0,
            on_errors=["*"],
        )

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TypeError("type error")
            return "ok"

        with patch(
            _PATCH_TARGET,
            side_effect=fail_then_succeed,
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_error_types_in_filter(self):
        """on_errors with multiple types matches any of them."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(
            max_retries=2,
            backoff=0.0,
            on_errors=["TimeoutError", "ConnectionError"],
        )

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("network error")
            return "ok"

        with patch(
            _PATCH_TARGET,
            side_effect=fail_then_succeed,
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "ok"


class TestRetryStepBackoff:
    """Backoff timing behavior."""

    @pytest.mark.asyncio
    async def test_backoff_increases_with_attempt(self):
        """Backoff delay = backoff * (attempt + 1)."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=3, backoff=2.0)

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise RuntimeError("fail")
            return "ok"

        with (
            patch(
                _PATCH_TARGET,
                side_effect=fail_then_succeed,
            ),
            patch("packages.harness.ideer.workflows.steps.retry_step.asyncio.sleep", side_effect=mock_sleep),
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "ok"
        # Backoff: 2.0*1, 2.0*2, 2.0*3 = [2.0, 4.0, 6.0]
        assert sleep_calls == [2.0, 4.0, 6.0]

    @pytest.mark.asyncio
    async def test_no_backoff_on_last_attempt(self):
        """No sleep after the last failed attempt (since it raises)."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=1, backoff=5.0)

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with (
            patch(
                _PATCH_TARGET,
                new_callable=AsyncMock,
                side_effect=RuntimeError("fail"),
            ),
            patch("packages.harness.ideer.workflows.steps.retry_step.asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(RuntimeError):
                await execute_retry_step(step_def, state)

        # Only 1 sleep call: between attempt 0 and attempt 1
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == 5.0


class TestRetryStepValidation:
    """Input validation edge cases."""

    @pytest.mark.asyncio
    async def test_empty_sub_steps_raises_value_error(self):
        """Retry step with no sub-steps raises ValueError."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = _retry_step_def(sub_steps=[])

        with pytest.raises(ValueError, match="must contain at least one sub-step"):
            await execute_retry_step(step_def, state)

    @pytest.mark.asyncio
    async def test_missing_steps_key_raises_value_error(self):
        """Retry step with missing 'steps' key raises ValueError."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        step_def = {"id": "retry1", "type": "retry", "max": 3}

        with pytest.raises(ValueError, match="must contain at least one sub-step"):
            await execute_retry_step(step_def, state)

    @pytest.mark.asyncio
    async def test_default_values_when_not_specified(self):
        """Default max=3, backoff=5.0, on_errors=['*'] when not provided."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        # Don't set max, backoff, or on_errors
        step_def = {
            "id": "retry1",
            "type": "retry",
            "steps": [{"id": "s1", "type": "tool", "tool": "t1"}],
        }

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fail")
            return "ok"

        with (
            patch(
                _PATCH_TARGET,
                side_effect=fail_then_succeed,
            ),
            patch(
                "packages.harness.ideer.workflows.steps.retry_step.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await execute_retry_step(step_def, state)

        assert result == "ok"
        # Should have retried (default on_errors=["*"] matches all)
        assert call_count == 2


class TestRetryStepDispatch:
    """Tests for execute_step dispatch to retry type."""

    @pytest.mark.asyncio
    async def test_dispatch_routes_to_retry_step(self):
        """execute_step with StepType.RETRY dispatches to execute_retry_step."""
        from packages.harness.ideer.workflows.steps import execute_step

        state = _make_state()
        step_def = _retry_step_def(max_retries=1, backoff=0.0)

        with patch(
            _PATCH_TARGET,
            new_callable=AsyncMock,
            return_value="dispatched",
        ):
            result = await execute_step(StepType.RETRY, step_def, state)

        assert result == "dispatched"

    @pytest.mark.asyncio
    async def test_dispatch_raises_for_unknown_type(self):
        """execute_step raises ValueError for unknown step types."""
        from packages.harness.ideer.workflows.steps import execute_step

        state = _make_state()

        with pytest.raises(ValueError, match="Unknown step type"):
            await execute_step("unknown_type", {"id": "x"}, state)


class TestRetryStepWithWorkflowExecutor:
    """Integration tests with WorkflowExecutor."""

    @pytest.mark.asyncio
    async def test_executor_runs_retry_step(self):
        """WorkflowExecutor correctly executes a retry step in a workflow."""
        from packages.harness.ideer.workflows.executor import WorkflowExecutor
        from packages.harness.ideer.workflows.schema import (
            StepDef,
            StepType,
            WorkflowDef,
        )
        from packages.harness.ideer.workflows.store import WorkflowStore

        mock_store = MagicMock(spec=WorkflowStore)
        mock_store.save_run_state = AsyncMock()

        retry_inner = StepDef(id="inner", type=StepType.TOOL, tool="test_tool")
        retry_step = StepDef(
            id="retry_call",
            type=StepType.RETRY,
            steps=[retry_inner],
        )
        wf = WorkflowDef(name="test-retry-wf", steps=[retry_step])

        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(executor, "_dispatch", new_callable=AsyncMock, return_value="success"):
            state = await executor.run(inputs={"q": "test"})

        assert state.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_executor_retry_step_failure_marks_workflow_failed(self):
        """When retry step exhausts retries, workflow fails."""
        from packages.harness.ideer.workflows.executor import WorkflowExecutor
        from packages.harness.ideer.workflows.schema import (
            RetryPolicy,
            StepDef,
            StepType,
            WorkflowDef,
        )
        from packages.harness.ideer.workflows.store import WorkflowStore

        mock_store = MagicMock(spec=WorkflowStore)
        mock_store.save_run_state = AsyncMock()

        retry_inner = StepDef(id="inner", type=StepType.TOOL, tool="fail_tool")
        retry_step = StepDef(
            id="retry_call",
            type=StepType.RETRY,
            steps=[retry_inner],
            retry=RetryPolicy(max=0),
        )
        wf = WorkflowDef(name="test-retry-fail-wf", steps=[retry_step])

        executor = WorkflowExecutor(wf, store=mock_store)

        with patch.object(
            executor,
            "_dispatch",
            new_callable=AsyncMock,
            side_effect=ValueError("tool exploded"),
        ):
            state = await executor.run(inputs={})

        assert state.status == RunStatus.FAILED


class TestRetryStepContextIntegration:
    """Tests that retry step interacts correctly with workflow state/context."""

    @pytest.mark.asyncio
    async def test_sub_step_can_access_workflow_inputs(self):
        """Sub-steps within retry can access workflow state context."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state(query="hello world")
        step_def = _retry_step_def(
            sub_steps=[{"id": "s1", "type": "agent", "agent": "researcher"}],
            max_retries=1,
            backoff=0.0,
        )

        captured_state = None

        async def capture_state(step_type, step_def_dict, st):
            nonlocal captured_state
            captured_state = st
            return "done"

        with patch(
            _PATCH_TARGET,
            side_effect=capture_state,
        ):
            await execute_retry_step(step_def, state)

        assert captured_state is state
        assert state.inputs["query"] == "hello world"

    @pytest.mark.asyncio
    async def test_retry_preserves_results_from_earlier_steps(self):
        """Previous step results survive through retry attempts."""
        from packages.harness.ideer.workflows.steps.retry_step import execute_retry_step

        state = _make_state()
        # Simulate a previous step result
        state.set_step_result("prev_step", status="completed", output="previous_output")

        step_def = _retry_step_def(max_retries=1, backoff=0.0)

        call_count = 0

        async def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("oops")
            return "recovered"

        with patch(
            _PATCH_TARGET,
            side_effect=fail_then_succeed,
        ):
            await execute_retry_step(step_def, state)

        # Previous step result should still be there
        assert state.steps["prev_step"].output == "previous_output"
        assert state.steps["prev_step"].status == "completed"
