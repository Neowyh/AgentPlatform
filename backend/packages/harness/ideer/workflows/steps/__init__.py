"""Step executors for each workflow step type.

Note: HUMAN_REVIEW is handled directly by the executor (which passes
the store), so it is not dispatched here.
"""

from __future__ import annotations

from typing import Any

from ..schema import StepType
from ..state import WorkflowState


async def execute_step(step_type: StepType, step_def: dict[str, Any], state: WorkflowState) -> Any:
    """Dispatch execution to the appropriate step executor."""
    if step_type == StepType.AGENT:
        from .agent_step import execute_agent_step

        return await execute_agent_step(step_def, state)

    elif step_type == StepType.TOOL:
        from .tool_step import execute_tool_step

        return await execute_tool_step(step_def, state)

    elif step_type == StepType.CONDITION:
        from .condition_step import execute_condition_step

        return await execute_condition_step(step_def, state)

    elif step_type == StepType.PARALLEL:
        from .parallel_step import execute_parallel_step

        return await execute_parallel_step(step_def, state)

    elif step_type == StepType.LOOP:
        from .loop_step import execute_loop_step

        return await execute_loop_step(step_def, state)

    elif step_type == StepType.RETRY:
        from .retry_step import execute_retry_step

        return await execute_retry_step(step_def, state)

    raise ValueError(f"Unknown step type: {step_type}")
