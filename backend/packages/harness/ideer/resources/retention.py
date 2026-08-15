"""Report-only retention eligibility for archived canonical resource files."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceVersion,
    RunResourceSnapshot,
)


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
