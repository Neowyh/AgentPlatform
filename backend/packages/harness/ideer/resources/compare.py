"""Read-only dual-mode parity comparison between legacy and canonical resources.

The comparison gate proves migration fidelity before the canonical cutover:
every legacy Skill, Agent, and Workflow row must have a canonical counterpart
with identical identity, owner, visibility, and resolved dependency closure.

Item statuses:

- ``ok``: canonical counterpart matches the legacy source exactly (including
  filesystem content parity for file-backed resources).
- ``diverged``: structural parity holds but the canonical latest published
  content differs from the legacy source. In dual mode this is the expected
  signal of canonical-first writes; it is reported but does not fail the gate.
- ``error``: structural mismatch (missing resource, identity/visibility drift,
  missing version, dependency drift, or an unresolvable legacy source).

Canonical resources without any legacy counterpart (resources created after
migration, bundled, or forked) are reported as ``extras`` and never fail the
gate. This module never mutates legacy or canonical state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceVersion
from ideer.resources.migration import LegacyResourceMigrator
from ideer.resources.storage import ResourceStorage, StorageValidationError


@dataclass(frozen=True)
class ComparisonItem:
    resource_type: str
    slug: str
    owner_id: str
    resource_id: str
    status: str
    error: str | None = None


@dataclass
class ComparisonReport:
    items: list[ComparisonItem] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [item.error for item in self.items if item.status == "error" and item.error is not None]

    @property
    def diverged(self) -> list[str]:
        return [f"{item.resource_type}/{item.slug}" for item in self.items if item.status == "diverged"]

    @property
    def ok_count(self) -> int:
        return sum(1 for item in self.items if item.status == "ok")


class DualModeComparator:
    """Compare every legacy resource row against its canonical counterpart."""

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
        self._migrator = LegacyResourceMigrator(
            session,
            storage,
            legacy_base_dir=legacy_base_dir,
            skills_root=skills_root,
        )

    async def compare(self) -> ComparisonReport:
        report = ComparisonReport()
        sources = await self._migrator._legacy_sources()
        plans = self._migrator._dependency_plans(sources)

        resources = {resource.id: resource for resource in (await self.session.execute(select(Resource))).scalars()}
        version_rows = list((await self.session.execute(select(ResourceVersion).order_by(ResourceVersion.resource_id, ResourceVersion.version))).scalars())
        versions: dict[str, list[ResourceVersion]] = {}
        for row in version_rows:
            versions.setdefault(row.resource_id, []).append(row)
        dependency_rows = list((await self.session.execute(select(ResourceDependency))).scalars())
        dependencies: dict[str, set[str]] = {}
        for row in dependency_rows:
            dependencies.setdefault(row.source_resource_id, set()).add(row.target_resource_id)

        for source in sources:
            plan = plans[source.resource_id]
            error = self._structural_error(source, plan, resources, versions, dependencies)
            if error is not None:
                report.items.append(
                    ComparisonItem(
                        resource_type=source.metadata.resource_type,
                        slug=source.metadata.resource_id,
                        owner_id=source.metadata.owner_id,
                        resource_id=source.resource_id,
                        status="error",
                        error=error,
                    )
                )
                continue
            latest = versions[source.resource_id][-1]
            diverged = self._content_diverged(source, plan, latest)
            report.items.append(
                ComparisonItem(
                    resource_type=source.metadata.resource_type,
                    slug=source.metadata.resource_id,
                    owner_id=source.metadata.owner_id,
                    resource_id=source.resource_id,
                    status="diverged" if diverged else "ok",
                )
            )

        legacy_ids = {source.resource_id for source in sources}
        report.extras = sorted(resource_id for resource_id in resources if resource_id not in legacy_ids)
        return report

    def _structural_error(
        self,
        source: object,
        plan: object,
        resources: dict[str, Resource],
        versions: dict[str, list[ResourceVersion]],
        dependencies: dict[str, set[str]],
    ) -> str | None:
        metadata = source.metadata
        if source.content_hash is None:
            return "Legacy source is missing or invalid"
        if plan.error is not None:
            return plan.error
        resource = resources.get(source.resource_id)
        if resource is None:
            return "Canonical resource is missing"
        if resource.type != metadata.resource_type or resource.slug != metadata.resource_id or resource.owner_id != metadata.owner_id:
            return "Canonical identity, owner, or slug differs from legacy metadata"
        expected_scope = metadata.department_id if metadata.visibility == "department" else None
        if resource.visibility != metadata.visibility or resource.scope_department_id != expected_scope:
            return "Canonical visibility or department scope differs from legacy metadata"
        if resource.latest_version < 1 or source.resource_id not in versions:
            return "Canonical version is missing"
        if versions[source.resource_id][-1].version != resource.latest_version:
            return "Canonical latest version pointer is inconsistent"
        if dependencies.get(source.resource_id, set()) != set(plan.target_ids):
            return "Canonical dependencies differ from resolved legacy references"
        return None

    def _content_diverged(self, source: object, plan: object, latest: ResourceVersion) -> bool:
        if source.metadata.resource_type == "workflow":
            return latest.content != plan.workflow_definition
        if latest.content_hash != plan.canonical_hash:
            return True
        canonical_path = self.storage.resources_root / latest.storage_key
        try:
            filesystem_hash = self.storage.inspect_directory(source.metadata.resource_type, canonical_path).content_hash
        except (OSError, StorageValidationError):
            filesystem_hash = None
        return filesystem_hash != latest.content_hash
