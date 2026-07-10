import asyncio
import logging
import uuid

import yaml
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from sqlalchemy import select

from ideer.config.agents_config import validate_agent_name
from ideer.config.paths import get_paths
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.runtime.user_context import resolve_runtime_user_id
from ideer.tools.types import Runtime

logger = logging.getLogger(__name__)


def _upsert_agent_metadata(agent_name: str, user_id: str) -> None:
    """Persist agent metadata to ResourceMetadata table.

    This is a sync wrapper (for use in @tool) that runs the async DB operation
    via asyncio.run(). When DB is unavailable (memory mode), silently skips.
    """
    sf = get_session_factory()
    if sf is None:
        return

    async def _upsert():
        async with sf() as session:
            stmt = select(ResourceMetadata).where(
                ResourceMetadata.resource_type == "agent",
                ResourceMetadata.resource_id == agent_name,
                ResourceMetadata.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()
            if not resource:
                resource = ResourceMetadata(
                    id=str(uuid.uuid4()),
                    resource_type="agent",
                    resource_id=agent_name,
                    owner_id=user_id,
                    department_id=None,
                    visibility="private",
                )
                session.add(resource)
                await session.commit()

    try:
        asyncio.run(_upsert())
    except Exception:
        logger.exception("Failed to write agent metadata to ResourceMetadata table")


@tool(parse_docstring=True)
def setup_agent(
    soul: str,
    description: str,
    runtime: Runtime,
    skills: list[str] | None = None,
) -> Command:
    """Setup the custom iDeer agent.

    Args:
        soul: Full SOUL.md content defining the agent's personality and behavior.
        description: One-line description of what the agent does.
        skills: Optional list of skill names this agent should use. None means use all enabled skills, empty list means no skills.
    """

    agent_name: str | None = runtime.context.get("agent_name") if runtime.context else None
    agent_dir = None
    is_new_dir = False

    try:
        agent_name = validate_agent_name(agent_name)
        paths = get_paths()
        if agent_name:
            # Custom agents are persisted under the current user's bucket so
            # different users do not see each other's agents.
            user_id = resolve_runtime_user_id(runtime)
            agent_dir = paths.user_agent_dir(user_id, agent_name)
        else:
            # Default agent (no agent_name): SOUL.md lives at the global base dir.
            agent_dir = paths.base_dir
        is_new_dir = not agent_dir.exists()
        agent_dir.mkdir(parents=True, exist_ok=True)

        if agent_name:
            # If agent_name is provided, we are creating a custom agent in the agents/ directory
            config_data: dict = {"name": agent_name}
            if description:
                config_data["description"] = description
            if skills is not None:
                config_data["skills"] = skills

            config_file = agent_dir / "config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        soul_file = agent_dir / "SOUL.md"
        soul_file.write_text(soul, encoding="utf-8")

        if agent_name:
            _upsert_agent_metadata(agent_name, user_id)

        logger.info(f"[agent_creator] Created agent '{agent_name}' at {agent_dir}")
        return Command(
            update={
                "created_agent_name": agent_name,
                "messages": [ToolMessage(content=f"Agent '{agent_name}' created successfully!", tool_call_id=runtime.tool_call_id)],
            }
        )

    except Exception as e:
        import shutil

        if agent_name and is_new_dir and agent_dir is not None and agent_dir.exists():
            # Cleanup the custom agent directory only if it was newly created during this call
            shutil.rmtree(agent_dir)
        logger.error(f"[agent_creator] Failed to create agent '{agent_name}': {e}", exc_info=True)
        return Command(update={"messages": [ToolMessage(content=f"Error: {e}", tool_call_id=runtime.tool_call_id)]})
