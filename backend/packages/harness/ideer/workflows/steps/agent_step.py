"""Agent step executor — invokes an AI agent with a rendered prompt."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..state import WorkflowState
from ..template import render_value

logger = logging.getLogger(__name__)


async def execute_agent_step(step_def: dict[str, Any], state: WorkflowState) -> str:
    """Execute an agent step.

    1. Render the prompt template with current workflow context.
    2. Load the agent config and create a chat model.
    3. Invoke the model and return the response.
    """
    from ideer.config.agents_config import load_agent_config, load_agent_soul
    from ideer.config.app_config import get_app_config
    from ideer.models import create_chat_model

    agent_name = step_def["agent"]
    prompt_template = step_def.get("prompt", "")

    context = state.get_context()
    prompt = render_value(prompt_template, context)

    logger.info("Agent step '%s': invoking agent '%s'", step_def["id"], agent_name)

    try:
        agent_config = load_agent_config(agent_name)
    except FileNotFoundError:
        raise ValueError(f"Agent '{agent_name}' not found")

    app_config = get_app_config()
    model_name = agent_config.model or app_config.model
    model = create_chat_model(name=model_name, thinking_enabled=False, app_config=app_config)

    # Build messages: system prompt (from agent soul) + user prompt
    messages = []
    soul = load_agent_soul(agent_name)
    if soul:
        messages.append(SystemMessage(content=soul))
    messages.append(HumanMessage(content=prompt))

    result = await model.ainvoke(messages)
    return result.content
