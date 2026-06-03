"""Condition step executor — evaluates expressions and branches."""

from __future__ import annotations

import logging
from typing import Any

from ..state import WorkflowState
from ..template import render_value

logger = logging.getLogger(__name__)


async def execute_condition_step(step_def: dict[str, Any], state: WorkflowState) -> Any:
    """Execute a condition step.

    Evaluates the expression and returns the result.
    Branching (then/else) is handled by the executor engine.
    """
    expression = step_def.get("expression", "true")
    context = state.get_context()

    result = bool(render_value(expression, context))
    logger.info(
        "Condition step '%s': expression='%s' → %s",
        step_def["id"],
        expression,
        result,
    )
    return result
