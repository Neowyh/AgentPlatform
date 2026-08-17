"""Consistency checks between canonical catalog pointers and filesystem content."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ideer.persistence.models.resource_catalog import Resource, ResourceDraft, ResourceVersion
from ideer.resources.storage import ReconciliationReport, ResourceStorage


class CatalogConsistencyError(RuntimeError):
    pass


async def reconcile_catalog_storage(
    session: AsyncSession,
    storage: ResourceStorage,
) -> ReconciliationReport:
    version_rows = (
        await session.execute(
            select(ResourceVersion.storage_key, ResourceVersion.content_hash)
            .join(Resource, Resource.id == ResourceVersion.resource_id)
            .where(
                Resource.storage_kind == "filesystem",
                Resource.type != "workflow",
            )
        )
    ).all()
    draft_rows = (
        await session.execute(
            select(ResourceDraft.storage_key, ResourceDraft.content_hash)
            .join(Resource, Resource.id == ResourceDraft.resource_id)
            .where(
                Resource.storage_kind == "filesystem",
                Resource.type != "workflow",
            )
        )
    ).all()
    report = await asyncio.to_thread(
        storage.reconcile,
        dict(version_rows),
        expected_drafts=dict(draft_rows),
    )
    corrupt = {
        "missing_versions": report.missing_versions,
        "hash_mismatches": report.hash_mismatches,
        "missing_drafts": report.missing_drafts,
        "draft_hash_mismatches": report.draft_hash_mismatches,
    }
    failures = {key: value for key, value in corrupt.items() if value}
    if failures:
        detail = ", ".join(f"{key}={value}" for key, value in failures.items())
        raise CatalogConsistencyError(f"Canonical resource storage is inconsistent: {detail}")
    return report
