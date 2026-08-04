"""Start-up validation: host paths in file_access roots are rejected (400)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers import workflows as workflows_module
from app.gateway.routers.workflows import router as workflows_router
from ideer.workflows.v2 import file_roots

_FAULT_ZEROING = {
    "schema_version": 2,
    "name": "fault-zeroing",
    "description": "test",
    "inputs": {
        "upload_dir": {"type": "string", "required": True},
        "output_base_dir": {"type": "string", "default": "/mnt/user-data/outputs"},
    },
    "state": {},
    "entrypoint": "evidence_collection",
    "nodes": [
        {
            "id": "evidence_collection",
            "type": "action",
            "action": {
                "kind": "agent",
                "name": "fault-zeroing",
                "file_access": {
                    "read": ["{{inputs.upload_dir}}"],
                    "write": ["{{inputs.output_base_dir}}/artifacts/evidence/evidence_table.json"],
                },
            },
        }
    ],
    "edges": [],
}


class StubStore:
    def __init__(self, definition: dict) -> None:
        self.definition = definition
        self.created: list[tuple] = []

    async def get_latest_definition(self, workflow_name: str):
        if workflow_name != "fault-zeroing":
            return None
        return SimpleNamespace(definition=self.definition, version=1)

    async def create_run(self, *args, **kwargs) -> None:
        self.created.append((args, kwargs))


class StubMetaStore:
    async def load_meta(self, workflow_name: str):
        return {"visibility": "private", "owner_id": None, "department_id": None}


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(workflows_router)

    async def _stub_user():
        return SimpleNamespace(id="user-1", role="user", department_id=None, username="u@test.com")

    app.dependency_overrides[get_current_rbac_user] = _stub_user

    store = StubStore(_FAULT_ZEROING)
    monkeypatch.setattr(workflows_module, "_v2_store", lambda: store)
    monkeypatch.setattr(workflows_module, "_workflow_store", StubMetaStore())
    monkeypatch.setattr(workflows_module, "check_resource_access", lambda *args: True)

    async def _noop_audit(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(workflows_module, "record_audit", _noop_audit)
    monkeypatch.setattr(
        workflows_module,
        "get_app_config",
        lambda: SimpleNamespace(workflow_runtime=SimpleNamespace(user_concurrency=10, department_concurrency=10)),
    )
    monkeypatch.setattr(file_roots, "_get_custom_mounts", lambda: [])

    with TestClient(app) as test_client:
        test_client.workflow_store = store  # type: ignore[attr-defined]
        yield test_client


def _run(client: TestClient, inputs: dict):
    return client.post("/api/workflows/fault-zeroing/run", json={"inputs": inputs})


def test_host_path_upload_dir_is_rejected_with_400(client: TestClient) -> None:
    response = _run(client, {"upload_dir": "/home/wangyh/case_01", "problem_description": "x"})
    assert response.status_code == 400
    assert "Invalid file_access paths" in response.json()["detail"]
    assert "node 'evidence_collection'" in response.json()["detail"]
    assert client.workflow_store.created == []  # type: ignore[attr-defined]


def test_tmp_path_output_dir_is_rejected_with_400(client: TestClient) -> None:
    response = _run(client, {"upload_dir": "/mnt/user-data/uploads", "output_base_dir": "/tmp/outputs"})
    assert response.status_code == 400


def test_virtual_paths_are_accepted_and_run_created(client: TestClient) -> None:
    response = _run(
        client,
        {
            "upload_dir": "/mnt/user-data/uploads",
            "output_base_dir": "/mnt/user-data/outputs",
            "problem_description": "top event",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert len(client.workflow_store.created) == 1  # type: ignore[attr-defined]
