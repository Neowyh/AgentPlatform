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


def _scope_restriction(context: dict[str, Any], key: str) -> set[str] | None:
    """Read an optional logical/provider KB restriction from run context."""

    value = context.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return {item for item in value if isinstance(item, str) and item.strip()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return {item for item in value if isinstance(item, str) and item.strip()}
    return set()


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

    from agentplatform_extension.knowledge.scope import KnowledgeScope
    from sqlalchemy import select

    from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument
    from app.agentplatform.knowledge.scope import calculate_effective_knowledge_scope
    from app.agentplatform.rbac_models import UserModel, UserRole
    from app.agentplatform.resource_runtime import CanonicalResourceLoader, ResourceRuntimeError, ResourceStorage
    from app.agentplatform.resource_service import (
        ResourceAction,
        ResourceActor,
        ResourceConflict,
        ResourceNotFound,
        ResourcePermissionDenied,
        ResourceService,
        VisibilityClosureError,
    )
    from app.agentplatform.runtime_adapter import build_canonical_agent_factory
    from deerflow.config.app_config import get_app_config
    from deerflow.config.paths import get_paths
    from deerflow.persistence.engine import get_session_factory

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
            # T3: resolve the closure once — it serves the Skill check below
            # and the snapshot freeze, instead of walking the graph twice.
            closure = await service.resolve_dependency_closure(resource_id)
            selected_skill_id = None
            if preferred_skill:
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
                closure=closure,
            )
            storage = ResourceStorage(get_paths().base_dir)
            loader = CanonicalResourceLoader(session, storage)
            definition = await loader.load_agent(run_id, resource_id)
            skill_definitions = await loader.load_agent_skill_definitions(run_id, resource_id, definition=definition)
            skills = [value.skill for value in skill_definitions]
            knowledge_resources = {item.resource.id: item.resource for item in closure if item.resource.type == "knowledge_base"}
            bindings = {}
            ready_document_ids: dict[str, list[str]] = {}
            if knowledge_resources:
                rows = await session.execute(select(KnowledgeBase).where(KnowledgeBase.resource_id.in_(knowledge_resources)))
                bindings = {row.resource_id: row.provider_dataset_id for row in rows.scalars()}
                ready_rows = await session.execute(
                    select(KnowledgeDocument.resource_id, KnowledgeDocument.provider_document_id).where(
                        KnowledgeDocument.resource_id.in_(knowledge_resources),
                        KnowledgeDocument.status == "ready",
                        KnowledgeDocument.provider_document_id.is_not(None),
                    )
                )
                for resource_id, provider_document_id in ready_rows:
                    dataset_id = bindings.get(resource_id)
                    if dataset_id and provider_document_id:
                        ready_document_ids.setdefault(dataset_id, []).append(provider_document_id)
            run_context = diagnostic_context or {}
            tool_config = None
            try:
                tool_config = get_app_config().get_tool_config("knowledge_search")
            except Exception:
                # A deployment policy that cannot be read must deny retrieval;
                # treating it as absent would turn a configuration failure into
                # an authorization bypass.
                tool_config = None
                deployment_allowed = set()
            else:
                deployment_allowed = getattr(tool_config, "datasets", None)
            # The scope is keyed by canonical KB UUIDs. Slugs are display
            # aliases and may collide across owners/departments.
            caller_allowed = set(knowledge_resources)
            knowledge_scope = calculate_effective_knowledge_scope(
                bindings,
                caller_allowed=caller_allowed,
                workflow_allowed=_scope_restriction(run_context, "knowledge_scope"),
                runtime_allowed=_scope_restriction(run_context, "runtime_knowledge_scope"),
                deployment_allowed=deployment_allowed,
            )
            knowledge_scope = {logical: dataset for logical, dataset in knowledge_scope.items() if ready_document_ids.get(dataset)}
            await asyncio.to_thread(
                storage.create_run_skill_view,
                run_id,
                [(value.resource_id, value.version, value.content_hash) for value in skill_definitions],
            )
            await session.commit()
        return build_canonical_agent_factory(
            definition,
            skills,
            runner_tool_groups=actor.tool_groups,
            knowledge_scope=KnowledgeScope.from_bindings(
                knowledge_scope,
                ready_document_ids={dataset: ready_document_ids[dataset] for dataset in knowledge_scope.values()},
            ),
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
