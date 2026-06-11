"""Workflow execution engine."""

from __future__ import annotations

import asyncio
import logging
import operator
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from .schema import RetryPolicy, StepDef, StepType, WorkflowDef
from .state import RunStatus, WorkflowState
from .steps import execute_step
from .store import WorkflowStore, get_workflow_store
from .template import render_value

logger = logging.getLogger(__name__)

# Comparison operators for condition expression evaluation (BUG-03 fix).
# Order matters: check longer operators first to avoid partial matches.
_OPS: list[tuple[str, Any]] = [
    (">=", operator.ge),
    ("<=", operator.le),
    ("!=", operator.ne),
    ("==", operator.eq),
    (">", operator.gt),
    ("<", operator.lt),
]


def _evaluate_expression(expression: str, context: dict[str, Any]) -> bool:
    """Evaluate a condition expression with comparison operator support.

    Handles cases like ``"{{steps.a.output.score}} > 80"`` where
    render_value produces the string ``"42 > 80"`` which must be
    evaluated as a comparison, not just bool()-tested.

    Supports: ``>``, ``<``, ``>=``, ``<=``, ``==``, ``!=``,
    and logical ``and``/``or``/``not``.

    Falls back to ``bool()`` for plain truthy/falsy expressions.
    """
    rendered = render_value(expression, context)

    # If render_value returned a non-string (dict, list, int, etc.), use bool()
    if not isinstance(rendered, str):
        return bool(rendered)

    rendered = rendered.strip()

    # Handle logical operators first (low precedence)
    # Split on " and " / " or " respecting simple precedence
    if " and " in rendered:
        parts = rendered.split(" and ", 1)
        return _evaluate_expression(parts[0].strip(), context) and _evaluate_expression(parts[1].strip(), context)
    if " or " in rendered:
        parts = rendered.split(" or ", 1)
        return _evaluate_expression(parts[0].strip(), context) or _evaluate_expression(parts[1].strip(), context)
    if rendered.startswith("not "):
        return not _evaluate_expression(rendered[4:].strip(), context)

    # Try comparison operators
    for op_str, op_func in _OPS:
        if op_str in rendered:
            left, right = rendered.split(op_str, 1)
            left = left.strip()
            right = right.strip()
            # Try numeric comparison
            try:
                left_val = float(left)
                right_val = float(right)
                return op_func(left_val, right_val)
            except ValueError:
                pass
            # String comparison
            if op_str == "==":
                return left == right
            if op_str == "!=":
                return left != right
            # For >, <, >=, <= on strings, fall back to bool
            logger.warning("Cannot compare non-numeric values: '%s' %s '%s'", left, op_str, right)
            return False

    # No operator found — fall back to truthy/falsy
    return bool(rendered)


class WorkflowExecutor:
    """Executes a parsed workflow definition with database persistence."""

    def __init__(self, workflow: WorkflowDef, store: WorkflowStore | None = None):
        self.workflow = workflow
        self.store = store or get_workflow_store()

    async def run(self, inputs: dict[str, Any], run_id: str | None = None) -> WorkflowState:
        """Execute the full workflow."""
        run_id = run_id or str(uuid.uuid4())
        state = WorkflowState(
            workflow_name=self.workflow.name,
            run_id=run_id,
            inputs=inputs,
        )
        state.status = RunStatus.RUNNING

        # Persist initial state
        await self.store.save_run_state(state)

        try:
            for current_idx, step in enumerate(self.workflow.steps):
                if not self._should_run(step, state):
                    state.set_step_result(step.id, status="skipped")
                    await self.store.save_run_state(state)
                    continue

                state.current_step = step.id
                await self._execute_step(step, state)

                # Check if the step output is a goto directive and handle it
                step_result = state.steps.get(step.id)
                if step_result and hasattr(step_result, "output") and isinstance(step_result.output, str) and step_result.output.startswith("goto:"):
                    target_id = step_result.output[5:]
                    # Find target step index and skip to it
                    target_idx = next((i for i, s in enumerate(self.workflow.steps) if s.id == target_id), None)
                    if target_idx is not None:
                        # Skip to target step (the loop will continue from there)
                        # Mark intermediate steps as skipped
                        for i in range(current_idx + 1, target_idx):
                            state.set_step_result(self.workflow.steps[i].id, status="skipped")

                # Persist after each step
                await self.store.save_run_state(state)

                if state.status == RunStatus.FAILED:
                    break

            if state.status == RunStatus.RUNNING:
                state.status = RunStatus.COMPLETED
                await self.store.save_run_state(state)

        except Exception as e:
            # Preserve CANCELLED status if set by human_step or external cancellation
            if state.status != RunStatus.CANCELLED:
                state.status = RunStatus.FAILED
            state.error = str(e)
            logger.exception("Workflow %s failed: %s", run_id, e)
            try:
                await self.store.save_run_state(state)
            except Exception:
                logger.exception("Workflow %s: failed to persist error state to DB", run_id)

        return state

    def _should_run(self, step: StepDef, state: WorkflowState) -> bool:
        """Evaluate the step's ``condition`` field."""
        if step.condition is None:
            return True
        context = state.get_context()
        return _evaluate_expression(step.condition, context)

    async def _execute_step(self, step: StepDef, state: WorkflowState) -> None:
        """Execute a single step with retry logic."""
        # BUG-14: Condition steps with inline sub-steps should not be retried
        # at the condition level, as sub-steps have their own retry policies.
        # Retrying the condition would multiply sub-step executions.
        if step.type == StepType.CONDITION and isinstance(step.then, StepDef):
            retry = RetryPolicy(max=0)
        elif step.type == StepType.CONDITION and isinstance(step.else_, StepDef):
            retry = RetryPolicy(max=0)
        else:
            retry = step.retry or RetryPolicy(max=0)
        last_error: Exception | None = None

        for attempt in range(retry.max + 1):
            # Preserve original started_at across retries
            existing = state.steps.get(step.id)
            started = existing.started_at if existing and existing.started_at else _now()
            state.set_step_result(step.id, status="running", started_at=started, retries=attempt)
            try:
                result = await self._dispatch(step, state)
                state.set_step_result(step.id, status="completed", output=result, finished_at=_now())
                return
            except Exception as e:
                last_error = e
                logger.warning("Step %s attempt %d failed: %s", step.id, attempt + 1, e)
                # Check if this error type should trigger a retry
                should_retry = "*" in retry.on_errors or type(e).__name__ in retry.on_errors
                if not should_retry:
                    logger.info("Step %s: error type '%s' not in on_errors %s, not retrying", step.id, type(e).__name__, retry.on_errors)
                    break
                if attempt < retry.max:
                    # P2-WF-06: Add jitter to prevent thundering herd on retry
                    await asyncio.sleep(retry.backoff * (attempt + 1) + random.uniform(0, 1))

        # All retries exhausted
        state.set_step_result(step.id, status="failed", error=str(last_error), finished_at=_now())

        if step.on_error == "skip":
            return
        state.status = RunStatus.FAILED
        state.error = f"Step '{step.id}' failed: {last_error}"

    async def _dispatch(self, step: StepDef, state: WorkflowState) -> Any:
        """Dispatch step execution by type."""
        step_dict = step.model_dump(by_alias=True)

        if step.type == StepType.CONDITION:
            return await self._execute_condition(step, state)

        if step.type == StepType.HUMAN_REVIEW:
            from .steps.human_step import execute_human_review_step

            return await execute_human_review_step(step_dict, state, self.store)

        return await execute_step(step.type, step_dict, state)

    async def _execute_condition(self, step: StepDef, state: WorkflowState) -> Any:
        """Execute a condition step with branching."""
        context = state.get_context()
        result = _evaluate_expression(step.expression or "true", context)

        if result and step.then:
            if isinstance(step.then, StepDef):
                await self._execute_step(step.then, state)
                sub_result = state.steps.get(step.then.id)
                if sub_result and sub_result.status == "failed":
                    raise RuntimeError(f"Condition branch '{step.then.id}' failed: {sub_result.error}")
                return sub_result.output if sub_result else None
            return f"goto:{step.then}"
        elif not result and step.else_:
            if isinstance(step.else_, StepDef):
                await self._execute_step(step.else_, state)
                sub_result = state.steps.get(step.else_.id)
                if sub_result and sub_result.status == "failed":
                    raise RuntimeError(f"Condition branch '{step.else_.id}' failed: {sub_result.error}")
                return sub_result.output if sub_result else None
            return f"goto:{step.else_}"
        return result


def _now() -> str:
    return datetime.now(UTC).isoformat()
