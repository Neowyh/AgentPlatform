"""Tool step executor — invokes a tool with rendered parameters."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from ..state import WorkflowState
from ..template import render_params

logger = logging.getLogger(__name__)


async def execute_tool_step(step_def: dict[str, Any], state: WorkflowState) -> Any:
    """Execute a tool step.

    1. Render parameter templates with current workflow context.
    2. Find the tool by name.
    3. Invoke the tool and return the result.
    """
    from ideer.config.app_config import get_app_config
    from ideer.tools.tools import get_available_tools

    tool_name = step_def["tool"]
    raw_params = step_def.get("params", {})

    # Validate and coerce timeout
    raw_timeout = step_def.get("timeout")
    if raw_timeout is None:
        timeout = 300.0
    else:
        try:
            timeout = float(raw_timeout)
            if timeout <= 0:
                raise ValueError("timeout must be positive")
        except (TypeError, ValueError):
            raise ValueError(f"Invalid timeout value: {raw_timeout!r}")

    context = state.get_context()
    params = render_params(raw_params, context)

    logger.info("Tool step '%s': invoking tool '%s'", step_def["id"], tool_name)

    config = get_app_config()
    tools = get_available_tools(app_config=config)
    tool = next((t for t in tools if hasattr(t, "name") and t.name == tool_name), None)

    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not available")

    async def _invoke(p):
        if hasattr(tool, "ainvoke"):
            return await asyncio.wait_for(tool.ainvoke(p), timeout=timeout)
        return await asyncio.wait_for(asyncio.to_thread(tool.invoke, p), timeout=timeout)

    try:
        return await _invoke(params)
    except TimeoutError:
        raise TimeoutError(f"Tool '{tool_name}' timed out after {timeout}s")
    except TypeError as e:
        # Only retry if it looks like a parameter format issue, not a tool bug
        error_msg = str(e).lower()
        if "argument" not in error_msg and "params" not in error_msg and "invoke" not in error_msg:
            raise  # Re-raise if it's not a parameter format issue
        # Tool may expect a string instead of a dict — retry with serialized params
        logger.info("Tool '%s' rejected dict params (%s), retrying with string", tool_name, e)
        param_str = json.dumps(params) if len(params) != 1 else next(iter(params.values()))
        if not isinstance(param_str, str):
            param_str = json.dumps(params)
        try:
            return await _invoke(param_str)
        except TimeoutError:
            raise TimeoutError(f"Tool '{tool_name}' timed out after {timeout}s")
        except TypeError:
            logger.info("Tool '%s' also rejected string params, giving up", tool_name)
            raise
