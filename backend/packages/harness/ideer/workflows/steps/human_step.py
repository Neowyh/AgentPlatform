"""Human review step executor — pauses execution and waits for human input."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..state import RunStatus, WorkflowState

logger = logging.getLogger(__name__)

# Global registry: run_id → Future for human_review pause/resume
_pending_reviews: dict[str, asyncio.Future] = {}


async def execute_human_review_step(step_def: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
    """Execute a human review step.

    1. Set workflow status to WAITING_HUMAN.
    2. Create a Future and suspend.
    3. Wait for API callback via resume_review().
    4. Return the review result.
    """
    state.status = RunStatus.WAITING_HUMAN

    loop = asyncio.get_event_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending_reviews[state.run_id] = future

    logger.info(
        "Workflow %s paused at human_review step '%s'",
        state.run_id,
        step_def["id"],
    )

    try:
        timeout = step_def.get("timeout")
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    finally:
        _pending_reviews.pop(state.run_id, None)
        state.status = RunStatus.RUNNING


async def resume_review(run_id: str, result: dict[str, Any]) -> bool:
    """Resume a paused human review step via API callback."""
    future = _pending_reviews.get(run_id)
    if future is None or future.done():
        return False
    future.set_result(result)
    return True


def get_pending_review(run_id: str) -> bool:
    """Check if a run has a pending human review."""
    future = _pending_reviews.get(run_id)
    return future is not None and not future.done()
