"""Workflow execution engine."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from .schema import RetryPolicy, StepDef, StepType, WorkflowDef
from .state import RunStatus, WorkflowState
from .steps import execute_step
from .store import WorkflowStore, get_workflow_store
from .template import render_value

logger = logging.getLogger(__name__)


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
            for step in self.workflow.steps:
                if not self._should_run(step, state):
                    state.set_step_result(step.id, status="skipped")
                    continue

                state.current_step = step.id
                await self._execute_step(step, state)

                # Persist after each step
                await self.store.save_run_state(state)

                if state.status == RunStatus.FAILED:
                    break

            if state.status == RunStatus.RUNNING:
                state.status = RunStatus.COMPLETED
                await self.store.save_run_state(state)

        except Exception as e:
            state.status = RunStatus.FAILED
            state.error = str(e)
            await self.store.save_run_state(state)
            logger.exception("Workflow %s failed", run_id)

        return state

    def _should_run(self, step: StepDef, state: WorkflowState) -> bool:
        """Evaluate the step's ``condition`` field."""
        if step.condition is None:
            return True
        context = state.get_context()
        result = render_value(step.condition, context)
        return bool(result)

    async def _execute_step(self, step: StepDef, state: WorkflowState) -> None:
        """Execute a single step with retry logic."""
        retry = step.retry or RetryPolicy(max=0)
        last_error: Exception | None = None

        for attempt in range(retry.max + 1):
            state.set_step_result(step.id, status="running", started_at=_now(), retries=attempt)
            try:
                result = await self._dispatch(step, state)
                state.set_step_result(step.id, status="completed", output=result, finished_at=_now())
                return
            except Exception as e:
                last_error = e
                logger.warning("Step %s attempt %d failed: %s", step.id, attempt + 1, e)
                if attempt < retry.max:
                    await asyncio.sleep(retry.backoff * (attempt + 1))

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
        result = bool(render_value(step.expression or "true", context))

        if result and step.then:
            if isinstance(step.then, StepDef):
                await self._execute_step(step.then, state)
                return state.steps[step.then.id].output
            return f"goto:{step.then}"
        elif not result and step.else_:
            if isinstance(step.else_, StepDef):
                await self._execute_step(step.else_, state)
                return state.steps[step.else_.id].output
            return f"goto:{step.else_}"
        return result


def _now() -> str:
    return datetime.now(UTC).isoformat()
