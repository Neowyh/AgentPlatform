"""CRUD API for custom agents."""

import logging
import re
import shutil
import uuid
from collections import defaultdict
from datetime import UTC, datetime

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.gateway.audit import record_audit
from app.gateway.authz import check_resource_access, check_resource_modify, get_current_rbac_user, get_optional_rbac_user, require_role
from app.gateway.resource_catalog_mode import require_legacy_resource_facades
from ideer.config.agents_api_config import get_agents_api_config
from ideer.config.agents_config import AgentConfig, list_custom_agents, load_agent_config, load_agent_soul
from ideer.config.paths import get_paths
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import UserModel, UserRole
from ideer.runtime.user_context import get_effective_user_id

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api",
    tags=["agents"],
    dependencies=[Depends(require_legacy_resource_facades)],
)


# ---------------------------------------------------------------------------
# RBAC helpers — now backed by real UserModel from authz.py
# ---------------------------------------------------------------------------

VALID_ROLES = tuple(UserRole)


AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


class AgentResponse(BaseModel):
    """Response model for a custom agent."""

    name: str = Field(..., description="Agent name (hyphen-case)")
    description: str = Field(default="", description="Agent description")
    model: str | None = Field(default=None, description="Optional model override")
    tool_groups: list[str] | None = Field(default=None, description="Optional tool group whitelist")
    skills: list[str] | None = Field(default=None, description="Optional skill whitelist (None=all, []=none)")
    soul: str | None = Field(default=None, description="SOUL.md content")
    read_only: bool = Field(default=False, description="Whether this agent is a shared read-only template")
    visibility: str = Field(default="private", description="Visibility: private, department, or public")
    owner_id: str | None = Field(default=None, description="Owner user ID")
    department_id: str | None = Field(default=None, description="Department ID for department-scoped visibility")
    is_favorited: bool = Field(default=False, description="Whether this agent is favorited by the user")


class AgentsListResponse(BaseModel):
    """Response model for listing all custom agents."""

    agents: list[AgentResponse]


class AgentCreateRequest(BaseModel):
    """Request body for creating a custom agent."""

    name: str = Field(..., description="Agent name (must match ^[A-Za-z0-9-]+$, stored as lowercase)")
    description: str = Field(default="", description="Agent description")
    model: str | None = Field(default=None, description="Optional model override")
    tool_groups: list[str] | None = Field(default=None, description="Optional tool group whitelist")
    skills: list[str] | None = Field(default=None, description="Optional skill whitelist (None=all enabled, []=none)")
    soul: str = Field(default="", description="SOUL.md content — agent personality and behavioral guardrails")
    visibility: str = Field(default="private", description="Visibility: private, department, or public")


class AgentUpdateRequest(BaseModel):
    """Request body for updating a custom agent."""

    description: str | None = Field(default=None, description="Updated description")
    model: str | None = Field(default=None, description="Updated model override")
    tool_groups: list[str] | None = Field(default=None, description="Updated tool group whitelist")
    skills: list[str] | None = Field(default=None, description="Updated skill whitelist (None=all, []=none)")
    soul: str | None = Field(default=None, description="Updated SOUL.md content")
    version: int = Field(..., description="Current resource version for optimistic locking")


def _validate_agent_name(name: str) -> None:
    """Validate agent name against allowed pattern.

    Args:
        name: The agent name to validate.

    Raises:
        HTTPException: 422 if the name is invalid.
    """
    if not AGENT_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid agent name '{name}'. Must match ^[A-Za-z0-9-]+$ (letters, digits, and hyphens only).",
        )


def _normalize_agent_name(name: str) -> str:
    """Normalize agent name to lowercase for filesystem storage."""
    return name.lower()


def _require_agents_api_enabled() -> None:
    """Reject access unless the custom-agent management API is explicitly enabled."""
    if not get_agents_api_config().enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AGENTS_API_DISABLED",
                "message": "Custom-agent management API is disabled. Set agents_api.enabled=true to expose agent and user-profile routes over HTTP.",
            },
        )


def _is_shared_only(agent_name: str, user_id: str) -> bool:
    """Return True if the agent exists only in the shared read-only template directory."""
    paths = get_paths()
    return paths.agent_dir(agent_name).exists() and not paths.user_agent_dir(user_id, agent_name).exists()


async def _resolve_agent_config(name: str, user_id: str) -> tuple[AgentConfig, str, dict]:
    """Resolve an agent config for read endpoints, falling back to its owner's directory.

    Reads search the current user's directory first (plus the legacy shared
    path via ``load_agent_config``). When that fails, the resource_metadata
    record is consulted: if it declares another owner whose per-user directory
    holds the agent, the config is loaded from there so public/department
    agents remain reachable in detail views.

    Returns:
        ``(agent_cfg, resolved_user_id, meta)`` — ``resolved_user_id`` is the
        user id whose directory the config was loaded from (the owner for
        other-owned agents).

    Raises:
        FileNotFoundError: If the agent is not found in the current user's
            directory nor the declared owner's directory.
    """
    try:
        agent_cfg = load_agent_config(name, user_id=user_id)
        return agent_cfg, user_id, await _load_agent_meta(name, user_id)
    except FileNotFoundError:
        pass

    meta = await _load_agent_meta(name, user_id)
    owner_id = meta.get("owner_id")
    if owner_id and owner_id != user_id and get_paths().user_agent_dir(owner_id, name).exists():
        return load_agent_config(name, user_id=owner_id), owner_id, meta
    raise FileNotFoundError(f"Agent directory not found: {name}")


async def _load_agent_meta(agent_name: str, user_id: str, for_owner: str | None = None) -> dict:
    """Load agent RBAC metadata from resource_metadata table."""
    from ideer.persistence.engine import get_session_factory

    sf = get_session_factory()
    if sf is not None:
        try:
            async with sf() as session:
                from sqlalchemy import select

                from ideer.persistence.models.resource_metadata import ResourceMetadata

                stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == "agent",
                    ResourceMetadata.resource_id == agent_name,
                )
                if for_owner is not None:
                    stmt = stmt.where(ResourceMetadata.owner_id == for_owner)
                    result = await session.execute(stmt)
                    resource = result.scalar_one_or_none()
                else:
                    result = await session.execute(stmt)
                    resources = result.scalars().all()
                    resource = resources[0] if resources else None
                if resource:
                    return {
                        "visibility": resource.visibility,
                        "owner_id": resource.owner_id,
                        "department_id": resource.department_id,
                        "version": resource.version,
                        "is_favorited": resource.is_favorited,
                        "created_at": str(resource.created_at) if resource.created_at else None,
                    }
        except Exception:
            logger.error("Failed to load agent meta from DB for %s", agent_name, exc_info=True)
    return {}


async def _save_agent_meta(agent_name: str, user_id: str, meta: dict) -> None:
    """Persist agent RBAC metadata to resource_metadata table."""
    from ideer.persistence.engine import get_session_factory

    sf = get_session_factory()
    if sf is None:
        return

    try:
        async with sf() as session:
            from sqlalchemy import select

            from ideer.persistence.models.resource_metadata import ResourceMetadata

            stmt = select(ResourceMetadata).where(
                ResourceMetadata.resource_type == "agent",
                ResourceMetadata.resource_id == agent_name,
                ResourceMetadata.owner_id == user_id,
            )
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()
            if resource:
                resource.visibility = meta.get("visibility", "private")
                resource.department_id = meta.get("department_id")
                resource.version = ResourceMetadata.version + 1
            else:
                resource = ResourceMetadata(
                    id=str(uuid.uuid4()),
                    resource_type="agent",
                    resource_id=agent_name,
                    owner_id=meta.get("owner_id", user_id),
                    department_id=meta.get("department_id"),
                    visibility=meta.get("visibility", "private"),
                )
                session.add(resource)
            await session.commit()
    except Exception:
        logger.error("Failed to save agent meta to DB for %s", agent_name, exc_info=True)


async def _ensure_agent_meta(agent_name: str, user_id: str) -> None:
    """Lazy-migration: create ResourceMetadata for agents found on disk but missing from DB.

    Idempotent -- _save_agent_meta will update in-place if a non-deleted record
    already exists for (agent_name, owner_id).  Safe to call on every write path.
    """
    if get_paths().user_agent_dir(user_id, agent_name).exists() and not await _load_agent_meta(agent_name, user_id, for_owner=user_id):
        await _save_agent_meta(
            agent_name,
            user_id,
            {"visibility": "private", "owner_id": user_id, "department_id": None},
        )


def _agent_config_to_response(
    agent_cfg: AgentConfig,
    include_soul: bool = False,
    *,
    user_id: str | None = None,
    read_only: bool = False,
    visibility: str = "private",
    owner_id: str | None = None,
    department_id: str | None = None,
    is_favorited: bool = False,
) -> AgentResponse:
    """Convert AgentConfig to AgentResponse."""
    soul: str | None = None
    if include_soul:
        soul = load_agent_soul(agent_cfg.name, user_id=user_id) or ""

    return AgentResponse(
        name=agent_cfg.name,
        description=agent_cfg.description,
        model=agent_cfg.model,
        tool_groups=agent_cfg.tool_groups,
        skills=agent_cfg.skills,
        soul=soul,
        read_only=read_only,
        visibility=visibility,
        owner_id=owner_id,
        department_id=department_id,
        is_favorited=is_favorited,
    )


@router.get(
    "/agents",
    response_model=AgentsListResponse,
    summary="List Custom Agents",
    description="List all custom agents available in the agents directory, including their soul content.",
)
async def list_agents(
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> AgentsListResponse:
    """List all custom agents.

    Returns:
        List of all custom agents with their metadata and soul content.
        Results are filtered by visibility based on the current user's role
        and department when auth is active.
    """
    _require_agents_api_enabled()

    user_id = get_effective_user_id()
    try:
        agents = list_custom_agents(user_id=user_id)

        # Build response with RBAC metadata
        # Batch-load agent metadata from resource_metadata table
        agent_meta_map: dict[str, list[dict]] = defaultdict(list)
        sf = get_session_factory()
        if sf is not None:
            try:
                async with sf() as session:
                    from ideer.persistence.models.resource_metadata import ResourceMetadata

                    stmt = select(ResourceMetadata).where(
                        ResourceMetadata.resource_type == "agent",
                    )
                    result = await session.execute(stmt)
                    for r in result.scalars().all():
                        agent_meta_map[r.resource_id].append(
                            {
                                "resource_id": r.resource_id,
                                "visibility": r.visibility,
                                "owner_id": r.owner_id,
                                "department_id": r.department_id,
                                "is_favorited": r.is_favorited,
                            }
                        )
            except Exception:
                logger.error("Failed to batch-load agent metadata", exc_info=True)

        # Public and department-scoped agents live in their owners' directories,
        # so they are not returned by list_custom_agents(user_id=user_id).
        # Discover only metadata-backed, accessible entries and load each config
        # from its owner directory.
        agent_owner_map = {agent.name: None if _is_shared_only(agent.name, user_id) else user_id for agent in agents}
        local_agent_names = set(agent_owner_map)
        for records in agent_meta_map.values():
            for meta in records:
                owner_id = meta.get("owner_id")
                if not owner_id or owner_id == user_id:
                    continue
                visibility = meta.get("visibility", "private")
                department_id = meta.get("department_id")
                if current_user is not None:
                    accessible = check_resource_access(current_user, owner_id, department_id, visibility)
                else:
                    accessible = visibility == "public"
                if not accessible:
                    continue

                agent_name = meta["resource_id"]
                if agent_name in local_agent_names or not get_paths().user_agent_dir(owner_id, agent_name).exists():
                    continue
                try:
                    agent_cfg = load_agent_config(agent_name, user_id=owner_id)
                except Exception:
                    logger.warning("Skipping inaccessible agent '%s' for owner '%s'", agent_name, owner_id, exc_info=True)
                    continue
                if agent_cfg is not None:
                    agents.append(agent_cfg)
                    local_agent_names.add(agent_name)
                    agent_owner_map[agent_name] = owner_id

        # Lazy migration: auto-create ResourceMetadata for agents found on disk
        # but missing from DB. Only for per-user agents (not legacy shared).
        for a in agents:
            records = agent_meta_map.get(a.name, [])
            has_own_record = any(r.get("owner_id") == user_id for r in records)
            if not has_own_record and get_paths().user_agent_dir(user_id, a.name).exists():
                meta = {"visibility": "private", "owner_id": user_id, "department_id": None}
                await _save_agent_meta(a.name, user_id, meta)
                agent_meta_map[a.name].append(meta)

        responses: list[AgentResponse] = []
        for a in agents:
            # BUG-07: Check if agent is shared-only (exists in template dir but not user dir).
            # Shared agents are treated as public visibility regardless of metadata.
            agent_owner_id = agent_owner_map[a.name]
            is_shared = agent_owner_id is None
            if is_shared:
                visibility = "public"
                owner_id = None
                dept_id = None
                meta = {}
            else:
                records = agent_meta_map.get(a.name, [])
                meta = next(
                    (r for r in records if r.get("owner_id") == agent_owner_id),
                    records[0] if records else {},
                )
                # Default to 'private' when no metadata exists (secure-by-default for pre-RBAC agents)
                visibility = meta.get("visibility", "private")
                owner_id = meta.get("owner_id")
                dept_id = meta.get("department_id")

            # Filter by visibility
            if current_user is not None:
                if not check_resource_access(current_user, owner_id, dept_id, visibility):
                    continue
            elif visibility != "public":
                continue

            responses.append(
                _agent_config_to_response(
                    a,
                    include_soul=True,
                    user_id=agent_owner_id or user_id,
                    read_only=is_shared or agent_owner_id != user_id,
                    visibility=visibility,
                    owner_id=owner_id,
                    department_id=dept_id,
                    is_favorited=meta.get("is_favorited", False),
                )
            )

        return AgentsListResponse(agents=responses)
    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/agents/check",
    summary="Check Agent Name",
    description="Validate an agent name and check if it is available (case-insensitive).",
)
async def check_agent_name(name: str, current_user: UserModel | None = Depends(get_optional_rbac_user)) -> dict:
    """Check whether an agent name is valid and not yet taken.

    Args:
        name: The agent name to check.

    Returns:
        ``{"available": true/false, "name": "<normalized>"}``

    Raises:
        HTTPException: 422 if the name is invalid.
    """
    _require_agents_api_enabled()
    _validate_agent_name(name)
    normalized = _normalize_agent_name(name)
    user_id = get_effective_user_id()
    paths = get_paths()
    # Treat the name as taken if either the per-user path or the legacy shared
    # path holds an agent — picking a name that collides with an unmigrated
    # legacy agent would shadow the legacy entry once migration runs.
    available = not paths.user_agent_dir(user_id, normalized).exists() and not paths.agent_dir(normalized).exists()
    return {"available": available, "name": normalized}


@router.get(
    "/agents/{name}",
    response_model=AgentResponse,
    summary="Get Custom Agent",
    description="Retrieve details and SOUL.md content for a specific custom agent.",
)
async def get_agent(
    name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> AgentResponse:
    """Get a specific custom agent by name.

    Args:
        name: The agent name.

    Returns:
        Agent details including SOUL.md content.

    Raises:
        HTTPException: 404 if agent not found or not visible to user.
    """
    _require_agents_api_enabled()
    _validate_agent_name(name)
    name = _normalize_agent_name(name)
    user_id = get_effective_user_id()

    try:
        agent_cfg, resolved_user_id, meta = await _resolve_agent_config(name, user_id)

        # BUG-20: Shared agents are treated as public
        is_shared = _is_shared_only(name, user_id)
        if is_shared:
            meta = {}
            visibility = "public"
            owner_id = None
            department_id = None
        else:
            # Lazy migration: auto-create DB record for per-user agents without one
            if not meta and get_paths().user_agent_dir(user_id, name).exists():
                meta = {"visibility": "private", "owner_id": user_id, "department_id": None}
                await _save_agent_meta(name, user_id, meta)
            visibility = meta.get("visibility", "private")
            owner_id = meta.get("owner_id")
            department_id = meta.get("department_id")

        # Check visibility
        if current_user is not None:
            if not check_resource_access(current_user, owner_id, department_id, visibility):
                raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
        elif visibility != "public":
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

        return _agent_config_to_response(
            agent_cfg,
            include_soul=True,
            user_id=resolved_user_id,
            read_only=is_shared or resolved_user_id != user_id,
            visibility=visibility,
            owner_id=owner_id,
            department_id=department_id,
            is_favorited=meta.get("is_favorited", False),
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    except Exception as e:
        logger.error(f"Failed to get agent '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/agents/{name}/favorite",
    summary="Toggle Agent Favorite",
    description="Toggle favorite status for a custom agent.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def toggle_agent_favorite(
    name: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict:
    """Toggle favorite status for a custom agent."""
    _require_agents_api_enabled()
    _validate_agent_name(name)
    name = _normalize_agent_name(name)

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not available")

    try:
        async with sf() as session:
            from ideer.persistence.models.resource_metadata import ResourceMetadata

            stmt = select(ResourceMetadata).where(
                ResourceMetadata.resource_type == "agent",
                ResourceMetadata.resource_id == name,
                ResourceMetadata.owner_id == current_user.id,
            )
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()
            if resource:
                resource.is_favorited = not resource.is_favorited
                resource.version = ResourceMetadata.version + 1
            else:
                raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

            await session.commit()
            return {"success": True, "is_favorited": resource.is_favorited}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle favorite for agent '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/agents",
    response_model=AgentResponse,
    status_code=201,
    summary="Create Custom Agent",
    description="Create a new custom agent with its config and SOUL.md.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def create_agent_endpoint(
    request: AgentCreateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> AgentResponse:
    """Create a new custom agent.

    Args:
        request: The agent creation request.

    Returns:
        The created agent details.

    Raises:
        HTTPException: 409 if agent already exists, 422 if name is invalid.
    """
    _require_agents_api_enabled()
    _validate_agent_name(request.name)
    normalized_name = _normalize_agent_name(request.name)
    user_id = get_effective_user_id()
    paths = get_paths()

    agent_dir = paths.user_agent_dir(user_id, normalized_name)
    legacy_dir = paths.agent_dir(normalized_name)

    if legacy_dir.exists():
        raise HTTPException(status_code=409, detail=f"Agent '{normalized_name}' already exists")

    try:
        # Use exist_ok=False to prevent TOCTOU race on concurrent creation
        agent_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Agent '{normalized_name}' already exists")

    try:
        # Write config.yaml
        config_data: dict = {"name": normalized_name}
        if request.description:
            config_data["description"] = request.description
        if request.model is not None:
            config_data["model"] = request.model
        if request.tool_groups is not None:
            config_data["tool_groups"] = request.tool_groups
        if request.skills is not None:
            config_data["skills"] = request.skills

        config_file = agent_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        # Write SOUL.md
        soul_file = agent_dir / "SOUL.md"
        soul_file.write_text(request.soul, encoding="utf-8")

        # Persist RBAC metadata
        owner_id = current_user.id if current_user else user_id
        dept_id = current_user.department_id if current_user else None
        meta = {
            "visibility": "private",
            "owner_id": owner_id,
            "department_id": dept_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        await _save_agent_meta(normalized_name, user_id, meta)

        logger.info(f"Created agent '{normalized_name}' at {agent_dir}")

        agent_cfg = load_agent_config(normalized_name, user_id=user_id)
        return _agent_config_to_response(
            agent_cfg,
            include_soul=True,
            user_id=user_id,
            read_only=False,
            visibility="private",
            owner_id=owner_id,
            department_id=dept_id,
            is_favorited=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on failure
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
        logger.error(f"Failed to create agent '{request.name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/agents/{name}",
    response_model=AgentResponse,
    summary="Update Custom Agent",
    description="Update an existing custom agent's config and/or SOUL.md.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def update_agent(
    name: str,
    request: AgentUpdateRequest,
    http_request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> AgentResponse:
    """Update an existing custom agent.

    Args:
        name: The agent name.
        request: The update request (all fields optional).

    Returns:
        The updated agent details.

    Raises:
        HTTPException: 404 if agent not found.
    """
    _require_agents_api_enabled()
    _validate_agent_name(name)
    name = _normalize_agent_name(name)
    user_id = get_effective_user_id()

    try:
        agent_cfg = load_agent_config(name, user_id=user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    paths = get_paths()
    agent_dir = paths.user_agent_dir(user_id, name)
    if not agent_dir.exists() and paths.agent_dir(name).exists():
        raise HTTPException(
            status_code=409,
            detail=f"Agent '{name}' is a shared read-only template and cannot be modified.",
        )

    # Lazy-migration: ensure metadata exists before ownership check
    await _ensure_agent_meta(name, user_id)

    # RBAC: check ownership before allowing edit
    meta = await _load_agent_meta(name, user_id, for_owner=user_id)
    if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
        raise HTTPException(status_code=403, detail="You do not have permission to modify this resource")

    # Optimistic locking: verify version matches
    from app.gateway.error_codes import ApiException

    current_version = meta.get("version")
    if current_version is not None and request.version != current_version:
        raise ApiException("VERSION_CONFLICT", "乐观锁冲突，需刷新重试")

    try:
        # Ensure user directory exists before writing files
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Update config if any config fields changed
        # Use model_fields_set to distinguish "field omitted" from "explicitly set to null".
        # This is critical for skills where None means "inherit all" (not "don't change").
        fields_set = request.model_fields_set
        config_changed = bool(fields_set & {"description", "model", "tool_groups", "skills"})

        if config_changed:
            updated: dict = {
                "name": agent_cfg.name,
                "description": request.description if "description" in fields_set else agent_cfg.description,
            }
            new_model = request.model if "model" in fields_set else agent_cfg.model
            if new_model is not None:
                updated["model"] = new_model

            new_tool_groups = request.tool_groups if "tool_groups" in fields_set else agent_cfg.tool_groups
            if new_tool_groups is not None:
                updated["tool_groups"] = new_tool_groups

            # skills: None = inherit all, [] = no skills, ["a","b"] = whitelist
            if "skills" in fields_set:
                new_skills = request.skills
            else:
                new_skills = agent_cfg.skills
            if new_skills is not None:
                updated["skills"] = new_skills

            config_file = agent_dir / "config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(updated, f, default_flow_style=False, allow_unicode=True)

        # Update SOUL.md if provided
        if request.soul is not None:
            soul_path = agent_dir / "SOUL.md"
            soul_path.write_text(request.soul, encoding="utf-8")

        logger.info(f"Updated agent '{name}'")

        await record_audit(
            actor_id=current_user.id,
            action="update",
            resource_type="agent",
            resource_id=name,
            ip_address=http_request.client.host if http_request.client else None,
        )

        refreshed_cfg = load_agent_config(name, user_id=user_id)
        meta = await _load_agent_meta(name, user_id, for_owner=user_id)
        return _agent_config_to_response(
            refreshed_cfg,
            include_soul=True,
            user_id=user_id,
            read_only=False,
            visibility=meta.get("visibility", "private"),
            owner_id=meta.get("owner_id"),
            department_id=meta.get("department_id"),
            is_favorited=meta.get("is_favorited", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


class UserProfileResponse(BaseModel):
    """Response model for the global user profile (USER.md)."""

    content: str | None = Field(default=None, description="USER.md content, or null if not yet created")


class UserProfileUpdateRequest(BaseModel):
    """Request body for setting the global user profile."""

    content: str = Field(default="", description="USER.md content — describes the user's background and preferences")


@router.get(
    "/user-profile",
    response_model=UserProfileResponse,
    summary="Get User Profile",
    description="Read the global USER.md file that is injected into all custom agents.",
)
async def get_user_profile(current_user: UserModel = Depends(get_current_rbac_user)) -> UserProfileResponse:
    """Return the current USER.md content.

    Returns:
        UserProfileResponse with content=None if USER.md does not exist yet.
    """
    _require_agents_api_enabled()

    try:
        user_md_path = get_paths().user_md_file
        if not user_md_path.exists():
            return UserProfileResponse(content=None)
        raw = user_md_path.read_text(encoding="utf-8").strip()
        return UserProfileResponse(content=raw or None)
    except Exception as e:
        logger.error(f"Failed to read user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/user-profile",
    response_model=UserProfileResponse,
    summary="Update User Profile",
    description="Write the global USER.md file that is injected into all custom agents.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def update_user_profile(request: UserProfileUpdateRequest, current_user: UserModel = Depends(get_current_rbac_user)) -> UserProfileResponse:
    """Create or overwrite the global USER.md.

    Args:
        request: The update request with the new USER.md content.

    Returns:
        UserProfileResponse with the saved content.
    """
    _require_agents_api_enabled()

    try:
        paths = get_paths()
        paths.base_dir.mkdir(parents=True, exist_ok=True)
        paths.user_md_file.write_text(request.content, encoding="utf-8")
        logger.info(f"Updated USER.md at {paths.user_md_file}")
        return UserProfileResponse(content=request.content or None)
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/agents/{name}",
    status_code=204,
    summary="Delete Custom Agent",
    description="Delete a custom agent and all its files (config, SOUL.md, memory).",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def delete_agent(
    name: str,
    http_request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> None:
    """Delete a custom agent.

    Args:
        name: The agent name.

    Raises:
        HTTPException: 404 if no per-user copy exists; 409 if only a legacy
            shared copy exists (suggesting the migration script).
    """
    _require_agents_api_enabled()
    _validate_agent_name(name)
    name = _normalize_agent_name(name)
    user_id = get_effective_user_id()
    paths = get_paths()
    agent_dir = paths.user_agent_dir(user_id, name)

    if not agent_dir.exists():
        if paths.agent_dir(name).exists():
            raise HTTPException(
                status_code=409,
                detail=f"Agent '{name}' is a shared read-only template and cannot be deleted.",
            )
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # Lazy-migration: ensure metadata exists before ownership check
    await _ensure_agent_meta(name, user_id)

    # RBAC: check ownership before allowing delete
    meta = await _load_agent_meta(name, user_id, for_owner=user_id)
    if not check_resource_modify(current_user, meta.get("owner_id"), meta.get("department_id")):
        raise HTTPException(status_code=403, detail="You do not have permission to modify this resource")

    try:
        shutil.rmtree(agent_dir)

        # Capture metadata before deletion for audit trail
        meta = await _load_agent_meta(name, user_id, for_owner=user_id)

        sf = get_session_factory()
        if sf is not None:
            try:
                async with sf() as session:
                    from sqlalchemy import delete as sql_delete
                    from sqlalchemy import update as sql_update

                    from ideer.persistence.models.resource_metadata import ResourceMetadata
                    from ideer.persistence.models.visibility_application import VisibilityApplication

                    await session.execute(
                        sql_update(VisibilityApplication)
                        .where(
                            VisibilityApplication.resource_type == "agent",
                            VisibilityApplication.resource_id == name,
                            VisibilityApplication.applicant_id == str(current_user.id),
                            VisibilityApplication.status == "pending",
                        )
                        .values(status="rejected", review_comment="资源已删除，申请自动关闭")
                    )

                    await session.execute(
                        sql_delete(ResourceMetadata).where(
                            ResourceMetadata.resource_type == "agent",
                            ResourceMetadata.resource_id == name,
                            ResourceMetadata.owner_id == user_id,
                        )
                    )
                    await session.commit()
            except Exception:
                logger.warning("Failed to auto-reject pending applications for deleted agent %s", name)
        logger.info(f"Deleted agent '{name}' from {agent_dir}")
        await record_audit(
            actor_id=current_user.id,
            action="delete",
            resource_type="agent",
            resource_id=name,
            detail=meta if meta else None,
            ip_address=http_request.client.host if http_request.client else None,
        )
    except Exception as e:
        logger.error(f"Failed to delete agent '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Export / Import / Stats
# ---------------------------------------------------------------------------


class AgentExportResponse(BaseModel):
    """Response model for agent export."""

    name: str
    config: dict
    soul: str
    meta: dict


class AgentImportRequest(BaseModel):
    """Request body for agent import."""

    name: str = Field(..., description="Agent name (must match ^[A-Za-z0-9-]+$)")
    config: dict = Field(default_factory=dict, description="Agent config.yaml content as dict")
    soul: str = Field(default="", description="SOUL.md content")
    visibility: str = Field(default="private", description="Visibility: private, department, or public")


class AgentStatsResponse(BaseModel):
    """Response model for agent statistics."""

    name: str
    visibility: str
    owner_id: str | None = None
    department_id: str | None = None
    created_at: str | None = None
    has_soul: bool = False
    tool_groups_count: int = 0
    skills_count: int = 0
    total_runs: int = 0
    total_messages: int = 0


@router.post(
    "/agents/{name}/export",
    response_model=AgentExportResponse,
    summary="Export Custom Agent",
    description="Export an agent's config, SOUL.md, and metadata as a JSON bundle.",
)
async def export_agent(
    name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> AgentExportResponse:
    """Export a custom agent for sharing or backup.

    Args:
        name: The agent name.

    Returns:
        Agent config, soul content, and RBAC metadata.
    """
    _require_agents_api_enabled()
    _validate_agent_name(name)
    name = _normalize_agent_name(name)
    user_id = get_effective_user_id()

    try:
        agent_cfg, resolved_user_id, meta = await _resolve_agent_config(name, user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # BUG-20: Shared agents are treated as public
    is_shared = _is_shared_only(name, user_id)
    if is_shared:
        visibility = "public"
        owner_id = None
        department_id = None
        meta = {}
    else:
        if resolved_user_id == user_id:
            await _ensure_agent_meta(name, user_id)
            meta = await _load_agent_meta(name, user_id, for_owner=user_id)
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        department_id = meta.get("department_id")

    # Check visibility
    if current_user is not None:
        if not check_resource_access(current_user, owner_id, department_id, visibility):
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    elif visibility != "public":
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    soul = load_agent_soul(name, user_id=resolved_user_id) or ""

    config_dict: dict = {
        "name": agent_cfg.name,
        "description": agent_cfg.description,
    }
    if agent_cfg.model is not None:
        config_dict["model"] = agent_cfg.model
    if agent_cfg.tool_groups is not None:
        config_dict["tool_groups"] = agent_cfg.tool_groups
    if agent_cfg.skills is not None:
        config_dict["skills"] = agent_cfg.skills

    return AgentExportResponse(
        name=name,
        config=config_dict,
        soul=soul,
        meta=meta,
    )


@router.post(
    "/agents/import",
    response_model=AgentResponse,
    status_code=201,
    summary="Import Custom Agent",
    description="Import an agent from an exported JSON bundle.",
)
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def import_agent(
    request: AgentImportRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> AgentResponse:
    """Import a custom agent from an export bundle.

    Args:
        request: The agent import request with config, soul, and metadata.

    Returns:
        The imported agent details.
    """
    _require_agents_api_enabled()
    _validate_agent_name(request.name)
    normalized_name = _normalize_agent_name(request.name)
    user_id = get_effective_user_id()
    paths = get_paths()

    agent_dir = paths.user_agent_dir(user_id, normalized_name)
    legacy_dir = paths.agent_dir(normalized_name)

    if legacy_dir.exists():
        raise HTTPException(status_code=409, detail=f"Agent '{normalized_name}' already exists")

    try:
        # Use exist_ok=False to prevent TOCTOU race on concurrent creation
        agent_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Agent '{normalized_name}' already exists")

    try:
        # Write config.yaml from the imported config dict
        config_data: dict = {"name": normalized_name}
        for key in ("description", "model", "tool_groups", "skills"):
            if key in request.config:
                config_data[key] = request.config[key]

        config_file = agent_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        # Write SOUL.md
        soul_file = agent_dir / "SOUL.md"
        soul_file.write_text(request.soul, encoding="utf-8")

        # Persist RBAC metadata
        owner_id = current_user.id if current_user else user_id
        dept_id = current_user.department_id if current_user else None
        meta = {
            "visibility": "private",
            "owner_id": owner_id,
            "department_id": dept_id,
            "created_at": datetime.now(UTC).isoformat(),
            "imported": True,
        }
        await _save_agent_meta(normalized_name, user_id, meta)

        logger.info(f"Imported agent '{normalized_name}' to {agent_dir}")

        agent_cfg = load_agent_config(normalized_name, user_id=user_id)
        return _agent_config_to_response(
            agent_cfg,
            include_soul=True,
            user_id=user_id,
            read_only=False,
            visibility="private",
            owner_id=owner_id,
            department_id=dept_id,
            is_favorited=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
        logger.error(f"Failed to import agent '{request.name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/agents/{name}/stats",
    response_model=AgentStatsResponse,
    summary="Get Agent Statistics",
    description="Get statistics and metadata for a custom agent.",
)
async def get_agent_stats(
    name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
) -> AgentStatsResponse:
    """Get statistics for a custom agent.

    Args:
        name: The agent name.

    Returns:
        Agent statistics including visibility, ownership, and counts.
    """
    _require_agents_api_enabled()
    _validate_agent_name(name)
    name = _normalize_agent_name(name)
    user_id = get_effective_user_id()

    try:
        agent_cfg, resolved_user_id, meta = await _resolve_agent_config(name, user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # BUG-20: Shared agents are treated as public
    is_shared = _is_shared_only(name, user_id)
    if is_shared:
        visibility = "public"
        owner_id = None
        department_id = None
        meta = {}
    else:
        if not meta:
            meta = await _load_agent_meta(name, user_id)
        visibility = meta.get("visibility", "private")
        owner_id = meta.get("owner_id")
        department_id = meta.get("department_id")

    # Check visibility
    if current_user is not None:
        if not check_resource_access(current_user, owner_id, department_id, visibility):
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    elif visibility != "public":
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    soul = load_agent_soul(name, user_id=resolved_user_id)

    # Query real run/message stats from the database
    total_runs = 0
    total_messages = 0
    sf = get_session_factory()
    if sf is not None:
        try:
            from ideer.persistence.models.run_event import RunEventRow
            from ideer.persistence.run.model import RunRow

            async with sf() as session:
                # Count runs for this agent (graph_id matches agent name)
                run_count_stmt = select(func.count()).select_from(RunRow).where(RunRow.graph_id == name)
                total_runs = (await session.execute(run_count_stmt)).scalar() or 0

                # Count messages for this agent's runs
                msg_count_stmt = select(func.count()).select_from(RunEventRow).join(RunRow, RunRow.run_id == RunEventRow.run_id).where(RunRow.graph_id == name, RunEventRow.category == "message")
                total_messages = (await session.execute(msg_count_stmt)).scalar() or 0
        except Exception:
            logger.warning("Could not query run stats for agent %s", name, exc_info=True)

    return AgentStatsResponse(
        name=name,
        # Default to 'private' when no metadata exists (secure-by-default for pre-RBAC agents)
        visibility=meta.get("visibility", "private"),
        owner_id=meta.get("owner_id"),
        department_id=meta.get("department_id"),
        created_at=meta.get("created_at"),
        has_soul=bool(soul and soul.strip()),
        tool_groups_count=len(agent_cfg.tool_groups) if agent_cfg.tool_groups else 0,
        skills_count=len(agent_cfg.skills) if agent_cfg.skills else 0,
        total_runs=total_runs,
        total_messages=total_messages,
    )
