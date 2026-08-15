from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.user import UserModel, UserRole
from ideer.resources.retention import build_retention_report


@pytest.mark.asyncio
async def test_retention_report_never_marks_frozen_or_system_versions_eligible(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            UserModel(
                id="owner",
                username="owner@test.com",
                role=UserRole.SUPER_ADMIN,
                disabled=False,
            )
        )
        for resource_id, system_owned in (("archived", False), ("system", True)):
            session.add(
                Resource(
                    id=resource_id,
                    type="skill",
                    slug=resource_id,
                    display_name=resource_id,
                    owner_id="owner",
                    visibility="private",
                    lifecycle_status="archived",
                    latest_version=2 if resource_id == "archived" else 1,
                    draft_revision=0,
                    storage_kind="bundled" if system_owned else "filesystem",
                    storage_key=f"skills/{resource_id}",
                    system_owned=system_owned,
                    authz_revision=2,
                    created_at=old,
                    updated_at=old,
                )
            )
        session.add_all(
            [
                ResourceVersion(
                    id="version-1",
                    resource_id="archived",
                    version=1,
                    content_hash="a" * 64,
                    storage_key="skills/archived/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                ResourceVersion(
                    id="version-2",
                    resource_id="archived",
                    version=2,
                    content_hash="b" * 64,
                    storage_key="skills/archived/versions/2",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                ResourceVersion(
                    id="system-version",
                    resource_id="system",
                    version=1,
                    content_hash="c" * 64,
                    storage_key="skills/system/versions/1",
                    scan_result={},
                    created_by="owner",
                    published_at=old,
                ),
                RunResourceSnapshot(
                    id="snapshot",
                    run_id="run",
                    root_resource_id="archived",
                    resource_id="archived",
                    version=1,
                    content_hash="a" * 64,
                    authz_revision=1,
                    resolved_at=old,
                ),
            ]
        )
        await session.commit()

        report = await build_retention_report(
            session,
            cutoff=now - timedelta(days=30),
        )

    by_key = {(item.resource_id, item.version): item for item in report}
    assert by_key[("archived", 1)].eligible is False
    assert by_key[("archived", 1)].blockers == ("run_snapshot_reference",)
    assert by_key[("archived", 2)].eligible is True
    assert by_key[("system", 1)].eligible is False
    assert "system_owned" in by_key[("system", 1)].blockers
    await engine.dispose()
