"""Canonical Agent Run preparation.

This module is the single gateway seam for resolving an authorized Agent,
freezing its dependency closure, and preparing the frozen runtime view before
the Run record becomes visible to the worker.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, Request


async def prepare_canonical_agent_run(
    resource_id: str,
    request: Request,
    run_id: str,
    preferred_skill: str | None = None,
) -> Any:
    """Prepare one canonical Agent Run from the authenticated user's view."""

    from sqlalchemy import select

    from ideer.agents.lead_agent.agent import build_canonical_lead_agent_factory
    from ideer.config import get_paths
    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel, UserRole
    from ideer.resources.runtime import CanonicalResourceLoader, ResourceRuntimeError
    from ideer.resources.service import (
        ResourceAction,
        ResourceActor,
        ResourceConflict,
        ResourceNotFound,
        ResourcePermissionDenied,
        ResourceService,
        VisibilityClosureError,
    )
    from ideer.resources.storage import ResourceStorage

    user_id = getattr(getattr(request.state, "user", None), "id", None)
    if user_id is None:
        raise HTTPException(401, "Authentication required")
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(503, "Resource persistence is unavailable")
    try:
        async with session_factory() as session:
            user = (
                await session.execute(
                    select(UserModel).where(
                        UserModel.id == str(user_id),
                        UserModel.disabled.is_not(True),
                    )
                )
            ).scalar_one_or_none()
            if user is None:
                raise ResourcePermissionDenied("Active RBAC user is required")
            permissions = {ResourceAction.READ}
            if user.role in {UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN}:
                permissions.add(ResourceAction.USE)
            actor = ResourceActor(
                user_id=str(user.id),
                department_id=str(user.department_id) if user.department_id is not None else None,
                role=str(user.role),
                permissions=frozenset(permissions),
                tool_groups=None,
            )
            service = ResourceService(session, actor)
            selected_skill_id = None
            if preferred_skill:
                closure = await service.resolve_dependency_closure(resource_id)
                selected = next(
                    (item.resource for item in closure if item.resource.id == preferred_skill or item.resource.slug == preferred_skill),
                    None,
                )
                if selected is None or selected.type != "skill":
                    raise ResourceConflict(f"Selected Skill {preferred_skill} is outside Agent {resource_id}'s dependency closure")
                selected_skill_id = selected.id
            await service.create_run_snapshot(
                run_id,
                resource_id,
                selected_resource_id=selected_skill_id,
            )
            storage = ResourceStorage(get_paths().base_dir)
            loader = CanonicalResourceLoader(session, storage)
            definition = await loader.load_agent(run_id, resource_id)
            skill_definitions = await loader.load_agent_skill_definitions(run_id, resource_id)
            skills = [value.skill for value in skill_definitions]
            await asyncio.to_thread(
                storage.create_run_skill_view,
                run_id,
                [(value.resource_id, value.version, value.content_hash) for value in skill_definitions],
            )
            await session.commit()
        return build_canonical_lead_agent_factory(
            definition,
            skills,
            runner_tool_groups=actor.tool_groups,
        )
    except ResourceNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ResourcePermissionDenied as exc:
        raise HTTPException(403, str(exc)) from exc
    except VisibilityClosureError as exc:
        raise HTTPException(
            409,
            detail={
                "code": "visibility_closure_violation",
                "message": str(exc),
                "violations": exc.violations,
            },
        ) from exc
    except (ResourceConflict, ResourceRuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc
