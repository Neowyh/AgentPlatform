"""Assistants compatibility endpoints.

Provides LangGraph Platform-compatible assistants API backed by the
``langgraph.json`` graph registry and ``config.yaml`` agent definitions.

This is a minimal stub that satisfies the ``useStream`` React hook's
initialization requirements (``assistants.search()`` and ``assistants.get()``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.gateway.authz import require_permission
from ideer.resources.mode import ResourceCatalogMode, get_resource_catalog_mode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistants", tags=["assistants-compat"])


class AssistantResponse(BaseModel):
    assistant_id: str
    graph_id: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    created_at: str = ""
    updated_at: str = ""
    version: int = 1


class AssistantSearchRequest(BaseModel):
    graph_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] | None = None
    limit: int = 10
    offset: int = 0


def _get_default_assistant() -> AssistantResponse:
    """Return the default lead_agent assistant."""
    now = datetime.now(UTC).isoformat()
    return AssistantResponse(
        assistant_id="lead_agent",
        graph_id="lead_agent",
        name="lead_agent",
        config={},
        metadata={"created_by": "system"},
        description="iDeer lead agent",
        created_at=now,
        updated_at=now,
        version=1,
    )


def _list_assistants() -> list[AssistantResponse]:
    """List all available assistants from config."""
    assistants = [_get_default_assistant()]
    if get_resource_catalog_mode() is ResourceCatalogMode.CANONICAL:
        return assistants

    # Also include custom agents from config.yaml agents directory
    try:
        from ideer.config.agents_config import list_custom_agents

        for agent_cfg in list_custom_agents():
            now = datetime.now(UTC).isoformat()
            assistants.append(
                AssistantResponse(
                    assistant_id=agent_cfg.name,
                    graph_id="lead_agent",  # All agents use the same graph
                    name=agent_cfg.name,
                    config={},
                    metadata={"created_by": "user"},
                    description=agent_cfg.description or "",
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            )
    except Exception:
        logger.debug("Could not load custom agents for assistants list")

    return assistants


async def _list_canonical_assistants(request: Request) -> list[AssistantResponse]:
    """List only UUID Agent resources visible to the authenticated caller."""

    if get_resource_catalog_mode() is ResourceCatalogMode.LEGACY:
        return []

    from sqlalchemy import select

    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel
    from ideer.resources.service import ResourceAction, ResourceActor, ResourceService

    user_id = getattr(getattr(request.state, "user", None), "id", None)
    session_factory = get_session_factory()
    if user_id is None or session_factory is None:
        return []
    async with session_factory() as session:
        user = (
            await session.execute(
                select(UserModel).where(
                    UserModel.id == str(user_id),
                    UserModel.disabled.is_not(True),
                )
            )
        ).scalar_one_or_none()
        if user is None:
            return []
        actor = ResourceActor(
            user_id=str(user.id),
            department_id=str(user.department_id) if user.department_id is not None else None,
            role=str(user.role),
            permissions=frozenset({ResourceAction.READ}),
        )
        page = await ResourceService(session, actor).list_visible(resource_type="agent", limit=200)
        return [
            AssistantResponse(
                assistant_id=resource.id,
                graph_id="lead_agent",
                name=resource.display_name,
                config={},
                metadata={
                    "resource_id": resource.id,
                    "slug": resource.slug,
                    "owner_id": resource.owner_id,
                    "visibility": resource.visibility,
                },
                description=resource.display_name,
                created_at=resource.created_at.isoformat(),
                updated_at=resource.updated_at.isoformat(),
                version=resource.latest_version,
            )
            for resource in page.items
            if resource.latest_version > 0
        ]


@router.post("/search", response_model=list[AssistantResponse])
@require_permission("assistants", "read")
async def search_assistants(request: Request, body: AssistantSearchRequest | None = None) -> list[AssistantResponse]:
    """Search assistants.

    Returns all registered assistants (lead_agent + custom agents from config).
    """
    assistants = [*_list_assistants(), *await _list_canonical_assistants(request)]

    if body and body.graph_id:
        assistants = [a for a in assistants if a.graph_id == body.graph_id]
    if body and body.name:
        assistants = [a for a in assistants if body.name.lower() in a.name.lower()]

    offset = body.offset if body else 0
    limit = body.limit if body else 10
    return assistants[offset : offset + limit]


@router.get("/{assistant_id}", response_model=AssistantResponse)
@require_permission("assistants", "read")
async def get_assistant_compat(request: Request, assistant_id: str) -> AssistantResponse:
    """Get an assistant by ID."""
    for a in [*_list_assistants(), *await _list_canonical_assistants(request)]:
        if a.assistant_id == assistant_id:
            return a
    raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")


@router.get("/{assistant_id}/graph")
@require_permission("assistants", "read")
async def get_assistant_graph(request: Request, assistant_id: str) -> dict:
    """Get the graph structure for an assistant.

    Returns a minimal graph description. Full graph introspection is
    not supported in the Gateway — this stub satisfies SDK validation.
    """
    found = any(a.assistant_id == assistant_id for a in [*_list_assistants(), *await _list_canonical_assistants(request)])
    if not found:
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")

    return {
        "graph_id": "lead_agent",
        "nodes": [],
        "edges": [],
    }


@router.get("/{assistant_id}/schemas")
@require_permission("assistants", "read")
async def get_assistant_schemas(request: Request, assistant_id: str) -> dict:
    """Get JSON schemas for an assistant's input/output/state.

    Returns empty schemas — full introspection not supported in Gateway.
    """
    found = any(a.assistant_id == assistant_id for a in [*_list_assistants(), *await _list_canonical_assistants(request)])
    if not found:
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")

    return {
        "graph_id": "lead_agent",
        "input_schema": {},
        "output_schema": {},
        "state_schema": {},
        "config_schema": {},
    }
