"""Start-up validation: host paths in file_access roots are rejected (400)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers import workflows as workflows_module
from app.gateway.routers.workflows import router as workflows_router
from ideer.config.paths import Paths
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
        self.runs: dict[str, SimpleNamespace] = {}

    async def get_latest_definition(self, workflow_name: str):
        if workflow_name != "fault-zeroing":
            return None
        return SimpleNamespace(definition=self.definition, version=1)

    async def get_definition(self, workflow_name: str, version: int):
        if workflow_name != "fault-zeroing":
            return None
        return SimpleNamespace(definition=self.definition, version=1)

    async def create_run(self, *args, **kwargs) -> None:
        self.created.append((args, kwargs))

    async def get_run(self, run_id: str):
        return self.runs.get(run_id)


class StubMetaStore:
    async def load_meta(self, workflow_name: str):
        return {"visibility": "private", "owner_id": None, "department_id": None}


@pytest.fixture
def client(monkeypatch, tmp_path):
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
    monkeypatch.setattr(file_roots, "get_paths", lambda: Paths(str(tmp_path / "base")))

    with TestClient(app) as test_client:
        test_client.workflow_store = store  # type: ignore[attr-defined]
        yield test_client


def _make_run(run_id: str = "run-1", created_by: str = "user-1") -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_id,
        workflow_name="fault-zeroing",
        status="completed",
        definition_version=1,
        created_by=created_by,
        snapshot={"state": {"attempt": 1}, "outputs": {}},
        inputs={"upload_dir": "/mnt/user-data/uploads", "output_base_dir": "/mnt/user-data/outputs"},
        error=None,
    )


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


def _register_run(client: TestClient, run: SimpleNamespace) -> None:
    client.workflow_store.runs[run.run_id] = run  # type: ignore[attr-defined]


def _artifact_path(client: TestClient, run_id: str) -> str:
    return str(file_roots.get_paths().sandbox_outputs_dir(run_id, user_id="user-1") / "artifacts/evidence/evidence_table.json")


def test_list_run_artifacts_returns_files_with_virtual_paths(client: TestClient) -> None:
    run = _make_run()
    _register_run(client, run)
    artifact = _artifact_path(client, run.run_id)
    Path(artifact).parent.mkdir(parents=True, exist_ok=True)
    Path(artifact).write_text('{"fault": "x"}', encoding="utf-8")

    response = client.get(f"/api/workflows/fault-zeroing/runs/{run.run_id}/artifacts")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run-1"
    assert [item["path"] for item in body["artifacts"]] == ["/mnt/user-data/outputs/artifacts/evidence/evidence_table.json"]


def test_list_run_artifacts_is_404_for_unowned_run(client: TestClient) -> None:
    _register_run(client, _make_run(created_by="user-2"))
    response = client.get("/api/workflows/fault-zeroing/runs/run-1/artifacts")
    assert response.status_code == 404


def test_list_run_artifacts_is_404_for_unknown_run(client: TestClient) -> None:
    response = client.get("/api/workflows/fault-zeroing/runs/nope/artifacts")
    assert response.status_code == 404


def test_get_run_artifact_content_downloads_file(client: TestClient) -> None:
    run = _make_run()
    _register_run(client, run)
    artifact = _artifact_path(client, run.run_id)
    Path(artifact).parent.mkdir(parents=True, exist_ok=True)
    Path(artifact).write_text('{"fault": "x"}', encoding="utf-8")

    response = client.get(
        f"/api/workflows/fault-zeroing/runs/{run.run_id}/artifacts/content",
        params={"path": "/mnt/user-data/outputs/artifacts/evidence/evidence_table.json"},
    )
    assert response.status_code == 200
    assert response.text == '{"fault": "x"}'


def test_get_run_artifact_content_is_404_for_unknown_path(client: TestClient) -> None:
    _register_run(client, _make_run())
    response = client.get(
        "/api/workflows/fault-zeroing/runs/run-1/artifacts/content",
        params={"path": "/mnt/user-data/outputs/nope.json"},
    )
    assert response.status_code == 404
