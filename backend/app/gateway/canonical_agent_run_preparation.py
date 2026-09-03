"""Canonical Agent Run preparation.

This module is the single gateway seam for resolving an authorized Agent,
freezing its dependency closure, and preparing the frozen runtime view before
the Run record becomes visible to the worker.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, Request

from app.gateway.authz import _cached_rbac_identity


class SelectedSkillOutsideClosure(Exception):
    """Diagnostic-only conflict for an Expert/Skill mismatch."""

    def __init__(
        self,
        *,
        agent: dict[str, str],
        requested_skill: str,
        available_skills: list[dict[str, str]],
    ) -> None:
        self.agent = agent
        self.requested_skill = requested_skill
        self.available_skills = available_skills


async def prepare_canonical_agent_run(
    resource_id: str,
    request: Request,
    run_id: str,
    preferred_skill: str | None = None,
    diagnostic_context: dict[str, Any] | None = None,
    thread_id: str | None = None,
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
            # T2: reuse the identity _authenticate already resolved instead of
            # issuing a duplicate UserModel SELECT on every first turn.
            cached = _cached_rbac_identity(request, str(user_id))
            if cached is not None:
                permissions = {ResourceAction.READ}
                if cached["role"] in {
                    UserRole.USER.value,
                    UserRole.DEPARTMENT_ADMIN.value,
                    UserRole.SUPER_ADMIN.value,
                }:
                    permissions.add(ResourceAction.USE)
                actor = ResourceActor(
                    user_id=cached["user_id"],
                    department_id=cached["department_id"],
                    role=cached["role"],
                    permissions=frozenset(permissions),
                    tool_groups=None,
                )
            else:
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
                    agent = next(item.resource for item in closure if item.resource.id == resource_id)
                    available_skills = [{"resource_id": item.resource.id, "slug": item.resource.slug} for item in closure if item.resource.type == "skill"]
                    raise SelectedSkillOutsideClosure(
                        agent={"resource_id": agent.id, "slug": agent.slug},
                        requested_skill=str(preferred_skill),
                        available_skills=available_skills,
                    )
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
    except SelectedSkillOutsideClosure as exc:
        from app.gateway.audit import record_audit

        await record_audit(
            str(user_id),
            "run_preparation_rejected",
            resource_type="agent",
            resource_id=resource_id,
            detail={
                "thread_id": thread_id,
                "run_attempt_id": run_id,
                "agent": exc.agent,
                "requested_skill": exc.requested_skill,
                "available_skills": exc.available_skills,
                "task_id": (diagnostic_context or {}).get("task_id"),
                "context_source": (diagnostic_context or {}).get("context_source", "request"),
                "reason": "skill_outside_agent_closure",
            },
        )
        raise HTTPException(
            409,
            detail={
                "code": "skill_outside_agent_closure",
                "message": "The selected Skill is not available to the current Expert.",
                "agent": exc.agent,
                "requested_skill": exc.requested_skill,
                "available_skills": exc.available_skills,
                "context_source": (diagnostic_context or {}).get("context_source", "request"),
            },
        ) from exc
    except (ResourceConflict, ResourceRuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc
