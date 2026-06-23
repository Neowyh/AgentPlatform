"""Tests for feedback router — targeting uncovered lines.

Each test covers exactly one uncovered line in feedback.py.
Uses make_authed_test_app for stub auth and mocks app.state dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.feedback import router as feedback_router

pytestmark = pytest.mark.no_auto_user

THREAD_ID = "thread-abc"
RUN_ID = "run-123"
FEEDBACK_ID = "fb-999"


def _make_app(run_store=None, feedback_repo=None):
    """Build a test app with stubbed auth and mocked state dependencies."""
    app = make_authed_test_app()
    if run_store is None:
        run_store = MagicMock()
    if feedback_repo is None:
        feedback_repo = MagicMock()
    app.state.run_store = run_store
    app.state.feedback_repo = feedback_repo
    app.include_router(feedback_router)
    return app


# ---------------------------------------------------------------------------
# PUT /{thread_id}/runs/{run_id}/feedback — upsert_feedback
# ---------------------------------------------------------------------------


class TestUpsertFeedback:
    """Covers lines 71, 78, 80 in feedback.py."""

    def test_invalid_rating_returns_400(self):
        """Line 71: rating must be +1 or -1."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 0},
            )
        assert resp.status_code == 400
        assert "rating must be +1 or -1" in resp.json()["detail"]

    def test_run_not_found_returns_404(self):
        """Line 78: run is None."""
        run_store = MagicMock()
        run_store.get = AsyncMock(return_value=None)
        app = _make_app(run_store=run_store)
        with TestClient(app) as client:
            resp = client.put(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 1},
            )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_run_wrong_thread_returns_404(self):
        """Line 80: run exists but thread_id does not match."""
        run_store = MagicMock()
        run_store.get = AsyncMock(return_value={"thread_id": "other-thread"})
        app = _make_app(run_store=run_store)
        with TestClient(app) as client:
            resp = client.put(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 1},
            )
        assert resp.status_code == 404
        assert "not found in thread" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# DELETE /{thread_id}/runs/{run_id}/feedback — delete_run_feedback
# ---------------------------------------------------------------------------


class TestDeleteRunFeedback:
    """Covers line 108 in feedback.py."""

    def test_no_feedback_to_delete_returns_404(self):
        """Line 108: delete_by_run returns False."""
        feedback_repo = MagicMock()
        feedback_repo.delete_by_run = AsyncMock(return_value=False)
        app = _make_app(feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback")
        assert resp.status_code == 404
        assert "No feedback found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /{thread_id}/runs/{run_id}/feedback — create_feedback
# ---------------------------------------------------------------------------


class TestCreateFeedback:
    """Covers lines 122, 130, 132 in feedback.py."""

    def test_invalid_rating_returns_400(self):
        """Line 122: rating must be +1 or -1."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 5},
            )
        assert resp.status_code == 400
        assert "rating must be +1 or -1" in resp.json()["detail"]

    def test_run_not_found_returns_404(self):
        """Line 130: run is None."""
        run_store = MagicMock()
        run_store.get = AsyncMock(return_value=None)
        app = _make_app(run_store=run_store)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": -1},
            )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_run_wrong_thread_returns_404(self):
        """Line 132: run exists but thread_id does not match."""
        run_store = MagicMock()
        run_store.get = AsyncMock(return_value={"thread_id": "wrong-thread"})
        app = _make_app(run_store=run_store)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 1},
            )
        assert resp.status_code == 404
        assert "not found in thread" in resp.json()["detail"].lower()

    def test_create_feedback_success(self):
        """Happy path: feedback is created and returned."""
        run_store = MagicMock()
        run_store.get = AsyncMock(return_value={"thread_id": THREAD_ID})
        feedback_repo = MagicMock()
        feedback_repo.create = AsyncMock(
            return_value={
                "feedback_id": FEEDBACK_ID,
                "run_id": RUN_ID,
                "thread_id": THREAD_ID,
                "rating": 1,
                "comment": None,
                "message_id": None,
                "created_at": "2026-01-01T00:00:00Z",
            }
        )
        app = _make_app(run_store=run_store, feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback",
                json={"rating": 1, "comment": "great"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["feedback_id"] == FEEDBACK_ID
        assert data["rating"] == 1


# ---------------------------------------------------------------------------
# DELETE /{thread_id}/runs/{run_id}/feedback/{feedback_id} — delete_feedback
# ---------------------------------------------------------------------------


class TestDeleteFeedback:
    """Covers lines 184, 187 in feedback.py."""

    def test_feedback_not_found_returns_404(self):
        """Line 182/184: existing is None or thread/run mismatch."""
        feedback_repo = MagicMock()
        feedback_repo.get = AsyncMock(return_value=None)
        app = _make_app(feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback/{FEEDBACK_ID}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_feedback_wrong_thread_returns_404(self):
        """Line 184: feedback exists but thread_id/run_id does not match."""
        feedback_repo = MagicMock()
        feedback_repo.get = AsyncMock(
            return_value={
                "feedback_id": FEEDBACK_ID,
                "thread_id": "other-thread",
                "run_id": "other-run",
            }
        )
        app = _make_app(feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback/{FEEDBACK_ID}")
        assert resp.status_code == 404
        assert "not found in run" in resp.json()["detail"].lower()

    def test_delete_fails_after_verification_returns_404(self):
        """Line 187: feedback verified but delete returns False."""
        feedback_repo = MagicMock()
        feedback_repo.get = AsyncMock(
            return_value={
                "feedback_id": FEEDBACK_ID,
                "thread_id": THREAD_ID,
                "run_id": RUN_ID,
            }
        )
        feedback_repo.delete = AsyncMock(return_value=False)
        app = _make_app(feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback/{FEEDBACK_ID}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_success(self):
        """Happy path: feedback verified and deleted."""
        feedback_repo = MagicMock()
        feedback_repo.get = AsyncMock(
            return_value={
                "feedback_id": FEEDBACK_ID,
                "thread_id": THREAD_ID,
                "run_id": RUN_ID,
            }
        )
        feedback_repo.delete = AsyncMock(return_value=True)
        app = _make_app(feedback_repo=feedback_repo)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}/runs/{RUN_ID}/feedback/{FEEDBACK_ID}")
        assert resp.status_code == 200
        assert resp.json() == {"success": True}
