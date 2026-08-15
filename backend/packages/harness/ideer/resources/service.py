"""Authorization boundary for canonical Skill, Agent, and Workflow resources."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Select, delete, func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceDraft,
    ResourceFavorite,
    ResourceNotification,
    ResourceStorageKind,
    ResourceType,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.visibility_application import VisibilityApplication
from ideer.persistence.models.workflow_v2 import WorkflowCommandRow, WorkflowTaskRow, WorkflowV2RunRow


class ResourceAction(StrEnum):
    READ = "resources:read"
    USE = "resources:use"
    WRITE = "resources:write"
    SUSPEND = "resources:suspend"
    TRANSFER = "resources:transfer"
    PURGE = "resources:purge"
    APPROVE = "resources:approve"


@dataclass(frozen=True)
class ResourceActor:
    user_id: str
    department_id: str | None
    role: str
    permissions: frozenset[str | ResourceAction]
    tool_groups: frozenset[str] | None = None

    def can(self, action: ResourceAction) -> bool:
        return action in self.permissions or action.value in self.permissions


@dataclass(frozen=True)
class ResourcePage:
    items: list[Resource]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class VisibilityApplicationPage:
    items: list[VisibilityApplication]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class ResolvedResource:
    resource: Resource
    version: ResourceVersion


class ResourceError(RuntimeError):
    """Base error for canonical resource operations."""


class ResourceNotFound(ResourceError):
    pass


class ResourcePermissionDenied(ResourceError):
    pass


class ResourceConflict(ResourceError):
    pass


class ResourceApprovalRequired(ResourceError):
    pass


class ResourceService:
    """Single authorization and lifecycle boundary for canonical resources."""

    def __init__(self, session: AsyncSession, actor: ResourceActor) -> None:
        self.session = session
        self.actor = actor

    def _require_action(self, action: ResourceAction) -> None:
        if not self.actor.can(action):
            raise ResourcePermissionDenied(f"Permission denied: {action.value}")

    def _visible_query(self) -> Select[tuple[Resource]]:
        query = select(Resource)
        if self.actor.role == "super_admin":
            return query
        conditions = [
            Resource.owner_id == self.actor.user_id,
            Resource.visibility == "public",
        ]
        if self.actor.department_id is not None:
            conditions.append((Resource.visibility == "department") & (Resource.scope_department_id == self.actor.department_id))
        return query.where(or_(*conditions))

    async def create_resource(
        self,
        *,
        resource_type: str,
        slug: str,
        display_name: str,
        storage_kind: str,
    ) -> Resource:
        self._require_action(ResourceAction.WRITE)
        try:
            canonical_type = ResourceType(resource_type)
            canonical_storage = ResourceStorageKind(storage_kind)
        except ValueError as exc:
            raise ValueError("Invalid resource type or storage kind") from exc
        if not slug.strip():
            raise ValueError("slug cannot be empty")
        if not display_name.strip():
            raise ValueError("display_name cannot be empty")
        if canonical_type == ResourceType.WORKFLOW and canonical_storage != ResourceStorageKind.DATABASE:
            raise ValueError("Workflow resources require database storage")
        if canonical_type != ResourceType.WORKFLOW and canonical_storage != ResourceStorageKind.FILESYSTEM:
            raise ValueError("Skill and Agent resources require filesystem storage")

        resource_id = str(uuid.uuid4())
        directory = {
            ResourceType.SKILL: "skills",
            ResourceType.AGENT: "agents",
            ResourceType.WORKFLOW: "workflows",
        }[canonical_type]
        resource = Resource(
            id=resource_id,
            type=canonical_type.value,
            slug=slug,
            display_name=display_name,
            owner_id=self.actor.user_id,
            visibility="private",
            scope_department_id=None,
            lifecycle_status="active",
            latest_version=0,
            draft_revision=0,
            storage_kind=canonical_storage.value,
            storage_key=f"{directory}/{resource_id}",
            system_owned=False,
            authz_revision=1,
        )
        self.session.add(resource)
        await self.session.flush()
        return resource

    async def list_visible(
        self,
        *,
        resource_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
        include_archived: bool = False,
    ) -> ResourcePage:
        self._require_action(ResourceAction.READ)
        if offset < 0:
            raise ValueError("offset must be non-negative")
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")

        query = self._visible_query()
        if resource_type is not None:
            query = query.where(Resource.type == resource_type)
        if not include_archived:
            query = query.where(Resource.lifecycle_status == "active")

        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total = int((await self.session.execute(count_query)).scalar_one())
        result = await self.session.execute(query.order_by(Resource.created_at, Resource.id).offset(offset).limit(limit))
        return ResourcePage(items=list(result.scalars()), total=total, offset=offset, limit=limit)

    async def _get_visible(self, resource_id: str, *, include_inactive: bool = False) -> Resource:
        query = self._visible_query().where(Resource.id == resource_id)
        if not include_inactive:
            query = query.where(Resource.lifecycle_status == "active")
        resource = (await self.session.execute(query)).scalar_one_or_none()
        if resource is None:
            raise ResourceNotFound(f"Resource {resource_id} not found")
        return resource

    async def get_visible(self, resource_id: str) -> Resource:
        self._require_action(ResourceAction.READ)
        return await self._get_visible(resource_id)

    async def resolve_legacy_alias(self, resource_type: str, slug: str) -> Resource:
        """Resolve a legacy name without silently choosing between shared matches."""

        self._require_action(ResourceAction.READ)
        query = self._visible_query().where(
            Resource.type == resource_type,
            Resource.slug == slug,
            Resource.lifecycle_status == "active",
        )
        resources = list((await self.session.execute(query.order_by(Resource.id))).scalars())
        owned = [resource for resource in resources if resource.owner_id == self.actor.user_id]
        if owned:
            return owned[0]
        if not resources:
            raise ResourceNotFound(f"Resource alias {resource_type}/{slug} not found")
        if len(resources) > 1:
            raise ResourceConflict(f"Multiple visible {resource_type} resources use slug '{slug}'")
        return resources[0]

    async def resolve_for_use(self, resource_id: str) -> Resource:
        self._require_action(ResourceAction.USE)
        return await self._get_visible(resource_id)

    async def favorite(self, resource_id: str) -> ResourceFavorite:
        self._require_action(ResourceAction.READ)
        await self._get_visible(resource_id)
        favorite = await self.session.get(ResourceFavorite, (self.actor.user_id, resource_id))
        if favorite is None:
            favorite = ResourceFavorite(user_id=self.actor.user_id, resource_id=resource_id)
            self.session.add(favorite)
            await self.session.flush()
        return favorite

    async def unfavorite(self, resource_id: str) -> bool:
        self._require_action(ResourceAction.READ)
        favorite = await self.session.get(ResourceFavorite, (self.actor.user_id, resource_id))
        if favorite is None:
            return False
        await self.session.delete(favorite)
        await self.session.flush()
        return True

    def assert_modify(self, resource: Resource) -> None:
        self._require_action(ResourceAction.WRITE)
        if resource.system_owned or resource.owner_id != self.actor.user_id:
            raise ResourcePermissionDenied("Only the resource owner may modify owner content")

    async def _withdraw_pending_applications(self, resource_id: str) -> None:
        await self.session.execute(
            update(VisibilityApplication)
            .where(
                VisibilityApplication.canonical_resource_id == resource_id,
                VisibilityApplication.status == "pending",
            )
            .values(status="withdrawn")
        )

    async def _notify_dependent_owners(
        self,
        resource: Resource,
        *,
        event: str,
        detail: dict,
    ) -> None:
        rows = (
            await self.session.execute(
                select(Resource.owner_id, Resource.id)
                .join(
                    ResourceDependency,
                    ResourceDependency.source_resource_id == Resource.id,
                )
                .where(
                    ResourceDependency.target_resource_id == resource.id,
                    Resource.owner_id != self.actor.user_id,
                )
            )
        ).all()
        by_owner: dict[str, list[str]] = {}
        for owner_id, dependent_resource_id in rows:
            by_owner.setdefault(owner_id, []).append(dependent_resource_id)
        for owner_id, dependent_resource_ids in by_owner.items():
            self.session.add(
                ResourceNotification(
                    id=str(uuid.uuid4()),
                    recipient_id=owner_id,
                    resource_id=resource.id,
                    event=event,
                    detail={
                        **detail,
                        "dependent_resource_ids": sorted(dependent_resource_ids),
                    },
                )
            )

    async def change_visibility(
        self,
        resource_id: str,
        visibility: str,
        *,
        scope_department_id: str | None = None,
    ) -> Resource:
        resource = await self._get_visible(resource_id)
        self.assert_modify(resource)
        ranks = {"private": 0, "department": 1, "public": 2}
        if visibility not in ranks:
            raise ValueError(f"Invalid visibility: {visibility}")
        if visibility == "department" and scope_department_id is None:
            raise ValueError("scope_department_id is required for department visibility")
        if ranks[visibility] > ranks[resource.visibility]:
            raise ResourceApprovalRequired("Visibility expansion requires approval")

        changed = resource.visibility != visibility or (visibility == "department" and resource.scope_department_id != scope_department_id)
        if not changed:
            return resource
        resource.visibility = visibility
        resource.scope_department_id = scope_department_id if visibility == "department" else None
        resource.authz_revision += 1
        await self._withdraw_pending_applications(resource.id)
        await self._notify_dependent_owners(
            resource,
            event="visibility_reduced",
            detail={
                "visibility": visibility,
                "scope_department_id": resource.scope_department_id,
            },
        )
        await self.session.flush()
        return resource

    async def request_visibility(
        self,
        resource_id: str,
        *,
        target_visibility: str,
        scope_department_id: str | None,
        reason: str,
    ) -> VisibilityApplication:
        resource = await self._get_visible(resource_id)
        self.assert_modify(resource)
        ranks = {"private": 0, "department": 1, "public": 2}
        if target_visibility not in ranks or ranks[target_visibility] <= ranks[resource.visibility]:
            raise ValueError("Visibility application must expand access")
        if target_visibility == "department" and scope_department_id is None:
            raise ValueError("scope_department_id is required for department visibility")
        if resource.latest_version < 1:
            raise ResourceConflict("Only a published resource may expand visibility")
        pending = (
            await self.session.execute(
                select(VisibilityApplication.id).where(
                    VisibilityApplication.canonical_resource_id == resource.id,
                    VisibilityApplication.status == "pending",
                )
            )
        ).scalar_one_or_none()
        if pending is not None:
            raise ResourceConflict("Resource already has a pending visibility application")
        published = (
            await self.session.execute(
                select(ResourceVersion).where(
                    ResourceVersion.resource_id == resource.id,
                    ResourceVersion.version == resource.latest_version,
                )
            )
        ).scalar_one_or_none()
        if published is None:
            raise ResourceConflict("Resource latest version is missing")
        application = VisibilityApplication(
            id=str(uuid.uuid4()),
            resource_type=resource.type,
            resource_id=resource.slug,
            canonical_resource_id=resource.id,
            requested_version=published.version,
            requested_hash=published.content_hash,
            applicant_id=self.actor.user_id,
            current_visibility=resource.visibility,
            target_visibility=target_visibility,
            department_id=scope_department_id if target_visibility == "department" else self.actor.department_id,
            reason=reason,
            status="pending",
            version=1,
        )
        self.session.add(application)
        await self.session.flush()
        return application

    def _visibility_review_query(self) -> Select[tuple[VisibilityApplication]]:
        self._require_action(ResourceAction.APPROVE)
        query = select(VisibilityApplication).where(
            VisibilityApplication.canonical_resource_id.is_not(None),
            VisibilityApplication.status == "pending",
        )
        if self.actor.role == "super_admin":
            return query
        if self.actor.role != "department_admin" or self.actor.department_id is None:
            raise ResourcePermissionDenied("Only an authorized admin may review visibility applications")
        return query.where(VisibilityApplication.department_id == self.actor.department_id)

    async def list_pending_visibility_applications(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> VisibilityApplicationPage:
        if offset < 0:
            raise ValueError("offset must be non-negative")
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        query = self._visibility_review_query()
        total = int((await self.session.execute(select(func.count()).select_from(query.subquery()))).scalar_one())
        applications = list((await self.session.execute(query.order_by(VisibilityApplication.submitted_at, VisibilityApplication.id).offset(offset).limit(limit))).scalars())
        return VisibilityApplicationPage(items=applications, total=total, offset=offset, limit=limit)

    async def review_visibility_application(
        self,
        application_id: str,
        *,
        approve: bool,
        comment: str,
        expected_version: int | None = None,
    ) -> VisibilityApplication:
        query = self._visibility_review_query().where(VisibilityApplication.id == application_id)
        if expected_version is not None:
            query = query.where(VisibilityApplication.version == expected_version)
        application = (await self.session.execute(query)).scalar_one_or_none()
        if application is None:
            exists = await self.session.get(VisibilityApplication, application_id)
            if exists is not None and expected_version is not None:
                raise ResourceConflict(f"Visibility application version changed from {expected_version}")
            if exists is not None and self.actor.role == "department_admin":
                raise ResourcePermissionDenied("Department admin cannot review another department")
            raise ResourceNotFound(f"Visibility application {application_id} not found")
        resource = await self.session.get(Resource, application.canonical_resource_id)
        if resource is None or resource.lifecycle_status != "active":
            raise ResourceConflict("Visibility application resource is not active")

        if approve:
            version = (
                await self.session.execute(
                    select(ResourceVersion).where(
                        ResourceVersion.resource_id == resource.id,
                        ResourceVersion.version == application.requested_version,
                    )
                )
            ).scalar_one_or_none()
            if version is None or resource.latest_version != application.requested_version or version.content_hash != application.requested_hash or resource.visibility != application.current_visibility:
                raise ResourceConflict("Visibility application is stale")
            targets = list((await self.session.execute(select(Resource).join(ResourceDependency, ResourceDependency.target_resource_id == Resource.id).where(ResourceDependency.source_resource_id == resource.id))).scalars())
            for target in targets:
                self._assert_visibility_closure(
                    resource,
                    target,
                    source_visibility=application.target_visibility,
                    source_department_id=application.department_id,
                )
            resource.visibility = application.target_visibility
            resource.scope_department_id = application.department_id if application.target_visibility == "department" else None
            resource.authz_revision += 1
            application.status = "approved"
        else:
            application.status = "rejected"
        application.reviewed_by = self.actor.user_id
        application.reviewed_at = datetime.now(UTC)
        application.review_comment = comment
        application.version += 1
        await self.session.flush()
        return application

    async def archive(self, resource_id: str) -> Resource:
        resource = await self._get_visible(resource_id)
        self.assert_modify(resource)
        if resource.lifecycle_status != "archived":
            resource.lifecycle_status = "archived"
            resource.authz_revision += 1
            await self._withdraw_pending_applications(resource.id)
            await self._notify_dependent_owners(
                resource,
                event="resource_archived",
                detail={},
            )
            await self.session.flush()
        return resource

    async def suspend(self, resource_id: str) -> Resource:
        self._require_action(ResourceAction.SUSPEND)
        if self.actor.role != "super_admin":
            raise ResourcePermissionDenied("Only a super admin may suspend a resource")
        resource = await self.session.get(Resource, resource_id)
        if resource is None:
            raise ResourceNotFound(f"Resource {resource_id} not found")
        if resource.lifecycle_status != "suspended":
            resource.lifecycle_status = "suspended"
            resource.authz_revision += 1
            await self._withdraw_pending_applications(resource.id)
            await self._cancel_snapshotted_workflow_runs(resource.id)
            await self._notify_dependent_owners(
                resource,
                event="resource_suspended",
                detail={},
            )
            await self.session.flush()
        return resource

    async def _cancel_snapshotted_workflow_runs(self, resource_id: str) -> None:
        run_ids = list((await self.session.execute(select(RunResourceSnapshot.run_id).where(RunResourceSnapshot.resource_id == resource_id).distinct())).scalars())
        if not run_ids:
            return
        tasks = list(
            (
                await self.session.execute(
                    select(WorkflowTaskRow).where(
                        WorkflowTaskRow.run_id.in_(run_ids),
                        WorkflowTaskRow.status.in_(["queued", "running", "paused"]),
                    )
                )
            ).scalars()
        )
        for task in tasks:
            run = await self.session.get(WorkflowV2RunRow, task.run_id)
            if run is None or run.status not in {"queued", "running", "paused"}:
                continue
            self.session.add(
                WorkflowCommandRow(
                    command_id=str(uuid.uuid4()),
                    run_id=task.run_id,
                    command_type="cancel",
                    payload={"reason": "resource_suspended", "resource_id": resource_id},
                    created_by=self.actor.user_id,
                )
            )
            if task.status in {"queued", "paused"}:
                task.status = "cancelled"
                run.status = "cancelled"
            else:
                task.cancel_requested = True

    async def restore(self, resource_id: str) -> Resource:
        self._require_action(ResourceAction.SUSPEND)
        if self.actor.role != "super_admin":
            raise ResourcePermissionDenied("Only a super admin may restore a suspended resource")
        resource = await self.session.get(Resource, resource_id)
        if resource is None:
            raise ResourceNotFound(f"Resource {resource_id} not found")
        if resource.lifecycle_status != "suspended":
            raise ResourceConflict("Only a suspended resource may be restored")
        resource.lifecycle_status = "active"
        resource.authz_revision += 1
        await self.session.flush()
        return resource

    async def transfer_owner(
        self,
        resource_id: str,
        target_owner_id: str,
        *,
        new_slug: str | None = None,
    ) -> Resource:
        self._require_action(ResourceAction.TRANSFER)
        if self.actor.role != "super_admin":
            raise ResourcePermissionDenied("Only a super admin may transfer a resource")
        resource = await self.session.get(Resource, resource_id)
        if resource is None:
            raise ResourceNotFound(f"Resource {resource_id} not found")
        target_slug = new_slug or resource.slug
        if not target_slug.strip():
            raise ValueError("slug cannot be empty")
        collision = (
            await self.session.execute(
                select(Resource.id).where(
                    Resource.type == resource.type,
                    Resource.owner_id == target_owner_id,
                    Resource.slug == target_slug,
                    Resource.id != resource.id,
                )
            )
        ).scalar_one_or_none()
        if collision is not None:
            raise ResourceConflict(f"Target owner already has {resource.type} slug '{target_slug}'")

        previous_owner_id = resource.owner_id
        resource.owner_id = target_owner_id
        resource.slug = target_slug
        resource.visibility = "private"
        resource.scope_department_id = None
        resource.authz_revision += 1
        await self._withdraw_pending_applications(resource.id)
        await self._notify_dependent_owners(
            resource,
            event="ownership_transferred",
            detail={
                "previous_owner_id": previous_owner_id,
                "target_owner_id": target_owner_id,
                "visibility": "private",
            },
        )
        await self.session.flush()
        return resource

    async def govern_owner_deletion(
        self,
        owner_id: str,
        *,
        strategy: str,
        target_owner_id: str | None = None,
    ) -> list[Resource]:
        """Apply account deletion policy without hard-deleting catalog history."""

        self._require_action(ResourceAction.PURGE)
        if self.actor.role != "super_admin":
            raise ResourcePermissionDenied("Only a super admin may govern deleted-owner resources")
        if strategy not in {"transfer", "archive"}:
            raise ValueError("Owner deletion strategy must be transfer or archive")
        if strategy == "transfer":
            self._require_action(ResourceAction.TRANSFER)
            if target_owner_id is None:
                raise ValueError("target_owner_id is required for transfer")

        resources = list((await self.session.execute(select(Resource).where(Resource.owner_id == owner_id).order_by(Resource.id))).scalars())
        if strategy == "transfer":
            collisions = (
                list(
                    (
                        await self.session.execute(
                            select(Resource.type, Resource.slug).where(
                                Resource.owner_id == target_owner_id,
                                tuple_(Resource.type, Resource.slug).in_([(resource.type, resource.slug) for resource in resources]),
                            )
                        )
                    ).all()
                )
                if resources
                else []
            )
            if collisions:
                resource_type, slug = collisions[0]
                raise ResourceConflict(f"Target owner already has {resource_type} slug '{slug}'")
            for resource in resources:
                resource.owner_id = target_owner_id
                resource.visibility = "private"
                resource.scope_department_id = None
                resource.authz_revision += 1
                await self._withdraw_pending_applications(resource.id)
                await self._notify_dependent_owners(
                    resource,
                    event="owner_deleted_resource_transferred",
                    detail={
                        "previous_owner_id": owner_id,
                        "target_owner_id": target_owner_id,
                        "visibility": "private",
                    },
                )
        else:
            for resource in resources:
                if resource.lifecycle_status != "archived":
                    resource.lifecycle_status = "archived"
                    resource.authz_revision += 1
                await self._withdraw_pending_applications(resource.id)
                await self._notify_dependent_owners(
                    resource,
                    event="owner_deleted_resource_archived",
                    detail={"previous_owner_id": owner_id},
                )
        await self.session.flush()
        return resources

    async def govern_department_deletion(
        self,
        department_id: str,
        *,
        target_department_id: str | None,
    ) -> list[Resource]:
        """Move department scope or immediately narrow it before department deletion."""

        self._require_action(ResourceAction.PURGE)
        if self.actor.role != "super_admin":
            raise ResourcePermissionDenied("Only a super admin may govern deleted-department resources")
        resources = list((await self.session.execute(select(Resource).where(Resource.scope_department_id == department_id).order_by(Resource.id))).scalars())
        for resource in resources:
            if target_department_id is None:
                resource.visibility = "private"
                resource.scope_department_id = None
            else:
                resource.scope_department_id = target_department_id
            resource.authz_revision += 1
            await self._withdraw_pending_applications(resource.id)
            await self._notify_dependent_owners(
                resource,
                event="department_scope_changed",
                detail={
                    "previous_department_id": department_id,
                    "target_department_id": target_department_id,
                    "visibility": resource.visibility,
                },
            )
        await self.session.flush()
        return resources

    async def get_owner_draft(self, resource_id: str) -> ResourceDraft:
        self._require_action(ResourceAction.READ)
        resource = await self.session.get(Resource, resource_id)
        if resource is None or resource.owner_id != self.actor.user_id:
            raise ResourceNotFound(f"Resource {resource_id} not found")
        draft = await self.session.get(ResourceDraft, resource_id)
        if draft is None:
            raise ResourceNotFound(f"Draft for resource {resource_id} not found")
        return draft

    async def save_draft(
        self,
        resource_id: str,
        *,
        expected_revision: int,
        content_hash: str,
        storage_key: str,
        content: dict | None = None,
    ) -> ResourceDraft:
        resource = await self._get_visible(resource_id)
        self.assert_modify(resource)
        if resource.draft_revision != expected_revision:
            raise ResourceConflict(f"Expected draft revision {expected_revision}, current draft revision is {resource.draft_revision}")
        revision = expected_revision + 1
        draft = await self.session.get(ResourceDraft, resource_id)
        if draft is None:
            draft = ResourceDraft(
                resource_id=resource.id,
                revision=revision,
                content_hash=content_hash,
                storage_key=storage_key,
                content=copy.deepcopy(content),
                modified_by=self.actor.user_id,
            )
            self.session.add(draft)
        else:
            draft.revision = revision
            draft.content_hash = content_hash
            draft.storage_key = storage_key
            draft.content = copy.deepcopy(content)
            draft.modified_by = self.actor.user_id
        resource.draft_revision = revision
        await self.session.flush()
        return draft

    async def publish(
        self,
        resource_id: str,
        *,
        expected_draft_revision: int,
        scan_result: dict,
    ) -> ResourceVersion:
        resource = await self._get_visible(resource_id)
        self.assert_modify(resource)
        draft = await self.session.get(ResourceDraft, resource_id)
        if draft is None or draft.revision != expected_draft_revision or resource.draft_revision != expected_draft_revision:
            raise ResourceConflict("Draft revision changed before publication")
        version = ResourceVersion(
            id=str(uuid.uuid4()),
            resource_id=resource.id,
            version=resource.latest_version + 1,
            content_hash=draft.content_hash,
            storage_key=draft.storage_key,
            scan_result=dict(scan_result),
            content=copy.deepcopy(draft.content),
            created_by=self.actor.user_id,
        )
        self.session.add(version)
        resource.latest_version = version.version
        await self.session.delete(draft)
        await self.session.flush()
        return version

    async def get_published_content(self, resource_id: str, *, version: int | None = None) -> ResourceVersion:
        self._require_action(ResourceAction.READ)
        resource = await self._get_visible(resource_id)
        requested_version = resource.latest_version if version is None else version
        if requested_version < 1:
            raise ResourceNotFound(f"Published resource {resource_id} not found")
        published = (
            await self.session.execute(
                select(ResourceVersion).where(
                    ResourceVersion.resource_id == resource.id,
                    ResourceVersion.version == requested_version,
                )
            )
        ).scalar_one_or_none()
        if published is None:
            raise ResourceNotFound(f"Published resource {resource_id}@{requested_version} not found")
        return published

    async def rollback(
        self,
        resource_id: str,
        *,
        source_version: int,
        copied_storage_key: str | None = None,
    ) -> ResourceVersion:
        resource = await self._get_visible(resource_id)
        self.assert_modify(resource)
        source = (
            await self.session.execute(
                select(ResourceVersion).where(
                    ResourceVersion.resource_id == resource.id,
                    ResourceVersion.version == source_version,
                )
            )
        ).scalar_one_or_none()
        if source is None:
            raise ResourceNotFound(f"Published resource {resource_id}@{source_version} not found")
        version = ResourceVersion(
            id=str(uuid.uuid4()),
            resource_id=resource.id,
            version=resource.latest_version + 1,
            content_hash=source.content_hash,
            storage_key=copied_storage_key or source.storage_key,
            scan_result=dict(source.scan_result),
            content=copy.deepcopy(source.content),
            created_by=self.actor.user_id,
            source_resource_id=resource.id,
            source_version=source.version,
        )
        self.session.add(version)
        resource.latest_version = version.version
        await self.session.flush()
        return version

    @staticmethod
    def _assert_dependency_type(source: Resource, target: Resource) -> None:
        allowed_targets = {
            "skill": set(),
            "agent": {"skill"},
            "workflow": {"agent", "skill"},
        }
        if target.type not in allowed_targets[source.type]:
            raise ResourceConflict(f"{source.type} resources cannot depend on {target.type} resources")

    @staticmethod
    def _assert_visibility_closure(
        source: Resource,
        target: Resource,
        *,
        source_visibility: str | None = None,
        source_department_id: str | None = None,
    ) -> None:
        visibility = source.visibility if source_visibility is None else source_visibility
        department_id = source.scope_department_id if source_department_id is None else source_department_id
        if visibility == "public" and target.visibility != "public":
            raise ResourceConflict("Dependency violates public visibility closure")
        if visibility == "department":
            valid_department = target.visibility == "department" and target.scope_department_id == department_id
            if target.visibility != "public" and not valid_department:
                raise ResourceConflict("Dependency violates department visibility closure")

    async def replace_dependencies(self, resource_id: str, target_resource_ids: list[str]) -> list[ResourceDependency]:
        self._require_action(ResourceAction.USE)
        source = await self._get_visible(resource_id)
        self.assert_modify(source)
        if len(target_resource_ids) != len(set(target_resource_ids)):
            raise ResourceConflict("Duplicate resource dependency")

        targets: list[Resource] = []
        for target_id in target_resource_ids:
            if target_id == source.id:
                raise ResourceConflict("Resource dependency cycle: self dependency")
            target = await self._get_visible(target_id)
            self._assert_dependency_type(source, target)
            self._assert_visibility_closure(source, target)
            targets.append(target)

        await self.session.execute(delete(ResourceDependency).where(ResourceDependency.source_resource_id == source.id))
        dependencies = [
            ResourceDependency(
                id=str(uuid.uuid4()),
                source_resource_id=source.id,
                target_resource_id=target.id,
            )
            for target in targets
        ]
        self.session.add_all(dependencies)
        await self.session.flush()
        return dependencies

    async def resolve_dependency_closure(self, root_resource_id: str) -> list[ResolvedResource]:
        self._require_action(ResourceAction.USE)
        resolved: list[ResolvedResource] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        async def visit(resource_id: str) -> None:
            if resource_id in visiting:
                raise ResourceConflict(f"Resource dependency cycle includes {resource_id}")
            if resource_id in visited:
                return
            visiting.add(resource_id)
            resource = await self._get_visible(resource_id)
            if resource.latest_version < 1:
                raise ResourceConflict(f"Resource {resource_id} has no published version")
            version = (
                await self.session.execute(
                    select(ResourceVersion).where(
                        ResourceVersion.resource_id == resource.id,
                        ResourceVersion.version == resource.latest_version,
                    )
                )
            ).scalar_one_or_none()
            if version is None:
                raise ResourceConflict(f"Resource {resource_id} latest version is missing")
            resolved.append(ResolvedResource(resource=resource, version=version))
            target_ids = list((await self.session.execute(select(ResourceDependency.target_resource_id).where(ResourceDependency.source_resource_id == resource.id).order_by(ResourceDependency.target_resource_id))).scalars())
            for target_id in target_ids:
                target = await self._get_visible(target_id)
                self._assert_visibility_closure(resource, target)
                await visit(target_id)
            visiting.remove(resource_id)
            visited.add(resource_id)

        await visit(root_resource_id)
        return resolved

    async def create_run_snapshot(self, run_id: str, root_resource_id: str) -> list[RunResourceSnapshot]:
        existing = (await self.session.execute(select(RunResourceSnapshot.id).where(RunResourceSnapshot.run_id == run_id).limit(1))).scalar_one_or_none()
        if existing is not None:
            raise ResourceConflict(f"Run {run_id} already has a resource snapshot")
        closure = await self.resolve_dependency_closure(root_resource_id)
        snapshots = [
            RunResourceSnapshot(
                id=str(uuid.uuid4()),
                run_id=run_id,
                root_resource_id=root_resource_id,
                resource_id=item.resource.id,
                version=item.version.version,
                content_hash=item.version.content_hash,
                authz_revision=item.resource.authz_revision,
            )
            for item in closure
        ]
        self.session.add_all(snapshots)
        await self.session.flush()
        return snapshots

    async def fork(
        self,
        source_resource_id: str,
        *,
        slug: str,
        display_name: str,
        copied_storage_key: str,
        target_resource_id: str | None = None,
    ) -> Resource:
        self._require_action(ResourceAction.WRITE)
        source = await self.resolve_for_use(source_resource_id)
        source_version = await self.get_published_content(source.id)
        collision = (
            await self.session.execute(
                select(Resource.id).where(
                    Resource.type == source.type,
                    Resource.owner_id == self.actor.user_id,
                    Resource.slug == slug,
                )
            )
        ).scalar_one_or_none()
        if collision is not None:
            raise ResourceConflict(f"Current owner already has {source.type} slug '{slug}'")

        edges = list((await self.session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == source.id))).scalars())
        for edge in edges:
            await self._get_visible(edge.target_resource_id)

        resource = Resource(
            id=target_resource_id or str(uuid.uuid4()),
            type=source.type,
            slug=slug,
            display_name=display_name,
            owner_id=self.actor.user_id,
            visibility="private",
            scope_department_id=None,
            lifecycle_status="active",
            latest_version=1,
            draft_revision=0,
            storage_kind=source.storage_kind,
            storage_key=copied_storage_key,
            system_owned=False,
            authz_revision=1,
        )
        self.session.add(resource)
        self.session.add(
            ResourceVersion(
                id=str(uuid.uuid4()),
                resource_id=resource.id,
                version=1,
                content_hash=source_version.content_hash,
                storage_key=copied_storage_key,
                scan_result=dict(source_version.scan_result),
                content=copy.deepcopy(source_version.content),
                created_by=self.actor.user_id,
                source_resource_id=source.id,
                source_version=source_version.version,
            )
        )
        self.session.add_all(
            [
                ResourceDependency(
                    id=str(uuid.uuid4()),
                    source_resource_id=resource.id,
                    target_resource_id=edge.target_resource_id,
                )
                for edge in edges
            ]
        )
        await self.session.flush()
        return resource
