"""Loop step executor — iterates over items and runs sub-steps for each."""

from __future__ import annotations

import copy
import logging
from typing import Any

from ..state import WorkflowState
from ..template import render_value

logger = logging.getLogger(__name__)


async def execute_loop_step(step_def: dict[str, Any], state: WorkflowState) -> list[dict[str, Any]]:
    """Execute a loop step.

    Iterates over ``items`` (a template that resolves to a list) and
    runs the sub-steps for each item.
    """
    from . import execute_step

    items_expr = step_def.get("items", "[]")
    sub_steps = step_def.get("steps", [])
    max_iterations = step_def.get("max_iterations", 1000)
    # BUG-12: When fail_fast is True, stop the loop on first sub-step failure
    fail_fast = step_def.get("fail_fast", False)

    context = state.get_context()
    items = render_value(items_expr, context)
    if items is None:
        logger.warning(
            "Loop step '%s': items expression '%s' resolved to None, skipping iteration",
            step_def["id"],
            items_expr,
        )
        return []
    if not isinstance(items, list):
        # Wrap scalars/iterators in a list, but don't decompose strings into characters
        if isinstance(items, (str, bytes)) or not hasattr(items, "__iter__"):
            items = [items]
        else:
            try:
                items = list(items)
            except TypeError:
                logger.warning(
                    "Loop step '%s': items expression '%s' is not iterable, wrapping in list",
                    step_def["id"],
                    items_expr,
                )
                items = [items]

    # Safety limit to prevent unbounded loops
    if len(items) > max_iterations:
        logger.warning(
            "Loop step '%s': items count %d exceeds max_iterations %d, truncating",
            step_def["id"],
            len(items),
            max_iterations,
        )
        items = items[:max_iterations]

    parent_id = step_def["id"]
    logger.info("Loop step '%s': iterating over %d items", parent_id, len(items))

    # Save outer loop context in case of nested loops (deep copy to prevent
    # mutation of mutable items like dicts/lists in nested iterations)
    prev_loop = copy.deepcopy(state.loop_vars)

    results: list[dict[str, Any]] = []
    # Collect per-sub-step outputs across all iterations
    sub_step_outputs: dict[str, list[Any]] = {}
    sub_step_status: dict[str, str] = {}
    sub_step_failed_indices: dict[str, set[int]] = {}  # Track which iterations failed
    try:
        for idx, item in enumerate(items):
            # Inject current item into loop context (separate from user inputs)
            state.loop_vars["index"] = idx
            state.loop_vars["item"] = item

            item_result: dict[str, Any] = {}
            for sub_def in sub_steps:
                sub_id = sub_def["id"]
                # P2-WF-02: Use namespaced key for per-iteration state so
                # concurrent iterations don't overwrite each other.
                iter_key = f"{parent_id}.{sub_id}[{idx}]"
                sub_type = sub_def["type"]
                try:
                    result = await execute_step(sub_type, sub_def, state)
                    # Write per-iteration result so next sub-step in same
                    # iteration can reference {{steps.sub_id.output}}
                    state.set_step_result(iter_key, status="completed", output=result)
                    sub_step_outputs.setdefault(sub_id, []).append(result)
                    # Only upgrade status if not already marked as failed
                    if sub_step_status.get(sub_id) != "failed":
                        sub_step_status[sub_id] = "completed"
                    item_result[sub_id] = result
                except Exception as e:
                    state.set_step_result(iter_key, status="failed", error=str(e))
                    sub_step_outputs.setdefault(sub_id, []).append(None)
                    sub_step_status[sub_id] = "failed"
                    sub_step_failed_indices.setdefault(sub_id, set()).add(idx)
                    item_result[sub_id] = None
                    logger.warning("Loop sub-step '%s' failed on item %d: %s", iter_key, idx, e)
                    # BUG-12: If fail_fast is enabled, re-raise immediately
                    if fail_fast:
                        raise RuntimeError(f"Loop step '{parent_id}': fail_fast enabled, sub-step '{sub_id}' failed on item {idx}: {e}") from e

            results.append(item_result)
    finally:
        # Overwrite with aggregated results so post-loop steps can access
        # all iterations via {{steps.sub_id.output}} (returns the full list).
        # The final aggregated result uses the original sub_id as key.
        for sub_id, outputs in sub_step_outputs.items():
            status = sub_step_status.get(sub_id, "completed")
            failed_count = len(sub_step_failed_indices.get(sub_id, set()))
            state.set_step_result(
                sub_id,
                status=status,
                output=outputs,
                error=f"Failed on {failed_count} of {len(outputs)} iterations" if status == "failed" else None,
            )
        # Restore outer loop context
        state.loop_vars.clear()
        state.loop_vars.update(prev_loop)

    return results
