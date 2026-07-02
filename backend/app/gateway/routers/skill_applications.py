"""Skill application API routes."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.gateway.authz import get_current_rbac_user
from app.gateway.deps import get_config
from ideer.config.app_config import AppConfig
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.skill_application import SkillApplication, SkillApplicationResponse, SkillApplicationStatus
from ideer.persistence.models.user import UserModel
from ideer.skills.storage import get_or_new_skill_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skill-applications"])


class SubmitApplicationRequest(BaseModel):
    request_level: str = Field(..., pattern="^(department|public)$")
    reason: str = ""


@router.post("/{skill_id}/apply", response_model=SkillApplicationResponse)
async def submit_application(
    skill_id: str,
    request: SubmitApplicationRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
    config: AppConfig = Depends(get_config),
) -> SkillApplicationResponse:
    """Submit a skill open application."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Look up actual skill name
    storage = get_or_new_skill_storage(app_config=config)
    skills = storage.load_skills(enabled_only=False)
    matched_skill = next((s for s in skills if s.name == skill_id), None)
    if not matched_skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    skill_name = matched_skill.name

    try:
        async with sf() as session:
            stmt = select(SkillApplication).where(
                SkillApplication.skill_id == skill_id,
                SkillApplication.applicant_id == current_user.id,
                SkillApplication.status == SkillApplicationStatus.PENDING,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                raise HTTPException(status_code=400, detail="You already have a pending application for this skill")

            application = SkillApplication(
                id=str(uuid.uuid4()),
                skill_id=skill_id,
                skill_name=skill_name,
                applicant_id=current_user.id,
                request_level=request.request_level,
                department_id=current_user.department_id,
                reason=request.reason,
                status=SkillApplicationStatus.PENDING,
            )
            session.add(application)
            await session.commit()
            await session.refresh(application)

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
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit skill application for %s: %s", skill_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{skill_id}/application", response_model=SkillApplicationResponse | None)
async def get_application(
    skill_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> SkillApplicationResponse | None:
    """Get the current user's application for a skill."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = (
                select(SkillApplication)
                .where(
                    SkillApplication.skill_id == skill_id,
                    SkillApplication.applicant_id == current_user.id,
                )
                .order_by(SkillApplication.submitted_at.desc())
            )
            result = await session.execute(stmt)
            application = result.scalar_one_or_none()

            if not application:
                return None

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
    except Exception as e:
        logger.error("Failed to get skill application for %s: %s", skill_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{skill_id}/application")
async def withdraw_application(
    skill_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    """Withdraw a pending application."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillApplication).where(
                SkillApplication.skill_id == skill_id,
                SkillApplication.applicant_id == current_user.id,
                SkillApplication.status == SkillApplicationStatus.PENDING,
            )
            result = await session.execute(stmt)
            application = result.scalar_one_or_none()

            if not application:
                raise HTTPException(status_code=404, detail="No pending application found")

            await session.delete(application)
            await session.commit()

        return {"message": "Application withdrawn successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to withdraw skill application for %s: %s", skill_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
