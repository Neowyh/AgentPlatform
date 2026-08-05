"""DELETE /api/workflows/{name} must remove the definition and metadata together.

Regression: delete_workflow only hard-deleted resource_metadata, leaving the
workflow_definition_versions row behind — a "ghost" workflow that keeps
appearing in listings while lacking RBAC metadata. This suite drives the
endpoint against a real FK-enabled database and asserts both tables are
cleaned while historical run rows survive.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers import workflows as workflows_module
from app.gateway.routers.workflows import router as workflows_router
from ideer.persistence.base import Base
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.workflow_v2 import WorkflowDefinitionVersionRow, WorkflowV2RunRow
from ideer.workflows.v2.store import WorkflowV2Store

_DEFINITION = {
    "schema_version": 2,
    "name": "test-wf",
    "description": "test",
    "inputs": {},
    "state": {},
    "entrypoint": "step_1",
    "nodes": [{"id": "step_1", "type": "action", "action": {"kind": "agent", "name": "fault-zeroing"}}],
    "edges": [],
}


@pytest_asyncio.fixture
async def real_env(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _record):  # noqa: ARG001 — SQLAlchemy contract
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        session.add(UserModel(id="user-1", username="user@test.com", role=UserRole.USER, disabled=False))
        await session.commit()

    monkeypatch.setattr(workflows_module, "get_session_factory", lambda: sf)
    monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: sf)
    monkeypatch.setattr("app.gateway.utils.get_session_factory", lambda: sf)

    async def _noop_audit(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(workflows_module, "record_audit", _noop_audit)

    store = WorkflowV2Store(sf)
    await store.save_definition("test-wf", _DEFINITION, "hash", "user-1")

    from app.gateway.utils import ResourceMetadataStore

    await ResourceMetadataStore("workflow").save_meta("test-wf", {"owner_id": "user-1", "visibility": "private"})

    app = FastAPI()
    app.include_router(workflows_router)

    async def _stub_user():
        return SimpleNamespace(id="user-1", role=UserRole.USER, department_id=None, username="user@test.com")

    app.dependency_overrides[get_current_rbac_user] = _stub_user

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sf=sf, store=store)
    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_removes_definition_and_metadata_but_keeps_runs(real_env) -> None:
    await real_env.store.create_run("run-1", "test-wf", 1, {}, "user-1")

    response = real_env.client.delete("/api/workflows/test-wf")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    async with real_env.sf() as session:
        definitions = (await session.execute(select(WorkflowDefinitionVersionRow).where(WorkflowDefinitionVersionRow.workflow_name == "test-wf"))).scalars().all()
        assert definitions == []
        metas = (await session.execute(select(ResourceMetadata).where(ResourceMetadata.resource_type == "workflow", ResourceMetadata.resource_id == "test-wf"))).scalars().all()
        assert metas == []
        run = await session.get(WorkflowV2RunRow, "run-1")
        assert run is not None
        assert run.workflow_name == "test-wf"


@pytest.mark.asyncio
async def test_delete_clears_workflow_from_listing(real_env) -> None:
    response = real_env.client.delete("/api/workflows/test-wf")
    assert response.status_code == 200

    listing = real_env.client.get("/api/workflows")
    assert listing.status_code == 200
    assert listing.json()["workflows"] == []
    assert listing.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_of_unknown_workflow_returns_404(real_env) -> None:
    response = real_env.client.delete("/api/workflows/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_does_not_touch_other_workflows(real_env) -> None:
    await real_env.store.save_definition("keep-wf", _DEFINITION, "hash-2", "user-1")
    from app.gateway.utils import ResourceMetadataStore

    await ResourceMetadataStore("workflow").save_meta("keep-wf", {"owner_id": "user-1", "visibility": "private"})

    response = real_env.client.delete("/api/workflows/test-wf")
    assert response.status_code == 200

    async with real_env.sf() as session:
        remaining = (await session.execute(select(WorkflowDefinitionVersionRow))).scalars().all()
        assert [row.workflow_name for row in remaining] == ["keep-wf"]
