"""Agent step executor — invokes a full agent with tools and middleware.

Uses SubagentExecutor to get the complete agent capability set:
tool calling, sandbox, memory, guardrails, sub-agent delegation, etc.
"""

from __future__ import annotations

import logging
from typing import Any

from ..state import WorkflowState
from ..template import render_value

logger = logging.getLogger(__name__)


async def execute_agent_step(step_def: dict[str, Any], state: WorkflowState) -> str:
    """Execute an agent step.

    1. Render the prompt template with current workflow context.
    2. Load the agent config to get model, tools, skills.
    3. Create a SubagentExecutor with full capabilities.
    4. Execute and return the result text.
    """
    from ideer.config.agents_config import load_agent_config, load_agent_soul
    from ideer.config.app_config import get_app_config
    from ideer.subagents.config import SubagentConfig
    from ideer.subagents.executor import SubagentExecutor, SubagentStatus
    from ideer.tools.tools import get_available_tools

    agent_name = step_def["agent"]
    prompt_template = step_def.get("prompt", "")

    context = state.get_context()
    prompt = render_value(prompt_template, context)

    logger.info("Agent step '%s': invoking agent '%s'", step_def["id"], agent_name)

    # Load agent config
    try:
        agent_config = load_agent_config(agent_name)
    except FileNotFoundError:
        raise ValueError(f"Agent '{agent_name}' not found")

    app_config = get_app_config()
    soul = load_agent_soul(agent_name)

    # Build SubagentConfig from agent config
    sub_config = SubagentConfig(
        name=agent_name,
        description=f"Workflow step: {step_def['id']}",
        system_prompt=soul,
        tools=agent_config.tool_groups,
        skills=agent_config.skills,
        model=agent_config.model or "inherit",
    )

    # Get available tools and create executor
    tools = get_available_tools(app_config=app_config)
    executor = SubagentExecutor(
        sub_config,
        tools,
        app_config=app_config,
    )

    # Execute
    result = await executor._aexecute(prompt)

    if result.status == SubagentStatus.COMPLETED and result.result:
        return result.result
    elif result.error:
        raise RuntimeError(f"Agent '{agent_name}' failed: {result.error}")
    else:
        return str(result.result or "")
