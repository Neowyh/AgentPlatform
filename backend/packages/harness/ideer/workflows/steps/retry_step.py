"""Retry step executor — wraps a sub-step and retries on failure.

Unlike the per-step ``RetryPolicy`` (which is built into the executor),
this is a *standalone step type* that lets workflow authors explicitly
model retry-then-fallback logic in the YAML DSL.

Example YAML::

    - id: resilient_call
      type: retry
      max: 3
      backoff: 2.0
      on_errors:
        - TimeoutError
        - ConnectionError
      steps:
        - id: call_api
          type: tool
          tool: http_request
          params:
            url: "https://api.example.com/data"
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..state import WorkflowState

logger = logging.getLogger(__name__)


async def execute_retry_step(
    step_def: dict[str, Any],
    state: WorkflowState,
) -> Any:
    """Execute a retry step.

    Runs the contained sub-steps sequentially, retrying the entire
    sub-step sequence up to ``max`` times on failure.

    Parameters
    ----------
    step_def:
        The step definition dict (already model_dump'd).
    state:
        Mutable workflow state.

    Returns
    -------
    The output of the last sub-step in the sequence.

    Raises
    ------
    RuntimeError
        When all retry attempts are exhausted.
    """
    from . import execute_step

    sub_steps = step_def.get("steps", [])
    if not sub_steps:
        raise ValueError("Retry step must contain at least one sub-step")

    max_retries = step_def.get("max", 3)
    backoff = step_def.get("backoff", 5.0)
    on_errors = step_def.get("on_errors", ["*"])

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        logger.info(
            "Retry step '%s': attempt %d/%d",
            step_def["id"],
            attempt + 1,
            max_retries + 1,
        )

        try:
            last_output: Any = None
            for sub_def in sub_steps:
                sub_id = sub_def["id"]
                sub_type = sub_def["type"]
                result = await execute_step(sub_type, sub_def, state)
                state.set_step_result(sub_id, status="completed", output=result)
                last_output = result
            return last_output
        except Exception as e:
            last_error = e
            logger.warning(
                "Retry step '%s': attempt %d failed: %s",
                step_def["id"],
                attempt + 1,
                e,
            )

            # Mark sub-steps as failed for this attempt
            for sub_def in sub_steps:
                state.set_step_result(sub_def["id"], status="failed", error=str(e))

            # Check if this error type should trigger a retry
            should_retry = "*" in on_errors or type(e).__name__ in on_errors
            if not should_retry:
                logger.info(
                    "Retry step '%s': error type '%s' not in on_errors %s, not retrying",
                    step_def["id"],
                    type(e).__name__,
                    on_errors,
                )
                raise

            if attempt < max_retries:
                delay = backoff * (attempt + 1)
                logger.info(
                    "Retry step '%s': waiting %.1fs before retry",
                    step_def["id"],
                    delay,
                )
                await asyncio.sleep(delay)

    # All retries exhausted
    raise RuntimeError(f"Retry step '{step_def['id']}' failed after {max_retries + 1} attempts: {last_error}") from last_error
