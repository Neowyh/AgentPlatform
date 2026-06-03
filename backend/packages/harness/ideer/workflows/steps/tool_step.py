"""Tool step executor — invokes a tool with rendered parameters."""

from __future__ import annotations

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

    context = state.get_context()
    params = render_params(raw_params, context)

    logger.info("Tool step '%s': invoking tool '%s'", step_def["id"], tool_name)

    config = get_app_config()
    tools = get_available_tools(config)
    tool = next((t for t in tools if hasattr(t, "name") and t.name == tool_name), None)

    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not available")

    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(params)
    return tool.invoke(params)
