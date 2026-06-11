"""Parallel step executor — runs sub-steps concurrently."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..state import WorkflowState

logger = logging.getLogger(__name__)

# BUG-13: Sentinel key to distinguish error results from normal tool output.
# Prevents false positives when a tool legitimately returns {"status": "failed"}.
_ERROR_SENTINEL = "__parallel_sub_step_error__"


async def execute_parallel_step(step_def: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
    """Execute sub-steps in parallel and collect outputs.

    Each sub-step runs concurrently via ``asyncio.gather``.
    Results are keyed by sub-step id. An optional ``timeout`` (seconds)
    on the parent step limits total wall-clock time for all sub-steps.
    """
    from . import execute_step

    sub_steps = step_def.get("steps", [])
    if not sub_steps:
        return {}

    parent_id = step_def["id"]
    # BUG-11: Read timeout from step definition
    raw_timeout = step_def.get("timeout")
    timeout: float | None = None
    if raw_timeout is not None:
        try:
            timeout = float(raw_timeout)
            if timeout <= 0:
                timeout = None
        except (TypeError, ValueError):
            pass

    logger.info("Parallel step '%s': running %d sub-steps (timeout=%s)", parent_id, len(sub_steps), timeout)

    async def _run_sub(sub_def: dict[str, Any]) -> tuple[str, Any]:
        sub_id = sub_def["id"]
        namespaced_id = f"{parent_id}.{sub_id}"
        sub_type = sub_def["type"]
        try:
            result = await execute_step(sub_type, sub_def, state)
            state.set_step_result(namespaced_id, status="completed", output=result)
            return sub_id, result
        except Exception as e:
            state.set_step_result(namespaced_id, status="failed", error=str(e))
            logger.warning("Parallel sub-step '%s' failed: %s", namespaced_id, e)
            # BUG-13: Use sentinel to distinguish errors from normal output
            return sub_id, {_ERROR_SENTINEL: True, "error": str(e), "sub_step_id": sub_id}

    # BUG-11: Apply timeout to the entire parallel gather
    coro = asyncio.gather(*[_run_sub(s) for s in sub_steps])
    if timeout is not None:
        try:
            pairs = await asyncio.wait_for(coro, timeout=timeout)
        except TimeoutError:
            logger.error("Parallel step '%s' timed out after %ss", parent_id, timeout)
            raise TimeoutError(f"Parallel step '{parent_id}' timed out after {timeout}s")
    else:
        pairs = await coro
    results = dict(pairs)

    # BUG-13: Check for all-failed using sentinel instead of "status" key
    if results and all(isinstance(v, dict) and v.get(_ERROR_SENTINEL) for v in results.values()):
        failed_ids = [k for k, v in results.items() if isinstance(v, dict) and v.get(_ERROR_SENTINEL)]
        raise RuntimeError(f"All parallel sub-steps failed: {', '.join(failed_ids)}")

    return results
