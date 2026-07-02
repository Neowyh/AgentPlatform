"""User skill preferences API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.gateway.authz import get_current_rbac_user
from app.gateway.deps import get_config
from ideer.config.app_config import AppConfig
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.user import UserModel
from ideer.persistence.models.user_skill_preference import UserSkillPreference
from ideer.skills.storage import get_or_new_skill_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user-skill-preferences"])


class SkillPreferenceResponse(BaseModel):
    skill_name: str
    enabled: bool


class SkillPreferencesResponse(BaseModel):
    preferences: list[SkillPreferenceResponse]


class UpdateSkillPreferenceRequest(BaseModel):
    skill_name: str
    enabled: bool


class UpdateAllSkillPreferencesRequest(BaseModel):
    preferences: list[UpdateSkillPreferenceRequest]


@router.get("/skill-preferences", response_model=SkillPreferencesResponse)
async def get_skill_preferences(
    current_user: UserModel = Depends(get_current_rbac_user),
) -> SkillPreferencesResponse:
    """Get current user's skill preferences."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(UserSkillPreference).where(UserSkillPreference.user_id == current_user.id)
        result = await session.execute(stmt)
        preferences = result.scalars().all()

        return SkillPreferencesResponse(
            preferences=[
                SkillPreferenceResponse(
                    skill_name=pref.skill_name,
                    enabled=pref.enabled,
                )
                for pref in preferences
            ]
        )


@router.put("/skill-preferences")
async def update_skill_preferences(
    request: UpdateAllSkillPreferencesRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
    app_config: AppConfig = Depends(get_config),
) -> dict[str, Any]:
    """Update current user's skill preferences."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            for pref in request.preferences:
                stmt = select(UserSkillPreference).where(
                    UserSkillPreference.user_id == current_user.id,
                    UserSkillPreference.skill_name == pref.skill_name,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.enabled = pref.enabled
                else:
                    new_pref = UserSkillPreference(
                        user_id=current_user.id,
                        skill_name=pref.skill_name,
                        enabled=pref.enabled,
                    )
                    session.add(new_pref)

            await session.commit()
    except Exception as e:
        logger.error("Failed to update skill preferences for %s: %s", current_user.id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    # Invalidate cache so updated preferences take effect immediately
    try:
        storage = get_or_new_skill_storage(app_config=app_config)
        if hasattr(storage, "clear_cache"):
            await storage.clear_cache()
    except Exception:
        pass

    return {"message": "Skill preferences updated successfully"}
