"""Tests for the workflows router (backend/app/gateway/routers/workflows.py).

Covers all 9 workflows endpoints:
- GET /api/workflows — list all workflows
- GET /api/workflows/{workflow_name} — get workflow details
- POST /api/workflows — create workflow from YAML
- PUT /api/workflows/{workflow_name} — update workflow YAML
- DELETE /api/workflows/{workflow_name} — delete a workflow
- POST /api/workflows/{workflow_name}/run — start workflow execution
- GET /api/workflows/{workflow_name}/runs/{run_id} — get run status
- GET /api/workflows/{workflow_name}/runs — list run history
- POST /api/workflows/{workflow_name}/runs/{run_id}/review — submit human review
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.workflows import router as workflows_router

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
    return app, user


def _make_workflow_store(**kwargs):
    """Build a mock WorkflowStore matching the real WorkflowStore API.

    The real store methods are: list_workflows, load_workflow, save_workflow,
    delete_workflow, load_run_state, list_runs, save_review_result, etc.
    """
    store = MagicMock()
    # list_workflows returns (items, total_count)
    store.list_workflows = AsyncMock(return_value=kwargs.get("list_result", ([], 0)))
    # load_workflow returns yaml string or None
    store.load_workflow = AsyncMock(return_value=kwargs.get("load_result"))
    # save_workflow returns None
    store.save_workflow = AsyncMock(return_value=kwargs.get("save_result", None))
    # delete_workflow returns bool
    store.delete_workflow = AsyncMock(return_value=kwargs.get("delete_result", True))
    # load_run_state returns WorkflowState or None
    store.load_run_state = AsyncMock(return_value=kwargs.get("load_run_result"))
    # list_runs returns (runs_list, total_count)
    store.list_runs = AsyncMock(return_value=kwargs.get("list_runs_result", ([], 0)))
    # save_review_result returns bool
    store.save_review_result = AsyncMock(return_value=kwargs.get("review_result", True))
    return store


def _mock_get_workflow_store(store):
    """Return a contextmanager-style patch for get_workflow_store."""
    return patch("app.gateway.routers.workflows.get_workflow_store", return_value=store)


# ---------------------------------------------------------------------------
# Tests — List Workflows
# ---------------------------------------------------------------------------


class TestListWorkflows:
    """Tests for GET /api/workflows."""

    def test_list_returns_list(self):
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


# ---------------------------------------------------------------------------
# Tests — Get Workflow
# ---------------------------------------------------------------------------


class TestGetWorkflow:
    """Tests for GET /api/workflows/{workflow_name}."""

    def test_get_workflow_found(self):
        """Get workflow returns workflow details."""
        store = _make_workflow_store(load_result=VALID_YAML)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.get(f"/api/workflows/{WORKFLOW_NAME}")
        assert resp.status_code == 200

    def test_get_workflow_not_found(self):
        """Get workflow returns 404 when not found."""
        store = _make_workflow_store(load_result=None)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.get("/api/workflows/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Create Workflow
# ---------------------------------------------------------------------------


class TestCreateWorkflow:
    """Tests for POST /api/workflows."""

    def test_create_success(self):
        """Create workflow succeeds with valid YAML."""
        store = _make_workflow_store()
        # save_workflow succeeds (returns None), load_workflow returns None (no existing)
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


# ---------------------------------------------------------------------------
# Tests — Update Workflow
# ---------------------------------------------------------------------------


class TestUpdateWorkflow:
    """Tests for PUT /api/workflows/{workflow_name}."""

    def test_update_success(self):
        """Update workflow succeeds."""
        store = _make_workflow_store()
        # load_workflow returns existing yaml (workflow exists)
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        store.save_workflow = AsyncMock(return_value=None)
        app, _ = _make_app(role="department_admin")
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/workflows/{WORKFLOW_NAME}",
                    json={"yaml_content": VALID_YAML},
                )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — Delete Workflow
# ---------------------------------------------------------------------------


class TestDeleteWorkflow:
    """Tests for DELETE /api/workflows/{workflow_name}."""

    def test_delete_success(self):
        """Delete workflow succeeds."""
        store = _make_workflow_store(delete_result=True)
        app, _ = _make_app(role="super_admin")
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.delete(f"/api/workflows/{WORKFLOW_NAME}")
        assert resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Tests — Run Workflow
# ---------------------------------------------------------------------------


class TestRunWorkflow:
    """Tests for POST /api/workflows/{workflow_name}/run."""

    def test_run_success(self):
        """Run workflow succeeds."""
        store = _make_workflow_store()
        # load_workflow must return valid YAML so the router can parse it
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        app, _ = _make_app()
        with _mock_get_workflow_store(store):
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/workflows/{WORKFLOW_NAME}/run",
                    json={"inputs": {}},
                )
        assert resp.status_code in (200, 202)


# ---------------------------------------------------------------------------
# Tests — Get Run Status
# ---------------------------------------------------------------------------


class TestGetRunStatus:
    """Tests for GET /api/workflows/{workflow_name}/runs/{run_id}."""

    def test_get_run_status(self):
        """Get run status returns run details."""
        # Build a mock WorkflowState object
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


# ---------------------------------------------------------------------------
# Tests — List Runs
# ---------------------------------------------------------------------------


class TestListRuns:
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
# Tests — Submit Review
# ---------------------------------------------------------------------------


class TestSubmitReview:
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
        # load_run_state returns a waiting run
        store.load_run_state = AsyncMock(return_value=self._make_review_run_state())
        # load_workflow returns yaml (for approver check)
        store.load_workflow = AsyncMock(return_value=VALID_YAML)
        # save_review_result succeeds
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
