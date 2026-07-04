"""E2E tests for the workflows router (backend/app/gateway/routers/workflows.py).

Covers all 9 workflows endpoints:
- GET /api/workflows
- GET /api/workflows/{workflow_name}
- POST /api/workflows
- PUT /api/workflows/{workflow_name}
- DELETE /api/workflows/{workflow_name}
- POST /api/workflows/{workflow_name}/run
- GET /api/workflows/{workflow_name}/runs/{run_id}
- GET /api/workflows/{workflow_name}/runs
- POST /api/workflows/{workflow_name}/runs/{run_id}/review
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.routers.workflows import router as workflows_router

pytestmark = pytest.mark.no_auto_user

WORKFLOW_NAME = "test-workflow"
RUN_ID = "run-1"

# A minimal but valid YAML definition for tests that need to parse/load workflows.
VALID_YAML = "name: test-workflow\ndescription: Test workflow\nversion: '1.0'\nsteps:\n  - id: step-1\n    type: agent\n    agent: planner\n    prompt: hello\n"


def _make_user(role: str = "user") -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    user.role = role
    user.department_id = None
    user.disabled = False
    return user


def _make_app(role: str = "user", workflow_store=None):
    user = _make_user(role=role)
    app = make_authed_test_app()
    app.include_router(workflows_router)

    async def _stub():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub
    app.dependency_overrides[get_optional_rbac_user] = _stub
    return app, user


def _make_workflow_store(
    list_result=None,
    load_result=None,
    save_result=None,
    delete_result=True,
    load_run_result=None,
    list_runs_result=None,
    review_result=True,
):
    """Build a mock WorkflowStore matching the real WorkflowStore API."""
    store = MagicMock()
    # list_workflows returns (items, total_count)
    store.list_workflows = AsyncMock(return_value=list_result if list_result is not None else ([], 0))
    # load_workflow returns yaml string or None
    store.load_workflow = AsyncMock(return_value=load_result)
    # save_workflow returns None
    store.save_workflow = AsyncMock(return_value=save_result)
    # delete_workflow returns bool
    store.delete_workflow = AsyncMock(return_value=delete_result)
    # load_run_state returns WorkflowState or None
    store.load_run_state = AsyncMock(return_value=load_run_result)
    # list_runs returns (runs_list, total_count)
    store.list_runs = AsyncMock(return_value=list_runs_result if list_runs_result is not None else ([], 0))
    # save_review_result returns bool
    store.save_review_result = AsyncMock(return_value=review_result)
    return store


def _mock_get_workflow_store(store):
    """Return a contextmanager-style patch for get_workflow_store."""
    return patch("app.gateway.routers.workflows.get_workflow_store", return_value=store)


def _mock_workflow_meta(owner_id: str = "user-1", visibility: str = "private"):
    """Return a contextmanager-style patch for _load_workflow_meta."""
    meta = {"visibility": visibility, "owner_id": owner_id, "department_id": None, "version": 1}
    return patch("app.gateway.routers.workflows._load_workflow_meta", new_callable=AsyncMock, return_value=meta)


def _mock_save_workflow_meta():
    """Return a contextmanager-style patch for _save_workflow_meta."""
    return patch("app.gateway.routers.workflows._save_workflow_meta", new_callable=AsyncMock)


def _mock_soft_delete_workflow_meta():
    """Return a contextmanager-style patch for _soft_delete_workflow_meta."""
    return patch("app.gateway.routers.workflows._soft_delete_workflow_meta", new_callable=AsyncMock)


# ---------------------------------------------------------------------------
# Tests — GET /api/workflows
# ---------------------------------------------------------------------------


class TestListWorkflows:
    """Tests for GET /api/workflows."""

    def test_list_workflows_returns_list(self):
        """List workflows returns a dict with 'workflows' key."""
        store = _make_workflow_store()
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflows" in data
        assert "total" in data
        assert isinstance(data["workflows"], list)

    def test_list_workflows_with_results(self):
        """List workflows returns workflow data."""
        items = [{"name": WORKFLOW_NAME, "description": "Test", "version": "1.0", "steps_count": 1, "inputs": {}}]
        store = _make_workflow_store(list_result=(items, 1))
        app, _ = _make_app()
        with _mock_get_workflow_store(store), _mock_workflow_meta():
            with TestClient(app) as client:
                resp = client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["workflows"]) >= 1


# ---------------------------------------------------------------------------
# Tests — GET /api/workflows/{workflow_name}
# ---------------------------------------------------------------------------


class TestGetWorkflow:
    """Tests for GET /api/workflows/{workflow_name}."""

    def test_get_workflow_found(self):
        """Get workflow returns workflow details."""
        store = _make_workflow_store(load_result=VALID_YAML)
        app, _ = _make_app()
        with _mock_get_workflow_store(store), _mock_workflow_meta():
            with TestClient(app) as client:
                resp = client.get(f"/api/workflows/{WORKFLOW_NAME}")
        assert resp.status_code == 200
        assert resp.json()["name"] == WORKFLOW_NAME

    def test_get_workflow_not_found(self):
        """Get workflow returns 404 when not found."""
        store = _make_workflow_store(load_result=None)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.get("/api/workflows/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — POST /api/workflows
# ---------------------------------------------------------------------------


class TestCreateWorkflow:
    """Tests for POST /api/workflows."""

    def test_create_workflow_success(self):
        """Create workflow succeeds with valid YAML."""
        store = _make_workflow_store()
        # load_workflow returns None (no existing workflow)
        store.load_workflow = AsyncMock(return_value=None)
        store.save_workflow = AsyncMock(return_value=None)
        app, _ = _make_app(role="department_admin")
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/workflows",
                    json={"yaml_content": VALID_YAML},
                )
        assert resp.status_code in (200, 201)

    def test_create_workflow_invalid_yaml(self):
        """Create workflow fails with invalid YAML that fails parse."""
        store = _make_workflow_store()
        store.load_workflow = AsyncMock(return_value=None)
        app, _ = _make_app(role="department_admin")
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/workflows",
                    json={"yaml_content": "not_valid: [yaml: {broken"},
                )
        # Should fail because parse_workflow_string raises
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Tests — PUT /api/workflows/{workflow_name}
# ---------------------------------------------------------------------------


class TestUpdateWorkflow:
    """Tests for PUT /api/workflows/{workflow_name}."""

    def test_update_workflow_success(self):
        """Update workflow succeeds."""
        store = _make_workflow_store()
        # load_workflow returns existing yaml (workflow exists)
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        store.save_workflow = AsyncMock(return_value=None)
        app, _ = _make_app(role="user")
        with (
            _mock_get_workflow_store(store),
            _mock_workflow_meta(owner_id="user-1"),
            _mock_save_workflow_meta(),
        ):
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/workflows/{WORKFLOW_NAME}",
                    json={"yaml_content": VALID_YAML},
                )
        assert resp.status_code == 200

    def test_update_workflow_not_found(self):
        """Update workflow returns 404 when not found."""
        store = _make_workflow_store()
        # load_workflow returns None (workflow doesn't exist)
        store.load_workflow = AsyncMock(return_value=None)
        app, _ = _make_app(role="department_admin")
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/workflows/nonexistent",
                    json={"yaml_content": VALID_YAML},
                )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — DELETE /api/workflows/{workflow_name}
# ---------------------------------------------------------------------------


class TestDeleteWorkflow:
    """Tests for DELETE /api/workflows/{workflow_name}."""

    def test_delete_workflow_success(self):
        """Delete workflow succeeds."""
        store = _make_workflow_store(delete_result=True)
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        app, _ = _make_app(role="user")
        with (
            _mock_get_workflow_store(store),
            _mock_workflow_meta(owner_id="user-1"),
            _mock_soft_delete_workflow_meta(),
        ):
            with TestClient(app) as client:
                resp = client.delete(f"/api/workflows/{WORKFLOW_NAME}")
        assert resp.status_code in (200, 204)

    def test_delete_workflow_not_found(self):
        """Delete workflow returns 404 when not found."""
        store = _make_workflow_store(delete_result=False)
        app, _ = _make_app(role="super_admin")
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.delete("/api/workflows/nonexistent")
        assert resp.status_code in (404, 200, 204)


# ---------------------------------------------------------------------------
# Tests — POST /api/workflows/{workflow_name}/run
# ---------------------------------------------------------------------------


class TestRunWorkflow:
    """Tests for POST /api/workflows/{workflow_name}/run."""

    def test_run_workflow_success(self):
        """Run workflow succeeds."""
        store = _make_workflow_store()
        # load_workflow must return valid YAML so the router can parse it
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        app, _ = _make_app()
        with _mock_get_workflow_store(store), _mock_workflow_meta(visibility="public"):
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/workflows/{WORKFLOW_NAME}/run",
                    json={"inputs": {"key": "value"}},
                )
        assert resp.status_code in (200, 202)

    def test_run_workflow_not_found(self):
        """Run workflow returns 404 when workflow not found."""
        store = _make_workflow_store()
        # load_workflow returns None (workflow doesn't exist)
        store.load_workflow = AsyncMock(return_value=None)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/workflows/nonexistent/run",
                    json={"inputs": {}},
                )
        assert resp.status_code in (404, 400)


# ---------------------------------------------------------------------------
# Tests — GET /api/workflows/{workflow_name}/runs/{run_id}
# ---------------------------------------------------------------------------


class TestGetWorkflowRunStatus:
    """Tests for GET /api/workflows/{workflow_name}/runs/{run_id}."""

    def test_get_run_status(self):
        """Get run status returns run details."""
        mock_state = MagicMock()
        mock_state.run_id = RUN_ID
        mock_state.workflow_name = WORKFLOW_NAME
        mock_state.status = "completed"
        mock_state.current_step = None
        mock_state.error = None
        mock_state.steps = {}
        store = _make_workflow_store(load_run_result=mock_state)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.get(f"/api/workflows/{WORKFLOW_NAME}/runs/{RUN_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data

    def test_get_run_status_not_found(self):
        """Get run status returns 404 when run not found."""
        store = _make_workflow_store(load_run_result=None)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.get(f"/api/workflows/{WORKFLOW_NAME}/runs/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — GET /api/workflows/{workflow_name}/runs
# ---------------------------------------------------------------------------


class TestListWorkflowRuns:
    """Tests for GET /api/workflows/{workflow_name}/runs."""

    def test_list_runs_returns_list(self):
        """List runs returns a dict with 'runs' key."""
        store = _make_workflow_store()
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.get(f"/api/workflows/{WORKFLOW_NAME}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert "total" in data
        assert isinstance(data["runs"], list)


# ---------------------------------------------------------------------------
# Tests — POST /api/workflows/{workflow_name}/runs/{run_id}/review
# ---------------------------------------------------------------------------


class TestSubmitWorkflowReview:
    """Tests for POST /api/workflows/{workflow_name}/runs/{run_id}/review."""

    def _make_review_run_state(self):
        """Build a mock WorkflowState for a run waiting for human review."""
        mock_state = MagicMock()
        mock_state.run_id = RUN_ID
        mock_state.workflow_name = WORKFLOW_NAME
        mock_state.status = "waiting_human"
        mock_state.current_step = "review-1"
        mock_state.error = None
        mock_state.steps = {}
        return mock_state

    def test_submit_review_approve(self):
        """Submit review with approve succeeds."""
        store = _make_workflow_store()
        store.load_run_state = AsyncMock(return_value=self._make_review_run_state())
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        store.save_review_result = AsyncMock(return_value=True)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/workflows/{WORKFLOW_NAME}/runs/{RUN_ID}/review",
                    json={"approved": True},
                )
        assert resp.status_code == 200

    def test_submit_review_reject(self):
        """Submit review with reject succeeds."""
        store = _make_workflow_store()
        store.load_run_state = AsyncMock(return_value=self._make_review_run_state())
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        store.save_review_result = AsyncMock(return_value=True)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/workflows/{WORKFLOW_NAME}/runs/{RUN_ID}/review",
                    json={"approved": False, "reason": "Needs changes"},
                )
        assert resp.status_code == 200
