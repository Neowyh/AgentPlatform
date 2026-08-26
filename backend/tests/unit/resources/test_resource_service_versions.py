"""Draft, publication, dependency, fork, and snapshot contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceDraft,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.visibility_application import VisibilityApplication
from ideer.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceConflict,
    ResourceNotFound,
    ResourceService,
    VisibilityClosureError,
)


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'versions.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def _actor(
    user_id: str = "owner",
    *,
    role: str = "user",
    permissions: set[ResourceAction] | None = None,
) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id="dept-a",
        role=role,
        permissions=frozenset(permissions or {ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


def _resource(
    resource_id: str,
    *,
    resource_type: str = "agent",
    owner_id: str = "owner",
    visibility: str = "private",
    department_id: str | None = None,
    latest_version: int = 0,
) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        slug=f"slug-{resource_id}",
        display_name=f"Resource {resource_id}",
        owner_id=owner_id,
        visibility=visibility,
        scope_department_id=department_id,
        lifecycle_status="active",
        latest_version=latest_version,
        draft_revision=0,
        storage_kind="database" if resource_type == "workflow" else "filesystem",
        storage_key=f"{resource_type}s/{resource_id}",
        system_owned=False,
        authz_revision=1,
    )


async def _publish(
    service: ResourceService,
    resource_id: str,
    *,
    expected_revision: int,
    content_hash: str,
    storage_key: str,
) -> ResourceVersion:
    draft = await service.save_draft(
        resource_id,
        expected_revision=expected_revision,
        content_hash=content_hash,
        storage_key=storage_key,
    )
    return await service.publish(resource_id, expected_draft_revision=draft.revision, scan_result={"status": "clean"})


@pytest.mark.asyncio
async def test_draft_uses_optimistic_revision_and_is_owner_only(session: AsyncSession) -> None:
    resource = _resource("draft")
    session.add(resource)
    await session.commit()
    owner_service = ResourceService(session, _actor())

    draft = await owner_service.save_draft(
        resource.id,
        expected_revision=0,
        content_hash="a" * 64,
        storage_key="agents/draft/staging/a",
    )

    assert draft.revision == 1
    assert resource.draft_revision == 1
    with pytest.raises(ResourceConflict, match="draft revision"):
        await owner_service.save_draft(
            resource.id,
            expected_revision=0,
            content_hash="b" * 64,
            storage_key="agents/draft/staging/b",
        )
    with pytest.raises(ResourceNotFound):
        await ResourceService(session, _actor("other")).get_owner_draft(resource.id)


@pytest.mark.asyncio
async def test_publish_creates_immutable_versions_and_rollback_appends(session: AsyncSession) -> None:
    resource = _resource("publish")
    session.add(resource)
    await session.commit()
    service = ResourceService(session, _actor())

    version_one = await _publish(
        service,
        resource.id,
        expected_revision=0,
        content_hash="1" * 64,
        storage_key="agents/publish/versions/1",
    )
    version_two = await _publish(
        service,
        resource.id,
        expected_revision=1,
        content_hash="2" * 64,
        storage_key="agents/publish/versions/2",
    )
    rolled_back = await service.rollback(resource.id, source_version=1)

    assert (version_one.version, version_two.version, rolled_back.version) == (1, 2, 3)
    assert rolled_back.content_hash == version_one.content_hash
    assert rolled_back.storage_key == version_one.storage_key
    assert resource.latest_version == 3
    assert await session.get(ResourceDraft, resource.id) is None
    rows = list((await session.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource.id).order_by(ResourceVersion.version))).scalars())
    assert [row.content_hash for row in rows] == ["1" * 64, "2" * 64, "1" * 64]


@pytest.mark.asyncio
async def test_public_resource_cannot_depend_on_private_resource(session: AsyncSession) -> None:
    source = _resource("public-agent", visibility="public")
    target = _resource("private-skill", resource_type="skill", visibility="private")
    session.add_all([source, target])
    await session.commit()

    with pytest.raises(ResourceConflict, match="visibility closure"):
        await ResourceService(session, _actor()).replace_dependencies(source.id, [target.id])


@pytest.mark.asyncio
async def test_replace_dependencies_rejects_duplicate_explicit_ids(session: AsyncSession) -> None:
    source = _resource("workflow-dep")
    target = _resource("agent-dep", resource_type="agent")
    session.add_all([source, target])
    await session.commit()

    with pytest.raises(ResourceConflict, match="Duplicate resource dependency"):
        await ResourceService(session, _actor()).replace_dependencies(source.id, [target.id, target.id])


@pytest.mark.asyncio
async def test_dependency_closure_error_carries_structured_violation(session: AsyncSession) -> None:
    source = _resource("public-agent", visibility="public")
    target = _resource("private-skill", resource_type="skill", visibility="private")
    session.add_all([source, target])
    await session.commit()

    with pytest.raises(VisibilityClosureError) as excinfo:
        await ResourceService(session, _actor()).replace_dependencies(source.id, [target.id])

    assert "slug-public-agent" in str(excinfo.value)
    assert "slug-private-skill" in str(excinfo.value)
    assert excinfo.value.violations == [
        {
            "source": {"slug": source.slug, "display_name": source.display_name, "type": "agent"},
            "target": {
                "slug": target.slug,
                "display_name": target.display_name,
                "type": "skill",
                "visibility": "private",
            },
            "required_visibility": "public",
            "owned_by_actor": True,
        }
    ]


@pytest.mark.asyncio
async def test_dependency_closure_violation_flags_ownership_for_other_owners(session: AsyncSession) -> None:
    source = _resource("public-agent", visibility="public")
    target = _resource(
        "private-skill",
        resource_type="skill",
        visibility="department",
        department_id="dept-a",
        owner_id="someone-else",
    )
    session.add_all([source, target])
    await session.commit()

    with pytest.raises(VisibilityClosureError) as excinfo:
        await ResourceService(session, _actor()).replace_dependencies(source.id, [target.id])

    assert excinfo.value.violations[0]["owned_by_actor"] is False


@pytest.mark.asyncio
async def test_request_visibility_fails_fast_on_closure_violation(session: AsyncSession) -> None:
    agent = _resource("public-agent")
    skill = _resource("private-skill", resource_type="skill")
    session.add_all([agent, skill])
    await session.commit()
    service = ResourceService(session, _actor())
    await _publish(service, agent.id, expected_revision=0, content_hash="a" * 64, storage_key="agents/public-agent/1")
    session.add_all([ResourceDependency(id="edge-1", source_resource_id=agent.id, target_resource_id=skill.id)])
    await session.commit()

    with pytest.raises(VisibilityClosureError) as excinfo:
        await service.request_visibility(
            agent.id,
            target_visibility="public",
            scope_department_id=None,
            reason="share",
        )

    assert len(excinfo.value.violations) == 1
    assert excinfo.value.violations[0]["target"]["slug"] == skill.slug
    assert excinfo.value.violations[0]["required_visibility"] == "public"
    assert not list((await session.execute(select(VisibilityApplication))).scalars())


@pytest.mark.asyncio
async def test_review_aggregates_all_closure_violations(session: AsyncSession) -> None:
    agent = _resource("public-agent")
    skill_a = _resource("private-skill-a", resource_type="skill")
    skill_b = _resource("private-skill-b", resource_type="skill")
    session.add_all([agent, skill_a, skill_b])
    await session.commit()
    service = ResourceService(session, _actor())
    await _publish(service, agent.id, expected_revision=0, content_hash="a" * 64, storage_key="agents/public-agent/1")
    session.add_all(
        [
            ResourceDependency(id="edge-a", source_resource_id=agent.id, target_resource_id=skill_a.id),
            ResourceDependency(id="edge-b", source_resource_id=agent.id, target_resource_id=skill_b.id),
        ]
    )
    application = VisibilityApplication(
        id="app-1",
        resource_type="agent",
        resource_id=agent.slug,
        canonical_resource_id=agent.id,
        requested_version=1,
        requested_hash="a" * 64,
        applicant_id="owner",
        current_visibility="private",
        target_visibility="public",
        reason="share",
        status="pending",
        version=1,
    )
    session.add(application)
    await session.commit()

    reviewer = ResourceService(
        session,
        _actor(
            "reviewer",
            role="super_admin",
            permissions={
                ResourceAction.READ,
                ResourceAction.USE,
                ResourceAction.WRITE,
                ResourceAction.APPROVE,
            },
        ),
    )
    with pytest.raises(VisibilityClosureError) as excinfo:
        await reviewer.review_visibility_application("app-1", approve=True, comment="")

    assert {v["target"]["slug"] for v in excinfo.value.violations} == {skill_a.slug, skill_b.slug}
    assert application.status == "pending"


@pytest.mark.asyncio
async def test_dependency_cycle_is_rejected_before_snapshot(session: AsyncSession) -> None:
    first = _resource("first", resource_type="workflow")
    second = _resource("second", resource_type="agent")
    session.add_all([first, second])
    await session.commit()
    service = ResourceService(session, _actor())
    await _publish(service, first.id, expected_revision=0, content_hash="1" * 64, storage_key="db/first/1")
    await _publish(service, second.id, expected_revision=0, content_hash="2" * 64, storage_key="agents/second/1")
    session.add_all(
        [
            ResourceDependency(id="edge-1", source_resource_id=first.id, target_resource_id=second.id),
            ResourceDependency(id="edge-2", source_resource_id=second.id, target_resource_id=first.id),
        ]
    )
    await session.commit()

    with pytest.raises(ResourceConflict, match="cycle"):
        await service.create_run_snapshot("run-cycle", first.id)

    assert not list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == "run-cycle"))).scalars())


@pytest.mark.asyncio
async def test_run_snapshot_freezes_latest_dependency_versions(session: AsyncSession) -> None:
    workflow = _resource("workflow", resource_type="workflow")
    agent = _resource("agent")
    session.add_all([workflow, agent])
    await session.commit()
    service = ResourceService(session, _actor())
    await _publish(service, workflow.id, expected_revision=0, content_hash="w" * 64, storage_key="db/workflow/1")
    await _publish(service, agent.id, expected_revision=0, content_hash="a" * 64, storage_key="agents/agent/versions/1")
    await service.replace_dependencies(workflow.id, [agent.id])

    snapshot = await service.create_run_snapshot("run-1", workflow.id)
    await _publish(service, agent.id, expected_revision=1, content_hash="b" * 64, storage_key="agents/agent/versions/2")

    assert [(row.resource_id, row.version, row.content_hash) for row in snapshot] == [
        (workflow.id, 1, "w" * 64),
        (agent.id, 1, "a" * 64),
    ]
    persisted = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == "run-1").order_by(RunResourceSnapshot.id))).scalars())
    assert {(row.resource_id, row.version) for row in persisted} == {(workflow.id, 1), (agent.id, 1)}


@pytest.mark.asyncio
async def test_new_run_revalidates_visibility_closure_after_dependency_shrinks(
    session: AsyncSession,
) -> None:
    workflow = _resource("public-workflow", resource_type="workflow", visibility="public")
    agent = _resource("public-agent", visibility="public")
    session.add_all([workflow, agent])
    await session.commit()
    service = ResourceService(session, _actor())
    await _publish(service, workflow.id, expected_revision=0, content_hash="w" * 64, storage_key="db/workflow/1")
    await _publish(service, agent.id, expected_revision=0, content_hash="a" * 64, storage_key="agents/agent/versions/1")
    await service.replace_dependencies(workflow.id, [agent.id])
    agent.visibility = "private"
    agent.authz_revision += 1
    await session.commit()

    with pytest.raises(ResourceConflict, match="visibility closure"):
        await service.create_run_snapshot("run-after-shrink", workflow.id)

    assert not list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == "run-after-shrink"))).scalars())


@pytest.mark.asyncio
async def test_fork_creates_private_v1_and_keeps_shallow_dependencies(session: AsyncSession) -> None:
    source = _resource("source", visibility="public", owner_id="source-owner")
    dependency = _resource("dependency", resource_type="skill", visibility="public", owner_id="source-owner")
    session.add_all([source, dependency])
    session.add(
        ResourceVersion(
            id="source-version",
            resource_id=source.id,
            version=1,
            content_hash="f" * 64,
            storage_key="agents/source/versions/1",
            scan_result={"status": "clean"},
            created_by="source-owner",
        )
    )
    source.latest_version = 1
    session.add(ResourceDependency(id="source-dependency", source_resource_id=source.id, target_resource_id=dependency.id))
    await session.commit()

    forked = await ResourceService(session, _actor("fork-owner")).fork(
        source.id,
        slug="forked-agent",
        display_name="Forked Agent",
        copied_storage_key="agents/forked/versions/1",
    )

    assert forked.id != source.id
    assert forked.owner_id == "fork-owner"
    assert forked.visibility == "private"
    assert forked.latest_version == 1
    fork_version = (await session.execute(select(ResourceVersion).where(ResourceVersion.resource_id == forked.id))).scalar_one()
    assert (fork_version.source_resource_id, fork_version.source_version, fork_version.content_hash) == (
        source.id,
        1,
        "f" * 64,
    )
    fork_edges = list((await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == forked.id))).scalars())
    assert [edge.target_resource_id for edge in fork_edges] == [dependency.id]


@pytest.mark.asyncio
async def test_fork_of_bundled_resource_is_user_provenance(session: AsyncSession) -> None:
    source = _resource("bundled-source", resource_type="workflow", visibility="public", owner_id="source-owner")
    source.provenance = "bundled"
    session.add(source)
    session.add(
        ResourceVersion(
            id="source-version",
            resource_id=source.id,
            version=1,
            content_hash="e" * 64,
            storage_key="workflows/bundled-source/versions/1",
            scan_result={"status": "trusted_bundled_manifest"},
            created_by="source-owner",
        )
    )
    source.latest_version = 1
    await session.commit()

    forked = await ResourceService(session, _actor("fork-owner")).fork(
        source.id,
        slug="forked-flow",
        display_name="Forked Flow",
        copied_storage_key="workflows/forked/versions/1",
    )

    assert forked.provenance == "user"
    assert forked.storage_kind == "database"
