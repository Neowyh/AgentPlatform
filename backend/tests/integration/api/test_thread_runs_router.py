"""Tests for thread_runs router (backend/app/gateway/routers/thread_runs.py).

Covers gaps not addressed by existing test files:
- create_run (POST /api/threads/{thread_id}/runs)
- stream_run (POST /api/threads/{thread_id}/runs/stream)
- wait_run (POST /api/threads/{thread_id}/runs/wait)
- list_runs (GET /api/threads/{thread_id}/runs)
- get_run not found on thread mismatch
- join_run not found
- stream_existing_run with action + wait
- list_run_events
- list_thread_messages with feedback attachment
- _cancel_conflict_detail
- _record_to_response
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.gateway.routers import thread_runs
from app.gateway.routers.thread_runs import (
    RunResponse,
    _cancel_conflict_detail,
    _record_to_response,
    _response_with_message_summary,
)
from ideer.runtime import RunRecord, RunStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_record(
    run_id: str = "run-1",
    thread_id: str = "thread-1",
    status: RunStatus = RunStatus.running,
    task=None,
    store_only: bool = False,
) -> MagicMock:
    """Create a mock RunRecord."""
    record = MagicMock(spec=RunRecord)
    record.run_id = run_id
    record.thread_id = thread_id
    record.status = status
    record.error = None
    record.task = task
    record.assistant_id = "lead_agent"
    record.metadata = {}
    record.kwargs = {}
    record.multitask_strategy = "reject"
    record.created_at = "2026-01-01T00:00:00Z"
    record.updated_at = "2026-01-01T00:00:00Z"
    record.total_input_tokens = 0
    record.total_output_tokens = 0
    record.total_tokens = 0
    record.llm_call_count = 0
    record.lead_agent_tokens = 0
    record.subagent_tokens = 0
    record.middleware_tokens = 0
    record.message_count = 0
    record.store_only = store_only
    return record


def _make_app(**state_attrs):
    """Build a test app with stub auth and optional state attributes."""
    from _router_auth_helpers import make_authed_test_app

    app = make_authed_test_app()
    app.include_router(thread_runs.router)
    event_store = MagicMock()
    event_store.list_messages_by_run = AsyncMock(return_value=[])
    app.state.run_event_store = event_store
    for key, val in state_attrs.items():
        setattr(app.state, key, val)
    return app


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestCancelConflictDetail:
    """Tests for _cancel_conflict_detail helper."""

    def test_pending_run_returns_not_active_message(self):
        """Pending runs get 'not active on this worker' detail."""
        record = _make_run_record(status=RunStatus.pending)
        detail = _cancel_conflict_detail("run-1", record)
        assert "not active on this worker" in detail

    def test_running_run_returns_not_active_message(self):
        """Running runs get 'not active on this worker' detail."""
        record = _make_run_record(status=RunStatus.running)
        detail = _cancel_conflict_detail("run-1", record)
        assert "not active on this worker" in detail

    def test_success_run_returns_not_cancellable_message(self):
        """Successful runs get 'not cancellable' detail."""
        record = _make_run_record(status=RunStatus.success)
        detail = _cancel_conflict_detail("run-1", record)
        assert "not cancellable" in detail
        assert "success" in detail


class TestRunResponseSummary:
    def test_uses_persisted_first_user_and_last_assistant_messages(self):
        store = MagicMock()
        store.list_messages_by_run = AsyncMock(
            return_value=[
                {"event_type": "human_message", "content": {"content": "  plan  a  trip "}},
                {"event_type": "ai_message", "content": {"content": "First response"}},
                {"event_type": "ai_message", "content": {"content": "Final response"}},
            ]
        )

        response = asyncio.run(_response_with_message_summary(_make_run_record(), store))

        assert response.first_user_message == "plan a trip"
        assert response.last_assistant_message == "Final response"

    def test_error_run_returns_not_cancellable_message(self):
        """Error runs get 'not cancellable' detail."""
        record = _make_run_record(status=RunStatus.error)
        detail = _cancel_conflict_detail("run-1", record)
        assert "not cancellable" in detail


class TestRecordToResponse:
    """Tests for _record_to_response helper."""

    def test_maps_all_fields(self):
        """Response maps all RunRecord fields correctly."""
        record = _make_run_record()
        record.assistant_id = "custom-agent"
        record.total_input_tokens = 100
        record.total_output_tokens = 50
        record.total_tokens = 150

        resp = _record_to_response(record)
        assert isinstance(resp, RunResponse)
        assert resp.run_id == "run-1"
        assert resp.thread_id == "thread-1"
        assert resp.assistant_id == "custom-agent"
        assert resp.status == "running"
        assert resp.total_input_tokens == 100
        assert resp.total_output_tokens == 50
        assert resp.total_tokens == 150


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestCreateRun:
    """Tests for POST /api/threads/{thread_id}/runs."""

    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_create_run_returns_run_response(self, mock_get_rm, mock_start_run):
        """Creating a run returns a RunResponse with status 200."""
        record = _make_run_record()
        mock_start_run.return_value = record
        mock_get_rm.return_value = MagicMock()

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == "run-1"
        assert body["thread_id"] == "thread-1"
        assert body["status"] == "running"


class TestStreamRun:
    """Tests for POST /api/threads/{thread_id}/runs/stream."""

    @patch("app.gateway.routers.thread_runs.sse_consumer")
    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_stream_bridge")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_run_returns_sse(self, mock_get_rm, mock_get_bridge, mock_start_run, mock_sse):
        """Stream run returns StreamingResponse with Content-Location header."""
        record = _make_run_record()
        mock_start_run.return_value = record
        mock_get_rm.return_value = MagicMock()
        mock_get_bridge.return_value = MagicMock()
        mock_sse.return_value = iter([b"data: test\n\n"])

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs/stream", json={})

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        cl = response.headers.get("content-location", "")
        assert "run-1" in cl
        assert "thread-1" in cl


class TestWaitRun:
    """Tests for POST /api/threads/{thread_id}/runs/wait."""

    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    @patch("app.gateway.routers.thread_runs.get_checkpointer")
    def test_wait_run_returns_status_on_no_checkpoint(self, mock_get_cp, mock_get_rm, mock_start_run):
        """Returns status/error when checkpointer has no tuple."""
        record = _make_run_record(status=RunStatus.success)
        mock_start_run.return_value = record
        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=None)
        mock_get_cp.return_value = checkpointer
        mock_get_rm.return_value = MagicMock()

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs/wait", json={})

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    @patch("app.gateway.routers.thread_runs.get_checkpointer")
    def test_wait_run_handles_checkpointer_exception(self, mock_get_cp, mock_get_rm, mock_start_run):
        """Gracefully handles checkpointer exceptions."""
        record = _make_run_record(status=RunStatus.error)
        record.error = "boom"
        mock_start_run.return_value = record
        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(side_effect=Exception("DB error"))
        mock_get_cp.return_value = checkpointer
        mock_get_rm.return_value = MagicMock()

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs/wait", json={})

        assert response.status_code == 200
        assert response.json()["status"] == "error"
        assert response.json()["error"] == "boom"


class TestListRuns:
    """Tests for GET /api/threads/{thread_id}/runs."""

    @patch("app.gateway.routers.thread_runs.get_current_user")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_list_runs_returns_list(self, mock_get_rm, mock_get_user):
        """List runs returns a list of RunResponse objects."""
        mock_get_user.return_value = "user-1"
        rm = MagicMock()
        rm.list_by_thread = AsyncMock(
            return_value=[
                _make_run_record("run-1", "thread-1"),
                _make_run_record("run-2", "thread-1"),
            ]
        )
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs")

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 2
        assert body[0]["run_id"] == "run-1"

    @patch("app.gateway.routers.thread_runs.get_current_user")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_list_runs_empty(self, mock_get_rm, mock_get_user):
        """List runs returns empty list when no runs exist."""
        mock_get_user.return_value = "user-1"
        rm = MagicMock()
        rm.list_by_thread = AsyncMock(return_value=[])
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs")

        assert response.status_code == 200
        assert response.json() == []


class TestGetRun:
    """Tests for GET /api/threads/{thread_id}/runs/{run_id}."""

    @patch("app.gateway.routers.thread_runs.get_current_user")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_get_run_thread_mismatch_returns_404(self, mock_get_rm, mock_get_user):
        """Returns 404 when run exists but belongs to a different thread."""
        mock_get_user.return_value = "user-1"
        rm = MagicMock()
        rm.get = AsyncMock(return_value=_make_run_record("run-1", "other-thread"))
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/run-1")

        assert response.status_code == 404


class TestJoinRun:
    """Tests for GET /api/threads/{thread_id}/runs/{run_id}/join."""

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_join_run_not_found_returns_404(self, mock_get_rm):
        """Returns 404 when run doesn't exist."""
        rm = MagicMock()
        rm.get = AsyncMock(return_value=None)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/nonexistent/join")

        assert response.status_code == 404

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_join_run_thread_mismatch_returns_404(self, mock_get_rm):
        """Returns 404 when run belongs to a different thread."""
        rm = MagicMock()
        rm.get = AsyncMock(return_value=_make_run_record("run-1", "other-thread"))
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/run-1/join")

        assert response.status_code == 404


class TestStreamExistingRun:
    """Tests for POST /api/threads/{thread_id}/runs/{run_id}/stream."""

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_not_found(self, mock_get_rm):
        """Returns 404 when run doesn't exist."""
        rm = MagicMock()
        rm.get = AsyncMock(return_value=None)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/nonexistent/stream")

        assert response.status_code == 404

    @patch("app.gateway.routers.thread_runs.sse_consumer")
    @patch("app.gateway.routers.thread_runs.get_stream_bridge")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_get_returns_sse(self, mock_get_rm, mock_get_bridge, mock_sse):
        """GET on stream endpoint returns SSE when run exists and is active."""
        rm = MagicMock()
        rm.get = AsyncMock(return_value=_make_run_record("run-1", "thread-1"))
        mock_get_rm.return_value = rm
        mock_get_bridge.return_value = MagicMock()
        mock_sse.return_value = iter([b"data: test\n\n"])

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/run-1/stream")

        assert response.status_code == 200

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_post_with_action_cancel_returns(self, mock_get_rm):
        """POST with action=interrupt cancels the run."""
        record = _make_run_record("run-1", "thread-1")

        async def _noop():
            pass

        record.task = _noop()

        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=True)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/threads/thread-1/runs/run-1/stream",
            params={"action": "interrupt", "wait": 1},
        )
        assert response.status_code in (200, 204)
        rm.cancel.assert_awaited_once_with("run-1", action="interrupt")


class TestListRunEvents:
    """Tests for GET /api/threads/{thread_id}/runs/{run_id}/events."""

    @patch("app.gateway.routers.thread_runs.get_run_event_store")
    def test_list_run_events_returns_list(self, mock_get_es):
        """Returns list of events for a run."""
        es = MagicMock()
        es.list_events = AsyncMock(
            return_value=[
                {"event_type": "on_chat_model_stream", "content": "hello"},
            ]
        )
        mock_get_es.return_value = es

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/run-1/events")

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1

    @patch("app.gateway.routers.thread_runs.get_run_event_store")
    def test_list_run_events_with_filter(self, mock_get_es):
        """event_types query param is split and forwarded."""
        es = MagicMock()
        es.list_events = AsyncMock(return_value=[])
        mock_get_es.return_value = es

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/run-1/events?event_types=on_chat_model_stream,custom")

        assert response.status_code == 200
        es.list_events.assert_awaited_once_with(
            "thread-1",
            "run-1",
            event_types=["on_chat_model_stream", "custom"],
            limit=500,
        )


class TestListThreadMessages:
    """Tests for GET /api/threads/{thread_id}/messages with feedback attachment."""

    @patch("app.gateway.routers.thread_runs.get_current_user")
    @patch("app.gateway.routers.thread_runs.get_feedback_repo")
    @patch("app.gateway.routers.thread_runs.get_run_event_store")
    def test_thread_messages_attach_feedback(self, mock_get_es, mock_get_fb, mock_get_user):
        """Feedback is attached to the last AI message of each run."""
        es = MagicMock()
        es.list_messages = AsyncMock(
            return_value=[
                {"seq": 1, "run_id": "run-1", "event_type": "human_message", "content": "hi"},
                {"seq": 2, "run_id": "run-1", "event_type": "ai_message", "content": "hello"},
                {"seq": 3, "run_id": "run-1", "event_type": "ai_message", "content": "world"},
            ]
        )
        mock_get_es.return_value = es
        mock_get_user.return_value = "user-1"

        fb_repo = MagicMock()
        fb_repo.list_by_thread_grouped = AsyncMock(
            return_value={
                "run-1": {"feedback_id": "fb-1", "rating": 1, "comment": "good"},
            }
        )
        mock_get_fb.return_value = fb_repo

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/messages")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 3
        # The last AI message (index 2) should have feedback
        assert body[2]["feedback"]["feedback_id"] == "fb-1"
        # The first AI message (index 1) should have None feedback
        assert body[1]["feedback"] is None
        # Human message should have None feedback
        assert body[0]["feedback"] is None

    @patch("app.gateway.routers.thread_runs.get_current_user")
    @patch("app.gateway.routers.thread_runs.get_feedback_repo")
    @patch("app.gateway.routers.thread_runs.get_run_event_store")
    def test_thread_messages_no_feedback(self, mock_get_es, mock_get_fb, mock_get_user):
        """Messages without feedback get feedback=None."""
        es = MagicMock()
        es.list_messages = AsyncMock(
            return_value=[
                {"seq": 1, "run_id": "run-1", "event_type": "ai_message", "content": "hello"},
            ]
        )
        mock_get_es.return_value = es
        mock_get_user.return_value = "user-1"

        fb_repo = MagicMock()
        fb_repo.list_by_thread_grouped = AsyncMock(return_value={})
        mock_get_fb.return_value = fb_repo

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/messages")

        assert response.status_code == 200
        body = response.json()
        assert body[0]["feedback"] is None
