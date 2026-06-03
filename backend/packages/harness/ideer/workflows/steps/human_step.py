"""Human review step executor — database-backed pause/resume.

Instead of in-memory asyncio.Future (single-process only), this
implementation persists the waiting state to the database and polls
for the review result.  Supports multi-worker deployments and
survives server restarts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..state import RunStatus, WorkflowState
from ..store import WorkflowStore

logger = logging.getLogger(__name__)


async def execute_human_review_step(
    step_def: dict[str, Any],
    state: WorkflowState,
    store: WorkflowStore,
) -> dict[str, Any]:
    """Execute a human review step.

    1. Set workflow status to WAITING_HUMAN and persist.
    2. Poll the database for a review_result.
    3. Return the review result when available.
    """
    state.status = RunStatus.WAITING_HUMAN
    await store.save_run_state(state)

    timeout = step_def.get("timeout", 3600)  # default 1 hour
    poll_interval = 2  # seconds
    elapsed = 0.0

    logger.info(
        "Workflow %s paused at human_review step '%s'",
        state.run_id,
        step_def["id"],
    )

    while elapsed < timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        run_data = await store.load_run_state(state.run_id)
        if run_data is None:
            raise RuntimeError(f"Run {state.run_id} disappeared from database")

        # Check if review has been submitted
        # The API endpoint sets review_result and status back to "running"
        if run_data.status == RunStatus.RUNNING and run_data.review_result is not None:
            state.status = RunStatus.RUNNING
            # Copy review_result into the run state so downstream steps can access it
            state.set_step_result(
                step_def["id"],
                status="completed",
                output=run_data.review_result,
            )
            logger.info("Workflow %s resumed after human_review", state.run_id)
            return run_data.review_result

    raise TimeoutError(f"Human review timed out after {timeout}s")
