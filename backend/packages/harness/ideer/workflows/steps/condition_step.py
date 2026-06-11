"""Condition step executor — evaluates expressions and handles branching."""

from __future__ import annotations

import logging
from typing import Any

from ..state import WorkflowState

logger = logging.getLogger(__name__)


def _evaluate_expression(expression: str, context: dict[str, Any]) -> bool:
    """Evaluate a condition expression with comparison operator support.

    Same logic as executor._evaluate_expression — duplicated here to avoid
    circular imports between steps/ and the executor module.
    """
    import operator as op

    from ..template import render_value

    _OPS = [
        (">=", op.ge),
        ("<=", op.le),
        ("!=", op.ne),
        ("==", op.eq),
        (">", op.gt),
        ("<", op.lt),
    ]

    rendered = render_value(expression, context)
    if not isinstance(rendered, str):
        return bool(rendered)
    rendered = rendered.strip()

    # Logical operators
    if " and " in rendered:
        parts = rendered.split(" and ", 1)
        return _evaluate_expression(parts[0].strip(), context) and _evaluate_expression(parts[1].strip(), context)
    if " or " in rendered:
        parts = rendered.split(" or ", 1)
        return _evaluate_expression(parts[0].strip(), context) or _evaluate_expression(parts[1].strip(), context)
    if rendered.startswith("not "):
        return not _evaluate_expression(rendered[4:].strip(), context)

    # Comparison operators
    for op_str, op_func in _OPS:
        if op_str in rendered:
            left, right = rendered.split(op_str, 1)
            left, right = left.strip(), right.strip()
            try:
                return op_func(float(left), float(right))
            except ValueError:
                if op_str == "==":
                    return left == right
                if op_str == "!=":
                    return left != right
                return False

    return bool(rendered)


async def _execute_branch(branch: Any, step_id: str, state: WorkflowState) -> Any:
    """Execute a condition branch (dict, list, or return goto for string)."""
    from . import execute_step

    if isinstance(branch, dict):
        branch_type = branch.get("type")
        branch_id = branch.get("id")
        if branch_type:
            branch_result = await execute_step(branch_type, branch, state)
            if branch_id:
                state.set_step_result(branch_id, status="completed", output=branch_result)
            return branch_result
        logger.warning(
            "Condition step '%s': inline branch dict has no 'type' key, skipping",
            step_id,
        )
        return None

    # BUG-04 fix: Handle list-type branches (multiple sub-steps)
    if isinstance(branch, list):
        results = []
        for sub_step in branch:
            if isinstance(sub_step, dict) and sub_step.get("type"):
                sub_result = await execute_step(sub_step["type"], sub_step, state)
                sub_id = sub_step.get("id")
                if sub_id:
                    state.set_step_result(sub_id, status="completed", output=sub_result)
                results.append(sub_result)
            else:
                logger.warning(
                    "Condition step '%s': list branch item missing 'type', skipping: %s",
                    step_id,
                    sub_step,
                )
        return results if len(results) != 1 else results[0]

    # String step_id — return goto directive in the format the executor expects
    if isinstance(branch, str):
        return f"goto:{branch}"

    return None


async def execute_condition_step(step_def: dict[str, Any], state: WorkflowState) -> Any:
    """Execute a condition step.

    Evaluates the expression and handles then/else branching.
    When nested inside loop/parallel steps, this function executes
    the branch sub-steps directly instead of delegating to the executor.
    """
    expression = step_def.get("expression", "true")
    context = state.get_context()

    result = _evaluate_expression(expression, context)
    logger.info(
        "Condition step '%s': expression='%s' → %s",
        step_def["id"],
        expression,
        result,
    )

    # Handle branching for nested condition steps (inside loop/parallel)
    branch = step_def.get("then") if result else step_def.get("else")
    if branch is not None:
        return await _execute_branch(branch, step_def["id"], state)

    return result
