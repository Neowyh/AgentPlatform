"""Admin management APIs for iDeer software factory."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.gateway.authz import get_current_rbac_user, require_role
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import DepartmentModel, UserModel, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def get_admin_stats(
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Get admin dashboard statistics."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        user_count = (await session.execute(select(func.count()).select_from(UserModel))).scalar() or 0
        dept_count = (await session.execute(select(func.count()).select_from(DepartmentModel))).scalar() or 0

    return {
        "total_users": user_count,
        "total_departments": dept_count,
        "total_agents": 0,  # Agents are file-based; counted via agents API
        "total_tools": 0,  # Tools are file-based; counted via tools API
        "total_skills": 0,  # Skills are file-based; counted via skills API
    }


class UpdateRoleRequest(BaseModel):
    role: str


class CreateDepartmentRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: str = Field("", max_length=500)


class UpdateDepartmentRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)


class CreateUserRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=6, max_length=128)
    username: str = Field(..., max_length=100)
    role: str = Field(default=UserRole.USER)
    department_id: str | None = Field(None)


# --- User Management ---


@router.post("/users")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def create_user(
    body: CreateUserRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Create a new user.

    super_admin can create any user in any department.
    department_admin can only create regular users in their own department.
    """
    if body.role not in tuple(UserRole):
        raise HTTPException(status_code=400, detail=f"Invalid role: '{body.role}'. Valid roles: {', '.join(r.value for r in UserRole)}")

    if not body.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty")

    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: '{body.role}'")

    department_id = body.department_id

    if current_user.role == UserRole.DEPARTMENT_ADMIN:
        if role in (UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN):
            raise HTTPException(status_code=403, detail="Cannot create super_admin or department_admin users")
        role = UserRole.USER
        department_id = current_user.department_id

    if department_id is not None:
        sf = get_session_factory()
        if sf is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        async with sf() as session:
            dept = await session.get(DepartmentModel, department_id)
            if dept is None:
                raise HTTPException(status_code=404, detail="Department not found")

    from app.gateway.deps import get_local_provider

    try:
        auth_user = await get_local_provider().create_user(
            email=body.email,
            password=body.password,
            system_role=role.value,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Email already exists")

    user_id = str(auth_user.id)

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    async with sf() as session:
        rbac_user = UserModel(
            id=user_id,
            username=body.username.strip(),
            role=role.value,
            department_id=department_id,
        )
        try:
            session.add(rbac_user)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Username already exists")

    logger.info("User created: id=%s, email=%s, role=%s, by=%s", user_id, body.email, role.value, current_user.id)
    return {
        "id": user_id,
        "email": body.email,
        "username": body.username.strip(),
        "role": role.value,
        "department_id": department_id,
    }


@router.get("/users")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def list_users(
    department_id: str | None = None,
    role: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List users with optional filters.

    super_admin sees all users. department_admin sees only their own department.
    """
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Validate role filter
    if role is not None and role not in tuple(UserRole):
        raise HTTPException(status_code=400, detail=f"Invalid role filter: '{role}'. Valid roles: {', '.join(r.value for r in UserRole)}")

    # department_admin: force scope to own department, ignore query params
    if current_user.role == UserRole.DEPARTMENT_ADMIN:
        if not current_user.department_id:
            return {"users": [], "total": 0, "limit": limit, "offset": offset}
        department_id = current_user.department_id

    async with sf() as session:
        # Count total matching users
        count_stmt = select(func.count()).select_from(UserModel)
        if department_id:
            count_stmt = count_stmt.where(UserModel.department_id == department_id)
        if role:
            count_stmt = count_stmt.where(UserModel.role == role)
        total = (await session.execute(count_stmt)).scalar() or 0

        # Fetch paginated results (eagerly load department to avoid lazy-load after session close)
        stmt = select(UserModel).options(selectinload(UserModel.department))
        if department_id:
            stmt = stmt.where(UserModel.department_id == department_id)
        if role:
            stmt = stmt.where(UserModel.role == role)
        stmt = stmt.order_by(UserModel.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        users = result.scalars().all()

        return {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "role": u.role,
                    "department_id": u.department_id,
                    "department_name": u.department.name if u.department else None,
                    "disabled": u.disabled,
                    "created_at": str(u.created_at) if u.created_at else None,
                    "last_login": str(u.last_login) if u.last_login else None,
                }
                for u in users
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.put("/users/{user_id}/role")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update a user's role.

    super_admin can change any role. department_admin can only change
    role within their own department and cannot promote to super_admin.
    """
    if body.role not in tuple(UserRole):
        raise HTTPException(status_code=400, detail="Invalid role")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        # Lock the target user row to prevent concurrent modification
        stmt = select(UserModel).where(UserModel.id == user_id)
        try:
            stmt = stmt.with_for_update()
        except Exception:
            pass  # SQLite doesn't support FOR UPDATE
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # department_admin: restrict scope
        if current_user.role == UserRole.DEPARTMENT_ADMIN:
            if user_id == current_user.id:
                raise HTTPException(status_code=400, detail="Cannot change your own role")
            if user.role == UserRole.SUPER_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot modify super_admin")
            if user.role == UserRole.DEPARTMENT_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot modify another department_admin")
            if body.role == UserRole.SUPER_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot promote to super_admin")
            if user.department_id != current_user.department_id:
                raise HTTPException(status_code=403, detail="Cannot modify users outside your department")
            if not user.department_id:
                raise HTTPException(status_code=403, detail="Cannot modify users without a department")

        # Prevent removing the last active super_admin (including self-demotion)
        if user.role == UserRole.SUPER_ADMIN and body.role != UserRole.SUPER_ADMIN:
            # Use FOR UPDATE to serialize concurrent demotion attempts
            count_stmt = select(func.count()).select_from(UserModel).where(UserModel.role == UserRole.SUPER_ADMIN, UserModel.disabled.is_not(True))
            try:
                count_stmt = count_stmt.with_for_update()
            except Exception:
                pass  # SQLite fallback — less safe but functional
            super_admin_count = (await session.execute(count_stmt)).scalar() or 0
            if super_admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last active super_admin")

        old_role = user.role
        user.role = UserRole(body.role)

        # Also update the legacy users table to keep system_role in sync
        from ideer.persistence.user.model import UserRow

        user_row = await session.get(UserRow, user_id)
        if user_row is not None:
            user_row.system_role = body.role

        await session.commit()

    logger.warning("Role changed: user=%s, old_role=%s, new_role=%s, by=%s", user_id, old_role, body.role, current_user.id)
    return {"success": True, "user_id": user_id, "new_role": body.role}


@router.delete("/users/{user_id}")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def disable_user(
    user_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Disable a user.

    super_admin can disable anyone. department_admin can only disable
    regular users within their own department.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        # Lock the target user row to prevent concurrent modification
        stmt = select(UserModel).where(UserModel.id == user_id)
        try:
            stmt = stmt.with_for_update()
        except Exception:
            pass  # SQLite doesn't support FOR UPDATE
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # department_admin: restrict scope
        if current_user.role == UserRole.DEPARTMENT_ADMIN:
            if user.role == UserRole.SUPER_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot disable super_admin")
            if user.role == UserRole.DEPARTMENT_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot disable another department_admin")
            if user.department_id != current_user.department_id:
                raise HTTPException(status_code=403, detail="Cannot disable users outside your department")
            if not user.department_id:
                raise HTTPException(status_code=403, detail="Cannot disable users without a department")

        # Prevent disabling the last active super_admin
        if user.role == UserRole.SUPER_ADMIN:
            count_stmt = select(func.count()).select_from(UserModel).where(UserModel.role == UserRole.SUPER_ADMIN, UserModel.disabled.is_not(True))
            try:
                count_stmt = count_stmt.with_for_update()
            except Exception:
                pass  # SQLite fallback
            active_super_admin_count = (await session.execute(count_stmt)).scalar() or 0
            if active_super_admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot disable the last active super_admin")

        user.disabled = True
        await session.commit()

    logger.warning("User disabled: user_id=%s, by=%s", user_id, current_user.id)
    return {"success": True}


# --- Department Management ---


@router.get("/departments")
async def list_departments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List all departments. Any authenticated user can view.

    Design decision: member_count is redacted for non-admin users to avoid
    leaking organizational structure details (e.g. team sizes) to regular
    users who only need department names for assignment purposes.
    """
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Clamp limit and offset to prevent abuse
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    async with sf() as session:
        # Count total
        count_stmt = select(func.count()).select_from(DepartmentModel)
        total = (await session.execute(count_stmt)).scalar() or 0

        # Fetch paginated results
        stmt = select(DepartmentModel).order_by(DepartmentModel.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        departments = result.scalars().all()

        # Get member counts per department
        dept_ids = [d.id for d in departments]
        member_counts: dict[str, int] = {}
        if dept_ids:
            count_stmt = select(UserModel.department_id, func.count()).where(UserModel.department_id.in_(dept_ids), UserModel.disabled.is_not(True)).group_by(UserModel.department_id)
            count_result = await session.execute(count_stmt)
            member_counts = {row[0]: row[1] for row in count_result.all()}

    return {
        "departments": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "created_at": str(d.created_at) if d.created_at else None,
                "member_count": member_counts.get(d.id, 0) if current_user.role in (UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN) else None,
                "agent_count": 0,  # Agents are file-based
                "skill_count": 0,  # Skills are file-based
            }
            for d in departments
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/departments")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def create_department(
    body: CreateDepartmentRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Create a new department. Requires super_admin role."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Department name cannot be empty")

    # Strip whitespace to prevent duplicate-looking departments
    name = body.name.strip()

    dept_id = str(uuid.uuid4())
    async with sf() as session:
        # Check for duplicate name
        existing = await session.execute(select(DepartmentModel).where(DepartmentModel.name == name))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Department name already exists")

        dept = DepartmentModel(id=dept_id, name=name, description=body.description)
        try:
            session.add(dept)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Department name already exists")

    return {"id": dept_id, "name": name, "description": body.description}


@router.put("/departments/{dept_id}")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
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
            if not body.name.strip():
                raise HTTPException(status_code=400, detail="Department name cannot be empty")
            # Strip whitespace to prevent duplicate-looking departments
            name = body.name.strip()
            # Check for duplicate name
            dup = await session.execute(select(DepartmentModel).where(DepartmentModel.name == name, DepartmentModel.id != dept_id))
            if dup.scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail="Department name already exists")
            dept.name = name
        if body.description is not None:
            dept.description = body.description
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Department name already exists")

    return {"success": True}


@router.delete("/departments/{dept_id}")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
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

        # Check if department has active (non-disabled) members
        member_count = await session.execute(
            select(func.count())
            .select_from(UserModel)
            .where(
                UserModel.department_id == dept_id,
                UserModel.disabled.is_not(True),
            )
        )
        if (member_count.scalar() or 0) > 0:
            raise HTTPException(status_code=400, detail="Cannot delete department with members. Reassign members first.")

        # Clear department_id on disabled users still referencing this department
        # to prevent orphaned foreign key references.
        from sqlalchemy import update as sql_update

        await session.execute(sql_update(UserModel).where(UserModel.department_id == dept_id).values(department_id=None))

        try:
            await session.delete(dept)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Cannot delete department due to remaining database references. Ensure all members have been reassigned.")

    return {"success": True}
