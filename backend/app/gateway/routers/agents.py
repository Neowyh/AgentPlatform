"""CRUD API for custom agents."""

import json
import logging
import re
import shutil
from datetime import UTC, datetime

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.gateway.authz import get_optional_rbac_user
from ideer.config.agents_api_config import get_agents_api_config
from ideer.config.agents_config import AgentConfig, list_custom_agents, load_agent_config, load_agent_soul
from ideer.config.paths import get_paths
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import UserModel, UserRole
from ideer.runtime.user_context import get_effective_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agents"])


# ---------------------------------------------------------------------------
# RBAC helpers — now backed by real UserModel from authz.py
# ---------------------------------------------------------------------------

VALID_ROLES = tuple(UserRole)


def _check_resource_modify(resource_owner_id: str | None, resource_department_id: str | None, current_user: UserModel | None) -> None:
    """Raise 403 if *current_user* is not allowed to modify the resource.

    Rules:
    - super_admin: always allowed
    - department_admin: allowed if same department
    - user: allowed only if they own the resource
    - No user context (auth disabled): always allowed
    """
    if current_user is None:
        return  # auth not wired — allow everything

    if current_user.role == UserRole.SUPER_ADMIN:
        return

    if current_user.role == UserRole.DEPARTMENT_ADMIN:
        if resource_department_id and resource_department_id == current_user.department_id:
            return
        if resource_owner_id and resource_owner_id == current_user.id:
            return
        raise HTTPException(status_code=403, detail="Department admins can only modify resources in their own department")

    # Regular user
    if resource_owner_id and resource_owner_id == current_user.id:
        return
    raise HTTPException(status_code=403, detail="You can only modify your own resources")


def _can_set_visibility(visibility: str, current_user: UserModel | None) -> bool:
    """Check whether the user is allowed to set the given visibility level.

    - private: anyone
    - department: department_admin or super_admin
    - public: super_admin only
    - No user context: always allowed
    """
    if current_user is None:
        return True

    if visibility == "public":
        return current_user.role == UserRole.SUPER_ADMIN
    if visibility == "department":
        return current_user.role in (UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
    return True  # private — anyone


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
            detail=("Custom-agent management API is disabled. Set agents_api.enabled=true to expose agent and user-profile routes over HTTP."),
        )


def _is_shared_only(agent_name: str, user_id: str) -> bool:
    """Return True if the agent exists only in the shared read-only template directory."""
    paths = get_paths()
    return paths.agent_dir(agent_name).exists() and not paths.user_agent_dir(user_id, agent_name).exists()


def _agent_meta_path(agent_name: str, user_id: str):
    """Return the path to the agent's RBAC metadata JSON file."""
    paths = get_paths()
    return paths.user_agent_dir(user_id, agent_name) / ".meta.json"


def _load_agent_meta(agent_name: str, user_id: str) -> dict:
    """Load agent RBAC metadata from disk. Returns empty dict if missing."""
    meta_file = _agent_meta_path(agent_name, user_id)
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_agent_meta(agent_name: str, user_id: str, meta: dict) -> None:
    """Persist agent RBAC metadata to disk."""
    meta_file = _agent_meta_path(agent_name, user_id)
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_visible_to_user(visibility: str, owner_id: str | None, department_id: str | None, current_user: UserModel) -> bool:
    """Check whether an agent with the given visibility is visible to *current_user*.

    Visibility rules:
    - private: only the owner
    - department: same department members + owner
    - public: everyone
    """
    if visibility == "public":
        return True
    if current_user.role == UserRole.SUPER_ADMIN:
        return True
    if owner_id and owner_id == current_user.id:
        return True
    if visibility == "department":
        if current_user.department_id and department_id and current_user.department_id == department_id:
            return True
    return False


def _agent_config_to_response(
    agent_cfg: AgentConfig,
    include_soul: bool = False,
    *,
    user_id: str | None = None,
    read_only: bool = False,
    visibility: str = "private",
    owner_id: str | None = None,
    department_id: str | None = None,
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
        responses: list[AgentResponse] = []
        for a in agents:
            # Load agent metadata for visibility filtering
            meta = _load_agent_meta(a.name, user_id)
            visibility = meta.get("visibility", "private")
            owner_id = meta.get("owner_id")
            dept_id = meta.get("department_id")

            # Filter by visibility when auth is active
            if current_user is not None and not _is_visible_to_user(visibility, owner_id, dept_id, current_user):
                continue

            responses.append(
                _agent_config_to_response(
                    a,
                    include_soul=True,
                    user_id=user_id,
                    read_only=_is_shared_only(a.name, user_id),
                    visibility=visibility,
                    owner_id=owner_id,
                    department_id=dept_id,
                )
            )

        return AgentsListResponse(agents=responses)
    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@router.get(
    "/agents/check",
    summary="Check Agent Name",
    description="Validate an agent name and check if it is available (case-insensitive).",
)
async def check_agent_name(name: str) -> dict:
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
async def get_agent(name: str) -> AgentResponse:
    """Get a specific custom agent by name.

    Args:
        name: The agent name.

    Returns:
        Agent details including SOUL.md content.

    Raises:
        HTTPException: 404 if agent not found.
    """
    _require_agents_api_enabled()
    _validate_agent_name(name)
    name = _normalize_agent_name(name)
    user_id = get_effective_user_id()

    try:
        agent_cfg = load_agent_config(name, user_id=user_id)
        meta = _load_agent_meta(name, user_id)
        return _agent_config_to_response(
            agent_cfg,
            include_soul=True,
            user_id=user_id,
            read_only=_is_shared_only(name, user_id),
            visibility=meta.get("visibility", "private"),
            owner_id=meta.get("owner_id"),
            department_id=meta.get("department_id"),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    except Exception as e:
        logger.error(f"Failed to get agent '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")


@router.post(
    "/agents",
    response_model=AgentResponse,
    status_code=201,
    summary="Create Custom Agent",
    description="Create a new custom agent with its config and SOUL.md.",
)
async def create_agent_endpoint(
    request: AgentCreateRequest,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
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

    # Validate visibility permissions
    if not _can_set_visibility(request.visibility, current_user):
        raise HTTPException(
            status_code=403,
            detail=f"Your role does not have permission to set visibility to '{request.visibility}'",
        )

    agent_dir = paths.user_agent_dir(user_id, normalized_name)
    legacy_dir = paths.agent_dir(normalized_name)

    if agent_dir.exists() or legacy_dir.exists():
        raise HTTPException(status_code=409, detail=f"Agent '{normalized_name}' already exists")

    try:
        agent_dir.mkdir(parents=True, exist_ok=True)

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
            "visibility": request.visibility,
            "owner_id": owner_id,
            "department_id": dept_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        _save_agent_meta(normalized_name, user_id, meta)

        logger.info(f"Created agent '{normalized_name}' at {agent_dir}")

        agent_cfg = load_agent_config(normalized_name, user_id=user_id)
        return _agent_config_to_response(
            agent_cfg,
            include_soul=True,
            user_id=user_id,
            read_only=False,
            visibility=request.visibility,
            owner_id=owner_id,
            department_id=dept_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on failure
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
        logger.error(f"Failed to create agent '{request.name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.put(
    "/agents/{name}",
    response_model=AgentResponse,
    summary="Update Custom Agent",
    description="Update an existing custom agent's config and/or SOUL.md.",
)
async def update_agent(
    name: str,
    request: AgentUpdateRequest,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
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

    # RBAC: check ownership before allowing edit
    meta = _load_agent_meta(name, user_id)
    _check_resource_modify(meta.get("owner_id"), meta.get("department_id"), current_user)

    try:
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

        refreshed_cfg = load_agent_config(name, user_id=user_id)
        meta = _load_agent_meta(name, user_id)
        return _agent_config_to_response(
            refreshed_cfg,
            include_soul=True,
            user_id=user_id,
            read_only=False,
            visibility=meta.get("visibility", "private"),
            owner_id=meta.get("owner_id"),
            department_id=meta.get("department_id"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")


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
async def get_user_profile() -> UserProfileResponse:
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
        raise HTTPException(status_code=500, detail=f"Failed to read user profile: {str(e)}")


@router.put(
    "/user-profile",
    response_model=UserProfileResponse,
    summary="Update User Profile",
    description="Write the global USER.md file that is injected into all custom agents.",
)
async def update_user_profile(request: UserProfileUpdateRequest) -> UserProfileResponse:
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
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")


@router.delete(
    "/agents/{name}",
    status_code=204,
    summary="Delete Custom Agent",
    description="Delete a custom agent and all its files (config, SOUL.md, memory).",
)
async def delete_agent(
    name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
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

    # RBAC: check ownership before allowing delete
    meta = _load_agent_meta(name, user_id)
    _check_resource_modify(meta.get("owner_id"), meta.get("department_id"), current_user)

    try:
        shutil.rmtree(agent_dir)
        logger.info(f"Deleted agent '{name}' from {agent_dir}")
    except Exception as e:
        logger.error(f"Failed to delete agent '{name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")


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
async def export_agent(name: str) -> AgentExportResponse:
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
        agent_cfg = load_agent_config(name, user_id=user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    meta = _load_agent_meta(name, user_id)
    soul = load_agent_soul(name, user_id=user_id) or ""

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
async def import_agent(
    request: AgentImportRequest,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
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

    # Validate visibility permissions
    if not _can_set_visibility(request.visibility, current_user):
        raise HTTPException(
            status_code=403,
            detail=f"Your role does not have permission to set visibility to '{request.visibility}'",
        )

    agent_dir = paths.user_agent_dir(user_id, normalized_name)
    legacy_dir = paths.agent_dir(normalized_name)

    if agent_dir.exists() or legacy_dir.exists():
        raise HTTPException(status_code=409, detail=f"Agent '{normalized_name}' already exists")

    try:
        agent_dir.mkdir(parents=True, exist_ok=True)

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
            "visibility": request.visibility,
            "owner_id": owner_id,
            "department_id": dept_id,
            "created_at": datetime.now(UTC).isoformat(),
            "imported": True,
        }
        _save_agent_meta(normalized_name, user_id, meta)

        logger.info(f"Imported agent '{normalized_name}' to {agent_dir}")

        agent_cfg = load_agent_config(normalized_name, user_id=user_id)
        return _agent_config_to_response(
            agent_cfg,
            include_soul=True,
            user_id=user_id,
            read_only=False,
            visibility=request.visibility,
            owner_id=owner_id,
            department_id=dept_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
        logger.error(f"Failed to import agent '{request.name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to import agent: {str(e)}")


@router.get(
    "/agents/{name}/stats",
    response_model=AgentStatsResponse,
    summary="Get Agent Statistics",
    description="Get statistics and metadata for a custom agent.",
)
async def get_agent_stats(name: str) -> AgentStatsResponse:
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
        agent_cfg = load_agent_config(name, user_id=user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    meta = _load_agent_meta(name, user_id)
    soul = load_agent_soul(name, user_id=user_id)

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
            logger.debug("Could not query run stats for agent %s", name, exc_info=True)

    return AgentStatsResponse(
        name=name,
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
