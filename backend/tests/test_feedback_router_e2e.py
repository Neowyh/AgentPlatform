"""E2E tests for the feedback router (backend/app/gateway/routers/feedback.py).

Covers all 6 feedback endpoints:
- POST /api/threads/{thread_id}/runs/{run_id}/feedback
- PUT /api/threads/{thread_id}/runs/{run_id}/feedback
- GET /api/threads/{thread_id}/runs/{run_id}/feedback
- GET /api/threads/{thread_id}/runs/{run_id}/feedback/stats
- DELETE /api/threads/{thread_id}/runs/{run_id}/feedback
- DELETE /api/threads/{thread_id}/runs/{run_id}/feedback/{feedback_id}
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.feedback import router as feedback_router

pytestmark = pytest.mark.no_auto_user

THREAD_ID = "thread-1"
RUN_ID = "run-1"


def _make_run_store():
    """Return a mock run_store that recognises RUN_ID."""
    store = MagicMock()
    store.get = AsyncMock(return_value={"run_id": RUN_ID, "thread_id": THREAD_ID})
    return store


def _make_app(feedback_repo=None, run_store=None):
    app = make_authed_test_app()
    app.include_router(feedback_router)
    if feedback_repo is not None:
        app.state.feedback_repo = feedback_repo
    if run_store is None:
        run_store = _make_run_store()
    app.state.run_store = run_store
    return app


def _make_feedback_repo(
    create_result=None,
    list_result=None,
    stats_result=None,
    get_result=None,
    delete_result=True,
    delete_by_run_result=True,
):
    repo = MagicMock()
    repo.create = AsyncMock(return_value=create_result or {"feedback_id": "fb-1", "rating": 1, "run_id": RUN_ID, "thread_id": THREAD_ID})
    repo.upsert = AsyncMock(return_value=create_result or {"feedback_id": "fb-1", "rating": 1, "run_id": RUN_ID, "thread_id": THREAD_ID})
    repo.list_by_run = AsyncMock(return_value=list_result or [])
    repo.aggregate_by_run = AsyncMock(return_value=stats_result or {"run_id": RUN_ID, "positive": 0, "negative": 0, "total": 0})
    repo.get = AsyncMock(return_value=get_result)
    repo.delete = AsyncMock(return_value=delete_result)
    repo.delete_by_run = AsyncMock(return_value=delete_by_run_result)
    return repo


# ---------------------------------------------------------------------------
# Tests — POST (create feedback)
# ---------------------------------------------------------------------------


class TestCreateFeedback:
    """Tests for POST /api/threads/{thread_id}/runs/{run_id}/feedback."""

    def test_create_feedback_success(self):
        """Create feedback succeeds with valid data."""
        repo = _make_feedback_repo()
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 1, "comment": "Good"},
            )
        assert resp.status_code in (200, 201)

    def test_create_feedback_negative_rating(self):
        """Create feedback with negative rating succeeds."""
        repo = _make_feedback_repo(create_result={"feedback_id": "fb-2", "rating": -1, "run_id": RUN_ID, "thread_id": THREAD_ID})
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": -1, "comment": "Bad"},
            )
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Tests — PUT (upsert feedback)
# ---------------------------------------------------------------------------


class TestUpsertFeedback:
    """Tests for PUT /api/threads/{thread_id}/runs/{run_id}/feedback."""

    def test_upsert_feedback_success(self):
        """Upsert feedback succeeds."""
        repo = _make_feedback_repo()
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.put(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 1},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — GET (list feedback)
# ---------------------------------------------------------------------------


class TestListFeedback:
    """Tests for GET /api/threads/{thread_id}/runs/{run_id}/feedback."""

    def test_list_feedback_returns_list(self):
        """List feedback returns a list."""
        repo = _make_feedback_repo(list_result=[])
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_feedback_with_results(self):
        """List feedback returns feedback data."""
        item = {"feedback_id": "fb-1", "run_id": RUN_ID, "thread_id": THREAD_ID, "rating": 1}
        repo = _make_feedback_repo(list_result=[item])
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["feedback_id"] == "fb-1"


# ---------------------------------------------------------------------------
# Tests — GET /feedback/stats
# ---------------------------------------------------------------------------


class TestFeedbackStats:
    """Tests for GET /api/threads/{thread_id}/runs/{run_id}/feedback/stats."""

    def test_feedback_stats_returns_counts(self):
        """Feedback stats returns positive/negative counts."""
        repo = _make_feedback_repo(stats_result={"run_id": RUN_ID, "positive": 5, "negative": 2, "total": 7})
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["positive"] == 5
        assert data["negative"] == 2
        assert data["total"] == 7


# ---------------------------------------------------------------------------
# Tests — DELETE (delete feedback)
# ---------------------------------------------------------------------------


class TestDeleteFeedback:
    """Tests for DELETE feedback endpoints."""

    def test_delete_run_feedback_success(self):
        """Delete current user's feedback succeeds."""
        repo = _make_feedback_repo(delete_by_run_result=True)
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback")
        assert resp.status_code == 200
        assert resp.json() == {"success": True}

    def test_delete_specific_feedback_success(self):
        """Delete specific feedback by ID succeeds."""
        existing = {"feedback_id": "fb-1", "thread_id": THREAD_ID, "run_id": RUN_ID}
        repo = _make_feedback_repo(get_result=existing, delete_result=True)
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback/fb-1")
        assert resp.status_code == 200
        assert resp.json() == {"success": True}

    def test_delete_feedback_not_found(self):
        """Delete feedback returns 404 when not found."""
        repo = _make_feedback_repo(get_result=None, delete_result=False)
        app = _make_app(feedback_repo=repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback/nonexistent")
        assert resp.status_code == 404
