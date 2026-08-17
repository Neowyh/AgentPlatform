"""Creation, approval, favorite, and administrative lifecycle contracts."""

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
    ResourceFavorite,
    ResourceNotification,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.visibility_application import VisibilityApplication
from ideer.persistence.models.workflow_v2 import WorkflowCommandRow, WorkflowTaskRow, WorkflowV2RunRow
from ideer.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceConflict,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceService,
)


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'governance.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def _actor(
    user_id: str,
    *,
    role: str = "user",
    department_id: str | None = "dept-a",
    permissions: set[ResourceAction] | None = None,
) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        role=role,
        department_id=department_id,
        permissions=frozenset(
            permissions
            or {
                ResourceAction.READ,
                ResourceAction.USE,
                ResourceAction.WRITE,
            }
        ),
    )


def _resource(
    resource_id: str,
    *,
    owner_id: str = "owner",
    visibility: str = "private",
    department_id: str | None = None,
    lifecycle_status: str = "active",
) -> Resource:
    return Resource(
        id=resource_id,
        type="agent",
        slug=f"slug-{resource_id}",
        display_name=resource_id,
        owner_id=owner_id,
        visibility=visibility,
        scope_department_id=department_id,
        lifecycle_status=lifecycle_status,
        latest_version=1,
        draft_revision=0,
        storage_kind="filesystem",
        storage_key=f"agents/{resource_id}",
        system_owned=False,
        authz_revision=1,
    )


def _version(resource: Resource) -> ResourceVersion:
    return ResourceVersion(
        id=f"version-{resource.id}",
        resource_id=resource.id,
        version=1,
        content_hash="a" * 64,
        storage_key=f"agents/{resource.id}/versions/1",
        scan_result={"status": "clean"},
        created_by=resource.owner_id,
    )


@pytest.mark.asyncio
async def test_create_resource_uses_uuid_and_rejects_invalid_storage_pairing(session: AsyncSession) -> None:
    service = ResourceService(session, _actor("owner"))

    resource = await service.create_resource(
        resource_type="agent",
        slug="writer",
        display_name="Writer",
        storage_kind="filesystem",
    )

    assert resource.owner_id == "owner"
    assert resource.visibility == "private"
    assert resource.storage_key == f"agents/{resource.id}"
    assert len(resource.id) == 36
    with pytest.raises(ValueError, match="database storage"):
        await service.create_resource(
            resource_type="workflow",
            slug="bad-workflow",
            display_name="Bad",
            storage_kind="filesystem",
        )


@pytest.mark.asyncio
async def test_favorite_requires_visibility_and_is_idempotent(session: AsyncSession) -> None:
    visible = _resource("visible", owner_id="other", visibility="public")
    hidden = _resource("hidden", owner_id="other")
    session.add_all([visible, hidden])
    await session.commit()
    service = ResourceService(session, _actor("runner"))

    first = await service.favorite(visible.id)
    second = await service.favorite(visible.id)

    assert first.resource_id == second.resource_id == visible.id
    assert len(list((await session.execute(select(ResourceFavorite))).scalars())) == 1
    with pytest.raises(ResourceNotFound):
        await service.favorite(hidden.id)
    assert await service.unfavorite(visible.id) is True
    assert await service.unfavorite(visible.id) is False


@pytest.mark.asyncio
async def test_visibility_reduction_notifies_every_affected_upstream_owner(
    session: AsyncSession,
) -> None:
    target = _resource("shared", visibility="public")
    dependent = _resource("dependent", owner_id="upstream", visibility="public")
    session.add_all(
        [
            target,
            dependent,
            ResourceDependency(
                id="dependency",
                source_resource_id=dependent.id,
                target_resource_id=target.id,
            ),
        ]
    )
    await session.commit()

    await ResourceService(session, _actor("owner")).change_visibility(
        target.id,
        "private",
    )
    notification = (await session.execute(select(ResourceNotification))).scalar_one()

    assert notification.recipient_id == "upstream"
    assert notification.resource_id == target.id
    assert notification.event == "visibility_reduced"
    assert notification.detail["dependent_resource_ids"] == [dependent.id]


@pytest.mark.asyncio
async def test_visibility_application_freezes_version_and_hash_and_prevents_duplicate_pending(
    session: AsyncSession,
) -> None:
    resource = _resource("share")
    session.add_all([resource, _version(resource)])
    await session.commit()
    service = ResourceService(session, _actor("owner"))

    application = await service.request_visibility(
        resource.id,
        target_visibility="department",
        scope_department_id="dept-a",
        reason="share within department",
    )

    assert application.canonical_resource_id == resource.id
    assert application.requested_version == 1
    assert application.requested_hash == "a" * 64
    with pytest.raises(ResourceConflict, match="pending"):
        await service.request_visibility(
            resource.id,
            target_visibility="department",
            scope_department_id="dept-a",
            reason="duplicate",
        )


@pytest.mark.asyncio
async def test_department_admin_queries_and_approves_only_own_department(session: AsyncSession) -> None:
    own = _resource("own-dept", department_id=None)
    other = _resource("other-dept", owner_id="other", department_id=None)
    session.add_all([own, other, _version(own), _version(other)])
    await session.commit()
    await ResourceService(session, _actor("owner", department_id="dept-a")).request_visibility(
        own.id,
        target_visibility="department",
        scope_department_id="dept-a",
        reason="own department",
    )
    await ResourceService(session, _actor("other", department_id="dept-b")).request_visibility(
        other.id,
        target_visibility="department",
        scope_department_id="dept-b",
        reason="other department",
    )
    reviewer = ResourceService(
        session,
        _actor(
            "reviewer",
            role="department_admin",
            department_id="dept-a",
            permissions={ResourceAction.READ, ResourceAction.APPROVE},
        ),
    )

    pending = await reviewer.list_pending_visibility_applications(offset=0, limit=20)

    assert [item.canonical_resource_id for item in pending.items] == [own.id]
    with pytest.raises(ResourceConflict, match="version changed"):
        await reviewer.review_visibility_application(
            pending.items[0].id,
            approve=True,
            comment="stale",
            expected_version=2,
        )
    approved = await reviewer.review_visibility_application(
        pending.items[0].id,
        approve=True,
        comment="ok",
        expected_version=1,
    )
    assert approved.status == "approved"
    assert approved.version == 2
    assert own.visibility == "department"
    assert own.scope_department_id == "dept-a"
    other_application = (await session.execute(select(VisibilityApplication).where(VisibilityApplication.canonical_resource_id == other.id))).scalar_one()
    with pytest.raises(ResourcePermissionDenied, match="department"):
        await reviewer.review_visibility_application(other_application.id, approve=True, comment="wrong scope")


@pytest.mark.asyncio
async def test_super_admin_can_restore_suspended_resource_without_editing_content(session: AsyncSession) -> None:
    resource = _resource("restore", lifecycle_status="suspended")
    session.add(resource)
    await session.commit()
    service = ResourceService(
        session,
        _actor(
            "admin",
            role="super_admin",
            permissions={ResourceAction.READ, ResourceAction.SUSPEND},
        ),
    )

    restored = await service.restore(resource.id)

    assert restored.lifecycle_status == "active"
    assert restored.authz_revision == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("task_status", ["queued", "paused", "running"])
async def test_emergency_suspend_cancels_active_snapshotted_workflow_runs(
    session: AsyncSession,
    task_status: str,
) -> None:
    resource = _resource("emergency", owner_id="owner", visibility="public")
    run_id = f"run-{task_status}"
    session.add_all(
        [
            resource,
            WorkflowV2RunRow(
                run_id=run_id,
                workflow_name="flow",
                definition_version=1,
                checkpoint_thread_id=f"thread-{task_status}",
                status=task_status,
                inputs={},
                snapshot={},
                event_seq=0,
                created_by="runner",
            ),
            WorkflowTaskRow(
                task_id=f"task-{task_status}",
                run_id=run_id,
                status=task_status,
                attempts=1,
                cancel_requested=False,
            ),
            RunResourceSnapshot(
                id=f"snapshot-{task_status}",
                run_id=run_id,
                root_resource_id=resource.id,
                resource_id=resource.id,
                version=1,
                content_hash="a" * 64,
                authz_revision=1,
            ),
        ]
    )
    await session.commit()
    service = ResourceService(
        session,
        _actor(
            "admin",
            role="super_admin",
            permissions={ResourceAction.READ, ResourceAction.SUSPEND},
        ),
    )

    await service.suspend(resource.id)

    task = (await session.execute(select(WorkflowTaskRow).where(WorkflowTaskRow.run_id == run_id))).scalar_one()
    run = await session.get(WorkflowV2RunRow, run_id)
    command = (await session.execute(select(WorkflowCommandRow).where(WorkflowCommandRow.run_id == run_id))).scalar_one()
    if task_status == "running":
        assert task.cancel_requested is True
        assert run is not None and run.status == "running"
    else:
        assert task.status == "cancelled"
        assert run is not None and run.status == "cancelled"
    assert command.command_type == "cancel"
    assert command.created_by == "admin"


@pytest.mark.asyncio
async def test_user_deletion_governance_transfers_or_archives_without_changing_uuid(session: AsyncSession) -> None:
    transferable = _resource("transferable", owner_id="deleted-user", visibility="public")
    archivable = _resource("archivable", owner_id="archive-user", visibility="department", department_id="dept-a")
    session.add_all([transferable, archivable])
    await session.commit()
    service = ResourceService(
        session,
        _actor(
            "admin",
            role="super_admin",
            permissions={ResourceAction.READ, ResourceAction.TRANSFER, ResourceAction.PURGE},
        ),
    )

    transferred = await service.govern_owner_deletion(
        "deleted-user",
        strategy="transfer",
        target_owner_id="target-user",
    )
    archived = await service.govern_owner_deletion("archive-user", strategy="archive")

    assert [(item.id, item.owner_id, item.visibility) for item in transferred] == [("transferable", "target-user", "private")]
    assert [(item.id, item.owner_id, item.lifecycle_status) for item in archived] == [("archivable", "archive-user", "archived")]


@pytest.mark.asyncio
async def test_department_deletion_governance_reassigns_or_downgrades_scope(session: AsyncSession) -> None:
    reassigned = _resource(
        "reassigned",
        owner_id="owner",
        visibility="department",
        department_id="deleted-dept",
    )
    downgraded = _resource(
        "downgraded",
        owner_id="owner",
        visibility="department",
        department_id="other-deleted-dept",
    )
    session.add_all([reassigned, downgraded])
    await session.commit()
    service = ResourceService(
        session,
        _actor(
            "admin",
            role="super_admin",
            permissions={ResourceAction.READ, ResourceAction.TRANSFER, ResourceAction.PURGE},
        ),
    )

    await service.govern_department_deletion("deleted-dept", target_department_id="target-dept")
    await service.govern_department_deletion("other-deleted-dept", target_department_id=None)

    assert (reassigned.visibility, reassigned.scope_department_id, reassigned.authz_revision) == (
        "department",
        "target-dept",
        2,
    )
    assert (downgraded.visibility, downgraded.scope_department_id, downgraded.authz_revision) == (
        "private",
        None,
        2,
    )


def _skill_resource(
    resource_id: str,
    *,
    owner_id: str = "owner",
    visibility: str = "private",
    department_id: str | None = None,
    system_owned: bool = False,
) -> Resource:
    return Resource(
        id=resource_id,
        type="skill",
        slug=f"slug-{resource_id}",
        display_name=resource_id,
        owner_id=owner_id,
        visibility=visibility,
        scope_department_id=department_id,
        lifecycle_status="active",
        latest_version=1,
        draft_revision=0,
        storage_kind="filesystem",
        storage_key=f"skills/{resource_id}",
        system_owned=system_owned,
        authz_revision=1,
    )


def _dependency(edge_id: str, source_id: str, target_id: str) -> ResourceDependency:
    return ResourceDependency(id=edge_id, source_resource_id=source_id, target_resource_id=target_id)


@pytest.mark.asyncio
async def test_visibility_reduction_impact_lists_direct_and_transitive_dependents(session: AsyncSession) -> None:
    skill = _skill_resource("shared-skill", visibility="public")
    agent = _resource("public-agent", owner_id="alice", visibility="public")
    workflow = _resource("public-workflow", owner_id="bob", visibility="public")
    session.add_all(
        [
            skill,
            agent,
            workflow,
            _dependency("e1", agent.id, skill.id),
            _dependency("e2", workflow.id, agent.id),
        ]
    )
    await session.commit()

    impact = await ResourceService(session, _actor("owner")).visibility_reduction_impact(skill.id, "private")

    assert impact["total"] == 2
    assert [item["resource_id"] for item in impact["direct"]] == ["public-agent"]
    assert [item["resource_id"] for item in impact["transitive"]] == ["public-workflow"]
    assert impact["blocked_count"] == 0
    assert impact["impacted"][0]["proposed_visibility"] == "private"
    assert impact["impacted"][0]["owned_by_actor"] is False


@pytest.mark.asyncio
async def test_visibility_reduction_impact_is_empty_without_dependents_or_reduction(session: AsyncSession) -> None:
    skill = _skill_resource("lonely-skill", visibility="public")
    session.add(skill)
    await session.commit()
    service = ResourceService(session, _actor("owner"))

    reduced = await service.visibility_reduction_impact(skill.id, "private")
    expanded = await service.visibility_reduction_impact(skill.id, "public")

    assert reduced["total"] == 0 and reduced["direct"] == [] and reduced["transitive"] == []
    assert expanded["total"] == 0


@pytest.mark.asyncio
async def test_visibility_reduction_impact_requires_owner(session: AsyncSession) -> None:
    skill = _skill_resource("others-skill", owner_id="someone", visibility="public")
    session.add(skill)
    await session.commit()

    with pytest.raises(ResourcePermissionDenied):
        await ResourceService(session, _actor("owner")).visibility_reduction_impact(skill.id, "private")


@pytest.mark.asyncio
async def test_visibility_reduction_impact_marks_system_owned_dependents_blocked(session: AsyncSession) -> None:
    skill = _skill_resource("shared-skill", visibility="public")
    bundled = _resource("bundled-agent", owner_id="bob", visibility="public")
    bundled.system_owned = True
    session.add_all([skill, bundled, _dependency("e1", bundled.id, skill.id)])
    await session.commit()

    impact = await ResourceService(session, _actor("owner")).visibility_reduction_impact(skill.id, "private")

    assert impact["blocked_count"] == 1
    assert impact["direct"][0]["blocked"] is True
    assert impact["direct"][0]["proposed_visibility"] == "public"


@pytest.mark.asyncio
async def test_cascade_repair_reduces_dependents_and_notifies_their_owners(session: AsyncSession) -> None:
    skill = _skill_resource("shared-skill", visibility="public")
    agent = _resource("public-agent", owner_id="alice", visibility="public")
    workflow = _resource("public-workflow", owner_id="bob", visibility="public")
    session.add_all(
        [
            skill,
            agent,
            workflow,
            _dependency("e1", agent.id, skill.id),
            _dependency("e2", workflow.id, agent.id),
        ]
    )
    await session.commit()
    service = ResourceService(session, _actor("owner"))

    changed = await service.change_visibility(skill.id, "private", cascade=True)

    assert changed.visibility == "private"
    assert (await session.get(Resource, agent.id)).visibility == "private"
    assert (await session.get(Resource, workflow.id)).visibility == "private"
    assert (await session.get(Resource, workflow.id)).scope_department_id is None
    assert (await session.get(Resource, workflow.id)).authz_revision == 2

    alice_notifications = list((await session.execute(select(ResourceNotification).where(ResourceNotification.recipient_id == "alice"))).scalars())
    assert [item.event for item in alice_notifications] == ["visibility_reduced_cascade"]
    assert alice_notifications[0].resource_id == agent.id
    assert alice_notifications[0].detail["source_slug"] == skill.slug
    bob_notifications = list((await session.execute(select(ResourceNotification).where(ResourceNotification.recipient_id == "bob"))).scalars())
    assert any(item.resource_id == workflow.id and item.event == "visibility_reduced_cascade" for item in bob_notifications)


@pytest.mark.asyncio
async def test_cascade_skips_system_owned_dependents(session: AsyncSession) -> None:
    skill = _skill_resource("shared-skill", visibility="public")
    bundled = _resource("bundled-agent", owner_id="bob", visibility="public")
    bundled.system_owned = True
    session.add_all([skill, bundled, _dependency("e1", bundled.id, skill.id)])
    await session.commit()
    service = ResourceService(session, _actor("owner"))

    await service.change_visibility(skill.id, "private", cascade=True)

    assert (await session.get(Resource, bundled.id)).visibility == "public"


@pytest.mark.asyncio
async def test_cascade_without_flag_keeps_dependents_and_notifies_directly(session: AsyncSession) -> None:
    skill = _skill_resource("shared-skill", visibility="public")
    agent = _resource("public-agent", owner_id="alice", visibility="public")
    session.add_all([skill, agent, _dependency("e1", agent.id, skill.id)])
    await session.commit()
    service = ResourceService(session, _actor("owner"))

    await service.change_visibility(skill.id, "private")

    assert (await session.get(Resource, agent.id)).visibility == "public"
    notification = (await session.execute(select(ResourceNotification))).scalar_one()
    assert notification.event == "visibility_reduced"
    assert notification.detail["dependent_resource_ids"] == [agent.id]
    assert notification.detail["dependent_display_names"] == [agent.display_name]
    assert notification.detail["resource_slug"] == skill.slug


@pytest.mark.asyncio
async def test_super_admin_alert_only_when_other_owners_are_impacted(session: AsyncSession) -> None:
    session.add(UserModel(id="sadmin", username="sadmin", role=UserRole.SUPER_ADMIN.value, disabled=False))
    skill = _skill_resource("shared-skill", visibility="public")
    agent = _resource("public-agent", owner_id="alice", visibility="public")
    session.add_all([skill, agent, _dependency("e1", agent.id, skill.id)])
    await session.commit()
    service = ResourceService(session, _actor("owner"))

    await service.change_visibility(skill.id, "private")

    admin_notifications = list((await session.execute(select(ResourceNotification).where(ResourceNotification.recipient_id == "sadmin"))).scalars())
    assert len(admin_notifications) == 1
    assert admin_notifications[0].event == "admin_visibility_reduced"
    assert admin_notifications[0].detail["impacted_count"] == 1
    assert admin_notifications[0].detail["previous_visibility"] == "public"

    own_skill = _skill_resource("own-skill", visibility="public")
    own_agent = _resource("own-agent", owner_id="owner", visibility="public")
    session.add_all([own_skill, own_agent, _dependency("e2", own_agent.id, own_skill.id)])
    await session.commit()

    await service.change_visibility(own_skill.id, "private")

    admin_notifications = list((await session.execute(select(ResourceNotification).where(ResourceNotification.recipient_id == "sadmin"))).scalars())
    assert len(admin_notifications) == 1
