"""Canonical runtime loading, snapshot, and caller-policy contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceVersion, RunResourceSnapshot
from ideer.resources.runtime import (
    CanonicalResourceLoader,
    ResourceRuntimeError,
    intersect_tool_groups,
    resource_memory_key,
)
from ideer.resources.storage import ResourceStorage


@pytest_asyncio.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'runtime.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def test_tool_groups_and_memory_keys_are_runner_scoped() -> None:
    assert intersect_tool_groups(["search", "bash"], frozenset({"search", "files"})) == ["search"]
    assert intersect_tool_groups(None, frozenset({"files"})) == ["files"]
    assert intersect_tool_groups(["search"], None) == ["search"]
    assert resource_memory_key("runner", "7e011a72-7e02-4df2-a881-babb18565bd3") == (
        "runner",
        "7e011a72-7e02-4df2-a881-babb18565bd3",
    )


async def _snapshot_agent(
    session: AsyncSession,
    storage: ResourceStorage,
    source: Path,
    *,
    lifecycle_status: str = "active",
) -> Resource:
    resource_id = "7e011a72-7e02-4df2-a881-babb18565bd3"
    published = storage.publish_staged(storage.stage_directory("agent", resource_id, source), version=1)
    resource = Resource(
        id=resource_id,
        type="agent",
        slug="writer",
        display_name="Writer",
        owner_id="owner",
        visibility="public",
        scope_department_id=None,
        lifecycle_status=lifecycle_status,
        latest_version=1,
        draft_revision=0,
        storage_kind="filesystem",
        storage_key=f"agents/{resource_id}",
        system_owned=False,
        authz_revision=1,
    )
    session.add_all(
        [
            resource,
            ResourceVersion(
                id="agent-version",
                resource_id=resource.id,
                version=1,
                content_hash=published.content_hash,
                storage_key=published.storage_key,
                scan_result={"status": "clean"},
                created_by="owner",
            ),
            RunResourceSnapshot(
                id="agent-snapshot",
                run_id="run-1",
                root_resource_id=resource.id,
                resource_id=resource.id,
                version=1,
                content_hash=published.content_hash,
                authz_revision=1,
            ),
        ]
    )
    await session.commit()
    return resource


@pytest.mark.asyncio
async def test_loader_uses_frozen_version_after_archive_but_denies_suspend_and_tamper(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    source = tmp_path / "agent"
    source.mkdir()
    (source / "config.yaml").write_text("name: writer\ntool_groups: [search]\n")
    (source / "SOUL.md").write_text("Careful.\n")
    storage = ResourceStorage(tmp_path)
    resource = await _snapshot_agent(session, storage, source)
    loader = CanonicalResourceLoader(session, storage)

    resource.lifecycle_status = "archived"
    await session.commit()
    definition = await loader.load_agent("run-1", resource.id)
    assert definition.config.name == "writer"
    assert definition.soul == "Careful."
    assert definition.version == 1

    resource.lifecycle_status = "suspended"
    await session.commit()
    with pytest.raises(ResourceRuntimeError, match="suspended"):
        await loader.load_agent("run-1", resource.id)

    resource.lifecycle_status = "archived"
    await session.commit()
    version_path = storage.resources_root / f"agents/{resource.id}/versions/1"
    version_path.chmod(0o755)
    (version_path / "SOUL.md").chmod(0o644)
    (version_path / "SOUL.md").write_text("tampered")
    with pytest.raises(ResourceRuntimeError, match="hash"):
        await loader.load_agent("run-1", resource.id)


@pytest.mark.asyncio
async def test_loader_rejects_plaintext_credentials_in_shared_agent_definition(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    source = tmp_path / "credential-agent"
    source.mkdir()
    (source / "config.yaml").write_text("name: writer\napi_key: plaintext-secret\n")
    storage = ResourceStorage(tmp_path)
    resource = await _snapshot_agent(session, storage, source)

    with pytest.raises(ResourceRuntimeError, match="credential"):
        await CanonicalResourceLoader(session, storage).load_agent("run-1", resource.id)


@pytest.mark.asyncio
async def test_agent_skills_load_only_from_uuid_dependencies_in_same_snapshot(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    agent_source = tmp_path / "agent-with-skill"
    agent_source.mkdir()
    (agent_source / "config.yaml").write_text("name: writer\nskills: [research]\n")
    skill_source = tmp_path / "skill"
    skill_source.mkdir()
    (skill_source / "SKILL.md").write_text("---\nname: research\ndescription: Research carefully\n---\n# Research\n")
    storage = ResourceStorage(tmp_path)
    agent = await _snapshot_agent(session, storage, agent_source)
    skill_id = "951d48c2-c528-41ac-b188-5636ca425f70"
    skill_published = storage.publish_staged(storage.stage_directory("skill", skill_id, skill_source), version=1)
    skill = Resource(
        id=skill_id,
        type="skill",
        slug="research",
        display_name="Research",
        owner_id="owner",
        visibility="public",
        scope_department_id=None,
        lifecycle_status="active",
        latest_version=1,
        draft_revision=0,
        storage_kind="filesystem",
        storage_key=f"skills/{skill_id}",
        system_owned=False,
        authz_revision=1,
    )
    from ideer.persistence.models.resource_catalog import ResourceDependency

    session.add_all(
        [
            skill,
            ResourceVersion(
                id="skill-version",
                resource_id=skill.id,
                version=1,
                content_hash=skill_published.content_hash,
                storage_key=skill_published.storage_key,
                scan_result={},
                created_by="owner",
            ),
            ResourceDependency(id="agent-skill", source_resource_id=agent.id, target_resource_id=skill.id),
            RunResourceSnapshot(
                id="skill-snapshot",
                run_id="run-1",
                root_resource_id=agent.id,
                resource_id=skill.id,
                version=1,
                content_hash=skill_published.content_hash,
                authz_revision=1,
            ),
        ]
    )
    await session.commit()

    skills = await CanonicalResourceLoader(session, storage).load_agent_skills("run-1", agent.id)

    assert [item.name for item in skills] == ["research"]
    assert skills[0].skill_file == storage.resources_root / f"skills/{skill.id}/versions/1/SKILL.md"


@pytest.mark.asyncio
async def test_agent_skills_resolve_uuid_references_from_bundled_manifest(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    skill_id = "951d48c2-c528-41ac-b188-5636ca425f70"
    agent_source = tmp_path / "agent-with-uuid-skill"
    agent_source.mkdir()
    (agent_source / "config.yaml").write_text(f"name: writer\nskills: [{skill_id}]\n")
    skill_source = tmp_path / "skill"
    skill_source.mkdir()
    (skill_source / "SKILL.md").write_text("---\nname: research\ndescription: Research carefully\n---\n# Research\n")
    storage = ResourceStorage(tmp_path)
    agent = await _snapshot_agent(session, storage, agent_source)
    skill_published = storage.publish_staged(storage.stage_directory("skill", skill_id, skill_source), version=1)
    skill = Resource(
        id=skill_id,
        type="skill",
        slug="research",
        display_name="Research",
        owner_id="owner",
        visibility="public",
        scope_department_id=None,
        lifecycle_status="active",
        latest_version=1,
        draft_revision=0,
        storage_kind="filesystem",
        storage_key=f"skills/{skill_id}",
        system_owned=False,
        authz_revision=1,
    )
    from ideer.persistence.models.resource_catalog import ResourceDependency

    session.add_all(
        [
            skill,
            ResourceVersion(
                id="skill-version",
                resource_id=skill.id,
                version=1,
                content_hash=skill_published.content_hash,
                storage_key=skill_published.storage_key,
                scan_result={},
                created_by="owner",
            ),
            ResourceDependency(id="agent-skill", source_resource_id=agent.id, target_resource_id=skill.id),
            RunResourceSnapshot(
                id="skill-snapshot",
                run_id="run-1",
                root_resource_id=agent.id,
                resource_id=skill.id,
                version=1,
                content_hash=skill_published.content_hash,
                authz_revision=1,
            ),
        ]
    )
    await session.commit()

    skills = await CanonicalResourceLoader(session, storage).load_agent_skills("run-1", agent.id)

    assert [item.name for item in skills] == ["research"]


@pytest.mark.asyncio
async def test_agent_skills_missing_reference_fails_closed(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    agent_source = tmp_path / "agent-with-missing-skill"
    agent_source.mkdir()
    (agent_source / "config.yaml").write_text("name: writer\nskills: [no-such-skill]\n")
    storage = ResourceStorage(tmp_path)
    agent = await _snapshot_agent(session, storage, agent_source)

    with pytest.raises(ResourceRuntimeError, match="unresolved Skill dependencies"):
        await CanonicalResourceLoader(session, storage).load_agent_skills("run-1", agent.id)
