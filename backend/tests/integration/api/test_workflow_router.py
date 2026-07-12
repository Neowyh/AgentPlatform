"""Tests for the workflows API router.

Covers:
- GET /api/workflows — list workflows
- GET /api/workflows/{name} — get workflow details
- POST /api/workflows — create workflow (validates YAML, checks duplicates)
- PUT /api/workflows/{name} — update workflow (validates YAML, name match)
- DELETE /api/workflows/{name} — delete workflow
- POST /api/workflows/{name}/run — start execution (input validation, defaults)
- GET /api/workflows/{name}/runs/{run_id} — get run status
- GET /api/workflows/{name}/runs — list runs
- POST /api/workflows/{name}/runs/{run_id}/review — submit review
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.harness.ideer.workflows.state import RunStatus, WorkflowState

# ── Helpers ──────────────────────────────────────────────────────────


def _make_app():
    """Create a FastAPI app with the workflows router."""
    from app.gateway.routers.workflows import router

    app = FastAPI()
    app.include_router(router)
    return app


def _mock_user(role: str = "super_admin"):
    """Build a mock UserModel."""
    from ideer.persistence.models.user import UserRole

    role_map = {
        "user": UserRole.USER,
        "department_admin": UserRole.DEPARTMENT_ADMIN,
        "super_admin": UserRole.SUPER_ADMIN,
    }
    return SimpleNamespace(
        id="test-user",
        email="test@example.com",
        role=role_map.get(role, UserRole.SUPER_ADMIN),
        department_id="dept-1",
    )


def _make_state(
    workflow_name: str = "test-wf",
    run_id: str = "run-001",
    status: RunStatus = RunStatus.RUNNING,
) -> WorkflowState:
    state = WorkflowState(workflow_name=workflow_name, run_id=run_id, inputs={"q": "test"})
    state.status = status
    state.set_step_result("s1", status="completed", output="ok")
    return state


SAMPLE_YAML = """\
name: test-wf
description: A test workflow
version: "1.0"
inputs:
  query:
    type: string
    required: true
steps:
  - id: s1
    type: tool
    tool: search
    params:
      q: "{{inputs.query}}"
"""


def _owner_meta(owner_id: str = "test-user"):
    """Return a metadata dict where the given user is owner."""
    return {"visibility": "private", "owner_id": owner_id, "department_id": "dept-1", "version": 1}


def _patch_meta(meta=None):
    """Context manager that patches _workflow_store.load_meta."""
    if meta is None:
        meta = _owner_meta()
    return patch("app.gateway.routers.workflows._workflow_store.load_meta", new_callable=AsyncMock, return_value=meta)


def _patch_save_meta():
    """Context manager that patches _workflow_store.save_meta (no-op)."""
    return patch("app.gateway.routers.workflows._workflow_store.save_meta", new_callable=AsyncMock)


def _patch_metadata_delete():
    """Context manager that patches hard deletion of workflow metadata."""
    return patch("app.gateway.routers.workflows._workflow_store.delete", new_callable=AsyncMock)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def app():
    return _make_app()


@pytest.fixture()
def client(app):
    """TestClient with auth dependency override (super_admin by default)."""
    from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user

    user = _mock_user("super_admin")

    async def _override():
        return user

    app.dependency_overrides[get_current_rbac_user] = _override
    app.dependency_overrides[get_optional_rbac_user] = _override
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _set_user(app, role: str = "super_admin"):
    """Change the auth override to a user with the given role."""
    from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user

    user = _mock_user(role)

    async def _override():
        return user

    app.dependency_overrides[get_current_rbac_user] = _override
    app.dependency_overrides[get_optional_rbac_user] = _override


# ── GET /api/workflows ───────────────────────────────────────────────


class TestListWorkflows:
    def test_list_workflows_success(self, client):
        mock_store = AsyncMock()
        mock_store.list_workflows = AsyncMock(return_value=([{"name": "wf1", "description": "desc", "version": "1.0", "steps_count": 1, "inputs": {}}], 1))

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.get("/api/workflows")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["workflows"]) == 1

    def test_list_workflows_empty(self, client):
        mock_store = AsyncMock()
        mock_store.list_workflows = AsyncMock(return_value=([], 0))

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.get("/api/workflows")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ── GET /api/workflows/{name} ────────────────────────────────────────


class TestGetWorkflow:
    def test_get_workflow_success(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.get("/api/workflows/test-wf")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-wf"
        assert data["description"] == "A test workflow"
        assert "yaml_content" in data

    def test_get_workflow_not_found(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=None)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.get("/api/workflows/nonexistent")

        assert resp.status_code == 404

    def test_get_workflow_invalid_yaml(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value="invalid: [yaml: broken")

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.get("/api/workflows/bad-wf")

        assert resp.status_code == 400


# ── POST /api/workflows ──────────────────────────────────────────────


class TestCreateWorkflow:
    def test_create_workflow_success(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=None)
        mock_store.save_workflow = AsyncMock()

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post("/api/workflows", json={"yaml_content": SAMPLE_YAML})

        assert resp.status_code == 200
        assert resp.json()["name"] == "test-wf"

    def test_create_workflow_duplicate_raises_409(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post("/api/workflows", json={"yaml_content": SAMPLE_YAML})

        assert resp.status_code == 409

    def test_create_workflow_invalid_yaml_raises_400(self, client):
        resp = client.post("/api/workflows", json={"yaml_content": "invalid: [yaml: broken"})
        assert resp.status_code == 400


# ── PUT /api/workflows/{name} ────────────────────────────────────────


class TestUpdateWorkflow:
    def test_update_workflow_success(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)
        mock_store.save_workflow = AsyncMock()

        with (
            patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store),
            _patch_meta(),
            _patch_save_meta(),
        ):
            resp = client.put("/api/workflows/test-wf", json={"yaml_content": SAMPLE_YAML, "version": 1})

        assert resp.status_code == 200

    def test_update_workflow_not_found(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=None)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.put("/api/workflows/nonexistent", json={"yaml_content": SAMPLE_YAML, "version": 1})

        assert resp.status_code == 404

    def test_update_workflow_name_mismatch(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.put("/api/workflows/other-wf", json={"yaml_content": SAMPLE_YAML, "version": 1})

        assert resp.status_code == 400
        assert "does not match" in resp.json()["detail"]

    def test_update_workflow_invalid_yaml(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.put("/api/workflows/test-wf", json={"yaml_content": "bad: [yaml", "version": 1})

        assert resp.status_code == 400


# ── DELETE /api/workflows/{name} ─────────────────────────────────────


class TestDeleteWorkflow:
    def test_delete_workflow_success(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)
        mock_store.delete_workflow = AsyncMock(return_value=True)

        with (
            patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store),
            _patch_meta(),
            _patch_metadata_delete(),
        ):
            resp = client.delete("/api/workflows/test-wf")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_workflow_not_found(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=None)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.delete("/api/workflows/nonexistent")

        assert resp.status_code == 404


# ── POST /api/workflows/{name}/run ───────────────────────────────────


class TestRunWorkflow:
    def test_run_workflow_success(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)
        mock_store.save_run_state = AsyncMock()

        with (
            patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store),
            _patch_meta(),
            patch("app.gateway.routers.workflows.WorkflowExecutor") as mock_executor_cls,
        ):
            mock_executor = AsyncMock()
            mock_executor.run = AsyncMock(return_value=_make_state())
            mock_executor_cls.return_value = mock_executor

            resp = client.post("/api/workflows/test-wf/run", json={"inputs": {"query": "test"}})

        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] == "running"

    def test_run_workflow_not_found(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=None)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post("/api/workflows/nonexistent/run", json={"inputs": {}})

        assert resp.status_code == 404

    def test_run_workflow_missing_required_input(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.post("/api/workflows/test-wf/run", json={"inputs": {}})

        assert resp.status_code == 400
        assert "Missing required input" in resp.json()["detail"]

    def test_run_workflow_type_mismatch_boolean(self, client):
        mock_store = AsyncMock()
        yaml_with_bool = """\
name: bool-wf
inputs:
  flag:
    type: boolean
steps:
  - id: s1
    type: tool
    tool: echo
"""
        mock_store.load_workflow = AsyncMock(return_value=yaml_with_bool)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.post("/api/workflows/bool-wf/run", json={"inputs": {"flag": "not_bool"}})

        assert resp.status_code == 400
        assert "boolean" in resp.json()["detail"]

    def test_run_workflow_type_mismatch_number(self, client):
        mock_store = AsyncMock()
        yaml_with_num = """\
name: num-wf
inputs:
  count:
    type: number
steps:
  - id: s1
    type: tool
    tool: echo
"""
        mock_store.load_workflow = AsyncMock(return_value=yaml_with_num)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.post("/api/workflows/num-wf/run", json={"inputs": {"count": "not_number"}})

        assert resp.status_code == 400
        assert "number" in resp.json()["detail"]

    def test_run_workflow_type_mismatch_string(self, client):
        mock_store = AsyncMock()
        mock_store.load_workflow = AsyncMock(return_value=SAMPLE_YAML)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.post("/api/workflows/test-wf/run", json={"inputs": {"query": 123}})

        assert resp.status_code == 400
        assert "string" in resp.json()["detail"]

    def test_run_workflow_applies_defaults(self, client):
        mock_store = AsyncMock()
        yaml_with_default = """\
name: default-wf
inputs:
  query:
    type: string
    default: "hello"
steps:
  - id: s1
    type: tool
    tool: echo
"""
        mock_store.load_workflow = AsyncMock(return_value=yaml_with_default)
        mock_store.save_run_state = AsyncMock()

        with (
            patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store),
            _patch_meta(),
            patch("app.gateway.routers.workflows.WorkflowExecutor") as mock_executor_cls,
        ):
            mock_executor = AsyncMock()
            mock_executor.run = AsyncMock(return_value=_make_state())
            mock_executor_cls.return_value = mock_executor

            resp = client.post("/api/workflows/default-wf/run", json={"inputs": {}})

        assert resp.status_code == 200


# ── GET /api/workflows/{name}/runs/{run_id} ──────────────────────────


class TestGetRunStatus:
    def test_get_run_status_success(self, client):
        state = _make_state()
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=state)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.get("/api/workflows/test-wf/runs/run-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run-001"
        assert data["status"] == "running"

    def test_get_run_status_not_found(self, client):
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=None)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.get("/api/workflows/test-wf/runs/nonexistent")

        assert resp.status_code == 404

    def test_get_run_status_wrong_workflow(self, client):
        state = _make_state(workflow_name="other-wf")
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=state)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.get("/api/workflows/test-wf/runs/run-001")

        assert resp.status_code == 404


# ── GET /api/workflows/{name}/runs ───────────────────────────────────


class TestListRuns:
    def test_list_runs_success(self, client):
        mock_store = AsyncMock()
        mock_store.list_runs = AsyncMock(return_value=([{"run_id": "run-001", "workflow": "test-wf", "status": "completed", "current_step": "s1", "error": None, "created_at": "2026-01-01T00:00:00"}], 1))

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.get("/api/workflows/test-wf/runs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["runs"]) == 1

    def test_list_runs_with_pagination(self, client):
        mock_store = AsyncMock()
        mock_store.list_runs = AsyncMock(return_value=([], 0))

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store), _patch_meta():
            resp = client.get("/api/workflows/test-wf/runs?limit=10&offset=5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 5


# ── POST /api/workflows/{name}/runs/{run_id}/review ──────────────────


class TestSubmitReview:
    def test_submit_review_success(self, client):
        state = _make_state(status=RunStatus.WAITING_HUMAN)
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=state)
        mock_store.save_review_result = AsyncMock(return_value=True)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post(
                "/api/workflows/test-wf/runs/run-001/review",
                json={"approved": True, "data": {"comment": "LGTM"}},
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_submit_review_not_found(self, client):
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=None)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post(
                "/api/workflows/test-wf/runs/nonexistent/review",
                json={"approved": True},
            )

        assert resp.status_code == 404

    def test_submit_review_wrong_workflow(self, client):
        state = _make_state(workflow_name="other-wf")
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=state)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post(
                "/api/workflows/test-wf/runs/run-001/review",
                json={"approved": True},
            )

        assert resp.status_code == 404

    def test_submit_review_not_waiting(self, client):
        state = _make_state(status=RunStatus.RUNNING)
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=state)
        mock_store.save_review_result = AsyncMock(return_value=False)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post(
                "/api/workflows/test-wf/runs/run-001/review",
                json={"approved": True},
            )

        assert resp.status_code == 409

    def test_submit_review_strips_approved_from_data(self, client):
        """The 'approved' key in body.data should be stripped to prevent overwrite."""
        state = _make_state(status=RunStatus.WAITING_HUMAN)
        mock_store = AsyncMock()
        mock_store.load_run_state = AsyncMock(return_value=state)

        captured_payload = None

        async def capture_save(run_id, payload):
            nonlocal captured_payload
            captured_payload = payload
            return True

        mock_store.save_review_result = AsyncMock(side_effect=capture_save)

        with patch("app.gateway.routers.workflows.get_workflow_store", return_value=mock_store):
            resp = client.post(
                "/api/workflows/test-wf/runs/run-001/review",
                json={"approved": True, "data": {"approved": False, "comment": "hack"}},
            )

        assert resp.status_code == 200
        assert captured_payload["approved"] is True
        assert "comment" in captured_payload
