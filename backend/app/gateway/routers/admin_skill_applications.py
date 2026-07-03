"""Admin skill applications API routes (DEPRECATED).

These endpoints are deprecated and will be removed after the frontend
migrates to the unified visibility_applications endpoints.

All endpoints now return 410 Gone with a message directing callers to
use the new /api/visibility-applications endpoints instead.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/admin", tags=["admin-skill-applications"])


@router.get("/skill-applications")
async def list_applications() -> None:
    """List skill applications (DEPRECATED).

    Use GET /api/visibility-applications instead.
    """
    raise HTTPException(
        status_code=410,
        detail={
            "message": "This endpoint is deprecated.",
            "replacement": "Use GET /api/visibility-applications instead.",
        },
    )


@router.get("/skill-applications/{application_id}")
async def get_application(application_id: str) -> None:
    """Get a specific skill application (DEPRECATED).

    Use GET /api/visibility-applications?resource_id={resource_id} instead.
    """
    raise HTTPException(
        status_code=410,
        detail={
            "message": "This endpoint is deprecated.",
            "replacement": "Use GET /api/visibility-applications?resource_id={resource_id} instead.",
        },
    )


@router.put("/skill-applications/{application_id}")
async def review_application(application_id: str) -> None:
    """Review a skill application (DEPRECATED).

    Use PUT /api/visibility-applications/{application_id} instead.
    """
    raise HTTPException(
        status_code=410,
        detail={
            "message": "This endpoint is deprecated.",
            "replacement": "Use PUT /api/visibility-applications/{application_id} instead.",
        },
    )
