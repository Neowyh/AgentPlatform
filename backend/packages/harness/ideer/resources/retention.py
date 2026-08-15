"""Retention eligibility and authorized physical purge of archived canonical files.

Purge is the only operation that removes archived canonical content. It is
fail-closed: only versions reported ``eligible`` by
:func:`build_retention_report` are candidates, the on-disk content hash must
match the catalog before anything moves, content is moved (not deleted) into a
fresh backup directory outside the canonical resources root, and any database
failure moves everything back before raising.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceType,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.resources.storage import ResourceStorage, StorageValidationError


@dataclass(frozen=True)
class RetentionVersion:
    resource_id: str
    resource_type: str
    slug: str
    version: int
    storage_key: str
    content_hash: str
    eligible: bool
    blockers: tuple[str, ...]

    def payload(self) -> dict:
        value = asdict(self)
        value["blockers"] = list(self.blockers)
        return value


async def build_retention_report(
    session: AsyncSession,
    *,
    cutoff: datetime,
) -> list[RetentionVersion]:
    """Return file candidates only; never remove catalog rows or content."""

    rows = (
        await session.execute(
            select(Resource, ResourceVersion)
            .join(ResourceVersion, ResourceVersion.resource_id == Resource.id)
            .where(
                Resource.lifecycle_status == "archived",
                Resource.type.in_(["skill", "agent"]),
            )
            .order_by(Resource.id, ResourceVersion.version)
        )
    ).all()
    if not rows:
        return []
    resource_ids = {resource.id for resource, _version in rows}
    frozen = {
        (resource_id, version)
        for resource_id, version in (
            await session.execute(
                select(
                    RunResourceSnapshot.resource_id,
                    RunResourceSnapshot.version,
                ).where(RunResourceSnapshot.resource_id.in_(resource_ids))
            )
        ).all()
    }
    report: list[RetentionVersion] = []
    canonical_cutoff = cutoff.replace(tzinfo=UTC) if cutoff.tzinfo is None else cutoff
    for resource, version in rows:
        blockers: list[str] = []
        updated_at = resource.updated_at
        published_at = version.published_at
        if resource.system_owned:
            blockers.append("system_owned")
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        if published_at is not None and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        if updated_at is None or updated_at > canonical_cutoff:
            blockers.append("resource_retention_period")
        if published_at is None or published_at > canonical_cutoff:
            blockers.append("version_retention_period")
        if (resource.id, version.version) in frozen:
            blockers.append("run_snapshot_reference")
        report.append(
            RetentionVersion(
                resource_id=resource.id,
                resource_type=resource.type,
                slug=resource.slug,
                version=version.version,
                storage_key=version.storage_key,
                content_hash=version.content_hash,
                eligible=not blockers,
                blockers=tuple(blockers),
            )
        )
    return report


class RetentionPurgeError(RuntimeError):
    """Purge precondition or consistency failure; nothing is removed."""


@dataclass(frozen=True)
class PurgeResult:
    moved_storage_keys: tuple[str, ...]
    removed_version_ids: tuple[str, ...]
    removed_resources: tuple[str, ...]
    blocked: tuple[str, ...]

    def payload(self) -> dict:
        return {
            "moved_storage_keys": list(self.moved_storage_keys),
            "removed_version_ids": list(self.removed_version_ids),
            "removed_resources": list(self.removed_resources),
            "blocked": list(self.blocked),
        }


async def purge_eligible_versions(
    session: AsyncSession,
    storage: ResourceStorage,
    *,
    cutoff: datetime,
    backup_dir: str | Path,
    authorized_by: str,
) -> PurgeResult:
    """Move eligible archived version content to backup and remove catalog rows.

    Gates (all must hold, else :class:`RetentionPurgeError`):

    - ``authorized_by`` must be a non-empty explicit authorization;
    - the backup directory must not exist and must be outside ``resources/``;
    - every moved version's on-disk hash must equal the catalog hash;
    - database failure moves every already-backed-up file back before raising.

    A resource row is removed only when none of its versions remain and no
    incoming dependency references it; otherwise it stays as an archived
    tombstone and is reported in ``blocked``.
    """
    if not authorized_by or not authorized_by.strip():
        raise RetentionPurgeError("Explicit authorization is required (authorized_by)")
    report = await build_retention_report(session, cutoff=cutoff)
    candidates = [item for item in report if item.eligible]
    if not candidates:
        return PurgeResult((), (), (), ())

    backup_root = Path(backup_dir).resolve()
    resources_root = storage.resources_root.resolve()
    if backup_root == resources_root or backup_root.is_relative_to(resources_root):
        raise RetentionPurgeError("Purge backup must be outside the canonical resources directory")
    if backup_root.exists():
        raise RetentionPurgeError(f"Purge backup already exists: {backup_root}")

    moved: list[tuple[Path, Path]] = []
    try:
        backup_root.mkdir(parents=True)
        for item in candidates:
            source_path = resources_root / item.storage_key
            if not source_path.is_dir() or source_path.is_symlink():
                raise RetentionPurgeError(f"Archived content is missing: {item.storage_key}")
            try:
                on_disk_hash = storage.inspect_directory(item.resource_type, source_path).content_hash
            except (OSError, StorageValidationError) as exc:
                raise RetentionPurgeError(f"Archived content is unreadable: {item.storage_key}") from exc
            if on_disk_hash != item.content_hash:
                raise RetentionPurgeError(f"Archived content hash mismatch: {item.storage_key}")
            target_path = backup_root / item.storage_key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source_path, target_path)
            moved.append((source_path, target_path))

        removed_version_ids: list[str] = []
        for item in candidates:
            await session.execute(
                delete(ResourceVersion).where(
                    ResourceVersion.resource_id == item.resource_id,
                    ResourceVersion.version == item.version,
                )
            )
            removed_version_ids.append(item.resource_id)

        removed_resources: list[str] = []
        blocked: list[str] = []
        resource_types = {item.resource_id: item.resource_type for item in candidates}
        for resource_id in sorted({item.resource_id for item in candidates}):
            remaining = (await session.execute(select(func.count()).select_from(ResourceVersion).where(ResourceVersion.resource_id == resource_id))).scalar_one()
            if remaining:
                continue
            incoming = (await session.execute(select(ResourceDependency.id).where(ResourceDependency.target_resource_id == resource_id).limit(1))).scalar_one_or_none()
            if incoming is not None:
                blocked.append(resource_id)
                continue
            await session.execute(delete(Resource).where(Resource.id == resource_id))
            removed_resources.append(resource_id)
            type_directory = storage._TYPE_DIRECTORIES[ResourceType(resource_types[resource_id])]
            resource_root = resources_root / type_directory / resource_id
            for directory in (resource_root / "versions", resource_root):
                try:
                    directory.rmdir()
                except OSError:
                    pass
        await session.commit()
    except BaseException:
        await session.rollback()
        for source_path, target_path in reversed(moved):
            source_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists() and not source_path.exists():
                os.replace(target_path, source_path)
        raise

    return PurgeResult(
        moved_storage_keys=tuple(item.storage_key for item in candidates),
        removed_version_ids=tuple(removed_version_ids),
        removed_resources=tuple(removed_resources),
        blocked=tuple(blocked),
    )
