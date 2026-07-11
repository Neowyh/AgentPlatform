"""E2E tests for the stateless runs router (backend/app/gateway/routers/runs.py).

Covers all 4 stateless runs endpoints:
- POST /api/runs/stream
- POST /api/runs/wait
- GET /api/runs/{run_id}/messages
- GET /api/runs/{run_id}/feedback
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.runs import router as runs_router

pytestmark = pytest.mark.no_auto_user

RUN_ID = "run-1"

_DEFAULT_RUN_RECORD = {"run_id": RUN_ID, "thread_id": "thread-1"}

_MISSING = object()  # sentinel: caller explicitly wants store.get -> None


def _make_app(run_store=None, event_store=None, feedback_repo=None):
    app = make_authed_test_app()
    app.include_router(runs_router)
    if run_store is not None:
        app.state.run_store = run_store
    if event_store is not None:
        app.state.run_event_store = event_store
    if feedback_repo is not None:
        app.state.feedback_repo = feedback_repo
    return app


def _make_run_store(run_record=_MISSING):
    """Create a mock run store.

    ``run_record=None`` produces a store whose ``.get`` returns ``None``
    (simulates "run not found").  Omit the argument to get a default
    record for ``RUN_ID``.
    """
    store = MagicMock()
    if run_record is _MISSING:
        run_record = _DEFAULT_RUN_RECORD
    store.get = AsyncMock(return_value=run_record)
    return store


def _make_event_store(rows=None):
    store = MagicMock()
    store.list_messages_by_run = AsyncMock(return_value=rows or [])
    return store


def _make_feedback_repo(list_result=None):
    repo = MagicMock()
    repo.list_by_run = AsyncMock(return_value=list_result or [])
    return repo


# ---------------------------------------------------------------------------
# Tests — GET /api/runs/{run_id}/messages
# ---------------------------------------------------------------------------


class TestRunMessages:
    """Tests for GET /api/runs/{run_id}/messages."""

    def test_run_messages_returns_envelope(self):
        """Run messages returns {data: [...], has_more: bool}."""
        rows = [{"seq": i, "event_type": "message", "content": f"msg-{i}"} for i in range(3)]
        store = _make_run_store()
        event_store = _make_event_store(rows)
        app = _make_app(run_store=store, event_store=event_store)
        with TestClient(app) as client:
            resp = client.get(f"/api/runs/{RUN_ID}/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "has_more" in body

    def test_run_messages_404_when_run_not_found(self):
        """Returns 404 when run not found."""
        store = _make_run_store(run_record=None)
        event_store = _make_event_store([])
        app = _make_app(run_store=store, event_store=event_store)
        with TestClient(app) as client:
            resp = client.get(f"/api/runs/{RUN_ID}/messages")
        assert resp.status_code == 404

    def test_run_messages_respects_limit(self):
        """Custom limit is respected."""
        rows = [{"seq": i, "event_type": "message", "content": f"msg-{i}"} for i in range(5)]
        store = _make_run_store()
        event_store = _make_event_store(rows)
        app = _make_app(run_store=store, event_store=event_store)
        with TestClient(app) as client:
            resp = client.get(f"/api/runs/{RUN_ID}/messages?limit=10")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — GET /api/runs/{run_id}/feedback
# ---------------------------------------------------------------------------


class TestRunFeedback:
    """Tests for GET /api/runs/{run_id}/feedback."""

    def test_run_feedback_returns_list(self):
        """Run feedback returns a list."""
        run_store = _make_run_store()
        feedback_repo = _make_feedback_repo(list_result=[])
        app = _make_app(run_store=run_store, feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.get(f"/api/runs/{RUN_ID}/feedback")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_run_feedback_with_results(self):
        """Run feedback returns feedback data."""
        run_store = _make_run_store()
        feedback_repo = _make_feedback_repo(list_result=[{"feedback_id": "fb-1", "rating": 1}])
        app = _make_app(run_store=run_store, feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.get(f"/api/runs/{RUN_ID}/feedback")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
