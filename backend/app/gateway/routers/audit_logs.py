"""Audit log query API — super_admin only."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.gateway.authz import get_current_rbac_user, require_role
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.audit_log import AuditLog
from ideer.persistence.models.user import UserModel, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/audit-logs", tags=["audit"])


class AuditLogResponse(BaseModel):
    id: str
    actor_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    detail: str | None = None
    ip_address: str | None = None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditLogListResponse)
@require_role(UserRole.SUPER_ADMIN)
async def list_audit_logs(
    request: Request,
    actor_id: str | None = Query(None, description="Filter by actor user ID"),
    action: str | None = Query(None, description="Filter by action type"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    start_date: str | None = Query(None, description="ISO datetime start (inclusive)"),
    end_date: str | None = Query(None, description="ISO datetime end (inclusive)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> AuditLogListResponse:
    """List audit logs with filtering and pagination."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            conditions = []
            if actor_id:
                conditions.append(AuditLog.actor_id == actor_id)
            if action:
                conditions.append(AuditLog.action == action)
            if resource_type:
                conditions.append(AuditLog.resource_type == resource_type)
            if start_date:
                conditions.append(AuditLog.created_at >= datetime.fromisoformat(start_date))
            if end_date:
                conditions.append(AuditLog.created_at <= datetime.fromisoformat(end_date))

            count_stmt = select(func.count()).select_from(AuditLog)
            if conditions:
                count_stmt = count_stmt.where(*conditions)
            total = (await session.execute(count_stmt)).scalar() or 0

            offset = (page - 1) * page_size
            query = select(AuditLog).offset(offset).limit(page_size).order_by(AuditLog.created_at.desc())
            if conditions:
                query = query.where(*conditions)

            result = await session.execute(query)
            rows = result.scalars().all()

            items = [
                AuditLogResponse(
                    id=r.id,
                    actor_id=r.actor_id,
                    action=r.action,
                    resource_type=r.resource_type,
                    resource_id=r.resource_id,
                    detail=r.detail,
                    ip_address=r.ip_address,
                    created_at=str(r.created_at) if r.created_at else "",
                )
                for r in rows
            ]

            return AuditLogListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to query audit logs")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{log_id}", response_model=AuditLogResponse)
@require_role(UserRole.SUPER_ADMIN)
async def get_audit_log_detail(
    log_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> AuditLogResponse:
    """Get a single audit log entry with full detail."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(AuditLog).where(AuditLog.id == log_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if not row:
                raise HTTPException(status_code=404, detail="Audit log not found")

            return AuditLogResponse(
                id=row.id,
                actor_id=row.actor_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                detail=row.detail,
                ip_address=row.ip_address,
                created_at=str(row.created_at) if row.created_at else "",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to query audit log")
        raise HTTPException(status_code=500, detail="Internal server error")
