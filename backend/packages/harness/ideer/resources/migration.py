"""Auditable migration from legacy name-addressed resources to the UUID catalog."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceDraft,
    ResourceFavorite,
    ResourceNotification,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.visibility_application import VisibilityApplication
from ideer.persistence.models.workflow_v2 import WorkflowDefinitionVersionRow
from ideer.resources.service import ResourceConflict
from ideer.resources.storage import ResourceStorage, StorageValidationError

_MIGRATION_NAMESPACE = uuid.UUID("64e2b7b8-24ac-5db8-94ba-4666b652c865")
_BUNDLED_NAMESPACE = uuid.UUID("6b82cb67-10bd-5d87-94ef-a0bb26cdcf1c")
_AGENT_RUNTIME_ENTRIES = {"agent-memory", "memory.json", "outputs", "threads", "uploads", "user-data"}


def stable_resource_id(resource_type: str, owner_id: str, slug: str) -> str:
    return str(uuid.uuid5(_MIGRATION_NAMESPACE, f"{resource_type}:{owner_id}:{slug}"))


def stable_bundled_resource_id(resource_type: str, slug: str) -> str:
    return str(uuid.uuid5(_BUNDLED_NAMESPACE, f"{resource_type}:{slug}"))


def _json_hash(content: dict) -> str:
    canonical = json.dumps(content, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class MigrationItem:
    resource_type: str
    slug: str
    owner_id: str
    resource_id: str
    content_hash: str | None
    error: str | None = None


@dataclass
class CatalogMigrationReport:
    items: list[MigrationItem] = field(default_factory=list)
    created: int = 0
    unchanged: int = 0
    removed: int = 0

    @property
    def errors(self) -> list[str]:
        return [item.error for item in self.items if item.error is not None]


@dataclass(frozen=True)
class _LegacySource:
    metadata: ResourceMetadata
    resource_id: str
    path: Path | None
    workflow_definition: dict | None
    content_hash: str | None


@dataclass(frozen=True)
class _DependencyPlan:
    target_ids: tuple[str, ...]
    workflow_definition: dict | None
    canonical_hash: str | None
    error: str | None = None


class LegacyResourceMigrator:
    """Read legacy sources without modifying them and create deterministic V2 rows."""

    def __init__(
        self,
        session: AsyncSession,
        storage: ResourceStorage,
        *,
        legacy_base_dir: str | Path,
        skills_root: str | Path,
    ) -> None:
        self.session = session
        self.storage = storage
        self.legacy_base_dir = Path(legacy_base_dir)
        self.skills_root = Path(skills_root)

    def _source_path(self, metadata: ResourceMetadata) -> Path:
        if metadata.resource_type == "skill":
            return self.skills_root / "custom" / metadata.resource_id
        user_path = self.legacy_base_dir / "users" / metadata.owner_id / "agents" / metadata.resource_id.lower()
        if user_path.is_dir():
            return user_path
        return self.legacy_base_dir / "agents" / metadata.resource_id.lower()

    @contextmanager
    def _definition_source(self, resource_type: str, source: Path) -> Iterator[Path]:
        if resource_type != "agent":
            yield source
            return
        with tempfile.TemporaryDirectory(prefix="resource-migration-") as temporary:
            target_root = Path(temporary)
            for entry in sorted(source.rglob("*")):
                relative = entry.relative_to(source)
                if entry.is_symlink():
                    raise StorageValidationError(f"Resource contains symlink: {relative.as_posix()}")
                if relative.parts[0] in _AGENT_RUNTIME_ENTRIES:
                    continue
                target = target_root / relative
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif entry.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(entry, target)
                else:
                    raise StorageValidationError(f"Resource contains non-regular file: {relative.as_posix()}")
            yield target_root

    async def _legacy_sources(self) -> list[_LegacySource]:
        metadata_rows = list(
            (
                await self.session.execute(select(ResourceMetadata).where(ResourceMetadata.resource_type.in_(["skill", "agent", "workflow"])).order_by(ResourceMetadata.resource_type, ResourceMetadata.resource_id, ResourceMetadata.owner_id))
            ).scalars()
        )
        sources: list[_LegacySource] = []
        for metadata in metadata_rows:
            resource_id = (
                stable_bundled_resource_id(
                    metadata.resource_type,
                    metadata.resource_id,
                )
                if metadata.imported_from == "bundled"
                else stable_resource_id(
                    metadata.resource_type,
                    metadata.owner_id,
                    metadata.resource_id,
                )
            )
            if metadata.resource_type == "workflow":
                definition = (
                    await self.session.execute(select(WorkflowDefinitionVersionRow.definition).where(WorkflowDefinitionVersionRow.workflow_name == metadata.resource_id).order_by(WorkflowDefinitionVersionRow.version.desc()).limit(1))
                ).scalar_one_or_none()
                sources.append(
                    _LegacySource(
                        metadata=metadata,
                        resource_id=resource_id,
                        path=None,
                        workflow_definition=definition,
                        content_hash=_json_hash(definition) if definition is not None else None,
                    )
                )
                continue
            path = self._source_path(metadata)
            content_hash: str | None = None
            if path.is_dir():
                try:
                    with self._definition_source(metadata.resource_type, path) as definition_source:
                        content_hash = self.storage.inspect_directory(metadata.resource_type, definition_source).content_hash
                except (OSError, StorageValidationError):
                    content_hash = None
            sources.append(
                _LegacySource(
                    metadata=metadata,
                    resource_id=resource_id,
                    path=path,
                    workflow_definition=None,
                    content_hash=content_hash,
                )
            )
        return sources

    @staticmethod
    def _item(source: _LegacySource, *, error: str | None = None) -> MigrationItem:
        return MigrationItem(
            resource_type=source.metadata.resource_type,
            slug=source.metadata.resource_id,
            owner_id=source.metadata.owner_id,
            resource_id=source.resource_id,
            content_hash=source.content_hash,
            error=error,
        )

    @staticmethod
    def _is_visible_to(source: _LegacySource, target: _LegacySource) -> bool:
        if source.metadata.owner_id == target.metadata.owner_id:
            return True
        if target.metadata.visibility == "public":
            return True
        return target.metadata.visibility == "department" and source.metadata.department_id is not None and source.metadata.department_id == target.metadata.department_id

    @staticmethod
    def _visibility_closure_allows(source: _LegacySource, target: _LegacySource) -> bool:
        if source.metadata.visibility == "public":
            return target.metadata.visibility == "public"
        if source.metadata.visibility == "department":
            return target.metadata.visibility == "public" or (target.metadata.visibility == "department" and source.metadata.department_id is not None and source.metadata.department_id == target.metadata.department_id)
        return True

    def _resolve_dependency(
        self,
        source: _LegacySource,
        sources: list[_LegacySource],
        *,
        target_type: str,
        slug: str,
    ) -> tuple[_LegacySource | None, str | None]:
        candidates = [candidate for candidate in sources if candidate.metadata.resource_type == target_type and candidate.metadata.resource_id == slug and self._is_visible_to(source, candidate)]
        owned = [candidate for candidate in candidates if candidate.metadata.owner_id == source.metadata.owner_id]
        if owned:
            target = owned[0]
        elif len(candidates) == 1:
            target = candidates[0]
        elif not candidates:
            return None, f"missing {target_type.title()} dependency '{slug}'"
        else:
            return None, f"ambiguous {target_type.title()} dependency '{slug}'"
        if not self._visibility_closure_allows(source, target):
            return None, f"visibility closure rejects {target_type.title()} dependency '{slug}'"
        return target, None

    @staticmethod
    def _agent_skill_names(source: _LegacySource) -> list[str]:
        if source.path is None:
            return []
        try:
            raw = yaml.safe_load((source.path / "config.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"Agent config is invalid: {exc}") from exc
        skills = raw.get("skills") if isinstance(raw, dict) else None
        if skills is None:
            return []
        if not isinstance(skills, list) or any(not isinstance(name, str) or not name for name in skills):
            raise ValueError("Agent skills must be a list of non-empty names")
        return list(dict.fromkeys(skills))

    @staticmethod
    def _workflow_agent_references(definition: dict) -> list[tuple[dict, str, str]]:
        references: list[tuple[dict, str, str]] = []
        nodes = definition.get("nodes", [])
        if not isinstance(nodes, list):
            raise ValueError("Workflow nodes must be a list")
        for node in nodes:
            if not isinstance(node, dict):
                continue
            action = node.get("action")
            if isinstance(action, dict) and action.get("kind") == "agent":
                name = action.get("name")
                if not isinstance(name, str) or not name:
                    raise ValueError("Workflow Agent action requires a non-empty name")
                references.append((action, "name", name))
            elif node.get("type") == "agent":
                name = node.get("agent")
                if not isinstance(name, str) or not name:
                    raise ValueError("Legacy Workflow Agent step requires a non-empty agent")
                references.append((node, "agent", name))
        return references

    def _dependency_plans(self, sources: list[_LegacySource]) -> dict[str, _DependencyPlan]:
        plans: dict[str, _DependencyPlan] = {}
        for source in sources:
            targets: list[str] = []
            workflow_definition = deepcopy(source.workflow_definition)
            try:
                if source.metadata.resource_type == "agent":
                    references = [("skill", name, None, None) for name in self._agent_skill_names(source)]
                elif source.metadata.resource_type == "workflow" and workflow_definition is not None:
                    references = [("agent", name, container, key) for container, key, name in self._workflow_agent_references(workflow_definition)]
                else:
                    references = []
                for target_type, slug, container, key in references:
                    target, error = self._resolve_dependency(
                        source,
                        sources,
                        target_type=target_type,
                        slug=slug,
                    )
                    if error is not None or target is None:
                        raise ValueError(error or f"unresolved {target_type} dependency '{slug}'")
                    targets.append(target.resource_id)
                    if container is not None and key is not None:
                        container[key] = target.resource_id
            except ValueError as exc:
                plans[source.resource_id] = _DependencyPlan((), workflow_definition, None, str(exc))
                continue
            canonical_hash = _json_hash(workflow_definition) if source.metadata.resource_type == "workflow" and workflow_definition is not None else source.content_hash
            plans[source.resource_id] = _DependencyPlan(
                tuple(dict.fromkeys(targets)),
                workflow_definition,
                canonical_hash,
            )
        return plans

    async def audit(self) -> CatalogMigrationReport:
        report = CatalogMigrationReport()
        sources = await self._legacy_sources()
        plans = self._dependency_plans(sources)
        for source in sources:
            if source.metadata.resource_type == "workflow" and source.workflow_definition is None:
                report.items.append(self._item(source, error="Workflow definition is missing"))
            elif source.path is not None and source.content_hash is None:
                report.items.append(self._item(source, error=f"Invalid or missing source directory: {source.path}"))
            elif plans[source.resource_id].error is not None:
                report.items.append(self._item(source, error=plans[source.resource_id].error))
            else:
                report.items.append(self._item(source))
        return report

    async def migrate(self) -> CatalogMigrationReport:
        sources = await self._legacy_sources()
        plans = self._dependency_plans(sources)
        report = CatalogMigrationReport()
        for source in sources:
            plan = plans[source.resource_id]
            error = "Legacy source is missing or invalid" if source.content_hash is None else plan.error
            if error is not None:
                report.items.append(self._item(source, error=error))
        if report.errors:
            await self.session.rollback()
            return report

        for source in sources:
            plan = plans[source.resource_id]
            assert plan.canonical_hash is not None
            existing = await self.session.get(Resource, source.resource_id)
            if existing is not None:
                version = (
                    await self.session.execute(
                        select(ResourceVersion).where(
                            ResourceVersion.resource_id == existing.id,
                            ResourceVersion.version == 1,
                        )
                    )
                ).scalar_one_or_none()
                if existing.type != source.metadata.resource_type or existing.owner_id != source.metadata.owner_id or existing.slug != source.metadata.resource_id or version is None or version.content_hash != plan.canonical_hash:
                    raise ResourceConflict(f"Existing canonical resource conflicts with {source.resource_id}")
                report.items.append(self._item(source))
                report.unchanged += 1
                continue
            collision = (
                await self.session.execute(
                    select(Resource.id).where(
                        Resource.type == source.metadata.resource_type,
                        Resource.owner_id == source.metadata.owner_id,
                        Resource.slug == source.metadata.resource_id,
                    )
                )
            ).scalar_one_or_none()
            if collision is not None:
                raise ResourceConflict(f"Canonical slug collision for legacy resource {source.metadata.id}")

            if source.path is not None:
                with self._definition_source(source.metadata.resource_type, source.path) as definition_source:
                    staged = self.storage.stage_directory(source.metadata.resource_type, source.resource_id, definition_source)
                    published = self.storage.publish_staged(staged, version=1)
                storage_kind = "bundled" if source.metadata.imported_from == "bundled" else "filesystem"
                storage_key = published.storage_key
                content = None
            else:
                storage_kind = "bundled" if source.metadata.imported_from == "bundled" else "database"
                storage_key = f"workflows/{source.resource_id}/versions/1"
                content = plan.workflow_definition

            resource = Resource(
                id=source.resource_id,
                type=source.metadata.resource_type,
                slug=source.metadata.resource_id,
                display_name=source.metadata.resource_id,
                owner_id=source.metadata.owner_id,
                visibility=source.metadata.visibility,
                scope_department_id=source.metadata.department_id if source.metadata.visibility == "department" else None,
                lifecycle_status="active",
                latest_version=1,
                draft_revision=0,
                storage_kind=storage_kind,
                storage_key=storage_key.rsplit("/versions/1", 1)[0],
                system_owned=False,
                authz_revision=1,
                created_at=source.metadata.created_at,
                updated_at=source.metadata.updated_at,
            )
            self.session.add(resource)
            self.session.add(
                ResourceVersion(
                    id=str(uuid.uuid4()),
                    resource_id=resource.id,
                    version=1,
                    content_hash=plan.canonical_hash,
                    storage_key=storage_key,
                    scan_result={
                        "status": "migrated",
                        "legacy_metadata_id": source.metadata.id,
                        "legacy_version": source.metadata.version,
                        "legacy_content_hash": source.content_hash,
                    },
                    content=content,
                    created_by=source.metadata.owner_id,
                    published_at=source.metadata.updated_at,
                )
            )
            if source.metadata.is_favorited:
                self.session.add(ResourceFavorite(user_id=source.metadata.owner_id, resource_id=resource.id))
            report.items.append(self._item(source))
            report.created += 1

        await self.session.flush()
        for source in sources:
            expected_targets = set(plans[source.resource_id].target_ids)
            existing_dependencies = list((await self.session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == source.resource_id))).scalars())
            existing_targets = {dependency.target_resource_id for dependency in existing_dependencies}
            if existing_targets - expected_targets:
                raise ResourceConflict(f"Canonical dependencies conflict for migrated resource {source.resource_id}")
            for target_id in sorted(expected_targets - existing_targets):
                self.session.add(
                    ResourceDependency(
                        id=str(uuid.uuid4()),
                        source_resource_id=source.resource_id,
                        target_resource_id=target_id,
                    )
                )
        try:
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise
        return report

    async def verify(self) -> CatalogMigrationReport:
        report = CatalogMigrationReport()
        sources = await self._legacy_sources()
        plans = self._dependency_plans(sources)
        for source in sources:
            plan = plans[source.resource_id]
            resource = await self.session.get(Resource, source.resource_id)
            version = None
            if resource is not None:
                version = (
                    await self.session.execute(
                        select(ResourceVersion).where(
                            ResourceVersion.resource_id == resource.id,
                            ResourceVersion.version == 1,
                        )
                    )
                ).scalar_one_or_none()
            error: str | None = None
            if source.content_hash is None:
                error = "Legacy source is missing or invalid"
            elif plan.error is not None:
                error = plan.error
            elif resource is None or version is None:
                error = "Canonical resource or version is missing"
            elif (
                resource.type != source.metadata.resource_type
                or resource.slug != source.metadata.resource_id
                or resource.owner_id != source.metadata.owner_id
                or resource.visibility != source.metadata.visibility
                or resource.scope_department_id != (source.metadata.department_id if source.metadata.visibility == "department" else None)
            ):
                error = "Canonical identity, owner, or visibility differs from legacy metadata"
            elif version.content_hash != plan.canonical_hash:
                error = "Canonical hash differs from the legacy source"
            elif resource.type != "workflow":
                canonical_path = self.storage.resources_root / version.storage_key
                try:
                    canonical_hash = self.storage.inspect_directory(resource.type, canonical_path).content_hash
                except (OSError, StorageValidationError):
                    canonical_hash = None
                if canonical_hash != version.content_hash:
                    error = "Canonical filesystem content is missing or mismatched"
            elif version.content != plan.workflow_definition:
                error = "Canonical Workflow content differs from the legacy definition"
            if error is None:
                actual_targets = set((await self.session.execute(select(ResourceDependency.target_resource_id).where(ResourceDependency.source_resource_id == source.resource_id))).scalars())
                if actual_targets != set(plan.target_ids):
                    error = "Canonical dependencies differ from resolved legacy references"
            report.items.append(self._item(source, error=error))
        return report

    async def rollback(self, *, backup_dir: str | Path) -> CatalogMigrationReport:
        """Remove only untouched migrated rows after moving file content to backup."""

        sources = await self._legacy_sources()
        source_by_id = {source.resource_id: source for source in sources}
        candidate_ids = set(source_by_id)
        resources = list((await self.session.execute(select(Resource).where(Resource.id.in_(candidate_ids)))).scalars())
        if len(resources) != len(candidate_ids):
            raise ResourceConflict("Canonical migration set is incomplete; rollback refused")

        for resource in resources:
            source = source_by_id[resource.id]
            versions = list((await self.session.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource.id))).scalars())
            provenance_matches = len(versions) == 1 and versions[0].version == 1 and versions[0].scan_result.get("legacy_metadata_id") == source.metadata.id
            draft_exists = await self.session.get(ResourceDraft, resource.id)
            snapshot_exists = (await self.session.execute(select(RunResourceSnapshot.id).where(RunResourceSnapshot.resource_id == resource.id).limit(1))).scalar_one_or_none()
            if resource.latest_version != 1 or resource.draft_revision != 0 or not provenance_matches or draft_exists is not None or snapshot_exists is not None:
                raise ResourceConflict(f"Resource {resource.id} has post-migration history; rollback refused")

        external_incoming = (
            await self.session.execute(
                select(ResourceDependency.id)
                .where(
                    ResourceDependency.target_resource_id.in_(candidate_ids),
                    ResourceDependency.source_resource_id.not_in(candidate_ids),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if external_incoming is not None:
            raise ResourceConflict("Migrated resources have external dependants; rollback refused")

        backup_root = Path(backup_dir).resolve()
        resources_root = self.storage.resources_root.resolve()
        if backup_root == resources_root or backup_root.is_relative_to(resources_root):
            raise ResourceConflict("Rollback backup must be outside the canonical resources directory")
        if backup_root.exists():
            raise ResourceConflict(f"Rollback backup already exists: {backup_root}")
        backup_root.mkdir(parents=True)

        moved: list[tuple[Path, Path]] = []
        try:
            for resource in resources:
                if resource.type == "workflow":
                    continue
                type_directory = "skills" if resource.type == "skill" else "agents"
                source_path = self.storage.resources_root / type_directory / resource.id
                if not source_path.is_dir() or source_path.is_symlink():
                    raise ResourceConflict(f"Canonical filesystem resource is missing: {resource.id}")
                target_path = backup_root / "resources" / type_directory / resource.id
                target_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source_path, target_path)
                moved.append((source_path, target_path))

            await self.session.execute(update(VisibilityApplication).where(VisibilityApplication.canonical_resource_id.in_(candidate_ids)).values(canonical_resource_id=None))
            await self.session.execute(delete(ResourceFavorite).where(ResourceFavorite.resource_id.in_(candidate_ids)))
            await self.session.execute(delete(ResourceNotification).where(ResourceNotification.resource_id.in_(candidate_ids)))
            await self.session.execute(
                delete(ResourceDependency).where(
                    or_(
                        ResourceDependency.source_resource_id.in_(candidate_ids),
                        ResourceDependency.target_resource_id.in_(candidate_ids),
                    )
                )
            )
            await self.session.execute(delete(ResourceVersion).where(ResourceVersion.resource_id.in_(candidate_ids)))
            await self.session.execute(delete(Resource).where(Resource.id.in_(candidate_ids)))
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            for source_path, target_path in reversed(moved):
                source_path.parent.mkdir(parents=True, exist_ok=True)
                if target_path.exists() and not source_path.exists():
                    os.replace(target_path, source_path)
            raise

        report = CatalogMigrationReport(removed=len(resources))
        report.items.extend(self._item(source) for source in sources)
        return report
