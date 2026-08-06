"""Run record download endpoint (feat: refactor/workflow-run-record).

Covers the HTTP contract of ``GET /api/workflows/{workflow}/runs/{run}/record``:

- ``format`` is restricted to ``jsonl`` or ``md`` (400 otherwise)
- unknown runs and runs owned by another user are 404
- a run with no persisted record is 404
- a persisted record downloads with the correct media type and filename
"""

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
from ideer.workflows.v2.file_roots import make_host_resolver, workflow_record_path


class StubStore:
    def __init__(self) -> None:
        self.runs: dict[str, SimpleNamespace] = {}

    async def get_run(self, run_id: str):
        return self.runs.get(run_id)


class StubMetaStore:
    async def load_meta(self, workflow_name: str):
        return {"visibility": "private", "owner_id": None, "department_id": None}


def _make_run(run_id: str = "run-1", created_by: str = "user-1") -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_id,
        workflow_name="fault-zeroing",
        status="completed",
        definition_version=1,
        created_by=created_by,
        snapshot={},
        inputs={},
        error=None,
        checkpoint_thread_id=f"wf-{run_id}",
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(workflows_router)

    async def _stub_user():
        return SimpleNamespace(id="user-1", role="user", department_id=None, username="u@test.com")

    app.dependency_overrides[get_current_rbac_user] = _stub_user

    store = StubStore()
    monkeypatch.setattr(workflows_module, "_v2_store", lambda: store)
    monkeypatch.setattr(workflows_module, "_workflow_store", StubMetaStore())
    monkeypatch.setattr(workflows_module, "check_resource_access", lambda *args: True)
    monkeypatch.setattr(file_roots, "get_paths", lambda: Paths(str(tmp_path / "base")))
    monkeypatch.setattr(file_roots, "_get_custom_mounts", lambda: [])

    with TestClient(app) as test_client:
        test_client.workflow_store = store  # type: ignore[attr-defined]
        yield test_client


def _record_host(run_id: str, created_by: str, ext: str) -> Path:
    host = make_host_resolver(run_id, created_by)(workflow_record_path(ext))
    assert host is not None, "record virtual path must resolve under the workspace"
    path = Path(host)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _record_url(run_id: str = "run-1", format: str = "jsonl") -> str:
    return f"/api/workflows/fault-zeroing/runs/{run_id}/record?format={format}"


def test_record_download_rejects_unknown_format(client: TestClient) -> None:
    _register_run(client)
    response = client.get(_record_url(format="pdf"))
    assert response.status_code == 400
    assert "format must be 'jsonl' or 'md'" in response.json()["detail"]


def test_record_download_is_404_for_unknown_run(client: TestClient) -> None:
    response = client.get(_record_url(run_id="nope"))
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_record_download_is_404_for_unowned_run(client: TestClient) -> None:
    _register_run(client, _make_run(created_by="user-2"))
    response = client.get(_record_url())
    assert response.status_code == 404


def test_record_download_is_404_when_record_not_persisted(client: TestClient) -> None:
    _register_run(client)
    response = client.get(_record_url())
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


def test_record_download_jsonl_returns_ndjson(client: TestClient, tmp_path: Path) -> None:
    _register_run(client)
    body = '{"seq":1,"type":"run_started","payload":{},"created_at":null}\n'
    _record_host("run-1", "user-1", "jsonl").write_text(body, encoding="utf-8")

    response = client.get(_record_url())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"
    assert response.headers["content-disposition"] == 'attachment; filename="run_run-1.jsonl"'
    assert response.text == body


def test_record_download_md_returns_markdown(client: TestClient) -> None:
    _register_run(client)
    _record_host("run-1", "user-1", "md").write_text("# 运行记录 `run-1`\n", encoding="utf-8")

    response = client.get(_record_url(format="md"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers["content-disposition"] == 'attachment; filename="run_run-1.md"'
    assert response.text == "# 运行记录 `run-1`\n"


def _register_run(client: TestClient, run: SimpleNamespace | None = None) -> None:
    client.workflow_store.runs[run.run_id if run else "run-1"] = run or _make_run()  # type: ignore[attr-defined]
