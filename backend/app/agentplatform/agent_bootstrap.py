"""Canonical bootstrap for in-run custom-agent creation (``setup_agent``).

AgentPlatform is canonical-only: a custom agent created by the lead agent
during a run must become a Resource-catalog row (plus its published filesystem
draft) owned by the authenticated user. DeerFlow's stock ``setup_agent`` builtin
only knows the legacy per-user agent store, so this module restores the
canonical publication by wrapping that tool at gateway composition time.

The wrap is installed once (``install()``) and replaces the module attributes
``deerflow.tools.builtins.setup_agent`` / ``...setup_agent_tool.setup_agent``;
the lead-agent assembly imports the tool lazily on every graph build, so every
subsequent build picks up the wrapped tool. The DeerFlow package itself is not
modified. The wrapper resolves ``get_paths`` and ``get_session_factory``
through the tool module namespace at call time, which keeps the contract-test
patch seams on that module load-bearing.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from sqlalchemy import select

from deerflow.config.agents_config import SOUL_FILENAME, validate_agent_name
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)

_TOOL_MODULE_NAME = "deerflow.tools.builtins.setup_agent_tool"
_BUILTINS_MODULE_NAME = "deerflow.tools.builtins"

_installed = False


def _create_canonical_agent(
    *,
    agent_name: str,
    description: str,
    soul: str,
    skills: list[str] | None,
    user_id: str,
) -> str:
    """Create or update the agent through the canonical resource catalog.

    Mirrors the /resources agent-draft and publish endpoints using the same
    service and publisher boundaries, so the catalog row, filesystem draft,
    dependencies, and published version stay consistent. Runs in asyncio.run
    because @tool bodies are synchronous.
    """
    from tempfile import TemporaryDirectory

    from app.agentplatform.rbac_models import UserModel, UserRole
    from app.agentplatform.resource_models import Resource
    from app.agentplatform.resource_runtime import ResourcePublisher, ResourceStorage, write_agent_draft_source
    from app.agentplatform.resource_service import ResourceAction, ResourceActor, ResourceNotFound, ResourceService

    tool_module = importlib.import_module(_TOOL_MODULE_NAME)
    session_factory = tool_module.get_session_factory()
    if session_factory is None:
        raise RuntimeError("Resource catalog persistence is unavailable")

    async def _create() -> str:
        async with session_factory() as session:
            user = (await session.execute(select(UserModel).where(UserModel.id == user_id, UserModel.disabled.is_not(True)))).scalar_one_or_none()
            if user is None:
                raise RuntimeError("Active user is required to create a catalog agent")
            permissions = {ResourceAction.READ, ResourceAction.USE}
            if user.role in {UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN}:
                permissions.add(ResourceAction.WRITE)
            actor = ResourceActor(
                user_id=str(user.id),
                department_id=str(user.department_id) if user.department_id is not None else None,
                role=str(user.role),
                permissions=frozenset(permissions),
                tool_groups=None,
            )
            service = ResourceService(session, actor)
            existing = (
                await session.execute(
                    select(Resource).where(
                        Resource.type == "agent",
                        Resource.owner_id == actor.user_id,
                        Resource.slug == agent_name,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                resource = await service.create_resource(
                    resource_type="agent",
                    slug=agent_name,
                    display_name=agent_name,
                    storage_kind="filesystem",
                )
            else:
                resource = existing
            dependencies: list[str] = []
            if skills:
                for name in skills:
                    try:
                        target = await service.resolve_legacy_alias("skill", name)
                    except ResourceNotFound:
                        logger.warning("[agent_creator] Skill '%s' is not catalogued; skipping dependency", name)
                        continue
                    dependencies.append(target.id)
            dependencies = list(dict.fromkeys(dependencies))
            config: dict = {"name": agent_name}
            if description:
                config["description"] = description
            if skills is not None:
                config["skills"] = dependencies
            if dependencies:
                await service.replace_dependencies(resource.id, dependencies)
            with TemporaryDirectory(prefix="agentplatform-setup-agent-") as temporary:
                source = Path(temporary)
                await asyncio.to_thread(
                    write_agent_draft_source,
                    source,
                    slug=agent_name,
                    config=config,
                    soul=soul,
                )
                publisher = ResourcePublisher(service, ResourceStorage(tool_module.get_paths().base_dir))
                draft = await publisher.save_filesystem_draft(
                    resource.id,
                    source_dir=source,
                    expected_revision=resource.draft_revision,
                )
            await publisher.publish_filesystem(
                resource.id,
                expected_draft_revision=draft.revision,
                scan_result={},
            )
            return resource.id

    try:
        return asyncio.run(_create())
    except Exception:
        logger.exception("[agent_creator] Failed to create canonical agent '%s'", agent_name)
        raise


@tool(parse_docstring=True)
def setup_agent(
    soul: str,
    description: str,
    runtime: Runtime,
    skills: list[str] | None = None,
) -> Command:
    """Setup the custom agent.

    Args:
        soul: Full SOUL.md content defining the agent's personality and behavior.
        description: One-line description of what the agent does.
        skills: Optional list of skill names this agent should use. None means use all enabled skills, empty list means no skills.
    """

    agent_name: str | None = runtime.context.get("agent_name") if runtime.context else None

    try:
        agent_name = validate_agent_name(agent_name)
        if agent_name:
            user_id = resolve_runtime_user_id(runtime)
            resource_id = _create_canonical_agent(
                agent_name=agent_name,
                description=description,
                soul=soul,
                skills=skills,
                user_id=user_id,
            )
            logger.info("[agent_creator] Created canonical agent '%s' (%s)", agent_name, resource_id)
            return Command(
                update={
                    "created_agent_name": agent_name,
                    "created_agent_resource_id": resource_id,
                    "messages": [ToolMessage(content=f"Agent '{agent_name}' created successfully!", tool_call_id=runtime.tool_call_id)],
                }
            )

        # Default agent (no agent_name): SOUL.md lives at the global base dir.
        # It is not a custom-agent record, so it stays file-based.
        paths = importlib.import_module(_TOOL_MODULE_NAME).get_paths()
        paths.base_dir.mkdir(parents=True, exist_ok=True)
        (paths.base_dir / SOUL_FILENAME).write_text(soul, encoding="utf-8")

        logger.info("[agent_creator] Created default agent SOUL at %s", paths.base_dir)
        return Command(
            update={
                "messages": [ToolMessage(content=f"Agent '{agent_name}' created successfully!", tool_call_id=runtime.tool_call_id)],
            }
        )

    except Exception as e:
        logger.error("[agent_creator] Failed to create agent '%s': %s", agent_name, e, exc_info=True)
        return Command(update={"messages": [ToolMessage(content=f"Error: {e}", tool_call_id=runtime.tool_call_id)]})


def install() -> None:
    """Replace DeerFlow's stock ``setup_agent`` with the canonical wrapper.

    Idempotent. Also exposes ``get_session_factory`` on the tool module so the
    catalog seam has a single, patchable home (the wrapper reads it lazily).
    """
    global _installed
    if _installed:
        return

    from deerflow.persistence.engine import get_session_factory

    tool_module = importlib.import_module(_TOOL_MODULE_NAME)
    if not hasattr(tool_module, "get_session_factory"):
        tool_module.get_session_factory = get_session_factory
    tool_module.setup_agent = setup_agent

    builtins_module = importlib.import_module(_BUILTINS_MODULE_NAME)
    builtins_module.setup_agent = setup_agent

    _installed = True
    logger.debug("agent_bootstrap: canonical setup_agent installed")
