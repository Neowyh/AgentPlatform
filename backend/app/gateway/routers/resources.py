"""UUID-first facade for canonical Skill, Agent, and Workflow resources."""

from __future__ import annotations

import asyncio
import json
import uuid
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from starlette.background import BackgroundTask

from app.gateway.audit import record_audit
from app.gateway.authz import get_current_rbac_user
from ideer.config import get_app_config, get_paths
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceFavorite,
    ResourceNotification,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.workflow_v2 import WorkflowV2RunRow
from ideer.resources.publisher import ResourcePublisher, write_agent_draft_source
from ideer.resources.retention import build_retention_report
from ideer.resources.runtime import load_validated_agent_definition
from ideer.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceApprovalRequired,
    ResourceConflict,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceService,
    VisibilityClosureError,
)
from ideer.resources.storage import ResourceStorage, StorageConflict, StorageValidationError
from ideer.workflows.v2.errors import WorkflowRunError
from ideer.workflows.v2.file_roots import (
    collect_artifacts,
    make_host_resolver,
    render_roots,
    workflow_record_path,
)
from ideer.workflows.v2.parser import parse_workflow_v2
from ideer.workflows.v2.store import WorkflowV2Store

router = APIRouter(prefix="/api/resources", tags=["resources"])


class ResourceCreateRequest(BaseModel):
    type: str = Field(pattern="^(skill|agent|workflow)$")
    slug: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    storage_kind: str = Field(pattern="^(filesystem|database)$")


class WorkflowDraftRequest(BaseModel):
    content: dict[str, Any] | str
    expected_revision: int = Field(ge=0)


class AgentDraftRequest(BaseModel):
    config: dict[str, Any]
    soul: str = ""
    expected_revision: int = Field(ge=0)


class PublishRequest(BaseModel):
    expected_draft_revision: int = Field(ge=1)
    scan_result: dict[str, Any] = Field(default_factory=dict)


class DependencyRequest(BaseModel):
    resource_ids: list[str]


class ForkRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)


class VisibilityRequest(BaseModel):
    visibility: str = Field(pattern="^(private|department|public)$")
    scope_department_id: str | None = None


class VisibilityApplicationRequest(BaseModel):
    target_visibility: str = Field(pattern="^(department|public)$")
    scope_department_id: str | None = None
    reason: str = Field(min_length=1, max_length=2000)


class VisibilityReviewRequest(BaseModel):
    approve: bool
    comment: str = Field(default="", max_length=2000)
    version: int = Field(ge=1)


class TransferRequest(BaseModel):
    target_owner_id: str = Field(min_length=1)
    new_slug: str | None = Field(default=None, min_length=1, max_length=128)


class WorkflowRunRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class WorkflowCommandRequest(BaseModel):
    command_id: str = Field(min_length=1)
    type: str = Field(pattern="^(resume|cancel)$")
    payload: dict[str, Any] = Field(default_factory=dict)


def _resource_actor(user: UserModel) -> ResourceActor:
    permissions = {ResourceAction.READ}
    if user.role in {UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN}:
        permissions.update({ResourceAction.USE, ResourceAction.WRITE})
    if user.role in {UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN}:
        permissions.add(ResourceAction.APPROVE)
    if user.role == UserRole.SUPER_ADMIN:
        permissions.update(ResourceAction)
    return ResourceActor(
        user_id=str(user.id),
        department_id=str(user.department_id) if user.department_id is not None else None,
        role=str(user.role),
        permissions=frozenset(permissions),
        tool_groups=None,
    )


def _translate_resource_errors(handler):
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        try:
            return await handler(*args, **kwargs)
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
        except (ResourceConflict, ResourceApprovalRequired, StorageConflict) as exc:
            raise HTTPException(409, str(exc)) from exc
        except WorkflowRunError as exc:
            raise HTTPException(400, detail=exc.api_detail()) from exc
        except (StorageValidationError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

    return wrapped


def _factory():
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(503, "Resource persistence is unavailable")
    return session_factory


def _resource_payload(
    resource: Resource,
    *,
    current_user: UserModel | None = None,
    is_favorited: bool = False,
) -> dict[str, Any]:
    can_modify = bool(
        current_user is not None
        and str(resource.owner_id) == str(current_user.id)
        and not resource.system_owned
        and resource.lifecycle_status == "active"
        and current_user.role in {UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN}
    )
    return {
        "id": resource.id,
        "type": resource.type,
        "slug": resource.slug,
        "display_name": resource.display_name,
        "owner_id": resource.owner_id,
        "visibility": resource.visibility,
        "scope_department_id": resource.scope_department_id,
        "lifecycle_status": resource.lifecycle_status,
        "latest_version": resource.latest_version,
        "draft_revision": resource.draft_revision,
        "storage_kind": resource.storage_kind,
        "provenance": resource.provenance,
        "system_owned": resource.system_owned,
        "authz_revision": resource.authz_revision,
        "can_modify": can_modify,
        "is_favorited": is_favorited,
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }


def _version_payload(version: ResourceVersion) -> dict[str, Any]:
    return {
        "resource_id": version.resource_id,
        "version": version.version,
        "content_hash": version.content_hash,
        "scan_result": version.scan_result,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "source_resource_id": version.source_resource_id,
        "source_version": version.source_version,
    }


def _visibility_application_payload(application: Any) -> dict[str, Any]:
    return {
        "id": application.id,
        "resource_type": application.resource_type,
        "resource_id": application.canonical_resource_id or application.resource_id,
        "applicant_id": application.applicant_id,
        "current_visibility": application.current_visibility,
        "target_visibility": application.target_visibility,
        "department_id": application.department_id,
        "reason": application.reason,
        "status": application.status,
        "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
        "reviewed_by": application.reviewed_by,
        "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
        "review_comment": application.review_comment,
        "version": application.version,
        "requested_version": application.requested_version,
        "requested_hash": application.requested_hash,
    }


async def _favorite_ids(session: Any, user_id: str, resource_ids: list[str]) -> set[str]:
    if not resource_ids:
        return set()
    return set(
        (
            await session.execute(
                select(ResourceFavorite.resource_id).where(
                    ResourceFavorite.user_id == user_id,
                    ResourceFavorite.resource_id.in_(resource_ids),
                )
            )
        ).scalars()
    )


def _archive_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def _extract_resource_archive(
    archive_path: Path,
    destination: Path,
    storage: ResourceStorage,
) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) > storage.limits.max_files:
                raise StorageValidationError("Archive file count exceeds limit")
            total_size = 0
            for item in members:
                relative = storage._validate_archive_member(item)
                if item.file_size > storage.limits.max_file_bytes:
                    raise StorageValidationError(f"Archive member exceeds size limit: {relative.as_posix()}")
                total_size += item.file_size
                if total_size > storage.limits.max_total_bytes:
                    raise StorageValidationError("Archive expanded size exceeds limit")
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                target.chmod(0o644)
    except zipfile.BadZipFile as exc:
        raise StorageValidationError("Resource archive is not a valid ZIP file") from exc


def _run_payload(run: WorkflowV2RunRow, resource_id: str) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "workflow": resource_id,
        "workflow_resource_id": run.workflow_resource_id,
        "status": run.status,
        "definition_version": run.definition_version,
        "snapshot": run.snapshot,
        "error": run.error,
    }


def _can_access_run(user: UserModel, run: WorkflowV2RunRow) -> bool:
    return user.role == UserRole.SUPER_ADMIN or str(user.id) == str(run.created_by)


def _required_canonical_resume_roles(
    run: WorkflowV2RunRow,
    definition: dict[str, Any],
) -> set[str]:
    interrupt_value = run.snapshot.get("interrupt") if isinstance(run.snapshot, dict) else None
    if isinstance(interrupt_value, list) and interrupt_value:
        first = interrupt_value[0]
        interrupt_node = first.get("node_id") if isinstance(first, dict) else None
    elif isinstance(interrupt_value, dict):
        interrupt_node = interrupt_value.get("node_id")
    else:
        interrupt_node = None
    return {role for node in definition.get("nodes", []) if isinstance(node, dict) and node.get("id") == interrupt_node for role in node.get("roles", []) if isinstance(role, str)}


@router.get("")
@_translate_resource_errors
async def list_resources(
    resource_type: str | None = Query(default=None, alias="type", pattern="^(skill|agent|workflow)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        page = await ResourceService(session, _resource_actor(current_user)).list_visible(
            resource_type=resource_type,
            offset=offset,
            limit=limit,
        )
        favorites = await _favorite_ids(session, str(current_user.id), [item.id for item in page.items])
        return {
            "items": [
                _resource_payload(
                    item,
                    current_user=current_user,
                    is_favorited=item.id in favorites,
                )
                for item in page.items
            ],
            "total": page.total,
            "offset": page.offset,
            "limit": page.limit,
        }


@router.get("/notifications")
async def list_resource_notifications(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        condition = ResourceNotification.recipient_id == str(current_user.id)
        total = int((await session.execute(select(func.count()).select_from(ResourceNotification).where(condition))).scalar_one())
        unread = int((await session.execute(select(func.count()).select_from(ResourceNotification).where(condition, ResourceNotification.read_at.is_(None)))).scalar_one())
        rows = list(
            (
                await session.execute(
                    select(ResourceNotification)
                    .where(condition)
                    .order_by(
                        ResourceNotification.created_at.desc(),
                        ResourceNotification.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).scalars()
        )
        return {
            "items": [
                {
                    "id": item.id,
                    "resource_id": item.resource_id,
                    "event": item.event,
                    "detail": item.detail,
                    "read_at": item.read_at.isoformat() if item.read_at else None,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in rows
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
            "unread_count": unread,
        }


@router.put("/notifications/{notification_id}/read", status_code=204)
async def mark_resource_notification_read(
    notification_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> Response:
    async with _factory()() as session:
        notification = (
            await session.execute(
                select(ResourceNotification).where(
                    ResourceNotification.id == notification_id,
                    ResourceNotification.recipient_id == str(current_user.id),
                )
            )
        ).scalar_one_or_none()
        if notification is None:
            raise HTTPException(404, "Notification not found")
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            await session.commit()
        return Response(status_code=204)


@router.put("/notifications/read-all", status_code=204)
async def mark_all_resource_notifications_read(
    current_user: UserModel = Depends(get_current_rbac_user),
) -> Response:
    async with _factory()() as session:
        await session.execute(
            update(ResourceNotification)
            .where(
                ResourceNotification.recipient_id == str(current_user.id),
                ResourceNotification.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        await session.commit()
        return Response(status_code=204)


@router.post("/import/agent", status_code=201)
@_translate_resource_errors
async def import_agent_resource(
    archive: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    storage = ResourceStorage(get_paths().base_dir)
    archive_path: Path | None = None
    try:
        with NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
            archive_path = Path(temporary.name)
            compressed_size = 0
            while chunk := await archive.read(1024 * 1024):
                compressed_size += len(chunk)
                if compressed_size > storage.limits.max_archive_bytes:
                    raise StorageValidationError("Archive exceeds compressed size limit")
                temporary.write(chunk)
        with TemporaryDirectory(prefix="ideer-agent-import-") as extracted:
            source = Path(extracted)
            await asyncio.to_thread(
                _extract_resource_archive,
                archive_path,
                source,
                storage,
            )
            config, soul = await asyncio.to_thread(
                load_validated_agent_definition,
                source,
                fallback_name="imported-agent",
            )
            async with _factory()() as session:
                service = ResourceService(session, _resource_actor(current_user))
                dependencies: list[str] = []
                for identity in config.skills or []:
                    target = await session.get(Resource, identity)
                    if target is None:
                        target = await service.resolve_legacy_alias(
                            "skill",
                            identity,
                        )
                    if target.type != "skill":
                        raise ValueError(f"Agent dependency {identity} is not a Skill")
                    dependencies.append(target.id)
                dependencies = list(dict.fromkeys(dependencies))
                write_agent_draft_source(
                    source,
                    slug=config.name,
                    config={
                        **config.model_dump(mode="json"),
                        "skills": dependencies,
                    },
                    soul=soul,
                )
                resource = await service.create_resource(
                    resource_type="agent",
                    slug=config.name,
                    display_name=config.name,
                    storage_kind="filesystem",
                )
                await service.replace_dependencies(resource.id, dependencies)
                publisher = ResourcePublisher(service, storage)
                draft = await publisher.save_filesystem_draft(
                    resource.id,
                    source_dir=source,
                    expected_revision=0,
                )
                try:
                    version = await publisher.publish_filesystem(
                        resource.id,
                        expected_draft_revision=draft.revision,
                        scan_result={"status": "validated_import"},
                    )
                except BaseException:
                    await service.archive(resource.id)
                    await session.commit()
                    raise
                await record_audit(
                    str(current_user.id),
                    "resource_imported",
                    "agent",
                    resource.id,
                    {
                        "version": version.version,
                        "content_hash": version.content_hash,
                    },
                )
                return _resource_payload(resource, current_user=current_user)
    finally:
        await archive.close()
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)


@router.post("", status_code=201)
@_translate_resource_errors
async def create_resource(
    body: ResourceCreateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).create_resource(
            resource_type=body.type,
            slug=body.slug,
            display_name=body.display_name,
            storage_kind=body.storage_kind,
        )
        await session.commit()
        await record_audit(
            str(current_user.id),
            "resource_created",
            resource.type,
            resource.id,
            {"slug": resource.slug, "visibility": resource.visibility},
        )
        return _resource_payload(resource, current_user=current_user)


@router.get("/aliases/{resource_type}/{slug}")
@_translate_resource_errors
async def resolve_resource_alias(
    resource_type: str,
    slug: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).resolve_legacy_alias(
            resource_type,
            slug,
        )
        return _resource_payload(resource, current_user=current_user)


@router.get("/{resource_id}")
@_translate_resource_errors
async def get_resource(
    resource_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).get_visible(resource_id)
        favorites = await _favorite_ids(session, str(current_user.id), [resource.id])
        return _resource_payload(
            resource,
            current_user=current_user,
            is_favorited=resource.id in favorites,
        )


@router.get("/{resource_id}/published")
@_translate_resource_errors
async def get_published_resource(
    resource_id: str,
    version: int | None = Query(default=None, ge=1),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        service = ResourceService(session, _resource_actor(current_user))
        resource = await service.get_visible(resource_id)
        published = await service.get_published_content(resource_id, version=version)
        payload: dict[str, Any] = {
            "resource": _resource_payload(resource, current_user=current_user),
            "version": _version_payload(published),
            "content": published.content,
        }
        if resource.type == "workflow":
            payload["yaml_content"] = yaml.safe_dump(published.content, sort_keys=False, allow_unicode=True)
            return payload
        expected_key = f"{'skills' if resource.type == 'skill' else 'agents'}/{resource.id}/versions/{published.version}"
        if published.storage_key != expected_key:
            raise StorageValidationError("Published resource has an invalid storage key")
        storage = ResourceStorage(get_paths().base_dir)
        source = storage.resources_root / expected_key
        inspected = await asyncio.to_thread(storage.inspect_directory, resource.type, source)
        if inspected.content_hash != published.content_hash:
            raise StorageValidationError("Published resource content hash mismatch")
        if resource.type == "agent":
            config, soul = await asyncio.to_thread(
                load_validated_agent_definition,
                source,
                fallback_name=resource.slug,
            )
            payload["content"] = {"config": config.model_dump(mode="json"), "soul": soul}
        else:
            from ideer.skills.parser import parse_skill_file
            from ideer.skills.types import SkillCategory

            skill = await asyncio.to_thread(
                parse_skill_file,
                source / "SKILL.md",
                category=SkillCategory.CUSTOM,
                relative_path=Path(resource.id),
            )
            if skill is None:
                raise StorageValidationError("Published Skill definition is invalid")
            payload["content"] = {
                "name": skill.name,
                "description": skill.description,
                "license": skill.license,
                "allowed_tools": skill.allowed_tools,
                "requires_internet": skill.requires_internet,
            }
        return payload


@router.get("/{resource_id}/export")
@_translate_resource_errors
async def export_resource(
    resource_id: str,
    version: int | None = Query(default=None, ge=1),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> Response:
    async with _factory()() as session:
        service = ResourceService(session, _resource_actor(current_user))
        resource = await service.get_visible(resource_id)
        published = await service.get_published_content(resource_id, version=version)
        if resource.type == "workflow":
            body = yaml.safe_dump(published.content, sort_keys=False, allow_unicode=True)
            return Response(
                body,
                media_type="application/yaml",
                headers={"Content-Disposition": f'attachment; filename="{resource.slug}-v{published.version}.yaml"'},
            )
        expected_key = f"{'skills' if resource.type == 'skill' else 'agents'}/{resource.id}/versions/{published.version}"
        if published.storage_key != expected_key:
            raise StorageValidationError("Published resource has an invalid storage key")
        source = ResourceStorage(get_paths().base_dir).resources_root / expected_key
        temporary = NamedTemporaryFile(suffix=".zip", delete=False)
        temporary_path = Path(temporary.name)
        temporary.close()
        try:
            await asyncio.to_thread(_archive_directory, source, temporary_path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
        return FileResponse(
            temporary_path,
            media_type="application/zip",
            filename=f"{resource.slug}-v{published.version}.zip",
            background=BackgroundTask(temporary_path.unlink, missing_ok=True),
        )


@router.put("/{resource_id}/workflow-draft")
@_translate_resource_errors
async def save_workflow_draft(
    resource_id: str,
    body: WorkflowDraftRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    content = body.content
    if isinstance(content, str):
        content = yaml.safe_load(content)
        if not isinstance(content, dict):
            raise ValueError("Workflow draft must contain a mapping")
    async with _factory()() as session:
        service = ResourceService(session, _resource_actor(current_user))
        workflow = parse_workflow_v2(yaml.safe_dump(content, sort_keys=False, allow_unicode=True))
        dependencies: list[str] = []
        for node in workflow.nodes:
            if node.type != "action" or node.action is None or node.action.kind != "agent":
                continue
            identity = node.action.name
            target = await session.get(Resource, identity)
            if target is None:
                target = await service.resolve_legacy_alias("agent", identity)
            if target.type != "agent":
                raise ValueError(f"Workflow dependency {identity} is not an Agent")
            node.action.name = target.id
            dependencies.append(target.id)
        dependencies = list(dict.fromkeys(dependencies))
        content = workflow.model_dump(mode="json", by_alias=True)
        await service.replace_dependencies(resource_id, dependencies)
        draft = await ResourcePublisher(service, ResourceStorage(get_paths().base_dir)).save_database_draft(
            resource_id,
            content=content,
            expected_revision=body.expected_revision,
        )
        return {
            "resource_id": draft.resource_id,
            "revision": draft.revision,
            "content_hash": draft.content_hash,
        }


@router.put("/{resource_id}/agent-draft")
@_translate_resource_errors
async def save_agent_draft(
    resource_id: str,
    body: AgentDraftRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    with TemporaryDirectory(prefix="ideer-agent-draft-") as temporary:
        source = Path(temporary)
        async with _factory()() as session:
            service = ResourceService(session, _resource_actor(current_user))
            resource = await service.get_visible(resource_id)
            if resource.type != "agent" or resource.storage_kind != "filesystem":
                raise ValueError("Only filesystem-backed Agent resources accept Agent drafts")
            dependencies: list[str] = []
            skills = body.config.get("skills")
            if skills is not None:
                if not isinstance(skills, list) or not all(isinstance(item, str) and item for item in skills):
                    raise ValueError("Agent skills must be a list of resource UUIDs or aliases")
                for identity in skills:
                    target = await session.get(Resource, identity)
                    if target is None:
                        target = await service.resolve_legacy_alias("skill", identity)
                    if target.type != "skill":
                        raise ValueError(f"Agent dependency {identity} is not a Skill")
                    dependencies.append(target.id)
            dependencies = list(dict.fromkeys(dependencies))
            config = dict(body.config)
            if skills is not None:
                config["skills"] = dependencies
            await asyncio.to_thread(
                write_agent_draft_source,
                source,
                slug=resource.slug,
                config=config,
                soul=body.soul,
            )
            await service.replace_dependencies(resource.id, dependencies)
            draft = await ResourcePublisher(
                service,
                ResourceStorage(get_paths().base_dir),
            ).save_filesystem_draft(
                resource.id,
                source_dir=source,
                expected_revision=body.expected_revision,
            )
            return {
                "resource_id": draft.resource_id,
                "revision": draft.revision,
                "content_hash": draft.content_hash,
            }


@router.put("/{resource_id}/archive-draft")
@_translate_resource_errors
async def save_archive_draft(
    resource_id: str,
    archive: UploadFile = File(...),
    expected_revision: int = Query(ge=0),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    storage = ResourceStorage(get_paths().base_dir)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            total = 0
            while chunk := await archive.read(1024 * 1024):
                total += len(chunk)
                if total > storage.limits.max_archive_bytes:
                    raise StorageValidationError("Archive exceeds compressed size limit")
                temporary.write(chunk)
        async with _factory()() as session:
            draft = await ResourcePublisher(
                ResourceService(session, _resource_actor(current_user)),
                storage,
            ).save_archive_draft(
                resource_id,
                archive_path=temporary_path,
                expected_revision=expected_revision,
            )
            return {
                "resource_id": draft.resource_id,
                "revision": draft.revision,
                "content_hash": draft.content_hash,
            }
    finally:
        await archive.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@router.post("/{resource_id}/publish")
@_translate_resource_errors
async def publish_resource(
    resource_id: str,
    body: PublishRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        service = ResourceService(session, _resource_actor(current_user))
        resource = await service.get_visible(resource_id)
        publisher = ResourcePublisher(service, ResourceStorage(get_paths().base_dir))
        if resource.storage_kind == "database":
            version = await publisher.publish_database(
                resource_id,
                expected_draft_revision=body.expected_draft_revision,
                scan_result=body.scan_result,
            )
        else:
            version = await publisher.publish_filesystem(
                resource_id,
                expected_draft_revision=body.expected_draft_revision,
                scan_result=body.scan_result,
            )
        await record_audit(
            str(current_user.id),
            "resource_published",
            resource.type,
            resource.id,
            {
                "version": version.version,
                "content_hash": version.content_hash,
            },
        )
        return _version_payload(version)


@router.put("/{resource_id}/dependencies")
@_translate_resource_errors
async def replace_dependencies(
    resource_id: str,
    body: DependencyRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        dependencies = await ResourceService(session, _resource_actor(current_user)).replace_dependencies(
            resource_id,
            body.resource_ids,
        )
        await session.commit()
        return {"resource_id": resource_id, "resource_ids": [item.target_resource_id for item in dependencies]}


@router.post("/{resource_id}/fork", status_code=201)
@_translate_resource_errors
async def fork_resource(
    resource_id: str,
    body: ForkRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourcePublisher(
            ResourceService(session, _resource_actor(current_user)),
            ResourceStorage(get_paths().base_dir),
        ).fork(
            resource_id,
            slug=body.slug,
            display_name=body.display_name,
        )
        await record_audit(
            str(current_user.id),
            "resource_forked",
            resource.type,
            resource.id,
            {"source_resource_id": resource_id, "version": resource.latest_version},
        )
        return _resource_payload(resource, current_user=current_user)


@router.post("/{resource_id}/visibility-applications", status_code=201)
@_translate_resource_errors
async def request_visibility(
    resource_id: str,
    body: VisibilityApplicationRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        application = await ResourceService(session, _resource_actor(current_user)).request_visibility(
            resource_id,
            target_visibility=body.target_visibility,
            scope_department_id=(body.scope_department_id or (str(current_user.department_id) if body.target_visibility == "department" and current_user.department_id is not None else None)),
            reason=body.reason,
        )
        await session.commit()
        await record_audit(
            str(current_user.id),
            "resource_visibility_requested",
            application.resource_type,
            resource_id,
            {
                "application_id": application.id,
                "target_visibility": application.target_visibility,
                "requested_version": application.requested_version,
                "requested_hash": application.requested_hash,
            },
        )
        return _visibility_application_payload(application)


@router.get("/{resource_id}/visibility-impact")
@_translate_resource_errors
async def get_visibility_impact(
    resource_id: str,
    target_visibility: str = Query(pattern="^(private|department|public)$"),
    scope_department_id: str | None = Query(default=None),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        return await ResourceService(session, _resource_actor(current_user)).visibility_reduction_impact(
            resource_id,
            target_visibility,
            scope_department_id=scope_department_id,
        )


@router.put("/{resource_id}/visibility")
@_translate_resource_errors
async def change_visibility(
    resource_id: str,
    body: VisibilityRequest,
    cascade: bool = Query(default=False),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).change_visibility(
            resource_id,
            body.visibility,
            scope_department_id=body.scope_department_id,
            cascade=cascade,
        )
        await session.commit()
        await record_audit(
            str(current_user.id),
            "resource_visibility_changed",
            resource.type,
            resource.id,
            {
                "visibility": resource.visibility,
                "scope_department_id": resource.scope_department_id,
                "authz_revision": resource.authz_revision,
                "cascade": cascade,
            },
        )
        return _resource_payload(resource, current_user=current_user)


@router.post("/{resource_id}/archive")
@_translate_resource_errors
async def archive_resource(
    resource_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).archive(resource_id)
        await session.commit()
        await record_audit(
            str(current_user.id),
            "resource_archived",
            resource.type,
            resource.id,
        )
        return _resource_payload(resource, current_user=current_user)


@router.post("/{resource_id}/suspend")
@_translate_resource_errors
async def suspend_resource(
    resource_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).suspend(resource_id)
        await session.commit()
        await record_audit(
            str(current_user.id),
            "resource_suspended",
            resource.type,
            resource.id,
            {"authz_revision": resource.authz_revision},
        )
        return _resource_payload(resource, current_user=current_user)


@router.post("/{resource_id}/restore")
@_translate_resource_errors
async def restore_resource(
    resource_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).restore(resource_id)
        await session.commit()
        await record_audit(
            str(current_user.id),
            "resource_restored",
            resource.type,
            resource.id,
            {"authz_revision": resource.authz_revision},
        )
        return _resource_payload(resource, current_user=current_user)


@router.post("/{resource_id}/transfer")
@_translate_resource_errors
async def transfer_resource(
    resource_id: str,
    body: TransferRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).transfer_owner(
            resource_id,
            body.target_owner_id,
            new_slug=body.new_slug,
        )
        await session.commit()
        await record_audit(
            str(current_user.id),
            "resource_transferred",
            resource.type,
            resource.id,
            {
                "target_owner_id": resource.owner_id,
                "slug": resource.slug,
                "visibility": resource.visibility,
            },
        )
        return _resource_payload(resource, current_user=current_user)


@router.post("/{resource_id}/favorite", status_code=204)
@_translate_resource_errors
async def favorite_resource(
    resource_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> None:
    async with _factory()() as session:
        await ResourceService(session, _resource_actor(current_user)).favorite(resource_id)
        await session.commit()


@router.delete("/{resource_id}/favorite", status_code=204)
@_translate_resource_errors
async def unfavorite_resource(
    resource_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> None:
    async with _factory()() as session:
        await ResourceService(session, _resource_actor(current_user)).unfavorite(resource_id)
        await session.commit()


@router.post("/{resource_id}/workflow-runs", status_code=201)
@_translate_resource_errors
async def create_workflow_run(
    resource_id: str,
    body: WorkflowRunRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    runtime = get_app_config().workflow_runtime
    try:
        run = await WorkflowV2Store(_factory()).create_canonical_run(
            str(uuid.uuid4()),
            resource_id,
            body.inputs,
            _resource_actor(current_user),
            user_concurrency=runtime.user_concurrency,
            department_concurrency=runtime.department_concurrency,
        )
    except RuntimeError as exc:
        if str(exc) in {"workflow_user_concurrency_exceeded", "workflow_department_concurrency_exceeded"}:
            raise HTTPException(429, str(exc)) from exc
        raise
    return {"run_id": run.run_id, "status": run.status, "workflow_resource_id": run.workflow_resource_id}


@router.get("/{resource_id}/workflow-runs")
@_translate_resource_errors
async def list_canonical_workflow_runs(
    resource_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).get_visible(resource_id)
        if resource.type != "workflow":
            raise ValueError("Resource is not a Workflow")
        query = select(WorkflowV2RunRow).where(WorkflowV2RunRow.workflow_resource_id == resource_id)
        if current_user.role != UserRole.SUPER_ADMIN:
            query = query.where(WorkflowV2RunRow.created_by == str(current_user.id))
        total = int((await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
        runs = list((await session.execute(query.order_by(WorkflowV2RunRow.created_at.desc()).offset(offset).limit(limit))).scalars())
        return {
            "runs": [_run_payload(run, resource_id) for run in runs],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


async def _get_canonical_run(
    resource_id: str,
    run_id: str,
    current_user: UserModel,
) -> WorkflowV2RunRow:
    async with _factory()() as session:
        resource = await ResourceService(session, _resource_actor(current_user)).get_visible(resource_id)
        if resource.type != "workflow":
            raise ValueError("Resource is not a Workflow")
        run = await session.get(WorkflowV2RunRow, run_id)
        if run is None or run.workflow_resource_id != resource_id or not _can_access_run(current_user, run):
            raise ResourceNotFound(f"Workflow Run {run_id} not found")
        return run


@router.get("/{resource_id}/workflow-runs/{run_id}")
@_translate_resource_errors
async def get_canonical_workflow_run(
    resource_id: str,
    run_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    return _run_payload(await _get_canonical_run(resource_id, run_id, current_user), resource_id)


@router.get("/{resource_id}/workflow-runs/{run_id}/events")
@_translate_resource_errors
async def stream_canonical_workflow_events(
    resource_id: str,
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> StreamingResponse:
    await _get_canonical_run(resource_id, run_id, current_user)

    return StreamingResponse(
        workflow_event_stream(WorkflowV2Store(_factory()), run_id, after_seq),
        media_type="text/event-stream",
    )


async def workflow_event_stream(
    store: WorkflowV2Store,
    run_id: str,
    after_seq: int,
    *,
    poll_seconds: float = 0.25,
) -> AsyncIterator[str]:
    """Replay and then tail the durable, run-local event sequence."""
    cursor = after_seq
    terminal = {"completed", "failed", "cancelled"}
    while True:
        events = await store.list_events(run_id, cursor)
        for event in events:
            cursor = event.seq
            yield f"id: {event.seq}\nevent: {event.event_type}\ndata: {json.dumps(event.payload, ensure_ascii=False)}\n\n"
        run = await store.get_run(run_id)
        if run is None or run.status in terminal:
            return
        await asyncio.sleep(poll_seconds)


def _run_write_roots(nodes: list[dict]) -> list[str]:
    """Collect every declared write root across a definition's nodes."""
    roots: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        action = node.get("action") or {}
        if not isinstance(action, dict):
            continue
        file_access = action.get("file_access") or {}
        if not isinstance(file_access, dict):
            continue
        roots.extend(file_access.get("write") or [])
    return roots


async def _run_definition(store: WorkflowV2Store, run) -> dict | None:
    """Resolve the definition a Run actually executed.

    Canonical Runs execute from the frozen resource snapshot taken at
    creation (the same closure the worker loads), so their definition is
    read from the resource catalog — the legacy workflow_definition_versions
    table never tracks resource versions. Legacy Runs fall back to the
    definition store, tolerating a missing exact version.
    """
    workflow_resource_id = getattr(run, "workflow_resource_id", None)
    if workflow_resource_id:
        async with store.session_factory() as session:
            snapshot = (
                await session.execute(
                    select(RunResourceSnapshot).where(
                        RunResourceSnapshot.run_id == run.run_id,
                        RunResourceSnapshot.resource_id == workflow_resource_id,
                    )
                )
            ).scalar_one_or_none()
            if snapshot is not None:
                version = (
                    await session.execute(
                        select(ResourceVersion).where(
                            ResourceVersion.resource_id == workflow_resource_id,
                            ResourceVersion.version == snapshot.version,
                        )
                    )
                ).scalar_one_or_none()
                if version is not None and isinstance(version.content, dict):
                    return version.content
    definition = await store.get_definition(run.workflow_name, run.definition_version)
    if definition is None:
        definition = await store.get_latest_definition(run.workflow_name)
    if definition is None:
        return None
    return definition.definition if isinstance(definition.definition, dict) else None


async def _run_artifacts(store: WorkflowV2Store, run) -> list[dict]:
    """List the files a run produced under its declared write roots.

    Roots are rendered against the persisted snapshot state so a run's
    artifacts can be browsed after completion; virtual paths are returned so
    host paths never leak to the client.
    """
    definition = await _run_definition(store, run)
    if definition is None:
        return []
    nodes = definition.get("nodes", []) if isinstance(definition, dict) else []
    write_roots = _run_write_roots(nodes)
    if not write_roots:
        return []
    snapshot = run.snapshot if isinstance(run.snapshot, dict) else {}
    state = {
        "inputs": run.inputs or {},
        "state": snapshot.get("state", {}),
        "outputs": snapshot.get("outputs", {}),
    }
    rendered = render_roots({"write": write_roots}, state)
    resolver = make_host_resolver(run.run_id, str(run.created_by))
    return collect_artifacts(rendered.get("write", []), resolver)


@router.get("/{resource_id}/workflow-runs/{run_id}/artifacts")
@_translate_resource_errors
async def list_canonical_run_artifacts(
    resource_id: str,
    run_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    run = await _get_canonical_run(resource_id, run_id, current_user)

    artifacts = await _run_artifacts(WorkflowV2Store(_factory()), run)
    return {"run_id": run_id, "workflow": resource_id, "artifacts": artifacts}


@router.get("/{resource_id}/workflow-runs/{run_id}/artifacts/content")
@_translate_resource_errors
async def get_canonical_run_artifact_content(
    resource_id: str,
    run_id: str,
    path: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> FileResponse:
    run = await _get_canonical_run(resource_id, run_id, current_user)

    artifacts = await _run_artifacts(WorkflowV2Store(_factory()), run)
    if not any(item["path"] == path for item in artifacts):
        raise ResourceNotFound(f"Artifact {path} not found for Run {run_id}")
    host = make_host_resolver(run.run_id, str(run.created_by))(path)
    if host is None or not Path(host).is_file():
        raise ResourceNotFound(f"Artifact {path} not found for Run {run_id}")
    return FileResponse(host, media_type="application/octet-stream", filename=Path(host).name)


@router.get("/{resource_id}/workflow-runs/{run_id}/record")
@_translate_resource_errors
async def download_canonical_run_record(
    resource_id: str,
    run_id: str,
    format: str = "md",
    current_user: UserModel = Depends(get_current_rbac_user),
) -> FileResponse:
    """Download the persisted run record (jsonl event log or markdown summary)."""
    if format not in {"jsonl", "md"}:
        raise ValueError("format must be 'jsonl' or 'md'")
    run = await _get_canonical_run(resource_id, run_id, current_user)
    host = make_host_resolver(run.run_id, str(run.created_by))(workflow_record_path(format))
    if host is None or not Path(host).is_file():
        raise ResourceNotFound(f"Run record for run '{run_id}' is not available")
    media_types = {"jsonl": "application/x-ndjson", "md": "text/markdown"}
    return FileResponse(host, media_type=media_types[format], filename=f"run_{run.run_id}.{format}")


@router.post("/{resource_id}/workflow-runs/{run_id}/commands")
@_translate_resource_errors
async def submit_canonical_workflow_command(
    resource_id: str,
    run_id: str,
    body: WorkflowCommandRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    run = await _get_canonical_run(resource_id, run_id, current_user)
    if body.type == "resume" and run.status == "failed":
        checkpointer = getattr(request.app.state, "checkpointer", None)
        if checkpointer is not None:
            checkpoint = await checkpointer.aget_tuple({"configurable": {"thread_id": run.checkpoint_thread_id}})
            if checkpoint is None:
                raise ResourceConflict("Run has no checkpoint to resume from")
    elif body.type == "resume" and current_user.role != UserRole.SUPER_ADMIN:
        async with _factory()() as session:
            version = (
                await session.execute(
                    select(ResourceVersion).where(
                        ResourceVersion.resource_id == resource_id,
                        ResourceVersion.version == run.definition_version,
                    )
                )
            ).scalar_one_or_none()
        if version is None or not isinstance(version.content, dict):
            raise ResourceConflict("Frozen Workflow definition is unavailable")
        required_roles = _required_canonical_resume_roles(run, version.content)
        if required_roles and current_user.role.value not in required_roles:
            raise ResourcePermissionDenied("You do not have permission to resume this Workflow")
    command = await WorkflowV2Store(_factory()).submit_command(
        body.command_id,
        run_id,
        body.type,
        body.payload,
        str(current_user.id),
    )
    return {
        "command_id": command.command_id,
        "run_id": command.run_id,
        "type": command.command_type,
        "accepted": True,
    }


@router.get("/admin/visibility-applications")
@_translate_resource_errors
async def list_visibility_applications(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        page = await ResourceService(
            session,
            _resource_actor(current_user),
        ).list_pending_visibility_applications(offset=offset, limit=limit)
        return {
            "items": [_visibility_application_payload(item) for item in page.items],
            "total": page.total,
            "offset": page.offset,
            "limit": page.limit,
        }


@router.get("/admin/retention-report")
@_translate_resource_errors
async def get_retention_report(
    retention_days: int = Query(default=90, ge=1, le=3650),
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    if current_user.role != UserRole.SUPER_ADMIN:
        raise ResourcePermissionDenied("Only super admin may inspect physical cleanup eligibility")
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    async with _factory()() as session:
        versions = await build_retention_report(session, cutoff=cutoff)
    return {
        "retention_days": retention_days,
        "cutoff": cutoff.isoformat(),
        "eligible_count": sum(item.eligible for item in versions),
        "blocked_count": sum(not item.eligible for item in versions),
        "versions": [item.payload() for item in versions],
        "destructive_action_performed": False,
    }


@router.post("/admin/visibility-applications/{application_id}/review")
@_translate_resource_errors
async def review_visibility_application(
    application_id: str,
    body: VisibilityReviewRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict[str, Any]:
    async with _factory()() as session:
        application = await ResourceService(
            session,
            _resource_actor(current_user),
        ).review_visibility_application(
            application_id,
            approve=body.approve,
            comment=body.comment,
            expected_version=body.version,
        )
        await session.commit()
        return _visibility_application_payload(application)
