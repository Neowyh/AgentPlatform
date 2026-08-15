"""Authorization and query contracts for the canonical ResourceService."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401 - register all ORM models
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource
from ideer.persistence.models.visibility_application import VisibilityApplication
from ideer.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceApprovalRequired,
    ResourceConflict,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceService,
)


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'resources.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def _actor(
    user_id: str = "runner",
    *,
    department_id: str | None = "dept-a",
    role: str = "user",
    permissions: set[ResourceAction] | None = None,
) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id=department_id,
        role=role,
        permissions=frozenset(permissions or {ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


def _resource(
    resource_id: str,
    *,
    owner_id: str,
    visibility: str,
    department_id: str | None = None,
    created_offset: int = 0,
    lifecycle_status: str = "active",
) -> Resource:
    created_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=created_offset)
    return Resource(
        id=resource_id,
        type="agent",
        slug=f"agent-{resource_id}",
        display_name=f"Agent {resource_id}",
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
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.mark.asyncio
async def test_list_visible_filters_in_sql_before_pagination(session: AsyncSession) -> None:
    session.add_all(
        [
            _resource("00-invisible-private", owner_id="other", visibility="private", created_offset=0),
            _resource("01-invisible-dept", owner_id="other", visibility="department", department_id="dept-b", created_offset=1),
            _resource("10-public", owner_id="other", visibility="public", created_offset=2),
            _resource("20-department", owner_id="other", visibility="department", department_id="dept-a", created_offset=3),
            _resource("30-owned", owner_id="runner", visibility="private", created_offset=4),
            _resource("40-archived", owner_id="runner", visibility="private", created_offset=5, lifecycle_status="archived"),
        ]
    )
    await session.commit()

    page = await ResourceService(session, _actor()).list_visible(resource_type="agent", offset=0, limit=2)

    assert page.total == 3
    assert [item.id for item in page.items] == ["10-public", "20-department"]


@pytest.mark.asyncio
async def test_get_visible_hides_an_inaccessible_resource_as_not_found(session: AsyncSession) -> None:
    session.add(_resource("private-other", owner_id="other", visibility="private"))
    await session.commit()

    with pytest.raises(ResourceNotFound):
        await ResourceService(session, _actor()).get_visible("private-other")


@pytest.mark.asyncio
async def test_resolve_legacy_alias_prefers_current_owner_then_requires_unique_shared_match(
    session: AsyncSession,
) -> None:
    owned = _resource("owned-alias", owner_id="runner", visibility="private")
    owned.slug = "shared-name"
    shared_a = _resource("shared-a", owner_id="owner-a", visibility="public")
    shared_a.slug = "shared-name"
    shared_b = _resource("shared-b", owner_id="owner-b", visibility="public")
    shared_b.slug = "shared-name"
    session.add_all([owned, shared_a, shared_b])
    await session.commit()

    service = ResourceService(session, _actor())
    assert (await service.resolve_legacy_alias("agent", "shared-name")).id == owned.id

    owned.lifecycle_status = "archived"
    await session.commit()
    with pytest.raises(ResourceConflict, match="Multiple visible"):
        await service.resolve_legacy_alias("agent", "shared-name")

    shared_b.visibility = "private"
    await session.commit()
    assert (await service.resolve_legacy_alias("agent", "shared-name")).id == shared_a.id


@pytest.mark.asyncio
async def test_resolve_for_use_requires_use_permission_separately_from_read(session: AsyncSession) -> None:
    session.add(_resource("public-agent", owner_id="other", visibility="public"))
    await session.commit()
    read_only_actor = _actor(permissions={ResourceAction.READ})
    service = ResourceService(session, read_only_actor)

    assert (await service.get_visible("public-agent")).id == "public-agent"
    with pytest.raises(ResourcePermissionDenied, match="resources:use"):
        await service.resolve_for_use("public-agent")


@pytest.mark.asyncio
async def test_super_admin_can_read_but_cannot_silently_modify_owner_content(session: AsyncSession) -> None:
    resource = _resource("owned-by-other", owner_id="other", visibility="private")
    session.add(resource)
    await session.commit()
    actor = _actor(
        user_id="admin",
        role="super_admin",
        permissions={ResourceAction.READ, ResourceAction.WRITE},
    )
    service = ResourceService(session, actor)

    assert (await service.get_visible(resource.id)).id == resource.id
    with pytest.raises(ResourcePermissionDenied, match="owner"):
        service.assert_modify(resource)


@pytest.mark.asyncio
async def test_visibility_expansion_requires_approval_but_shrink_is_immediate(session: AsyncSession) -> None:
    resource = _resource("visibility", owner_id="owner", visibility="private", department_id="dept-a")
    session.add(resource)
    await session.commit()
    service = ResourceService(session, _actor(user_id="owner"))

    with pytest.raises(ResourceApprovalRequired):
        await service.change_visibility(resource.id, "public")

    resource.visibility = "public"
    application = VisibilityApplication(
        id="application",
        resource_type="agent",
        resource_id=resource.slug,
        canonical_resource_id=resource.id,
        requested_version=1,
        requested_hash="a" * 64,
        applicant_id="owner",
        current_visibility="private",
        target_visibility="public",
        department_id="dept-a",
        reason="share",
        status="pending",
        version=1,
    )
    session.add(application)
    await session.commit()

    changed = await service.change_visibility(resource.id, "private")

    assert changed.visibility == "private"
    assert changed.scope_department_id is None
    assert changed.authz_revision == 2
    assert (await session.execute(select(VisibilityApplication.status).where(VisibilityApplication.id == application.id))).scalar_one() == "withdrawn"


@pytest.mark.asyncio
async def test_archive_blocks_new_use_but_preserves_the_row(session: AsyncSession) -> None:
    resource = _resource("archive-me", owner_id="owner", visibility="private")
    session.add(resource)
    await session.commit()
    service = ResourceService(session, _actor(user_id="owner"))

    archived = await service.archive(resource.id)

    assert archived.lifecycle_status == "archived"
    assert archived.authz_revision == 2
    assert await session.get(Resource, resource.id) is archived
    with pytest.raises(ResourceNotFound):
        await service.resolve_for_use(resource.id)


@pytest.mark.asyncio
async def test_only_super_admin_with_suspend_permission_can_emergency_suspend(session: AsyncSession) -> None:
    resource = _resource("suspend-me", owner_id="owner", visibility="private")
    session.add(resource)
    await session.commit()

    owner_service = ResourceService(session, _actor(user_id="owner", permissions={ResourceAction.READ, ResourceAction.WRITE, ResourceAction.SUSPEND}))
    with pytest.raises(ResourcePermissionDenied, match="super admin"):
        await owner_service.suspend(resource.id)

    admin_service = ResourceService(
        session,
        _actor(user_id="admin", role="super_admin", permissions={ResourceAction.READ, ResourceAction.SUSPEND}),
    )
    suspended = await admin_service.suspend(resource.id)

    assert suspended.lifecycle_status == "suspended"
    assert suspended.authz_revision == 2


@pytest.mark.asyncio
async def test_transfer_keeps_uuid_and_requires_explicit_rename_on_slug_conflict(session: AsyncSession) -> None:
    resource = _resource("transfer-me", owner_id="owner", visibility="public", department_id="dept-a")
    target_collision = _resource("target-existing", owner_id="target", visibility="private")
    target_collision.slug = resource.slug
    session.add_all([resource, target_collision])
    await session.commit()
    service = ResourceService(
        session,
        _actor(user_id="admin", role="super_admin", permissions={ResourceAction.READ, ResourceAction.TRANSFER}),
    )

    with pytest.raises(ResourceConflict, match="slug"):
        await service.transfer_owner(resource.id, "target")

    assert resource.owner_id == "owner"
    transferred = await service.transfer_owner(resource.id, "target", new_slug="renamed-agent")

    assert transferred.id == "transfer-me"
    assert transferred.owner_id == "target"
    assert transferred.slug == "renamed-agent"
    assert transferred.visibility == "private"
    assert transferred.scope_department_id is None
    assert transferred.authz_revision == 2
