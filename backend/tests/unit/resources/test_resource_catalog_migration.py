"""Legacy Skill, Agent, and Workflow catalog migration contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceVersion
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.workflow_v2 import WorkflowDefinitionVersionRow
from ideer.resources.migration import LegacyResourceMigrator, stable_bundled_resource_id
from ideer.resources.storage import ResourceStorage


@pytest_asyncio.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}")
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
    (agent / "memory.json").write_text('{"secret": true}')
    skills = tmp_path / "skills"
    skill = skills / "custom" / "research"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Research\n")
    return runtime, skills


def test_bundled_resource_id_is_owner_independent_and_matches_release_manifest() -> None:
    assert stable_bundled_resource_id("skill", "fault-zeroing") == ("f258c030-0aa2-5ca4-9072-c28fa9fdadbd")


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
                is_favorited=True,
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
            ResourceMetadata(
                id="legacy-tool",
                resource_type="tool",
                resource_id="search",
                owner_id="owner",
                visibility="private",
                version=1,
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


@pytest.mark.asyncio
async def test_audit_is_read_only_and_excludes_tool_and_agent_runtime_state(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    storage = ResourceStorage(runtime)
    migrator = LegacyResourceMigrator(session, storage, legacy_base_dir=runtime, skills_root=skills)

    report = await migrator.audit()

    assert [(item.resource_type, item.slug) for item in report.items] == [
        ("agent", "writer"),
        ("skill", "research"),
        ("workflow", "review-flow"),
    ]
    assert report.errors == []
    assert not storage.resources_root.exists()
    assert int((await session.execute(select(func.count()).select_from(Resource))).scalar_one()) == 0


@pytest.mark.asyncio
async def test_migrate_is_idempotent_preserves_sources_and_verify_checks_hashes(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    storage = ResourceStorage(runtime)
    migrator = LegacyResourceMigrator(session, storage, legacy_base_dir=runtime, skills_root=skills)

    first = await migrator.migrate()
    second = await migrator.migrate()
    verification = await migrator.verify()

    assert first.created == 3
    assert second.created == 0
    assert second.unchanged == 3
    assert verification.errors == []
    resources = list((await session.execute(select(Resource).order_by(Resource.type))).scalars())
    assert [resource.type for resource in resources] == ["agent", "skill", "workflow"]
    assert len({resource.id for resource in resources}) == 3
    assert int((await session.execute(select(func.count()).select_from(ResourceVersion))).scalar_one()) == 3
    dependencies = list((await session.execute(select(ResourceDependency))).scalars())
    assert len(dependencies) == 2
    agent = next(resource for resource in resources if resource.type == "agent")
    assert not (runtime / "resources" / "agents" / agent.id / "versions" / "1" / "memory.json").exists()
    assert (runtime / "users" / "owner" / "agents" / "writer" / "memory.json").exists()
    workflow_version = (await session.execute(select(ResourceVersion).join(Resource, ResourceVersion.resource_id == Resource.id).where(Resource.type == "workflow"))).scalar_one()
    agent_id = next(resource.id for resource in resources if resource.type == "agent")
    assert workflow_version.content == {
        "nodes": [
            {
                "id": "draft",
                "type": "action",
                "action": {"kind": "agent", "name": agent_id},
            }
        ],
        "edges": [],
    }


@pytest.mark.asyncio
async def test_migration_refuses_ambiguous_visible_name_dependencies(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    skills = tmp_path / "skills"
    for owner in ("first", "second"):
        agent = runtime / "users" / owner / "agents" / "writer"
        agent.mkdir(parents=True)
        (agent / "config.yaml").write_text("name: writer\nskills: []\n")
        session.add(
            ResourceMetadata(
                id=f"agent-{owner}",
                resource_type="agent",
                resource_id="writer",
                owner_id=owner,
                visibility="public",
                version=1,
            )
        )
    session.add(
        ResourceMetadata(
            id="workflow-third",
            resource_type="workflow",
            resource_id="ambiguous-flow",
            owner_id="third",
            visibility="private",
            version=1,
        )
    )
    session.add(
        WorkflowDefinitionVersionRow(
            id="ambiguous-definition",
            workflow_name="ambiguous-flow",
            version=1,
            definition={
                "nodes": [{"id": "run", "type": "action", "action": {"kind": "agent", "name": "writer"}}],
                "edges": [],
            },
            content_hash="legacy",
            created_by="third",
        )
    )
    await session.commit()
    migrator = LegacyResourceMigrator(
        session,
        ResourceStorage(runtime),
        legacy_base_dir=runtime,
        skills_root=skills,
    )

    report = await migrator.migrate()

    assert report.created == 0
    assert any("ambiguous Agent dependency 'writer'" in error for error in report.errors)
    assert int((await session.execute(select(func.count()).select_from(Resource))).scalar_one()) == 0


@pytest.mark.asyncio
async def test_rollback_requires_backup_and_removes_only_pristine_migrated_catalog(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(
        session,
        ResourceStorage(runtime),
        legacy_base_dir=runtime,
        skills_root=skills,
    )
    await migrator.migrate()

    report = await migrator.rollback(backup_dir=tmp_path / "rollback-backup")

    assert report.removed == 3
    assert int((await session.execute(select(func.count()).select_from(Resource))).scalar_one()) == 0
    assert (tmp_path / "rollback-backup" / "resources" / "agents").is_dir()
    assert (runtime / "users" / "owner" / "agents" / "writer" / "config.yaml").exists()


@pytest.mark.asyncio
async def test_rollback_refuses_a_resource_with_post_migration_versions(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    runtime, skills = _legacy_layout(tmp_path)
    await _seed_legacy(session)
    migrator = LegacyResourceMigrator(
        session,
        ResourceStorage(runtime),
        legacy_base_dir=runtime,
        skills_root=skills,
    )
    await migrator.migrate()
    resource = (await session.execute(select(Resource).where(Resource.type == "workflow"))).scalar_one()
    resource.latest_version = 2
    await session.commit()

    with pytest.raises(Exception, match="post-migration history"):
        await migrator.rollback(backup_dir=tmp_path / "unsafe-backup")

    assert int((await session.execute(select(func.count()).select_from(Resource))).scalar_one()) == 3
