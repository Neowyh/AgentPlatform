"""Knowledge reconciliation admin API governance (M4 ticket 05)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import deerflow.persistence.models  # noqa: F401  -- registers DeerFlow ORM tables
import deerflow.persistence.models.workflow_v2  # noqa: F401
from app.agentplatform.rbac_models import UserModel, UserRole
from app.gateway.routers import admin_knowledge
from deerflow.persistence.base import Base


async def _make_env(tmp_path, monkeypatch: pytest.MonkeyPatch, role: UserRole = UserRole.SUPER_ADMIN) -> tuple:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconcile-admin.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id="admin",
        username="admin@test.com",
        role=role,
        department_id=None,
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
    monkeypatch.setattr(admin_knowledge, "get_session_factory", lambda: factory)
    return engine, factory, current_user


@pytest.mark.asyncio
async def test_reconciliation_run_requires_super_admin(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _factory, _admin = await _make_env(tmp_path, monkeypatch, UserRole.USER)

    with pytest.raises(HTTPException) as forbidden:
        await admin_knowledge.trigger_reconciliation(
            SimpleNamespace(),
            admin_knowledge.ReconciliationRunRequest(),
            current_user=UserModel(id="user", username="user@test.com", role=UserRole.USER, department_id=None, disabled=False),
        )
    assert forbidden.value.status_code == 403
    await engine.dispose()


@pytest.mark.asyncio
async def test_reconciliation_run_without_provider_reports_unavailable(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _factory, admin = await _make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(admin_knowledge, "configured_ragflow_provider", lambda: None)

    with pytest.raises(HTTPException) as unavailable:
        await admin_knowledge.trigger_reconciliation(
            SimpleNamespace(),
            admin_knowledge.ReconciliationRunRequest(),
            current_user=admin,
        )
    assert unavailable.value.status_code == 503
    await engine.dispose()


@pytest.mark.asyncio
async def test_reconciliation_state_read_is_admin_scoped(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _factory, admin = await _make_env(tmp_path, monkeypatch)

    state = await admin_knowledge.get_reconciliation("kb-1", SimpleNamespace(), current_user=admin)
    assert state == {"knowledge_base_id": "kb-1", "revisions": [], "checks": []}

    with pytest.raises(HTTPException) as forbidden:
        await admin_knowledge.get_reconciliation(
            "kb-1",
            SimpleNamespace(),
            current_user=UserModel(id="user", username="user@test.com", role=UserRole.USER, department_id=None, disabled=False),
        )
    assert forbidden.value.status_code == 403
    await engine.dispose()
