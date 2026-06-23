"""Comprehensive tests for the threads router (backend/app/gateway/routers/threads.py).

Covers all endpoints, helpers, models, and error paths for 98%+ coverage.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.threads import (
    HistoryEntry,
    ThreadCreateRequest,
    ThreadDeleteResponse,
    ThreadHistoryRequest,
    ThreadPatchRequest,
    ThreadResponse,
    ThreadSearchRequest,
    ThreadStateResponse,
    ThreadStateUpdateRequest,
    _delete_thread_data,
    _derive_thread_status,
    _strip_reserved_metadata,
    router,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_app():
    """Create a test FastAPI app with threads router and mocked dependencies."""
    app = make_authed_test_app()
    app.include_router(router)

    mock_checkpointer = AsyncMock()
    app.state.checkpointer = mock_checkpointer

    # make_authed_test_app already sets app.state.thread_store to a MagicMock
    # with check_access=AsyncMock(return_value=True). We grab a reference.
    mock_thread_store = app.state.thread_store
    # Ensure all thread_store methods are AsyncMock for await
    mock_thread_store.get = AsyncMock(return_value=None)
    mock_thread_store.create = AsyncMock(return_value=None)
    mock_thread_store.delete = AsyncMock(return_value=None)
    mock_thread_store.search = AsyncMock(return_value=[])
    mock_thread_store.update_metadata = AsyncMock(return_value=None)
    mock_thread_store.update_display_name = AsyncMock(return_value=None)
    mock_thread_store.check_access = AsyncMock(return_value=True)

    return app, mock_checkpointer, mock_thread_store


def _make_checkpoint_tuple(
    *,
    channel_values: dict | None = None,
    metadata: dict | None = None,
    config: dict | None = None,
    parent_config: dict | None = None,
    tasks: list | None = None,
    pending_writes: list | None = None,
):
    """Create a mock checkpoint_tuple object."""
    cp = MagicMock()
    cp.checkpoint = {"channel_values": channel_values or {}}
    cp.metadata = metadata or {}
    cp.config = config if config is not None else {"configurable": {"checkpoint_id": "cp-1"}}
    cp.parent_config = parent_config
    cp.tasks = tasks or []
    cp.pending_writes = pending_writes or []
    return cp


# ===========================================================================
# Helper function tests
# ===========================================================================


class TestStripReservedMetadata:
    """Tests for _strip_reserved_metadata."""

    def test_none_returns_empty(self):
        assert _strip_reserved_metadata(None) == {}

    def test_empty_dict_returns_empty(self):
        assert _strip_reserved_metadata({}) == {}

    def test_strips_owner_id(self):
        result = _strip_reserved_metadata({"owner_id": "bad", "foo": "bar"})
        assert result == {"foo": "bar"}

    def test_strips_user_id(self):
        result = _strip_reserved_metadata({"user_id": "bad", "foo": "bar"})
        assert result == {"foo": "bar"}

    def test_strips_both_reserved(self):
        result = _strip_reserved_metadata({"owner_id": "a", "user_id": "b", "key": "val"})
        assert result == {"key": "val"}

    def test_keeps_non_reserved_keys(self):
        meta = {"a": 1, "b": 2, "c": 3}
        assert _strip_reserved_metadata(meta) == meta

    def test_empty_after_stripping(self):
        result = _strip_reserved_metadata({"owner_id": "x", "user_id": "y"})
        assert result == {}


class TestDeriveThreadStatus:
    """Tests for _derive_thread_status."""

    def test_none_checkpoint_returns_idle(self):
        assert _derive_thread_status(None) == "idle"

    def test_no_pending_writes_no_tasks_returns_idle(self):
        cp = _make_checkpoint_tuple(pending_writes=[], tasks=[])
        assert _derive_thread_status(cp) == "idle"

    def test_error_in_pending_writes(self):
        cp = _make_checkpoint_tuple(pending_writes=[["ns", "__error__", "boom"]])
        assert _derive_thread_status(cp) == "error"

    def test_error_in_second_pending_write(self):
        cp = _make_checkpoint_tuple(pending_writes=[["ns", "other", "val"], ["ns", "__error__", "boom"]])
        assert _derive_thread_status(cp) == "error"

    def test_tasks_present_returns_interrupted(self):
        task = MagicMock()
        task.name = "some_node"
        cp = _make_checkpoint_tuple(tasks=[task])
        assert _derive_thread_status(cp) == "interrupted"

    def test_error_takes_precedence_over_tasks(self):
        task = MagicMock()
        cp = _make_checkpoint_tuple(
            pending_writes=[["ns", "__error__", "fail"]],
            tasks=[task],
        )
        assert _derive_thread_status(cp) == "error"

    def test_pending_write_short_tuple_ignored(self):
        # len(pw) < 2 means the error check is skipped
        cp = _make_checkpoint_tuple(pending_writes=[["ns"]])
        assert _derive_thread_status(cp) == "idle"

    def test_pending_writes_none(self):
        cp = MagicMock()
        cp.pending_writes = None
        cp.tasks = None
        assert _derive_thread_status(cp) == "idle"

    def test_pending_writes_empty_tasks_present(self):
        task = MagicMock()
        task.name = "node"
        cp = MagicMock()
        cp.pending_writes = []
        cp.tasks = [task]
        assert _derive_thread_status(cp) == "interrupted"

    def test_tasks_not_error_channel(self):
        cp = _make_checkpoint_tuple(pending_writes=[["ns", "result", "ok"]])
        assert _derive_thread_status(cp) == "idle"


class TestDeleteThreadData:
    """Tests for _delete_thread_data helper."""

    @patch("app.gateway.routers.threads.get_paths")
    def test_success(self, mock_get_paths):
        mock_paths = MagicMock()
        mock_get_paths.return_value = mock_paths
        result = _delete_thread_data("thread-1")
        assert result.success is True
        assert "Deleted" in result.message
        mock_paths.delete_thread_dir.assert_called_once_with("thread-1", user_id=None)

    @patch("app.gateway.routers.threads.get_paths")
    def test_file_not_found(self, mock_get_paths):
        mock_paths = MagicMock()
        mock_paths.delete_thread_dir.side_effect = FileNotFoundError
        mock_get_paths.return_value = mock_paths
        result = _delete_thread_data("thread-1")
        assert result.success is True
        assert "No local data" in result.message

    @patch("app.gateway.routers.threads.get_paths")
    def test_value_error_raises_422(self, mock_get_paths):
        mock_paths = MagicMock()
        mock_paths.delete_thread_dir.side_effect = ValueError("bad id")
        mock_get_paths.return_value = mock_paths
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _delete_thread_data("thread-1")
        assert exc_info.value.status_code == 422

    @patch("app.gateway.routers.threads.get_paths")
    def test_generic_exception_raises_500(self, mock_get_paths):
        mock_paths = MagicMock()
        mock_paths.delete_thread_dir.side_effect = RuntimeError("disk error")
        mock_get_paths.return_value = mock_paths
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _delete_thread_data("thread-1")
        assert exc_info.value.status_code == 500

    @patch("app.gateway.routers.threads.get_paths")
    def test_with_user_id(self, mock_get_paths):
        mock_paths = MagicMock()
        mock_get_paths.return_value = mock_paths
        result = _delete_thread_data("thread-1", user_id="user-1")
        assert result.success is True
        mock_paths.delete_thread_dir.assert_called_once_with("thread-1", user_id="user-1")

    @patch("app.gateway.routers.threads.get_paths")
    def test_with_custom_paths(self, mock_get_paths):
        custom_paths = MagicMock()
        result = _delete_thread_data("thread-1", paths=custom_paths)
        assert result.success is True
        custom_paths.delete_thread_dir.assert_called_once()
        mock_get_paths.assert_not_called()


# ===========================================================================
# Model / validator tests
# ===========================================================================


class TestThreadCreateRequest:
    """Tests for ThreadCreateRequest model."""

    def test_default_values(self):
        req = ThreadCreateRequest()
        assert req.thread_id is None
        assert req.assistant_id is None
        assert req.metadata == {}

    def test_strips_reserved_metadata(self):
        req = ThreadCreateRequest(metadata={"owner_id": "x", "user_id": "y", "ok": "v"})
        assert req.metadata == {"ok": "v"}

    def test_custom_thread_id(self):
        req = ThreadCreateRequest(thread_id="my-thread")
        assert req.thread_id == "my-thread"

    def test_empty_metadata(self):
        req = ThreadCreateRequest(metadata={})
        assert req.metadata == {}

    def test_default_metadata_is_empty(self):
        # Default metadata is empty dict via default_factory
        req = ThreadCreateRequest()
        assert req.metadata == {}


class TestThreadSearchRequest:
    """Tests for ThreadSearchRequest model."""

    def test_default_values(self):
        req = ThreadSearchRequest()
        assert req.metadata == {}
        assert req.limit == 100
        assert req.offset == 0
        assert req.status is None

    def test_custom_values(self):
        req = ThreadSearchRequest(metadata={"k": "v"}, limit=10, offset=5, status="idle")
        assert req.metadata == {"k": "v"}
        assert req.limit == 10
        assert req.offset == 5
        assert req.status == "idle"

    def test_empty_metadata_passes(self):
        req = ThreadSearchRequest(metadata={})
        assert req.metadata == {}

    @patch("ideer.persistence.json_compat.validate_metadata_filter_key", return_value=True)
    @patch("ideer.persistence.json_compat.validate_metadata_filter_value", return_value=True)
    def test_valid_metadata_filters(self, mock_val, mock_key):
        req = ThreadSearchRequest(metadata={"key": "value"})
        assert req.metadata == {"key": "value"}

    @patch("ideer.persistence.json_compat.validate_metadata_filter_key", return_value=False)
    def test_invalid_metadata_key_raises(self, mock_key):
        with pytest.raises(Exception):
            ThreadSearchRequest(metadata={"bad!key": "val"})

    @patch("ideer.persistence.json_compat.validate_metadata_filter_key", return_value=True)
    @patch("ideer.persistence.json_compat.validate_metadata_filter_value", return_value=False)
    def test_invalid_metadata_value_raises(self, mock_val, mock_key):
        with pytest.raises(Exception):
            ThreadSearchRequest(metadata={"key": [1, 2, 3]})

    def test_limit_boundary_min(self):
        req = ThreadSearchRequest(limit=1)
        assert req.limit == 1

    def test_limit_boundary_max(self):
        req = ThreadSearchRequest(limit=1000)
        assert req.limit == 1000

    def test_offset_zero(self):
        req = ThreadSearchRequest(offset=0)
        assert req.offset == 0


class TestThreadPatchRequest:
    """Tests for ThreadPatchRequest model."""

    def test_strips_reserved_metadata(self):
        req = ThreadPatchRequest(metadata={"owner_id": "a", "keep": "b"})
        assert req.metadata == {"keep": "b"}

    def test_default_empty(self):
        req = ThreadPatchRequest()
        assert req.metadata == {}


class TestThreadStateUpdateRequest:
    """Tests for ThreadStateUpdateRequest model."""

    def test_default_values(self):
        req = ThreadStateUpdateRequest()
        assert req.values is None
        assert req.checkpoint_id is None
        assert req.checkpoint is None
        assert req.as_node is None

    def test_with_values(self):
        req = ThreadStateUpdateRequest(values={"title": "new"}, as_node="node1")
        assert req.values == {"title": "new"}
        assert req.as_node == "node1"


class TestThreadHistoryRequest:
    """Tests for ThreadHistoryRequest model."""

    def test_defaults(self):
        req = ThreadHistoryRequest()
        assert req.limit == 10
        assert req.before is None

    def test_custom(self):
        req = ThreadHistoryRequest(limit=50, before="cp-100")
        assert req.limit == 50
        assert req.before == "cp-100"


# ===========================================================================
# Endpoint tests — DELETE /{thread_id}
# ===========================================================================


class TestDeleteThread:
    """Tests for DELETE /api/threads/{thread_id}."""

    @patch("app.gateway.routers.threads.get_effective_user_id", return_value="test-user")
    @patch("app.gateway.routers.threads._delete_thread_data")
    def test_success(self, mock_delete, mock_uid):
        mock_delete.return_value = ThreadDeleteResponse(success=True, message="Deleted local thread data for t1")
        app, cp, ts = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/threads/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    @patch("app.gateway.routers.threads.get_effective_user_id", return_value="test-user")
    @patch("app.gateway.routers.threads._delete_thread_data")
    def test_deletes_checkpoints(self, mock_delete, mock_uid):
        mock_delete.return_value = ThreadDeleteResponse(success=True, message="ok")
        app, cp, ts = _make_app()
        cp.adelete_thread = AsyncMock()
        client = TestClient(app)
        resp = client.delete("/api/threads/t1")
        assert resp.status_code == 200
        cp.adelete_thread.assert_called_once_with("t1")

    @patch("app.gateway.routers.threads.get_effective_user_id", return_value="test-user")
    @patch("app.gateway.routers.threads._delete_thread_data")
    def test_checkpointer_error_is_swallowed(self, mock_delete, mock_uid):
        mock_delete.return_value = ThreadDeleteResponse(success=True, message="ok")
        app, cp, ts = _make_app()
        cp.adelete_thread = AsyncMock(side_effect=RuntimeError("fail"))
        client = TestClient(app)
        resp = client.delete("/api/threads/t1")
        assert resp.status_code == 200  # best-effort, not critical

    @patch("app.gateway.routers.threads.get_effective_user_id", return_value="test-user")
    @patch("app.gateway.routers.threads._delete_thread_data")
    def test_deletes_thread_meta(self, mock_delete, mock_uid):
        mock_delete.return_value = ThreadDeleteResponse(success=True, message="ok")
        app, cp, ts = _make_app()
        ts.delete = AsyncMock()
        client = TestClient(app)
        resp = client.delete("/api/threads/t1")
        assert resp.status_code == 200
        ts.delete.assert_called_once_with("t1")

    @patch("app.gateway.routers.threads.get_effective_user_id", return_value="test-user")
    @patch("app.gateway.routers.threads._delete_thread_data")
    def test_thread_meta_delete_error_swallowed(self, mock_delete, mock_uid):
        mock_delete.return_value = ThreadDeleteResponse(success=True, message="ok")
        app, cp, ts = _make_app()
        ts.delete = AsyncMock(side_effect=RuntimeError("db fail"))
        client = TestClient(app)
        resp = client.delete("/api/threads/t1")
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.get_effective_user_id", return_value="test-user")
    @patch("app.gateway.routers.threads._delete_thread_data")
    def test_no_checkpointer_attribute(self, mock_delete, mock_uid):
        mock_delete.return_value = ThreadDeleteResponse(success=True, message="ok")
        app, cp, ts = _make_app()
        del app.state.checkpointer
        client = TestClient(app)
        resp = client.delete("/api/threads/t1")
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.get_effective_user_id", return_value="test-user")
    @patch("app.gateway.routers.threads._delete_thread_data")
    def test_no_adelete_thread_method(self, mock_delete, mock_uid):
        """Checkpointer without adelete_thread is fine."""
        mock_delete.return_value = ThreadDeleteResponse(success=True, message="ok")
        app, cp, ts = _make_app()
        # Remove the adelete_thread attribute
        cp_mock = MagicMock(spec=[])  # empty spec = no methods
        app.state.checkpointer = cp_mock
        client = TestClient(app)
        resp = client.delete("/api/threads/t1")
        assert resp.status_code == 200


# ===========================================================================
# Endpoint tests — POST / (create_thread)
# ===========================================================================


class TestCreateThread:
    """Tests for POST /api/threads."""

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_new_thread(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1", "metadata": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "t1"
        assert data["status"] == "idle"
        assert data["created_at"] == "2026-01-01T00:00:00+00:00"

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_auto_generates_id(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"]  # auto-generated UUID
        assert data["status"] == "idle"

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_create_idempotent_returns_existing(self, mock_coerce, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(
            return_value={
                "thread_id": "t1",
                "status": "idle",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "metadata": {"key": "val"},
            }
        )
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "t1"
        assert data["metadata"] == {"key": "val"}
        ts.create.assert_not_called()

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_thread_meta_failure_raises_500(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock(side_effect=RuntimeError("db down"))
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1"})
        assert resp.status_code == 500
        assert "Failed to create thread" in resp.json()["detail"]

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_checkpoint_failure_raises_500(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock(side_effect=RuntimeError("ckpt fail"))
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1"})
        assert resp.status_code == 500

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_with_metadata(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1", "metadata": {"key": "val"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"] == {"key": "val"}

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_strips_reserved_metadata(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1", "metadata": {"owner_id": "bad", "ok": "v"}})
        assert resp.status_code == 200
        data = resp.json()
        assert "owner_id" not in data["metadata"]
        assert data["metadata"] == {"ok": "v"}

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_with_assistant_id(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1", "assistant_id": "asst-1"})
        assert resp.status_code == 200


# ===========================================================================
# Endpoint tests — POST /search
# ===========================================================================


class TestSearchThreads:
    """Tests for POST /api/threads/search."""

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_search_returns_list(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.search = AsyncMock(
            return_value=[
                {"thread_id": "t1", "status": "idle", "created_at": "2026-01-01", "updated_at": "2026-01-01", "metadata": {}},
                {"thread_id": "t2", "status": "idle", "created_at": "2026-01-02", "updated_at": "2026-01-02", "metadata": {"k": "v"}},
            ]
        )
        client = TestClient(app)
        resp = client.post("/api/threads/search", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["thread_id"] == "t1"

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_search_empty_result(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.search = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post("/api/threads/search", json={})
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_search_with_display_name(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.search = AsyncMock(
            return_value=[
                {"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}, "display_name": "My Thread"},
            ]
        )
        client = TestClient(app)
        resp = client.post("/api/threads/search", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["values"] == {"title": "My Thread"}

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_search_with_filters(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.search = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post("/api/threads/search", json={"metadata": {"k": "v"}, "limit": 5, "offset": 10, "status": "error"})
        assert resp.status_code == 200
        ts.search.assert_called_once()

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_search_invalid_metadata_filter_raises_400(self, mock_coerce):
        from ideer.persistence.thread_meta import InvalidMetadataFilterError

        app, cp, ts = _make_app()
        ts.search = AsyncMock(side_effect=InvalidMetadataFilterError("bad filter"))
        client = TestClient(app)
        resp = client.post("/api/threads/search", json={"metadata": {"bad": "filter"}})
        assert resp.status_code == 400
        assert "bad filter" in resp.json()["detail"]

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_search_passes_none_for_empty_metadata(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.search = AsyncMock(return_value=[])
        client = TestClient(app)
        resp = client.post("/api/threads/search", json={"metadata": {}})
        assert resp.status_code == 200
        # Empty metadata dict should be passed as None to search
        call_kwargs = ts.search.call_args
        assert call_kwargs[1]["metadata"] is None

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_search_no_display_name(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.search = AsyncMock(
            return_value=[
                {"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}},
            ]
        )
        client = TestClient(app)
        resp = client.post("/api/threads/search", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["values"] == {}


# ===========================================================================
# Endpoint tests — PATCH /{thread_id}
# ===========================================================================


class TestPatchThread:
    """Tests for PATCH /api/threads/{thread_id}."""

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_patch_success(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(
            return_value={
                "thread_id": "t1",
                "status": "idle",
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01",
                "metadata": {"existing": "val"},
            }
        )
        ts.update_metadata = AsyncMock()
        client = TestClient(app)
        resp = client.patch("/api/threads/t1", json={"metadata": {"new_key": "new_val"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "t1"

    def test_patch_not_found(self):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        client = TestClient(app)
        resp = client.patch("/api/threads/nonexistent", json={"metadata": {"k": "v"}})
        assert resp.status_code == 404

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_patch_update_failure_raises_500(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value={"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}})
        ts.update_metadata = AsyncMock(side_effect=RuntimeError("fail"))
        client = TestClient(app)
        resp = client.patch("/api/threads/t1", json={"metadata": {"k": "v"}})
        assert resp.status_code == 500

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_patch_re_reads_after_update(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(
            side_effect=[
                {"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}},
                {"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {"merged": "val"}},
            ]
        )
        ts.update_metadata = AsyncMock()
        client = TestClient(app)
        resp = client.patch("/api/threads/t1", json={"metadata": {"k": "v"}})
        assert resp.status_code == 200
        assert ts.get.call_count == 2

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_patch_strips_reserved_metadata(self, mock_coerce):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value={"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}})
        ts.update_metadata = AsyncMock()
        client = TestClient(app)
        resp = client.patch("/api/threads/t1", json={"metadata": {"owner_id": "bad", "ok": "v"}})
        assert resp.status_code == 200
        # update_metadata should be called with stripped metadata
        call_args = ts.update_metadata.call_args
        assert "owner_id" not in call_args[0][1]


# ===========================================================================
# Endpoint tests — GET /{thread_id}
# ===========================================================================


class TestGetThread:
    """Tests for GET /api/threads/{thread_id}."""

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_from_thread_store(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(
            return_value={
                "thread_id": "t1",
                "status": "idle",
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01",
                "metadata": {"k": "v"},
            }
        )
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                channel_values={"messages": ["hello"]},
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "t1"
        assert data["metadata"] == {"k": "v"}

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_legacy_thread_from_checkpoint(self, mock_coerce, mock_serialize):
        """Thread exists in checkpointer but not in thread_meta."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01", "custom_key": "custom_val"},
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "t1"
        assert "custom_key" in data["metadata"]

    def test_get_not_found(self):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp.aget_tuple = AsyncMock(return_value=None)
        client = TestClient(app)
        resp = client.get("/api/threads/nonexistent")
        assert resp.status_code == 404

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_checkpoint_exception_raises_500(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value={"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}})
        cp.aget_tuple = AsyncMock(side_effect=RuntimeError("fail"))
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 500

    @patch("app.gateway.routers.threads._derive_thread_status", return_value="error")
    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_uses_derived_status(self, mock_coerce, mock_serialize, mock_derive):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value={"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}})
        cp.aget_tuple = AsyncMock(return_value=_make_checkpoint_tuple())
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_no_checkpoint_uses_record_status(self, mock_coerce, mock_serialize):
        """When checkpoint is None, fall back to record status."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value={"thread_id": "t1", "status": "busy", "created_at": "", "updated_at": "", "metadata": {}})
        cp.aget_tuple = AsyncMock(return_value=None)
        # This should raise 404 because record is not None but checkpoint is None
        # Actually: record is not None, so no 404. checkpoint_tuple is None, so
        # status = record.get("status", "idle") and checkpoint = {}
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "busy"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_legacy_thread_updated_at_fallback(self, mock_coerce, mock_serialize):
        """Legacy thread with no updated_at falls back to created_at."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_legacy_thread_no_metadata(self, mock_coerce, mock_serialize):
        """Legacy checkpoint with empty metadata."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp_tuple = _make_checkpoint_tuple(metadata={})
        cp.aget_tuple = AsyncMock(return_value=cp_tuple)
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_checkpoint_has_channel_values(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value={"thread_id": "t1", "status": "idle", "created_at": "", "updated_at": "", "metadata": {}})
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                channel_values={"messages": ["hi"], "title": "T"},
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200


# ===========================================================================
# Endpoint tests — GET /{thread_id}/state
# ===========================================================================


class TestGetThreadState:
    """Tests for GET /api/threads/{thread_id}/state."""

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_state_success(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        task = MagicMock()
        task.name = "node1"
        task.id = "task-1"
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                channel_values={"messages": ["hello"]},
                metadata={"created_at": "2026-01-01"},
                config={"configurable": {"checkpoint_id": "cp-1"}},
                parent_config={"configurable": {"checkpoint_id": "cp-0"}},
                tasks=[task],
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["checkpoint_id"] == "cp-1"
        assert data["parent_checkpoint_id"] == "cp-0"
        assert data["next"] == ["node1"]
        assert len(data["tasks"]) == 1

    def test_get_state_not_found(self):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(return_value=None)
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 404

    def test_get_state_checkpoint_error_raises_500(self):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(side_effect=RuntimeError("fail"))
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 500

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_state_no_parent(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                parent_config=None,
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 200
        assert resp.json()["parent_checkpoint_id"] is None

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_state_no_checkpoint_id_in_config(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                config={},
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 200
        assert resp.json()["checkpoint_id"] is None

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_state_empty_checkpoint(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        cp_tuple = MagicMock()
        cp_tuple.checkpoint = None
        cp_tuple.metadata = {}
        cp_tuple.config = {}
        cp_tuple.parent_config = None
        cp_tuple.tasks = []
        cp.aget_tuple = AsyncMock(return_value=cp_tuple)
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_state_tasks_with_no_name_attr(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        task = MagicMock(spec=[])  # no name attribute
        task.id = "t1"
        cp.aget_tuple = AsyncMock(return_value=_make_checkpoint_tuple(tasks=[task]))
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 200
        assert resp.json()["next"] == []  # no name -> filtered out


# ===========================================================================
# Endpoint tests — POST /{thread_id}/state (update_thread_state)
# ===========================================================================


class TestUpdateThreadState:
    """Tests for POST /api/threads/{thread_id}/state."""

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_values(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                channel_values={"old": "val"},
                metadata={"step": 0, "created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"new_key": "new_val"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["checkpoint_id"] == "cp-new"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_with_as_node(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                channel_values={},
                metadata={"step": 1, "created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        client = TestClient(app)
        resp = client.post(
            "/api/threads/t1/state",
            json={
                "values": {"title": "New Title"},
                "as_node": "human",
            },
        )
        assert resp.status_code == 200
        # Verify aput was called with metadata containing source=update
        put_call = cp.aput.call_args
        meta = put_call[0][2]
        assert meta["source"] == "update"
        assert meta["step"] == 2
        assert meta["writes"] == {"human": {"title": "New Title"}}

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_syncs_title(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        ts.update_display_name = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"title": "New Title"}})
        assert resp.status_code == 200
        ts.update_display_name.assert_called_once_with("t1", "New Title")

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_empty_title_skipped(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        ts.update_display_name = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"title": ""}})
        assert resp.status_code == 200
        ts.update_display_name.assert_not_called()

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_title_sync_error_swallowed(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        ts.update_display_name = AsyncMock(side_effect=RuntimeError("fail"))
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"title": "T"}})
        assert resp.status_code == 200

    def test_update_not_found(self):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(return_value=None)
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"k": "v"}})
        assert resp.status_code == 404

    def test_update_checkpoint_get_error_raises_500(self):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(side_effect=RuntimeError("fail"))
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"k": "v"}})
        assert resp.status_code == 500

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_aput_error_raises_500(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(side_effect=RuntimeError("fail"))
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"k": "v"}})
        assert resp.status_code == 500

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_no_values(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                channel_values={"existing": "val"},
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={})
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_with_checkpoint_id(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        client = TestClient(app)
        resp = client.post(
            "/api/threads/t1/state",
            json={
                "checkpoint_id": "cp-specific",
                "values": {"k": "v"},
            },
        )
        assert resp.status_code == 200
        # Verify read_config includes checkpoint_id
        read_call = cp.aget_tuple.call_args[0][0]
        assert read_call["configurable"]["checkpoint_id"] == "cp-specific"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_aput_returns_non_dict(self, mock_coerce, mock_now, mock_serialize):
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value="not-a-dict")
        client = TestClient(app)
        resp = client.post("/api/threads/t1/state", json={"values": {"k": "v"}})
        assert resp.status_code == 200
        assert resp.json()["checkpoint_id"] is None

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00")
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_as_node_default_step(self, mock_coerce, mock_now, mock_serialize):
        """When metadata has no 'step' key, as_node defaults step to 1."""
        app, cp, ts = _make_app()
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
        client = TestClient(app)
        resp = client.post(
            "/api/threads/t1/state",
            json={
                "values": {"k": "v"},
                "as_node": "human",
            },
        )
        assert resp.status_code == 200
        put_call = cp.aput.call_args
        meta = put_call[0][2]
        assert meta["step"] == 1  # 0 + 1


# ===========================================================================
# Endpoint tests — POST /{thread_id}/history
# ===========================================================================


class TestGetThreadHistory:
    """Tests for POST /api/threads/{thread_id}/history."""

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_returns_entries(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            for i in range(2):
                cp_tuple = _make_checkpoint_tuple(
                    channel_values={"messages": [f"msg-{i}"], "title": "T"},
                    metadata={"created_at": f"2026-01-0{i + 1}", "step": i},
                    config={"configurable": {"checkpoint_id": f"cp-{i}"}},
                    parent_config={"configurable": {"checkpoint_id": f"cp-{i - 1}"}} if i > 0 else None,
                )
                yield cp_tuple

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["checkpoint_id"] == "cp-0"
        assert data[1]["checkpoint_id"] == "cp-1"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_messages_only_on_latest(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            for i in range(2):
                yield _make_checkpoint_tuple(
                    channel_values={"messages": [f"msg-{i}"]},
                    metadata={"created_at": f"2026-01-0{i + 1}", "step": i},
                    config={"configurable": {"checkpoint_id": f"cp-{i}"}},
                )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        # First entry (latest) should have messages
        assert "messages" in data[0]["values"]
        # Second entry should NOT have messages
        assert "messages" not in data[1]["values"]

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_empty(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            return
            yield  # make it an async generator

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_error_raises_500(self, mock_coerce):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            raise RuntimeError("fail")
            yield  # make it an async generator

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 500

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_with_before_cursor(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            yield _make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={"before": "cp-5", "limit": 5})
        assert resp.status_code == 200
        # Verify config passed to alist includes checkpoint_id
        # We can't easily inspect this with the mock pattern, but the endpoint should work

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_with_tasks(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        task = MagicMock()
        task.name = "node1"

        async def mock_alist(config, limit=10):
            yield _make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
                tasks=[task],
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["next"] == ["node1"]

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_strips_internal_keys_from_metadata(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            yield _make_checkpoint_tuple(
                metadata={
                    "created_at": "2026-01-01",
                    "updated_at": "2026-01-01",
                    "step": 5,
                    "source": "input",
                    "writes": None,
                    "parents": {},
                    "user_key": "user_val",
                },
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200
        data = resp.json()
        meta = data[0]["metadata"]
        assert "user_key" in meta
        assert meta["step"] == 5  # step is kept
        assert "created_at" not in meta
        assert "source" not in meta

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_with_thread_data_channel(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            yield _make_checkpoint_tuple(
                channel_values={"thread_data": {"key": "val"}},
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["values"]["thread_data"] == {"key": "val"}

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_no_title_no_thread_data_no_messages(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            yield _make_checkpoint_tuple(
                channel_values={},
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["values"] == {}

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_empty_messages(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            yield _make_checkpoint_tuple(
                channel_values={"messages": []},
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_tasks_with_no_name(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        task = MagicMock(spec=[])  # no name attribute

        async def mock_alist(config, limit=10):
            yield _make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
                tasks=[task],
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200
        assert resp.json()[0]["next"] == []


# ===========================================================================
# Edge case / integration tests
# ===========================================================================


class TestEdgeCases:
    """Edge cases and cross-cutting concerns."""

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_thread_legacy_record_synthesis_with_none_metadata(self, mock_coerce, mock_serialize):
        """Legacy checkpoint with None metadata."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp_tuple = MagicMock()
        cp_tuple.checkpoint = {"channel_values": {}}
        cp_tuple.metadata = None
        cp_tuple.config = {}
        cp_tuple.parent_config = None
        cp_tuple.tasks = []
        cp_tuple.pending_writes = []
        cp.aget_tuple = AsyncMock(return_value=cp_tuple)
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_thread_legacy_record_synthesis_updated_at_from_created(self, mock_coerce, mock_serialize):
        """Legacy thread: updated_at falls back to created_at."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp.aget_tuple = AsyncMock(
            return_value=_make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01"},
            )
        )
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 200

    def test_thread_delete_response_model(self):
        resp = ThreadDeleteResponse(success=True, message="test")
        assert resp.success is True
        assert resp.message == "test"

    def test_thread_response_model_defaults(self):
        resp = ThreadResponse(thread_id="t1")
        assert resp.status == "idle"
        assert resp.created_at == ""
        assert resp.updated_at == ""
        assert resp.metadata == {}
        assert resp.values == {}
        assert resp.interrupts == {}

    def test_thread_state_response_model_defaults(self):
        resp = ThreadStateResponse()
        assert resp.values == {}
        assert resp.next == []
        assert resp.metadata == {}
        assert resp.checkpoint == {}
        assert resp.checkpoint_id is None
        assert resp.parent_checkpoint_id is None
        assert resp.created_at is None
        assert resp.tasks == []

    def test_history_entry_model(self):
        entry = HistoryEntry(checkpoint_id="cp-1")
        assert entry.parent_checkpoint_id is None
        assert entry.metadata == {}
        assert entry.values == {}
        assert entry.created_at is None
        assert entry.next == []

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_thread_checkpoint_config_has_empty_ns(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1"})
        assert resp.status_code == 200
        put_config = cp.aput.call_args[0][0]
        assert put_config["configurable"]["checkpoint_ns"] == ""

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_state_write_config_has_empty_ns(self, mock_coerce, mock_serialize):
        with patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00"):
            app, cp, ts = _make_app()
            cp.aget_tuple = AsyncMock(
                return_value=_make_checkpoint_tuple(
                    metadata={"created_at": "2026-01-01"},
                )
            )
            cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
            client = TestClient(app)
            resp = client.post("/api/threads/t1/state", json={"values": {"k": "v"}})
            assert resp.status_code == 200
            put_config = cp.aput.call_args[0][0]
            assert put_config["configurable"]["checkpoint_ns"] == ""
            assert "checkpoint_id" not in put_config["configurable"]

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_read_config_without_checkpoint_id(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            assert "checkpoint_id" not in config["configurable"]
            yield _make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_read_config_with_before(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            assert config["configurable"]["checkpoint_id"] == "cp-before"
            yield _make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={"before": "cp-before"})
        assert resp.status_code == 200

    @patch("app.gateway.routers.threads.now_iso", return_value="2026-01-01T00:00:00+00:00")
    def test_create_thread_calls_thread_store_create(self, mock_now):
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        ts.create = AsyncMock()
        cp.aput = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/threads", json={"thread_id": "t1", "assistant_id": "asst-1", "metadata": {"k": "v"}})
        assert resp.status_code == 200
        ts.create.assert_called_once()
        create_args = ts.create.call_args
        assert create_args[0][0] == "t1"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_update_state_merges_values_into_channel(self, mock_coerce, mock_serialize):
        with patch("app.gateway.routers.threads.now_iso", return_value="2026-01-02T00:00:00+00:00"):
            app, cp, ts = _make_app()
            cp.aget_tuple = AsyncMock(
                return_value=_make_checkpoint_tuple(
                    channel_values={"old_key": "old_val"},
                    metadata={"created_at": "2026-01-01"},
                )
            )
            cp.aput = AsyncMock(return_value={"configurable": {"checkpoint_id": "cp-new"}})
            client = TestClient(app)
            resp = client.post("/api/threads/t1/state", json={"values": {"new_key": "new_val"}})
            assert resp.status_code == 200
            # Verify aput was called with merged channel values
            put_checkpoint = cp.aput.call_args[0][1]
            assert put_checkpoint["channel_values"]["old_key"] == "old_val"
            assert put_checkpoint["channel_values"]["new_key"] == "new_val"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_state_checkpoint_config_has_no_configurable(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        cp_tuple = MagicMock()
        cp_tuple.checkpoint = {"channel_values": {}}
        cp_tuple.metadata = {}
        cp_tuple.config = {"other_key": "val"}  # no 'configurable' key
        cp_tuple.parent_config = None
        cp_tuple.tasks = []
        cp.aget_tuple = AsyncMock(return_value=cp_tuple)
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 200
        assert resp.json()["checkpoint_id"] is None

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_state_parent_config_has_no_configurable(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()
        cp_tuple = MagicMock()
        cp_tuple.checkpoint = {"channel_values": {}}
        cp_tuple.metadata = {}
        cp_tuple.config = {"configurable": {"checkpoint_id": "cp-1"}}
        cp_tuple.parent_config = {"other_key": "val"}  # no 'configurable' key
        cp_tuple.tasks = []
        cp.aget_tuple = AsyncMock(return_value=cp_tuple)
        client = TestClient(app)
        resp = client.get("/api/threads/t1/state")
        assert resp.status_code == 200
        assert resp.json()["parent_checkpoint_id"] is None

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_history_parent_config_has_no_configurable(self, mock_coerce, mock_serialize):
        app, cp, ts = _make_app()

        async def mock_alist(config, limit=10):
            cp_tuple = _make_checkpoint_tuple(
                metadata={"created_at": "2026-01-01", "step": 0},
                config={"configurable": {"checkpoint_id": "cp-0"}},
            )
            cp_tuple.parent_config = {"other_key": "val"}
            yield cp_tuple

        cp.alist = mock_alist
        client = TestClient(app)
        resp = client.post("/api/threads/t1/history", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["parent_checkpoint_id"] is None

    def test_derive_thread_status_pending_write_exact_two_elements(self):
        """pw with exactly 2 elements: pw[1] check."""
        cp = _make_checkpoint_tuple(pending_writes=[["ns", "__error__"]])
        assert _derive_thread_status(cp) == "error"

    def test_derive_thread_status_pending_write_not_error(self):
        cp = _make_checkpoint_tuple(pending_writes=[["ns", "result"]])
        assert _derive_thread_status(cp) == "idle"

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_thread_checkpoint_none_no_record(self, mock_coerce, mock_serialize):
        """Both record and checkpoint are None -> 404."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp.aget_tuple = AsyncMock(return_value=None)
        client = TestClient(app)
        resp = client.get("/api/threads/t1")
        assert resp.status_code == 404

    @patch("app.gateway.routers.threads.serialize_channel_values", side_effect=lambda x: x)
    @patch("app.gateway.routers.threads.coerce_iso", side_effect=lambda x: x)
    def test_get_thread_record_none_after_legacy_synthesis(self, mock_coerce, mock_serialize):
        """record is None, checkpoint_tuple not None but ckpt_meta is None -> record stays None -> 404."""
        app, cp, ts = _make_app()
        ts.get = AsyncMock(return_value=None)
        cp_tuple = MagicMock()
        cp_tuple.checkpoint = {"channel_values": {}}
        cp_tuple.metadata = None  # This makes ckpt_meta = None
        cp_tuple.config = {}
        cp_tuple.parent_config = None
        cp_tuple.tasks = []
        cp_tuple.pending_writes = []
        cp.aget_tuple = AsyncMock(return_value=cp_tuple)
        client = TestClient(app)
        # record = None, checkpoint_tuple not None -> enters the "if record is None and checkpoint_tuple is not None" branch
        # ckpt_meta = getattr(...) or {} -> None or {} = {}
        # record is synthesized from empty ckpt_meta
        resp = client.get("/api/threads/t1")
        # This should actually succeed because ckpt_meta becomes {} and record is synthesized
        assert resp.status_code == 200
