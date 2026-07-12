"""Tool management APIs for iDeer software factory."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.gateway.authz import check_resource_access, get_current_rbac_user, get_optional_rbac_user, require_role
from ideer.config.app_config import get_app_config
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import UserModel, UserRole
from ideer.tools.tools import get_available_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolTestRequest(BaseModel):
    params: dict = Field(default_factory=dict)


async def _load_tool_meta(tool_name: str) -> dict:
    """Load tool RBAC metadata from resource_metadata table."""
    sf = get_session_factory()
    if sf is not None:
        try:
            async with sf() as session:
                from ideer.persistence.models.resource_metadata import ResourceMetadata

                stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == "tool",
                    ResourceMetadata.resource_id == tool_name,
                )
                result = await session.execute(stmt)
                resource = result.scalar_one_or_none()
                if resource:
                    return {
                        "visibility": resource.visibility,
                        "owner_id": resource.owner_id,
                        "department_id": resource.department_id,
                    }
        except Exception:
            logger.error("Failed to load tool meta for %s", tool_name, exc_info=True)
    return {}


@router.get("")
async def list_tools(
    search: str | None = None,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """List all available tools with metadata. Filters by visibility when auth is active."""
    config = get_app_config()
    tools = get_available_tools(app_config=config)

    if search:
        sl = search.lower()
        tools = [t for t in tools if sl in (t.name or "").lower() or sl in (t.description or "").lower()]

    # Batch-load tool metadata from resource_metadata table
    tool_meta_map: dict[str, dict] = {}
    tool_names = [t.name for t in tools]
    sf = get_session_factory()
    if sf is not None and tool_names:
        try:
            async with sf() as session:
                from ideer.persistence.models.resource_metadata import ResourceMetadata

                stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == "tool",
                    ResourceMetadata.resource_id.in_(tool_names),
                )
                result = await session.execute(stmt)
                for r in result.scalars().all():
                    tool_meta_map[r.resource_id] = {
                        "visibility": r.visibility,
                        "owner_id": r.owner_id,
                        "department_id": r.department_id,
                    }
        except Exception:
            logger.error("Failed to batch-load tool metadata", exc_info=True)

    # Filter by visibility
    filtered = []
    for t in tools:
        meta = tool_meta_map.get(t.name, {})
        visibility = meta.get("visibility", "public")
        owner_id = meta.get("owner_id")
        dept_id = meta.get("department_id")

        if current_user is not None:
            if not check_resource_access(current_user, owner_id, dept_id, visibility):
                continue
        elif visibility != "public":
            continue

        filtered.append(t)

    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description or "",
                "group": "",
                "requires_network": False,
                "configurable": False,
                "config_schema": {},
                "param_schema": _safe_schema_json(t.get_input_schema()) if hasattr(t, "get_input_schema") else {},
                "config": {},
            }
            for t in filtered
        ],
        "total": len(filtered),
    }


def _safe_schema_json(schema_cls: type) -> dict:
    """Return a JSON schema dict from a Pydantic model class, falling back to {} on failure."""
    try:
        return schema_cls.model_json_schema()
    except Exception:
        return {}


@router.get("/{tool_name}")
async def get_tool_detail(
    tool_name: str,
    current_user: UserModel | None = Depends(get_optional_rbac_user),
):
    """Get tool detail including parameter schema."""
    config = get_app_config()
    tools = get_available_tools(app_config=config)
    tool = next((t for t in tools if t.name == tool_name), None)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    # Check visibility
    meta = await _load_tool_meta(tool_name)
    visibility = meta.get("visibility", "public")
    owner_id = meta.get("owner_id")
    dept_id = meta.get("department_id")

    if current_user is not None:
        if not check_resource_access(current_user, owner_id, dept_id, visibility):
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    elif visibility != "public":
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return {
        "name": tool.name,
        "description": tool.description or "",
        "group": "",
        "requires_network": False,
        "configurable": False,
        "config_schema": {},
        "param_schema": _safe_schema_json(tool.get_input_schema()) if hasattr(tool, "get_input_schema") else {},
        "config": {},
    }


@router.post("/{tool_name}/test")
@require_role(UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
async def test_tool(
    tool_name: str,
    body: ToolTestRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Test-execute a tool with given parameters.

    Requires department_admin or super_admin role.
    """
    # Check visibility
    meta = await _load_tool_meta(tool_name)
    visibility = meta.get("visibility", "public")
    owner_id = meta.get("owner_id")
    dept_id = meta.get("department_id")
    if not check_resource_access(current_user, owner_id, dept_id, visibility):
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    # Load the actual tool instance and invoke it
    try:
        from ideer.tools.tools import get_available_tools

        config = get_app_config()
        available = get_available_tools(app_config=config)
        tool_instance = None
        for t in available:
            if hasattr(t, "name") and t.name == tool_name:
                tool_instance = t
                break

        if tool_instance is None:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' is not currently available (check config.yaml)",
            )

        # Execute the tool with provided params (BUG-19: with timeout)
        try:
            _TEST_TIMEOUT = 300.0  # 5 minutes max for tool testing
            if hasattr(tool_instance, "ainvoke"):
                result = await asyncio.wait_for(tool_instance.ainvoke(body.params), timeout=_TEST_TIMEOUT)
            else:
                # Run synchronous invoke in a thread to avoid blocking the event loop
                result = await asyncio.wait_for(asyncio.to_thread(tool_instance.invoke, body.params), timeout=_TEST_TIMEOUT)
            return {
                "success": True,
                "tool": tool_name,
                "result": str(result)[:2000],
            }
        except Exception as e:
            logger.error("Tool execution failed for %s: %s", tool_name, e, exc_info=True)
            return {
                "success": False,
                "tool": tool_name,
                "error": "Tool execution failed. Check server logs for details.",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to test tool %s: %s", tool_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
