"""Parallel step executor — runs sub-steps concurrently."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..state import WorkflowState

logger = logging.getLogger(__name__)


async def execute_parallel_step(step_def: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
    """Execute sub-steps in parallel and collect outputs.

    Each sub-step runs concurrently via ``asyncio.gather``.
    Results are keyed by sub-step id.
    """
    from . import execute_step

    sub_steps = step_def.get("steps", [])
    if not sub_steps:
        return {}

    logger.info("Parallel step '%s': running %d sub-steps", step_def["id"], len(sub_steps))

    async def _run_sub(sub_def: dict[str, Any]) -> tuple[str, Any]:
        sub_id = sub_def["id"]
        sub_type = sub_def["type"]
        try:
            result = await execute_step(sub_type, sub_def, state)
            state.set_step_result(sub_id, status="completed", output=result)
            return sub_id, result
        except Exception as e:
            state.set_step_result(sub_id, status="failed", error=str(e))
            logger.warning("Parallel sub-step '%s' failed: %s", sub_id, e)
            return sub_id, None

    pairs = await asyncio.gather(*[_run_sub(s) for s in sub_steps])
    return dict(pairs)
