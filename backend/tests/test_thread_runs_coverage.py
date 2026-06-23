"""Additional coverage tests for thread_runs router.

Targets specific uncovered lines:
- Lines 181-184: wait_run CancelledError path (record.task raises CancelledError)
- Lines 191-193: wait_run checkpoint_tuple found (returns serialized channel values)
- Lines 250-251: cancel_run wait path CancelledError
- Lines 268-269: join_run happy path (non-store_only run found, returns StreamingResponse)
- Line 307: stream_existing_run cancel failure (cancel returns False)
- Lines 311-312: stream_existing_run wait path with task exception
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.gateway.routers import thread_runs
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
    for key, val in state_attrs.items():
        setattr(app.state, key, val)
    return app


# ---------------------------------------------------------------------------
# Lines 181-184: wait_run when record.task raises CancelledError
# ---------------------------------------------------------------------------


class TestWaitRunCancelledError:
    """Cover the CancelledError branch in wait_run (lines 181-184)."""

    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    @patch("app.gateway.routers.thread_runs.get_checkpointer")
    def test_wait_run_task_cancelled_returns_status(self, mock_get_cp, mock_get_rm, mock_start_run):
        """When the background task is cancelled, wait_run catches CancelledError and returns status."""

        async def _raising_task():
            raise asyncio.CancelledError()

        record = _make_run_record(status=RunStatus.running)
        record.task = _raising_task()
        mock_start_run.return_value = record
        mock_get_rm.return_value = MagicMock()

        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=None)
        mock_get_cp.return_value = checkpointer

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs/wait", json={})

        assert response.status_code == 200
        assert response.json()["status"] == "running"


# ---------------------------------------------------------------------------
# Lines 191-193: wait_run when checkpoint_tuple exists and returns channel values
# ---------------------------------------------------------------------------


class TestWaitRunCheckpointFound:
    """Cover the checkpoint_tuple found branch in wait_run (lines 191-193)."""

    @patch("app.gateway.routers.thread_runs.serialize_channel_values")
    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    @patch("app.gateway.routers.thread_runs.get_checkpointer")
    def test_wait_run_with_checkpoint_returns_serialized_values(self, mock_get_cp, mock_get_rm, mock_start_run, mock_serialize):
        """When a checkpoint exists, wait_run returns serialized channel values."""
        record = _make_run_record(status=RunStatus.success)
        record.task = None
        mock_start_run.return_value = record
        mock_get_rm.return_value = MagicMock()

        checkpoint_tuple = MagicMock()
        checkpoint_tuple.checkpoint = {"channel_values": {"messages": [{"role": "user", "content": "hi"}]}}
        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_cp.return_value = checkpointer

        mock_serialize.return_value = {"messages": [{"role": "user", "content": "hi"}]}

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs/wait", json={})

        assert response.status_code == 200
        mock_serialize.assert_called_once()
        body = response.json()
        assert body["messages"][0]["content"] == "hi"

    @patch("app.gateway.routers.thread_runs.serialize_channel_values")
    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    @patch("app.gateway.routers.thread_runs.get_checkpointer")
    def test_wait_run_checkpoint_empty_channel_values(self, mock_get_cp, mock_get_rm, mock_start_run, mock_serialize):
        """When checkpoint exists but has no channel_values, returns empty dict."""
        record = _make_run_record(status=RunStatus.success)
        record.task = None
        mock_start_run.return_value = record
        mock_get_rm.return_value = MagicMock()

        checkpoint_tuple = MagicMock()
        checkpoint_tuple.checkpoint = {}
        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_cp.return_value = checkpointer

        mock_serialize.return_value = {}

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs/wait", json={})

        assert response.status_code == 200
        mock_serialize.assert_called_once_with({})

    @patch("app.gateway.routers.thread_runs.serialize_channel_values")
    @patch("app.gateway.routers.thread_runs.start_run")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    @patch("app.gateway.routers.thread_runs.get_checkpointer")
    def test_wait_run_checkpoint_none_attribute(self, mock_get_cp, mock_get_rm, mock_start_run, mock_serialize):
        """When getattr returns None, falls back to empty dict for channel_values."""
        record = _make_run_record(status=RunStatus.success)
        record.task = None
        mock_start_run.return_value = record
        mock_get_rm.return_value = MagicMock()

        checkpoint_tuple = MagicMock(spec=[])  # no 'checkpoint' attr
        checkpointer = MagicMock()
        checkpointer.aget_tuple = AsyncMock(return_value=checkpoint_tuple)
        mock_get_cp.return_value = checkpointer

        mock_serialize.return_value = {}

        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/threads/thread-1/runs/wait", json={})

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Lines 250-251: cancel_run wait path CancelledError
# ---------------------------------------------------------------------------


class TestCancelRunWaitCancelled:
    """Cover the CancelledError branch in cancel_run wait path (lines 250-251)."""

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_cancel_run_wait_task_cancelled_returns_204(self, mock_get_rm):
        """When wait=True and the task raises CancelledError, returns 204."""

        async def _raising_task():
            raise asyncio.CancelledError()

        record = _make_run_record(status=RunStatus.running)
        record.task = _raising_task()

        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=True)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/threads/thread-1/runs/run-1/cancel",
            params={"wait": True, "action": "interrupt"},
        )

        assert response.status_code == 204
        rm.cancel.assert_awaited_once_with("run-1", action="interrupt")

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_cancel_run_wait_task_completes_returns_204(self, mock_get_rm):
        """When wait=True and the task completes normally, returns 204."""

        async def _ok_task():
            return None

        record = _make_run_record(status=RunStatus.running)
        record.task = _ok_task()

        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=True)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/threads/thread-1/runs/run-1/cancel",
            params={"wait": True, "action": "interrupt"},
        )

        assert response.status_code == 204


# ---------------------------------------------------------------------------
# Lines 268-269: join_run happy path (non-store_only run returns StreamingResponse)
# ---------------------------------------------------------------------------


class TestJoinRunHappyPath:
    """Cover the join_run StreamingResponse path (lines 268-269)."""

    @patch("app.gateway.routers.thread_runs.sse_consumer")
    @patch("app.gateway.routers.thread_runs.get_stream_bridge")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_join_run_non_store_only_returns_sse(self, mock_get_rm, mock_get_bridge, mock_sse):
        """When run is found and not store_only, returns StreamingResponse with SSE."""
        record = _make_run_record("run-1", "thread-1", store_only=False)
        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        mock_get_rm.return_value = rm
        mock_get_bridge.return_value = MagicMock()
        mock_sse.return_value = iter([b"data: test\n\n"])

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/run-1/join")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestJoinRunStoreOnly:
    """Cover the join_run store_only 409 error path."""

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_join_run_store_only_returns_409(self, mock_get_rm):
        """When run is store_only, returns 409."""
        record = _make_run_record("run-1", "thread-1", store_only=True)
        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/threads/thread-1/runs/run-1/join")

        assert response.status_code == 409
        assert "not active on this worker" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Line 307: stream_existing_run cancel failure (cancel returns False)
# ---------------------------------------------------------------------------


class TestStreamExistingRunCancelFailure:
    """Cover the cancel failure branch in stream_existing_run (line 307)."""

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_cancel_fails_returns_409(self, mock_get_rm):
        """When action is provided but cancel returns False, returns 409."""
        record = _make_run_record("run-1", "thread-1", status=RunStatus.success)
        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=False)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/threads/thread-1/runs/run-1/stream",
            params={"action": "interrupt"},
        )

        assert response.status_code == 409
        assert "not cancellable" in response.json()["detail"] or "not active" in response.json()["detail"]

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_cancel_fails_running_status(self, mock_get_rm):
        """When cancel fails on a running run, 409 says 'not active on this worker'."""
        record = _make_run_record("run-1", "thread-1", status=RunStatus.running)
        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=False)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/threads/thread-1/runs/run-1/stream",
            params={"action": "interrupt"},
        )

        assert response.status_code == 409
        assert "not active on this worker" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Lines 311-312: stream_existing_run wait path with task exception
# ---------------------------------------------------------------------------


class TestStreamExistingRunWaitWithException:
    """Cover the exception catch in stream_existing_run wait path (lines 311-312)."""

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_wait_task_raises_exception_returns_204(self, mock_get_rm):
        """When wait=1 and the task raises a generic exception, returns 204."""

        async def _raising_task():
            raise RuntimeError("task failed")

        record = _make_run_record("run-1", "thread-1")
        record.task = _raising_task()

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

        assert response.status_code == 204

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_wait_task_cancelled_returns_204(self, mock_get_rm):
        """When wait=1 and the task raises CancelledError, returns 204."""

        async def _raising_task():
            raise asyncio.CancelledError()

        record = _make_run_record("run-1", "thread-1")
        record.task = _raising_task()

        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=True)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/threads/thread-1/runs/run-1/stream",
            params={"action": "rollback", "wait": 1},
        )

        assert response.status_code == 204

    @patch("app.gateway.routers.thread_runs.sse_consumer")
    @patch("app.gateway.routers.thread_runs.get_stream_bridge")
    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_stream_existing_run_wait_task_completes_returns_204(self, mock_get_rm, mock_get_bridge, mock_sse):
        """When wait=1 and the task completes normally, returns 204."""

        async def _ok_task():
            return None

        record = _make_run_record("run-1", "thread-1")
        record.task = _ok_task()

        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=True)
        mock_get_rm.return_value = rm
        mock_get_bridge.return_value = MagicMock()
        mock_sse.return_value = iter([b"data: test\n\n"])

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/threads/thread-1/runs/run-1/stream",
            params={"action": "interrupt", "wait": 1},
        )

        assert response.status_code == 204


# ---------------------------------------------------------------------------
# Additional: stream_existing_run store_only with action (skip store_only check)
# ---------------------------------------------------------------------------


class TestStreamExistingRunWithStoreOnlyAndAction:
    """When store_only=True but action is provided, store_only check is skipped."""

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_store_only_with_action_cancels(self, mock_get_rm):
        """store_only check is bypassed when action is provided."""
        record = _make_run_record("run-1", "thread-1", store_only=True, status=RunStatus.success)

        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        rm.cancel = AsyncMock(return_value=False)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        # Cancel fails, so we get 409 from the cancel path, not from store_only
        response = client.post(
            "/api/threads/thread-1/runs/run-1/stream",
            params={"action": "rollback"},
        )

        assert response.status_code == 409
        # The error is from cancel failure, not store_only
        rm.cancel.assert_awaited_once_with("run-1", action="rollback")

    @patch("app.gateway.routers.thread_runs.get_run_manager")
    def test_store_only_without_action_returns_409(self, mock_get_rm):
        """store_only without action returns 409 (existing store_only path)."""
        record = _make_run_record("run-1", "thread-1", store_only=True)

        rm = MagicMock()
        rm.get = AsyncMock(return_value=record)
        mock_get_rm.return_value = rm

        app = _make_app()
        client = TestClient(app)
        # GET without action triggers store_only check
        response = client.get("/api/threads/thread-1/runs/run-1/stream")

        assert response.status_code == 409
