"""GET /api/workflows/{name} must return unicode-preserving YAML content.

Regression: _definition_yaml re-serializes the stored definition with
yaml.safe_dump, which by default escapes every non-ASCII character into
\\uXXXX sequences. The detail page renders yaml_content verbatim, so Chinese
(and any non-ASCII) text showed as garbled escape sequences. safe_dump must
use allow_unicode=True.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.authz import get_optional_rbac_user
from app.gateway.routers import workflows as workflows_module
from app.gateway.routers.workflows import router as workflows_router
from ideer.persistence.base import Base
from ideer.persistence.models.user import UserModel, UserRole
from ideer.workflows.v2.store import WorkflowV2Store

_CHINESE_DEFINITION = {
    "schema_version": 2,
    "name": "test-wf",
    "description": "中文描述",
    "inputs": {},
    "state": {},
    "entrypoint": "step_1",
    "nodes": [
        {
            "id": "step_1",
            "type": "action",
            "action": {"kind": "agent", "name": "fault-zeroing", "prompt": "请处理这个故障"},
        }
    ],
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
        session.add(UserModel(id="admin-1", username="admin@test.com", role=UserRole.SUPER_ADMIN, disabled=False))
        await session.commit()

    monkeypatch.setattr(workflows_module, "get_session_factory", lambda: sf)
    monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: sf)
    monkeypatch.setattr("app.gateway.utils.get_session_factory", lambda: sf)

    async def _noop_audit(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(workflows_module, "record_audit", _noop_audit)

    store = WorkflowV2Store(sf)
    await store.save_definition("test-wf", _CHINESE_DEFINITION, "hash", "user-1")

    from app.gateway.utils import ResourceMetadataStore

    await ResourceMetadataStore("workflow").save_meta("test-wf", {"owner_id": "user-1", "visibility": "private", "department_id": None})

    app = FastAPI()
    app.include_router(workflows_router)

    async def _stub_admin():
        return SimpleNamespace(id="admin-1", role=UserRole.SUPER_ADMIN, department_id=None, username="admin@test.com")

    app.dependency_overrides[get_optional_rbac_user] = _stub_admin

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sf=sf, store=store)
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_workflow_yaml_content_preserves_unicode(real_env) -> None:
    response = real_env.client.get("/api/workflows/test-wf")

    assert response.status_code == 200
    body = response.json()
    assert "中文描述" in body["yaml_content"]
    assert "请处理这个故障" in body["yaml_content"]
    assert "\\u4e2d" not in body["yaml_content"]
