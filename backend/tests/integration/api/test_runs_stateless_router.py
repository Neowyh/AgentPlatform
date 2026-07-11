"""Tests for the stateless runs router (backend/app/gateway/routers/runs.py).

Covers:
- _resolve_thread_id: with and without config.configurable.thread_id
- POST /api/runs/stream: stateless stream
- POST /api/runs/wait: stateless wait with checkpointer
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.gateway.routers.runs import _resolve_thread_id
from app.gateway.routers.runs import router as runs_router
from app.gateway.routers.thread_runs import RunCreateRequest
from ideer.runtime import RunRecord, RunStatus

# ---------------------------------------------------------------------------
# _resolve_thread_id unit tests
# ---------------------------------------------------------------------------


class TestResolveThreadId:
    """Tests for _resolve_thread_id helper."""

    def test_returns_thread_id_from_config(self):
        """Returns thread_id from config.configurable.thread_id when present."""
        body = RunCreateRequest(
            config={"configurable": {"thread_id": "existing-thread-123"}},
        )
        result = _resolve_thread_id(body)
        assert result == "existing-thread-123"

    def test_generates_uuid_when_no_thread_id(self):
        """Generates a UUID when config.configurable.thread_id is absent."""
        body = RunCreateRequest()
        result = _resolve_thread_id(body)
        # Validate it's a valid UUID
        uuid.UUID(result)
        assert isinstance(result, str)

    def test_generates_uuid_when_config_is_none(self):
        """Generates a UUID when config is None."""
        body = RunCreateRequest(config=None)
        result = _resolve_thread_id(body)
        uuid.UUID(result)

    def test_generates_uuid_when_configurable_missing(self):
        """Generates a UUID when config has no configurable key."""
        body = RunCreateRequest(config={"other_key": "value"})
        result = _resolve_thread_id(body)
        uuid.UUID(result)

    def test_generates_uuid_when_thread_id_is_none(self):
        """Generates a UUID when thread_id is explicitly None."""
        body = RunCreateRequest(
            config={"configurable": {"thread_id": None}},
        )
        result = _resolve_thread_id(body)
        uuid.UUID(result)


# ---------------------------------------------------------------------------
# Integration-style tests for stateless endpoints
# ---------------------------------------------------------------------------


def _make_run_record(
    run_id: str = "run-1",
    thread_id: str = "thread-1",
    status: RunStatus = RunStatus.running,
) -> MagicMock:
    """Create a mock RunRecord."""
    record = MagicMock(spec=RunRecord)
    record.run_id = run_id
    record.thread_id = thread_id
    record.status = status
    record.error = None
    record.task = None
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
    record.store_only = False
    return record


def _make_test_app(
    *,
    run_manager=None,
    stream_bridge=None,
    checkpointer=None,
    start_run_fn=None,
    sse_consumer_fn=None,
):
    """Build a test FastAPI app for the stateless runs router."""
    from _router_auth_helpers import make_authed_test_app

    app = make_authed_test_app()
    app.include_router(runs_router)

    if run_manager is not None:
        app.state.run_manager = run_manager
    if stream_bridge is not None:
        app.state.stream_bridge = stream_bridge
    if checkpointer is not None:
        app.state.checkpointer = checkpointer

    return app


class TestStatelessStream:
    """Tests for POST /api/runs/stream."""

    @patch("app.gateway.routers.runs.sse_consumer")
    @patch("app.gateway.routers.runs.start_run")
    @patch("app.gateway.routers.runs.get_stream_bridge")
    @patch("app.gateway.routers.runs.get_run_manager")
    def test_stateless_stream_returns_sse(self, mock_get_rm, mock_get_bridge, mock_start_run, mock_sse):
        """Stateless stream returns a StreamingResponse with SSE headers."""
        record = _make_run_record()
        mock_start_run.return_value = record
        mock_get_rm.return_value = MagicMock()
        mock_get_bridge.return_value = MagicMock()
        mock_sse.return_value = iter([b"data: test\n\n"])

        app = _make_test_app()
        client = TestClient(app)
        response = client.post("/api/runs/stream", json={})

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        # Content-Location should contain the run id
        cl = response.headers.get("content-location", "")
        assert "run-1" in cl


class TestStatelessWait:
    """Tests for POST /api/runs/wait."""

    @patch("app.gateway.routers.runs.start_run")
    @patch("app.gateway.routers.runs.get_run_manager")
    @patch("app.gateway.routers.runs.get_checkpointer")
    def test_stateless_wait_returns_status_on_no_checkpoint(self, mock_get_cp, mock_get_rm, mock_start_run):
        """Returns status when checkpointer has no tuple."""
        record = _make_run_record(status=RunStatus.success)
        mock_start_run.return_value = record

        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=None)
        mock_get_cp.return_value = checkpointer
        mock_get_rm.return_value = MagicMock()

        app = _make_test_app()
        client = TestClient(app)
        response = client.post("/api/runs/wait", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"

    @patch("app.gateway.routers.runs.start_run")
    @patch("app.gateway.routers.runs.get_run_manager")
    @patch("app.gateway.routers.runs.get_checkpointer")
    @patch("app.gateway.routers.runs.serialize_channel_values")
    def test_stateless_wait_returns_checkpoint_values(self, mock_serialize, mock_get_cp, mock_get_rm, mock_start_run):
        """Returns serialized channel values when checkpoint is available."""
        record = _make_run_record(status=RunStatus.success)
        mock_start_run.return_value = record
        mock_serialize.return_value = {"messages": ["hello"]}

        checkpoint_tuple = MagicMock()
        checkpoint_tuple.checkpoint = {"channel_values": {"messages": ["hello"]}}
        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_cp.return_value = checkpointer
        mock_get_rm.return_value = MagicMock()

        app = _make_test_app()
        client = TestClient(app)
        response = client.post("/api/runs/wait", json={})

        assert response.status_code == 200
        assert response.json() == {"messages": ["hello"]}

    @patch("app.gateway.routers.runs.start_run")
    @patch("app.gateway.routers.runs.get_run_manager")
    @patch("app.gateway.routers.runs.get_checkpointer")
    def test_stateless_wait_handles_checkpointer_exception(self, mock_get_cp, mock_get_rm, mock_start_run):
        """Returns status when checkpointer raises an exception."""
        record = _make_run_record(status=RunStatus.error)
        record.error = "something went wrong"
        mock_start_run.return_value = record

        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(side_effect=Exception("DB connection lost"))
        mock_get_cp.return_value = checkpointer
        mock_get_rm.return_value = MagicMock()

        app = _make_test_app()
        client = TestClient(app)
        response = client.post("/api/runs/wait", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "error"
        assert body["error"] == "something went wrong"

    @patch("app.gateway.routers.runs.start_run")
    @patch("app.gateway.routers.runs.get_run_manager")
    @patch("app.gateway.routers.runs.get_checkpointer")
    def test_stateless_wait_with_thread_id(self, mock_get_cp, mock_get_rm, mock_start_run):
        """Passes thread_id from config to start_run."""
        record = _make_run_record(thread_id="custom-thread")
        mock_start_run.return_value = record

        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=None)
        mock_get_cp.return_value = checkpointer
        mock_get_rm.return_value = MagicMock()

        app = _make_test_app()
        client = TestClient(app)
        response = client.post(
            "/api/runs/wait",
            json={"config": {"configurable": {"thread_id": "custom-thread"}}},
        )

        assert response.status_code == 200
        # Verify start_run was called with the correct thread_id
        call_args = mock_start_run.call_args
        assert call_args[0][1] == "custom-thread"
