"""Admin skill applications API routes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.gateway.authz import get_current_rbac_user
from app.gateway.deps import get_config
from ideer.config.app_config import AppConfig
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.skill_application import SkillApplication, SkillApplicationResponse, SkillApplicationStatus
from ideer.persistence.models.user import UserModel, UserRole
from ideer.skills.storage import get_or_new_skill_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-skill-applications"])


class SkillApplicationsResponse(BaseModel):
    applications: list[SkillApplicationResponse]


class ReviewApplicationRequest(BaseModel):
    action: str = Field(..., pattern="^(approved|rejected)$")
    comment: str = ""


@router.get("/skill-applications", response_model=SkillApplicationsResponse)
async def list_applications(
    status: str | None = None,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> SkillApplicationsResponse:
    """List skill applications (filtered by status)."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillApplication)

            if status:
                stmt = stmt.where(SkillApplication.status == status)

            # Department admins can only see department-level applications in their own department
            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                stmt = stmt.where(
                    SkillApplication.request_level == "department",
                    SkillApplication.department_id == current_user.department_id,
                )

            stmt = stmt.order_by(SkillApplication.submitted_at.desc())
            result = await session.execute(stmt)
            applications = result.scalars().all()

            return SkillApplicationsResponse(
                applications=[
                    SkillApplicationResponse(
                        id=app.id,
                        skill_id=app.skill_id,
                        skill_name=app.skill_name,
                        applicant_id=app.applicant_id,
                        request_level=app.request_level,
                        department_id=app.department_id,
                        reason=app.reason,
                        status=app.status,
                        submitted_at=str(app.submitted_at) if app.submitted_at else None,
                        reviewed_by=app.reviewed_by,
                        reviewed_at=str(app.reviewed_at) if app.reviewed_at else None,
                        review_comment=app.review_comment,
                    )
                    for app in applications
                ]
            )
    except Exception as e:
        logger.error("Failed to list skill applications: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/skill-applications/{application_id}", response_model=SkillApplicationResponse)
async def get_application(
    application_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> SkillApplicationResponse:
    """Get a specific skill application."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillApplication).where(SkillApplication.id == application_id)
            result = await session.execute(stmt)
            application = result.scalar_one_or_none()

            if not application:
                raise HTTPException(status_code=404, detail="Application not found")

            return SkillApplicationResponse(
                id=application.id,
                skill_id=application.skill_id,
                skill_name=application.skill_name,
                applicant_id=application.applicant_id,
                request_level=application.request_level,
                department_id=application.department_id,
                reason=application.reason,
                status=application.status,
                submitted_at=str(application.submitted_at) if application.submitted_at else None,
                reviewed_by=application.reviewed_by,
                reviewed_at=str(application.reviewed_at) if application.reviewed_at else None,
                review_comment=application.review_comment,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get skill application %s: %s", application_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/skill-applications/{application_id}")
async def review_application(
    application_id: str,
    request: ReviewApplicationRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
    config: AppConfig = Depends(get_config),
) -> dict[str, Any]:
    """Review a skill application (approve or reject)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillApplication).where(SkillApplication.id == application_id)
            result = await session.execute(stmt)
            application = result.scalar_one_or_none()

            if not application:
                raise HTTPException(status_code=404, detail="Application not found")

            if application.status != SkillApplicationStatus.PENDING:
                raise HTTPException(status_code=400, detail="Application is not pending")

            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                if application.request_level == "public":
                    raise HTTPException(status_code=403, detail="Department admins cannot approve public-level applications")
                if application.department_id and application.department_id != current_user.department_id:
                    raise HTTPException(status_code=403, detail="Department admins can only review applications from their own department")

            from datetime import datetime

            application.status = request.action
            application.reviewed_by = current_user.id
            application.reviewed_at = datetime.now(datetime.UTC)
            application.review_comment = request.comment

            # Update skill visibility when approved
            if request.action == SkillApplicationStatus.APPROVED:
                await _update_skill_visibility(config, application.skill_id, application.request_level)

            await session.commit()

            # Invalidate cache after successful commit
            if request.action == SkillApplicationStatus.APPROVED:
                storage = get_or_new_skill_storage(app_config=config)
                if hasattr(storage, "clear_cache"):
                    await storage.clear_cache()

        return {"message": f"Application {request.action} successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to review skill application %s: %s", application_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _update_skill_visibility(config: AppConfig, skill_id: str, new_visibility: str) -> None:
    """Update skill's .meta.json visibility after approval.

    Uses file locking to prevent race conditions when multiple admins
    approve applications for the same skill concurrently.

    Raises on failure so the caller can roll back the DB transaction.
    """
    import fcntl
    import json
    import os
    import tempfile

    storage = get_or_new_skill_storage(app_config=config)
    if not hasattr(storage, "get_custom_skill_dir"):
        return

    skill_dir = storage.get_custom_skill_dir(skill_id)
    meta_file = skill_dir / ".meta.json"
    lock_file = skill_dir / ".meta.lock"

    await asyncio.to_thread(skill_dir.mkdir, parents=True, exist_ok=True)

    def _update_with_lock():
        with open(lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                meta = {}
                if meta_file.exists():
                    try:
                        content = meta_file.read_text(encoding="utf-8")
                        meta = json.loads(content)
                    except json.JSONDecodeError:
                        meta = {}

                meta["visibility"] = new_visibility

                fd, tmp_path = tempfile.mkstemp(dir=skill_dir, suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)
                    os.replace(tmp_path, meta_file)
                except BaseException:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    await asyncio.to_thread(_update_with_lock)

    logger.info("Skill '%s' visibility updated to %s via approval", skill_id, new_visibility)
