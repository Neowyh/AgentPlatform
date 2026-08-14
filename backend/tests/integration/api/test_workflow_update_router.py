"""PUT /api/workflows/{name} optimistic locking uses the definition version.

Regression: the update endpoint validated against resource_metadata.version
while get_workflow returns the definition version, so the two counters drift
(visibility approvals bump metadata only) and every edit returns 409
VERSION_CONFLICT. The lock token must be the latest definition version.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.routers import workflows as workflows_module
from app.gateway.routers.workflows import router as workflows_router
from ideer.persistence.base import Base
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.user import UserModel, UserRole
from ideer.workflows.v2.store import WorkflowV2Store

_DEFINITION = {
    "schema_version": 2,
    "name": "test-wf",
    "description": "original",
    "inputs": {},
    "state": {},
    "entrypoint": "step_1",
    "nodes": [
        {
            "id": "step_1",
            "type": "action",
            "action": {"kind": "agent", "name": "fault-zeroing", "prompt": "handle"},
        }
    ],
    "edges": [],
}


def _updated_yaml() -> str:
    import yaml

    return yaml.safe_dump({**_DEFINITION, "description": "updated"}, sort_keys=False, allow_unicode=True)


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

    await ResourceMetadataStore("workflow").save_meta("test-wf", {"owner_id": "user-1", "visibility": "private", "department_id": None})

    app = FastAPI()
    app.include_router(workflows_router)

    async def _stub_owner():
        return SimpleNamespace(id="user-1", role=UserRole.USER, department_id=None, username="user@test.com")

    app.dependency_overrides[get_optional_rbac_user] = _stub_owner
    app.dependency_overrides[get_current_rbac_user] = _stub_owner

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sf=sf, store=store)
    await engine.dispose()


async def _bump_meta_version(sf) -> None:
    async with sf() as session:
        await session.execute(
            update(ResourceMetadata)
            .values(version=ResourceMetadata.version + 1)
            .where(
                ResourceMetadata.resource_type == "workflow",
                ResourceMetadata.resource_id == "test-wf",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_update_without_version_returns_422(real_env) -> None:
    response = real_env.client.put("/api/workflows/test-wf", json={"yaml_content": _updated_yaml()})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_with_matching_definition_version_succeeds(real_env) -> None:
    # Simulate a visibility approval that bumped metadata version to 2 while
    # the definition is still v1 — the counters have drifted.
    await _bump_meta_version(real_env.sf)

    response = real_env.client.put("/api/workflows/test-wf", json={"yaml_content": _updated_yaml(), "version": 1})

    assert response.status_code == 200
    assert response.json()["version"] == "2"
    latest = await real_env.store.get_latest_definition("test-wf")
    assert latest is not None
    assert latest.version == 2
    assert "updated" in latest.definition["description"]


@pytest.mark.asyncio
async def test_update_with_stale_definition_version_returns_conflict(real_env) -> None:
    response = real_env.client.put("/api/workflows/test-wf", json={"yaml_content": _updated_yaml(), "version": 0})

    assert response.status_code == 409
    assert "冲突" in response.json()["detail"]
