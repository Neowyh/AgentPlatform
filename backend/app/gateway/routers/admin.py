"""Admin management APIs for iDeer software factory."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.gateway.authz import get_current_rbac_user, require_role
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import DepartmentModel, UserModel, UserRole

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
@require_role(UserRole.SUPER_ADMIN)
async def list_users(
    department_id: str | None = None,
    role: str | None = None,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List all users with optional filters. Requires super_admin role."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(UserModel)
        if department_id:
            stmt = stmt.where(UserModel.department_id == department_id)
        if role:
            stmt = stmt.where(UserModel.role == role)
        stmt = stmt.order_by(UserModel.created_at.desc())
        result = await session.execute(stmt)
        users = result.scalars().all()

    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "department_id": u.department_id,
                "created_at": str(u.created_at) if u.created_at else None,
                "last_login": str(u.last_login) if u.last_login else None,
            }
            for u in users
        ],
        "total": len(users),
    }


@router.put("/users/{user_id}/role")
@require_role(UserRole.SUPER_ADMIN)
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update a user's role. Requires super_admin role."""
    if body.role not in tuple(UserRole):
        raise HTTPException(status_code=400, detail="Invalid role")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user.role = body.role
        await session.commit()

    return {"success": True, "user_id": user_id, "new_role": body.role}


@router.delete("/users/{user_id}")
@require_role(UserRole.SUPER_ADMIN)
async def disable_user(
    user_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Disable a user by removing their RBAC profile. Requires super_admin role."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        await session.delete(user)
        await session.commit()

    return {"success": True}


# --- Department Management ---


@router.get("/departments")
async def list_departments(
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List all departments. Any authenticated user can view."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(DepartmentModel).order_by(DepartmentModel.created_at.desc())
        result = await session.execute(stmt)
        departments = result.scalars().all()

    return {
        "departments": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "created_at": str(d.created_at) if d.created_at else None,
            }
            for d in departments
        ],
        "total": len(departments),
    }


@router.post("/departments")
@require_role(UserRole.SUPER_ADMIN)
async def create_department(
    body: CreateDepartmentRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Create a new department. Requires super_admin role."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    dept_id = str(uuid.uuid4())
    async with sf() as session:
        # Check for duplicate name
        existing = await session.execute(select(DepartmentModel).where(DepartmentModel.name == body.name))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Department name already exists")

        dept = DepartmentModel(id=dept_id, name=body.name, description=body.description)
        session.add(dept)
        await session.commit()

    return {"id": dept_id, "name": body.name, "description": body.description}


@router.put("/departments/{dept_id}")
@require_role(UserRole.SUPER_ADMIN)
async def update_department(
    dept_id: str,
    body: UpdateDepartmentRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update a department. Requires super_admin role."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(DepartmentModel).where(DepartmentModel.id == dept_id)
        result = await session.execute(stmt)
        dept = result.scalar_one_or_none()
        if dept is None:
            raise HTTPException(status_code=404, detail="Department not found")

        if body.name is not None:
            # Check for duplicate name
            dup = await session.execute(select(DepartmentModel).where(DepartmentModel.name == body.name, DepartmentModel.id != dept_id))
            if dup.scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail="Department name already exists")
            dept.name = body.name
        if body.description is not None:
            dept.description = body.description
        await session.commit()

    return {"success": True}


@router.delete("/departments/{dept_id}")
@require_role(UserRole.SUPER_ADMIN)
async def delete_department(
    dept_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Delete a department. Requires super_admin role."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(DepartmentModel).where(DepartmentModel.id == dept_id)
        result = await session.execute(stmt)
        dept = result.scalar_one_or_none()
        if dept is None:
            raise HTTPException(status_code=404, detail="Department not found")

        # Check if department has members
        member_count = await session.execute(select(func.count()).select_from(UserModel).where(UserModel.department_id == dept_id))
        if (member_count.scalar() or 0) > 0:
            raise HTTPException(status_code=400, detail="Cannot delete department with members. Reassign members first.")

        await session.delete(dept)
        await session.commit()

    return {"success": True}
