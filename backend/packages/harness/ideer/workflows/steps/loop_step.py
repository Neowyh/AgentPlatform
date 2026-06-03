"""Loop step executor — iterates over items and runs sub-steps for each."""

from __future__ import annotations

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

    context = state.get_context()
    items = render_value(items_expr, context)
    if not isinstance(items, list):
        items = list(items)

    logger.info("Loop step '%s': iterating over %d items", step_def["id"], len(items))

    results: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        # Inject current item into context
        state.inputs["_loop_index"] = idx
        state.inputs["_loop_item"] = item

        item_result: dict[str, Any] = {}
        for sub_def in sub_steps:
            sub_id = sub_def["id"]
            sub_type = sub_def["type"]
            try:
                result = await execute_step(sub_type, sub_def, state)
                state.set_step_result(sub_id, status="completed", output=result)
                item_result[sub_id] = result
            except Exception as e:
                state.set_step_result(sub_id, status="failed", error=str(e))
                item_result[sub_id] = None
                logger.warning("Loop sub-step '%s' failed on item %d: %s", sub_id, idx, e)

        results.append(item_result)

    # Clean up loop context
    state.inputs.pop("_loop_index", None)
    state.inputs.pop("_loop_item", None)

    return results
