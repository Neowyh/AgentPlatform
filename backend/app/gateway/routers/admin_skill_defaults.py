"""Admin skill defaults API routes."""

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
from ideer.persistence.models.skill_default_config import SkillDefaultConfig
from ideer.persistence.models.user import UserModel, UserRole
from ideer.skills.storage import get_or_new_skill_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-skill-defaults"])


async def _invalidate_cache(app_config: AppConfig) -> None:
    """Clear skill storage caches after admin config changes."""
    try:
        storage = get_or_new_skill_storage(app_config=app_config)
        if hasattr(storage, "clear_cache"):
            await storage.clear_cache()
    except Exception:
        logger.warning("Failed to invalidate skill storage cache")


class SkillDefaultConfigResponse(BaseModel):
    id: str
    scope: str
    scope_id: str | None = None
    skill_name: str
    enabled: bool
    user_override_allowed: bool
    created_at: str | None = None
    updated_at: str | None = None


class SkillDefaultConfigsResponse(BaseModel):
    configs: list[SkillDefaultConfigResponse]


class CreateSkillDefaultConfigRequest(BaseModel):
    scope: str = Field(..., pattern="^(global|department)$")
    scope_id: str | None = None
    skill_name: str
    enabled: bool = True
    user_override_allowed: bool = True


class UpdateSkillDefaultConfigRequest(BaseModel):
    enabled: bool | None = None
    user_override_allowed: bool | None = None


@router.get("/skill-defaults", response_model=SkillDefaultConfigsResponse)
async def list_skill_defaults(
    scope: str | None = None,
    scope_id: str | None = None,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> SkillDefaultConfigsResponse:
    """List skill default configurations."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillDefaultConfig)

            if scope:
                stmt = stmt.where(SkillDefaultConfig.scope == scope)

            if scope_id:
                stmt = stmt.where(SkillDefaultConfig.scope_id == scope_id)

            # Department admins can only see global configs and configs for their department
            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                from sqlalchemy import or_

                stmt = stmt.where(
                    or_(
                        SkillDefaultConfig.scope == "global",
                        SkillDefaultConfig.scope_id == current_user.department_id,
                    )
                )

            result = await session.execute(stmt)
            configs = result.scalars().all()

            return SkillDefaultConfigsResponse(
                configs=[
                    SkillDefaultConfigResponse(
                        id=config.id,
                        scope=config.scope,
                        scope_id=config.scope_id,
                        skill_name=config.skill_name,
                        enabled=config.enabled,
                        user_override_allowed=config.user_override_allowed,
                        created_at=str(config.created_at) if config.created_at else None,
                        updated_at=str(config.updated_at) if config.updated_at else None,
                    )
                    for config in configs
                ]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list skill defaults: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/skill-defaults", response_model=SkillDefaultConfigResponse)
async def create_skill_default(
    request: CreateSkillDefaultConfigRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
    app_config: AppConfig = Depends(get_config),
) -> SkillDefaultConfigResponse:
    """Create a skill default configuration."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if current_user.role == UserRole.DEPARTMENT_ADMIN:
        if request.scope == "global":
            raise HTTPException(status_code=403, detail="Department admins cannot create global configs")
        if request.scope_id and request.scope_id != current_user.department_id:
            raise HTTPException(status_code=403, detail="Department admins can only create configs for their own department")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillDefaultConfig).where(
                SkillDefaultConfig.scope == request.scope,
                SkillDefaultConfig.scope_id == request.scope_id,
                SkillDefaultConfig.skill_name == request.skill_name,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                raise HTTPException(status_code=400, detail="Config already exists for this scope and skill")

            new_config = SkillDefaultConfig(
                id=str(uuid.uuid4()),
                scope=request.scope,
                scope_id=request.scope_id,
                skill_name=request.skill_name,
                enabled=request.enabled,
                user_override_allowed=request.user_override_allowed,
            )
            session.add(new_config)
            await session.commit()
            await session.refresh(new_config)

            response = SkillDefaultConfigResponse(
                id=new_config.id,
                scope=new_config.scope,
                scope_id=new_config.scope_id,
                skill_name=new_config.skill_name,
                enabled=new_config.enabled,
                user_override_allowed=new_config.user_override_allowed,
                created_at=str(new_config.created_at) if new_config.created_at else None,
                updated_at=str(new_config.updated_at) if new_config.updated_at else None,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create skill default: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        await _invalidate_cache(app_config)
    except Exception:
        logger.warning("Failed to invalidate cache after creating skill default")

    return response


@router.put("/skill-defaults/{config_id}", response_model=SkillDefaultConfigResponse)
async def update_skill_default(
    config_id: str,
    request: UpdateSkillDefaultConfigRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
    config: AppConfig = Depends(get_config),
) -> SkillDefaultConfigResponse:
    """Update a skill default configuration."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillDefaultConfig).where(SkillDefaultConfig.id == config_id)
            result = await session.execute(stmt)
            db_config = result.scalar_one_or_none()

            if not db_config:
                raise HTTPException(status_code=404, detail="Config not found")

            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                if db_config.scope == "global":
                    raise HTTPException(status_code=403, detail="Department admins cannot update global configs")
                if db_config.scope_id != current_user.department_id:
                    raise HTTPException(status_code=403, detail="Department admins can only update configs for their own department")

            if request.enabled is not None:
                db_config.enabled = request.enabled
            if request.user_override_allowed is not None:
                db_config.user_override_allowed = request.user_override_allowed

            await session.commit()
            await session.refresh(db_config)

            response = SkillDefaultConfigResponse(
                id=db_config.id,
                scope=db_config.scope,
                scope_id=db_config.scope_id,
                skill_name=db_config.skill_name,
                enabled=db_config.enabled,
                user_override_allowed=db_config.user_override_allowed,
                created_at=str(db_config.created_at) if db_config.created_at else None,
                updated_at=str(db_config.updated_at) if db_config.updated_at else None,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update skill default %s: %s", config_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        await _invalidate_cache(config)
    except Exception:
        logger.warning("Failed to invalidate cache after updating skill default")

    return response


@router.delete("/skill-defaults/{config_id}")
async def delete_skill_default(
    config_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
    app_config: AppConfig = Depends(get_config),
) -> dict[str, Any]:
    """Delete a skill default configuration."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(SkillDefaultConfig).where(SkillDefaultConfig.id == config_id)
            result = await session.execute(stmt)
            db_config = result.scalar_one_or_none()

            if not db_config:
                raise HTTPException(status_code=404, detail="Config not found")

            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                if db_config.scope == "global":
                    raise HTTPException(status_code=403, detail="Department admins cannot delete global configs")
                if db_config.scope_id != current_user.department_id:
                    raise HTTPException(status_code=403, detail="Department admins can only delete configs for their own department")

            await session.delete(db_config)
            await session.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete skill default %s: %s", config_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        await _invalidate_cache(app_config)
    except Exception:
        logger.warning("Failed to invalidate cache after deleting skill default")

    return {"message": "Config deleted successfully"}
