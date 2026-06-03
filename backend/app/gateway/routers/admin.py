"""Admin management APIs for iDeer software factory."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    department_id: str | None = None


class UpdateRoleRequest(BaseModel):
    role: str


class CreateDepartmentRequest(BaseModel):
    name: str
    description: str = ""


class UpdateDepartmentRequest(BaseModel):
    name: str | None = None
    description: str | None = None


# --- User Management ---


@router.get("/users")
async def list_users(
    department_id: str | None = None,
    role: str | None = None,
    # current_user = Depends(require_super_admin),  # uncomment when auth dep is ready
):
    """List all users with optional filters. Requires super_admin role."""
    # TODO: Implement with actual DB queries
    return {"users": [], "total": 0}


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    # current_user = Depends(require_super_admin),
):
    """Update a user's role. Requires super_admin role."""
    if body.role not in ("user", "department_admin", "super_admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    # TODO: Implement DB update
    return {"success": True}


@router.delete("/users/{user_id}")
async def disable_user(
    user_id: str,
    # current_user = Depends(require_super_admin),
):
    """Disable a user. Requires super_admin role."""
    # TODO: Implement
    return {"success": True}


# --- Department Management ---


@router.get("/departments")
async def list_departments():
    """List all departments."""
    # TODO: Implement
    return {"departments": [], "total": 0}


@router.post("/departments")
async def create_department(
    body: CreateDepartmentRequest,
    # current_user = Depends(require_super_admin),
):
    """Create a new department. Requires super_admin role."""
    dept_id = str(uuid.uuid4())
    # TODO: Implement DB insert
    return {"id": dept_id, "name": body.name}


@router.put("/departments/{dept_id}")
async def update_department(
    dept_id: str,
    body: UpdateDepartmentRequest,
    # current_user = Depends(require_super_admin),
):
    """Update a department. Requires super_admin role."""
    # TODO: Implement
    return {"success": True}


@router.delete("/departments/{dept_id}")
async def delete_department(
    dept_id: str,
    # current_user = Depends(require_super_admin),
):
    """Delete a department. Requires super_admin role."""
    # TODO: Implement
    return {"success": True}
