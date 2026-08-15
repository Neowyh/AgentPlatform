"""Visibility applications API routes.

Unified approval workflow for resource visibility changes across all
resource types (tool, skill, workflow, agent).

Endpoints:
  POST   /api/visibility-applications          — submit a new application
  PUT    /api/visibility-applications/{id}      — approve or reject (optimistic lock)
  PUT    /api/visibility-applications/{id}/withdraw — withdraw own pending application
  GET    /api/visibility-applications           — list pending applications (admin view)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError

from app.gateway.audit import record_audit
from app.gateway.authz import get_current_rbac_user, require_role
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.user import ResourceVisibility, UserModel, UserRole
from ideer.persistence.models.visibility_application import (
    VisibilityApplication,
    VisibilityApplicationStatus,
)
from ideer.resources.service import (
    ResourceConflict,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visibility-applications", tags=["visibility-applications"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateApplicationRequest(BaseModel):
    resource_type: str = Field(..., pattern="^(tool|skill|workflow|agent)$")
    resource_id: str
    target_visibility: ResourceVisibility
    reason: str = ""


class ReviewApplicationRequest(BaseModel):
    action: str = Field(..., pattern="^(approved|rejected)$")
    comment: str = ""
    version: int


class ApplicationResponse(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    applicant_id: str
    current_visibility: str
    target_visibility: str
    department_id: str | None = None
    reason: str
    status: str
    submitted_at: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_comment: str | None = None
    version: int


class ApplicationsResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int
    page: int
    page_size: int


def _to_response(app: VisibilityApplication) -> ApplicationResponse:
    return ApplicationResponse(
        id=app.id,
        resource_type=app.resource_type,
        resource_id=app.resource_id,
        applicant_id=app.applicant_id,
        current_visibility=app.current_visibility,
        target_visibility=app.target_visibility,
        department_id=app.department_id,
        reason=app.reason,
        status=app.status,
        submitted_at=str(app.submitted_at) if app.submitted_at else None,
        reviewed_by=app.reviewed_by,
        reviewed_at=str(app.reviewed_at) if app.reviewed_at else None,
        review_comment=app.review_comment,
        version=app.version,
    )


# ---------------------------------------------------------------------------
# POST /api/visibility-applications — submit application
# ---------------------------------------------------------------------------


@router.post("", response_model=ApplicationResponse, status_code=201)
async def create_application(
    request: CreateApplicationRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> ApplicationResponse:
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            # Check for an existing pending application for the same resource
            # (scoped to the applicant so same-named resources owned by
            # different users have independent application flows)
            pending_check = select(VisibilityApplication).where(
                VisibilityApplication.resource_type == request.resource_type,
                VisibilityApplication.resource_id == request.resource_id,
                VisibilityApplication.applicant_id == str(current_user.id),
                VisibilityApplication.status == VisibilityApplicationStatus.PENDING,
            )
            existing = (await session.execute(pending_check)).scalar_one_or_none()
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="A pending application already exists for this resource",
                )

            # Fetch current visibility from resource_metadata.
            # resource_id is only unique per owner, so collect all matches
            # instead of scalar_one_or_none() (which would raise 500 on
            # same-named resources owned by different users).
            resource_stmt = select(ResourceMetadata).where(
                ResourceMetadata.resource_type == request.resource_type,
                ResourceMetadata.resource_id == request.resource_id,
            )
            candidates = (await session.execute(resource_stmt)).scalars().all()
            if not candidates:
                raise HTTPException(status_code=404, detail="Resource not found")

            # Only the resource owner may submit a visibility application
            resource = next(
                (r for r in candidates if r.owner_id == str(current_user.id)),
                None,
            )
            if resource is None:
                raise HTTPException(
                    status_code=403,
                    detail="Only resource owner can submit visibility application",
                )

            # Check target_visibility != current_visibility
            if request.target_visibility.value == resource.visibility:
                raise HTTPException(
                    status_code=400,
                    detail="Target visibility cannot be the same as current visibility",
                )

            application = VisibilityApplication(
                id=str(uuid.uuid4()),
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                applicant_id=str(current_user.id),
                current_visibility=resource.visibility,
                target_visibility=request.target_visibility.value,
                department_id=resource.department_id,
                reason=request.reason,
                status=VisibilityApplicationStatus.PENDING.value,
                version=1,
                submitted_at=datetime.now(UTC),
            )
            session.add(application)
            await session.commit()
            await session.refresh(application)

            return _to_response(application)
    except HTTPException:
        raise
    except IntegrityError as e:
        orig_msg = str(getattr(e, "orig", e)).lower()
        if "unique constraint" in orig_msg:
            raise HTTPException(
                status_code=409,
                detail="A pending application already exists for this resource",
            )
        if "foreign key" in orig_msg:
            logger.warning("FK violation creating visibility application: %s", orig_msg)
            raise HTTPException(
                status_code=400,
                detail="Referenced record not found. Please check the resource data.",
            )
        if "not null constraint" in orig_msg:
            logger.error("NOT NULL constraint creating visibility application: %s", orig_msg)
            raise HTTPException(
                status_code=400,
                detail="A required field is missing. Please try again or contact support.",
            )
        logger.error("Unexpected IntegrityError creating visibility application: %s", orig_msg)
        raise HTTPException(
            status_code=400,
            detail="A data constraint was violated. Please try again or contact support.",
        )
    except Exception as e:
        logger.error("Failed to create visibility application: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


class WithdrawRequest(BaseModel):
    version: int = Field(..., description="Current version for optimistic locking")


# ---------------------------------------------------------------------------
# PUT /api/visibility-applications/{id}/withdraw — withdraw own application
# ---------------------------------------------------------------------------


@router.put("/{application_id}/withdraw")
async def withdraw_application(
    application_id: str,
    body: WithdrawRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict:
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(VisibilityApplication).where(VisibilityApplication.id == application_id)
            application = (await session.execute(stmt)).scalar_one_or_none()
            if not application:
                raise HTTPException(status_code=404, detail="Application not found")

            if application.applicant_id != str(current_user.id):
                raise HTTPException(status_code=403, detail="You can only withdraw your own applications")

            if application.status != VisibilityApplicationStatus.PENDING:
                raise HTTPException(status_code=400, detail="Only pending applications can be withdrawn")

            # Optimistic lock
            if application.version != body.version:
                raise HTTPException(
                    status_code=409,
                    detail=f"Version mismatch: expected {application.version}, got {body.version}",
                )

            application.status = VisibilityApplicationStatus.WITHDRAWN
            application.version += 1
            await session.commit()

            return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to withdraw visibility application %s: %s", application_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# PUT /api/visibility-applications/{id} — approve or reject (optimistic lock)
# ---------------------------------------------------------------------------


@router.put("/{application_id}", response_model=ApplicationResponse)
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def review_application(
    application_id: str,
    request: ReviewApplicationRequest,
    http_request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> ApplicationResponse:

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(VisibilityApplication).where(VisibilityApplication.id == application_id)
            application = (await session.execute(stmt)).scalar_one_or_none()
            if not application:
                raise HTTPException(status_code=404, detail="Application not found")

            if application.status != VisibilityApplicationStatus.PENDING:
                raise HTTPException(status_code=400, detail="Application is not pending")

            if application.version != request.version:
                raise HTTPException(
                    status_code=409,
                    detail=f"Version mismatch: expected {application.version}, got {request.version}",
                )

            # dept_admin cannot review own application
            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                if application.applicant_id == str(current_user.id):
                    raise HTTPException(status_code=403, detail="Cannot review your own application")
                if current_user.department_id and application.department_id != current_user.department_id:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only review applications from your own department",
                    )

            canonical_resource_id = getattr(application, "canonical_resource_id", None)
            if isinstance(canonical_resource_id, str) and canonical_resource_id:
                from app.gateway.routers.resources import _resource_actor

                reviewed = await ResourceService(
                    session,
                    _resource_actor(current_user),
                ).review_visibility_application(
                    application_id,
                    approve=request.action == VisibilityApplicationStatus.APPROVED.value,
                    comment=request.comment,
                    expected_version=request.version,
                )
                await session.commit()
                await session.refresh(reviewed)
                await record_audit(
                    actor_id=current_user.id,
                    action="visibility_change",
                    resource_type=reviewed.resource_type,
                    resource_id=reviewed.canonical_resource_id,
                    detail={
                        "old_visibility": reviewed.current_visibility,
                        "target_visibility": reviewed.target_visibility,
                        "status": reviewed.status,
                        "requested_version": reviewed.requested_version,
                        "requested_hash": reviewed.requested_hash,
                    },
                    ip_address=http_request.client.host if http_request.client else None,
                )
                return _to_response(reviewed)

            application.status = request.action
            application.reviewed_by = str(current_user.id)
            application.reviewed_at = datetime.now(UTC)
            application.review_comment = request.comment
            application.version += 1

            # On approval, sync visibility to resource_metadata. Scope by the
            # applicant (the resource owner) so same-named resources owned by
            # other users are never touched.
            if request.action == VisibilityApplicationStatus.APPROVED.value:
                await session.execute(
                    sql_update(ResourceMetadata)
                    .where(
                        ResourceMetadata.resource_type == application.resource_type,
                        ResourceMetadata.resource_id == application.resource_id,
                        ResourceMetadata.owner_id == application.applicant_id,
                    )
                    .values(
                        visibility=application.target_visibility,
                        version=ResourceMetadata.version + 1,
                    )
                )

            await session.commit()
            await session.refresh(application)

            if request.action == VisibilityApplicationStatus.APPROVED.value:
                await record_audit(
                    actor_id=current_user.id,
                    action="visibility_change",
                    resource_type=application.resource_type,
                    resource_id=application.resource_id,
                    detail={"old_visibility": application.current_visibility, "new_visibility": application.target_visibility, "status": "approved"},
                    ip_address=http_request.client.host if http_request.client else None,
                )
            else:
                await record_audit(
                    actor_id=current_user.id,
                    action="visibility_change",
                    resource_type=application.resource_type,
                    resource_id=application.resource_id,
                    detail={"old_visibility": application.current_visibility, "target_visibility": application.target_visibility, "status": "rejected"},
                    ip_address=http_request.client.host if http_request.client else None,
                )

            return _to_response(application)
    except HTTPException:
        raise
    except ResourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResourcePermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ResourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as e:
        logger.error("Failed to review visibility application %s: %s", application_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# GET /api/visibility-applications — list pending applications (admin view)
# ---------------------------------------------------------------------------


@router.get("", response_model=ApplicationsResponse)
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def list_applications(
    status: str | None = None,
    resource_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> ApplicationsResponse:

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(VisibilityApplication)

            if status:
                stmt = stmt.where(VisibilityApplication.status == status)
            else:
                stmt = stmt.where(VisibilityApplication.status == VisibilityApplicationStatus.PENDING)

            if resource_type:
                stmt = stmt.where(VisibilityApplication.resource_type == resource_type)

            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                if current_user.department_id is None:
                    stmt = stmt.where(VisibilityApplication.department_id.is_(None))
                else:
                    stmt = stmt.where(VisibilityApplication.department_id == str(current_user.department_id))

            # Count total
            from sqlalchemy import func

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar() or 0

            # Apply pagination
            offset = (page - 1) * page_size
            stmt = stmt.order_by(VisibilityApplication.submitted_at.desc()).offset(offset).limit(page_size)
            result = await session.execute(stmt)
            applications = result.scalars().all()

            return ApplicationsResponse(
                applications=[_to_response(app) for app in applications],
                total=total,
                page=page,
                page_size=page_size,
            )
    except Exception as e:
        logger.error("Failed to list visibility applications: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
