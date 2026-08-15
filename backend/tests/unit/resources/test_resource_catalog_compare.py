"""Dual-mode parity comparison contracts for the canonical catalog."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceVersion
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.workflow_v2 import WorkflowDefinitionVersionRow
from ideer.resources.compare import DualModeComparator
from ideer.resources.migration import LegacyResourceMigrator
from ideer.resources.storage import ResourceStorage


@pytest_asyncio.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'compare.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def _legacy_layout(tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "runtime"
    agent = runtime / "users" / "owner" / "agents" / "writer"
    agent.mkdir(parents=True)
    (agent / "config.yaml").write_text("name: writer\nskills: [research]\n")
    (agent / "SOUL.md").write_text("Careful.\n")
    skills = tmp_path / "skills"
    skill = skills / "custom" / "research"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Research\n")
    return runtime, skills


async def _seed_legacy(session: AsyncSession) -> None:
    session.add_all(
        [
            ResourceMetadata(
                id="legacy-skill",
                resource_type="skill",
                resource_id="research",
                owner_id="owner",
                department_id="dept-a",
                visibility="department",
                version=3,
            ),
            ResourceMetadata(
                id="legacy-agent",
                resource_type="agent",
                resource_id="writer",
                owner_id="owner",
                department_id=None,
                visibility="private",
                version=2,
            ),
            ResourceMetadata(
                id="legacy-workflow",
                resource_type="workflow",
                resource_id="review-flow",
                owner_id="owner",
                department_id=None,
                visibility="private",
                version=4,
            ),
            WorkflowDefinitionVersionRow(
                id="workflow-definition",
                workflow_name="review-flow",
                version=7,
                definition={
                    "nodes": [
                        {
                            "id": "draft",
                            "type": "action",
                            "action": {"kind": "agent", "name": "writer"},
                        }
                    ],
                    "edges": [],
                },
                content_hash="legacy-hash",
                created_by="owner",
            ),
        ]
    )
    await session.commit()


def _comparator(session: AsyncSession, runtime: Path, skills: Path) -> DualModeComparator:
    return DualModeComparator(
        session,
        ResourceStorage(runtime),
        legacy_base_dir=runtime,
        skills_root=skills,
    )


@pytest.mark.asyncio
async def test_compare_reports_full_parity_after_migration(session: AsyncSession, tmp_path: Path) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(session, ResourceStorage(runtime), legacy_base_dir=runtime, skills_root=skills)
    migrated = await migrator.migrate()
    assert migrated.errors == []

    report = await _comparator(session, runtime, skills).compare()

    assert report.errors == []
    assert report.diverged == []
    assert report.ok_count == 3
    assert report.extras == []
    assert all(item.status == "ok" for item in report.items)


@pytest.mark.asyncio
async def test_compare_flags_missing_canonical_resource(session: AsyncSession, tmp_path: Path) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)

    report = await _comparator(session, runtime, skills).compare()

    assert report.ok_count == 0
    assert len(report.errors) == 3
    assert all("Canonical resource is missing" in error for error in report.errors)


@pytest.mark.asyncio
async def test_compare_flags_visibility_drift(session: AsyncSession, tmp_path: Path) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(session, ResourceStorage(runtime), legacy_base_dir=runtime, skills_root=skills)
    await migrator.migrate()
    skill = (await session.execute(select(Resource).where(Resource.type == "skill"))).scalar_one()
    skill.visibility = "private"
    skill.scope_department_id = None
    await session.commit()

    report = await _comparator(session, runtime, skills).compare()

    assert any("visibility" in error for error in report.errors)
    assert report.ok_count == 2


@pytest.mark.asyncio
async def test_compare_flags_owner_drift(session: AsyncSession, tmp_path: Path) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(session, ResourceStorage(runtime), legacy_base_dir=runtime, skills_root=skills)
    await migrator.migrate()
    agent = (await session.execute(select(Resource).where(Resource.type == "agent"))).scalar_one()
    agent.owner_id = "intruder"
    await session.commit()

    report = await _comparator(session, runtime, skills).compare()

    assert any("owner" in error for error in report.errors)
    assert report.ok_count == 2


@pytest.mark.asyncio
async def test_compare_flags_dependency_drift(session: AsyncSession, tmp_path: Path) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(session, ResourceStorage(runtime), legacy_base_dir=runtime, skills_root=skills)
    await migrator.migrate()
    await session.execute(delete(ResourceDependency))
    await session.commit()

    report = await _comparator(session, runtime, skills).compare()

    assert any("dependencies" in error for error in report.errors)


@pytest.mark.asyncio
async def test_compare_reports_content_divergence_without_failing(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(session, ResourceStorage(runtime), legacy_base_dir=runtime, skills_root=skills)
    await migrator.migrate()
    workflow = (await session.execute(select(Resource).where(Resource.type == "workflow"))).scalar_one()
    workflow.latest_version = 2
    session.add(
        ResourceVersion(
            id="workflow-v2",
            resource_id=workflow.id,
            version=2,
            content_hash="new-hash",
            storage_key="workflows/dummy/versions/2",
            scan_result={},
            content={"nodes": [], "edges": []},
            created_by="owner",
        )
    )
    await session.commit()

    report = await _comparator(session, runtime, skills).compare()

    assert report.errors == []
    assert report.diverged == ["workflow/review-flow"]
    assert report.ok_count == 2


@pytest.mark.asyncio
async def test_compare_reports_canonical_extras_as_informational(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(session, ResourceStorage(runtime), legacy_base_dir=runtime, skills_root=skills)
    await migrator.migrate()
    session.add(
        Resource(
            id="canonical-only-resource",
            type="workflow",
            slug="new-flow",
            display_name="New Flow",
            owner_id="owner",
            visibility="private",
            lifecycle_status="active",
            latest_version=1,
            draft_revision=0,
            storage_kind="database",
            storage_key="workflows/canonical-only-resource",
            system_owned=False,
            authz_revision=1,
        )
    )
    await session.commit()

    report = await _comparator(session, runtime, skills).compare()

    assert report.errors == []
    assert report.ok_count == 3
    assert report.extras == ["canonical-only-resource"]


@pytest.mark.asyncio
async def test_compare_flags_missing_legacy_source_directory(session: AsyncSession, tmp_path: Path) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    (runtime / "users" / "owner" / "agents" / "writer").rename(runtime / "users" / "owner" / "agents" / "writer-moved")

    report = await _comparator(session, runtime, skills).compare()

    assert any("missing or invalid" in error for error in report.errors)
    assert report.ok_count == 0
