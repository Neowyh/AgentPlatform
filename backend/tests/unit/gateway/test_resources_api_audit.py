"""Canonical resource lifecycle endpoints record audit entries."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from app.gateway.routers import resources
from ideer.persistence.base import Base
from ideer.persistence.models.user import UserModel, UserRole
from ideer.resources.service import ResourceAction, ResourceActor, ResourceService


def _actor(role: str) -> ResourceActor:
    permissions = {ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}
    if role == "super_admin":
        permissions.update(ResourceAction)
    return ResourceActor(
        user_id="owner",
        department_id="dept-a",
        role=role,
        permissions=frozenset(permissions),
    )


async def _make_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: UserRole,
) -> tuple:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id="owner",
        username="owner@test.com",
        role=role,
        department_id="dept-a",
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
    monkeypatch.setattr(resources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(
        resources,
        "get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path),
    )
    return engine, factory, current_user


@pytest.mark.asyncio
async def test_canonical_create_and_archive_record_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creating and archiving a canonical resource emits audit entries."""
    engine, _factory, current_user = await _make_env(tmp_path, monkeypatch, UserRole.USER)
    calls: list[tuple] = []

    async def _audit(
        actor_id: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        detail: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        calls.append((actor_id, action, resource_type, resource_id, detail))

    monkeypatch.setattr(resources, "record_audit", _audit)

    created = await resources.create_resource(
        resources.ResourceCreateRequest(
            type="agent",
            slug="audit-agent",
            display_name="Audit Agent",
            storage_kind="filesystem",
        ),
        current_user,
    )
    resource_id = created["id"]

    assert calls[-1][0] == "owner"
    assert calls[-1][1] == "resource_created"
    assert calls[-1][2] == "agent"
    assert calls[-1][3] == resource_id

    await resources.archive_resource(resource_id, current_user)

    assert calls[-1][1] == "resource_archived"
    assert calls[-1][2] == "agent"
    assert calls[-1][3] == resource_id
    assert calls[-1][4] is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_canonical_suspend_and_restore_record_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Suspending and restoring a canonical resource emits audit entries."""
    engine, _factory, current_user = await _make_env(tmp_path, monkeypatch, UserRole.SUPER_ADMIN)
    calls: list[tuple] = []

    async def _audit(
        actor_id: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        detail: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        calls.append((actor_id, action, resource_type, resource_id, detail))

    monkeypatch.setattr(resources, "record_audit", _audit)

    created = await resources.create_resource(
        resources.ResourceCreateRequest(
            type="skill",
            slug="audit-skill",
            display_name="Audit Skill",
            storage_kind="filesystem",
        ),
        current_user,
    )
    resource_id = created["id"]
    calls.clear()

    await resources.suspend_resource(resource_id, current_user)

    assert calls[-1][1] == "resource_suspended"
    assert calls[-1][2] == "skill"
    assert calls[-1][3] == resource_id
    assert calls[-1][4] is not None

    await resources.restore_resource(resource_id, current_user)

    assert calls[-1][1] == "resource_restored"
    assert calls[-1][2] == "skill"
    assert calls[-1][3] == resource_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_canonical_archive_denied_for_non_owner_does_not_record_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A denied lifecycle action is not recorded as an audit entry."""
    engine, _factory, current_user = await _make_env(tmp_path, monkeypatch, UserRole.USER)
    async with _factory() as session:
        agent = await ResourceService(session, _actor("user")).create_resource(
            resource_type="agent",
            slug="owned-by-other",
            display_name="Owned By Other",
            storage_kind="filesystem",
        )
        await session.commit()
        resource_id = agent.id

    calls: list[tuple] = []

    async def _audit(*args, **kwargs) -> None:
        calls.append(args)

    monkeypatch.setattr(resources, "record_audit", _audit)

    intruder = UserModel(
        id="intruder",
        username="intruder@test.com",
        role=UserRole.USER,
        department_id="dept-a",
        disabled=False,
    )
    async with _factory() as session:
        session.add(intruder)
        await session.commit()

    with pytest.raises(Exception):
        await resources.archive_resource(resource_id, intruder)

    assert calls == []
    await engine.dispose()
