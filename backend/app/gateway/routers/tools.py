"""Tool management APIs for iDeer software factory."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.gateway.authz import get_current_rbac_user, require_role
from ideer.config.app_config import get_app_config
from ideer.persistence.models.user import UserModel, UserRole
from ideer.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolTestRequest(BaseModel):
    params: dict = {}


class ToolConfigUpdate(BaseModel):
    config: dict = {}


@router.get("")
async def list_tools(
    group: str | None = None,
    search: str | None = None,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List all registered tools with metadata. Any authenticated user can view."""
    registry = get_tool_registry()

    if search:
        tools = registry.search(search)
    elif group:
        tools = registry.list_by_group(group)
    else:
        tools = registry.list_all()

    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "group": t.group,
                "requires_network": t.requires_network,
                "configurable": t.configurable,
                "config_schema": t.config_schema,
                "param_schema": t.param_schema,
            }
            for t in tools
        ],
        "total": len(tools),
    }


@router.get("/groups")
async def list_tool_groups(
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List all tool groups. Any authenticated user can view."""
    registry = get_tool_registry()
    tools = registry.list_all()
    groups: dict[str, list[str]] = {}
    for t in tools:
        groups.setdefault(t.group, []).append(t.name)
    return {"groups": groups}


@router.get("/{tool_name}")
async def get_tool_detail(
    tool_name: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Get tool detail including parameter schema."""
    registry = get_tool_registry()
    tool = registry.get(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return {
        "name": tool.name,
        "description": tool.description,
        "group": tool.group,
        "requires_network": tool.requires_network,
        "configurable": tool.configurable,
        "config_schema": tool.config_schema,
        "param_schema": tool.param_schema,
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
    registry = get_tool_registry()
    tool_info = registry.get(tool_name)
    if tool_info is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    # Load the actual tool instance and invoke it
    try:
        from ideer.tools.tools import get_available_tools

        config = get_app_config()
        available = get_available_tools(config)
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

        # Execute the tool with provided params
        try:
            if hasattr(tool_instance, "ainvoke"):
                result = await tool_instance.ainvoke(body.params)
            else:
                result = tool_instance.invoke(body.params)
            return {
                "success": True,
                "tool": tool_name,
                "result": str(result)[:2000],
            }
        except Exception as e:
            return {
                "success": False,
                "tool": tool_name,
                "error": str(e),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to test tool %s: %s", tool_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test tool: {e}")


@router.put("/{tool_name}/config")
@require_role(UserRole.SUPER_ADMIN)
async def update_tool_config(
    tool_name: str,
    body: ToolConfigUpdate,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update tool configuration. Requires super_admin role."""
    registry = get_tool_registry()
    tool_info = registry.get(tool_name)
    if tool_info is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    if not tool_info.configurable:
        raise HTTPException(status_code=400, detail=f"Tool '{tool_name}' is not configurable")

    logger.info("Tool config update for %s: %s", tool_name, body.config)
    return {
        "success": True,
        "tool": tool_name,
        "message": "Config update acknowledged.",
    }
