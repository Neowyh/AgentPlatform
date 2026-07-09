"""Admin management APIs for iDeer software factory."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.gateway.authz import get_current_rbac_user, require_role
from app.gateway.rbac_users import create_auth_user_with_rbac
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.audit_log import AuditLog
from ideer.persistence.models.resource_metadata import ResourceMetadata
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

        resource_counts = (await session.execute(select(ResourceMetadata.resource_type, func.count()).where(ResourceMetadata.deleted_at.is_(None)).group_by(ResourceMetadata.resource_type))).all()
        type_counts = {row[0]: row[1] for row in resource_counts}

        audit_count = (await session.execute(select(func.count()).select_from(AuditLog))).scalar() or 0

    return {
        "total_users": user_count,
        "total_departments": dept_count,
        "total_agents": type_counts.get("agent", 0),
        "total_tools": type_counts.get("tool", 0),
        "total_skills": type_counts.get("skill", 0),
        "total_resources": sum(type_counts.values()),
        "audit_logs": audit_count,
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


class UpdateUserRequest(BaseModel):
    username: str | None = Field(None, max_length=100)
    department_id: str | None = Field(None)


# --- User Management ---


@router.post("/users", status_code=201)
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

    role = UserRole(body.role)

    department_id = body.department_id

    if current_user.role == UserRole.DEPARTMENT_ADMIN:
        if role in (UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN):
            raise HTTPException(status_code=403, detail="Cannot create super_admin or department_admin users")
        if not current_user.department_id:
            raise HTTPException(status_code=400, detail="No department assigned")
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

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    async with sf() as session:
        try:
            auth_user = await create_auth_user_with_rbac(
                session,
                email=body.email,
                password=body.password,
                username=body.username.strip(),
                role=role,
                department_id=department_id,
            )
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Email or username already exists")

    user_id = str(auth_user.id)

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
    http_request: Request,
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
            logger.debug("with_for_update not supported, skipping row lock", exc_info=True)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # department_admin: restrict scope
        if current_user.role == UserRole.DEPARTMENT_ADMIN:
            if user.role == UserRole.SUPER_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot modify super_admin")
            if user.role == UserRole.DEPARTMENT_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot modify another department_admin")
            if user.department_id != current_user.department_id:
                raise HTTPException(status_code=403, detail="Cannot modify users outside your department")
            if not user.department_id:
                raise HTTPException(status_code=403, detail="Cannot modify users without a department")

        # Prevent disabling the last active super_admin
        if user.role == UserRole.SUPER_ADMIN and not user.disabled:
            count_stmt = select(func.count()).select_from(UserModel).where(UserModel.role == UserRole.SUPER_ADMIN, UserModel.disabled.is_not(True))
            try:
                count_stmt = count_stmt.with_for_update()
            except Exception:
                logger.debug("with_for_update not supported, skipping row lock", exc_info=True)
            active_super_admin_count = (await session.execute(count_stmt)).scalar() or 0
            if active_super_admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot disable the last active super_admin")

        user.disabled = not user.disabled
        await session.commit()

        new_status = "disabled" if user.disabled else "enabled"

    logger.warning("User status toggled: user_id=%s, new_status=%s, by=%s", user_id, new_status, current_user.id)
    return {"success": True, "user_id": user_id, "disabled": user.disabled}


# --- Department Management ---


@router.get("/departments")
@require_role(UserRole.SUPER_ADMIN)
async def list_departments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """List all departments. Requires super_admin role."""
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
@require_role(UserRole.SUPER_ADMIN)
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


@router.get("/departments/{dept_id}/resources")
@require_role(UserRole.SUPER_ADMIN)
async def get_department_resources(
    dept_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Get affected resources when deleting a department. Requires super_admin role."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        # Verify department exists
        stmt = select(DepartmentModel).where(DepartmentModel.id == dept_id)
        result = await session.execute(stmt)
        dept = result.scalar_one_or_none()
        if dept is None:
            raise HTTPException(status_code=404, detail="Department not found")

        # Get all active resources in this department
        resources_stmt = select(ResourceMetadata).where(
            ResourceMetadata.department_id == dept_id,
            ResourceMetadata.deleted_at.is_(None),
        )
        resources_result = await session.execute(resources_stmt)
        resources = resources_result.scalars().all()

        return {
            "department_id": dept_id,
            "department_name": dept.name,
            "resources": [
                {
                    "id": r.id,
                    "resource_type": r.resource_type,
                    "resource_id": r.resource_id,
                    "visibility": r.visibility,
                    "owner_id": r.owner_id,
                }
                for r in resources
            ],
            "total_count": len(resources),
        }


class DeleteDepartmentRequest(BaseModel):
    target_dept_id: str | None = Field(None)


@router.delete("/departments/{dept_id}")
@require_role(UserRole.SUPER_ADMIN)
async def delete_department(
    dept_id: str,
    body: DeleteDepartmentRequest | None = None,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Delete a department. Requires super_admin role.

    Optional target_dept_id: if provided, resources will be reassigned to this department
    instead of being downgraded to private visibility.
    """
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

        # Resource handling: reassign to target_dept_id if provided, otherwise downgrade to private
        target_dept_id = body.target_dept_id if body else None

        if target_dept_id:
            # Verify target department exists
            target_dept_stmt = select(DepartmentModel).where(DepartmentModel.id == target_dept_id)
            target_dept_result = await session.execute(target_dept_stmt)
            target_dept = target_dept_result.scalar_one_or_none()
            if target_dept is None:
                raise HTTPException(status_code=404, detail="Target department not found")

            # Reassign department-level resources to target department
            await session.execute(
                sql_update(ResourceMetadata)
                .where(
                    ResourceMetadata.department_id == dept_id,
                    ResourceMetadata.visibility == "department",
                    ResourceMetadata.deleted_at.is_(None),
                )
                .values(department_id=target_dept_id)
            )
            # Also reassign private resources to target department
            await session.execute(sql_update(ResourceMetadata).where(ResourceMetadata.department_id == dept_id, ResourceMetadata.deleted_at.is_(None)).values(department_id=target_dept_id))
        else:
            # Lifecycle: downgrade department-level resources to private before deleting department
            await session.execute(
                sql_update(ResourceMetadata)
                .where(
                    ResourceMetadata.department_id == dept_id,
                    ResourceMetadata.visibility == "department",
                    ResourceMetadata.deleted_at.is_(None),
                )
                .values(visibility="private", department_id=None)
            )
            # Also clear department_id on all resources in this department
            await session.execute(sql_update(ResourceMetadata).where(ResourceMetadata.department_id == dept_id, ResourceMetadata.deleted_at.is_(None)).values(department_id=None))

        try:
            await session.delete(dept)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Cannot delete department due to remaining database references. Ensure all members have been reassigned.")

    return {"success": True}
