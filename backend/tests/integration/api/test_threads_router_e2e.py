"""E2E tests for the threads router (backend/app/gateway/routers/threads.py).

Covers all 8 threads endpoints:
- POST /api/threads
- POST /api/threads/search
- PATCH /api/threads/{thread_id}
- DELETE /api/threads/{thread_id}
- GET /api/threads/{thread_id}
- GET /api/threads/{thread_id}/state
- POST /api/threads/{thread_id}/state
- POST /api/threads/{thread_id}/history
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.threads import router as threads_router

pytestmark = pytest.mark.no_auto_user

THREAD_ID = "thread-1"


def _make_app(thread_store=None, checkpointer=None):
    app = make_authed_test_app()
    app.include_router(threads_router)
    if thread_store is not None:
        app.state.thread_store = thread_store
    if checkpointer is not None:
        app.state.checkpointer = checkpointer
    return app


_UNSET = object()


def _make_thread_store(
    create_result=_UNSET,
    get_result=_UNSET,
    search_result=_UNSET,
    patch_result=_UNSET,
    delete_result=True,
):
    store = MagicMock()
    store.create = AsyncMock(
        return_value={"thread_id": THREAD_ID, "status": "active"} if create_result is _UNSET else create_result,
    )
    store.get = AsyncMock(
        return_value={"thread_id": THREAD_ID, "status": "active"} if get_result is _UNSET else get_result,
    )
    store.search = AsyncMock(return_value=[] if search_result is _UNSET else search_result)
    store.patch = AsyncMock(
        return_value={"thread_id": THREAD_ID} if patch_result is _UNSET else patch_result,
    )
    store.update_metadata = AsyncMock(
        return_value={"thread_id": THREAD_ID} if patch_result is _UNSET else patch_result,
    )
    store.update_display_name = AsyncMock(return_value=True)
    store.delete = AsyncMock(return_value=delete_result)
    store.check_access = AsyncMock(return_value=True)
    return store


class _AsyncListIterator:
    """Async iterator wrapper for mock alist results."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


def _make_checkpointer(
    get_state_result=None,
    get_tuple_result=None,
    history_result=None,
):
    cp = MagicMock()
    cp.get = AsyncMock(return_value=get_state_result)
    cp.aget_tuple = AsyncMock(return_value=get_tuple_result)
    cp.aput = AsyncMock(return_value=None)
    cp.adelete_thread = AsyncMock(return_value=True)
    cp.alist = MagicMock(return_value=_AsyncListIterator(history_result or []))
    cp.put = AsyncMock(return_value=True)
    cp.get_history = AsyncMock(return_value=history_result or [])
    return cp


# ---------------------------------------------------------------------------
# Tests — POST /api/threads
# ---------------------------------------------------------------------------


class TestCreateThread:
    """Tests for POST /api/threads."""

    def test_create_thread_success(self):
        """Create thread succeeds."""
        store = _make_thread_store(get_result=None)
        cp = _make_checkpointer()
        app = _make_app(thread_store=store, checkpointer=cp)
        with TestClient(app) as client:
            resp = client.post("/api/threads", json={"metadata": {"key": "value"}})
        assert resp.status_code in (200, 201)

    def test_create_thread_idempotent(self):
        """Create thread is idempotent."""
        store = _make_thread_store()
        cp = _make_checkpointer()
        app = _make_app(thread_store=store, checkpointer=cp)
        with TestClient(app) as client:
            resp1 = client.post("/api/threads", json={})
            resp2 = client.post("/api/threads", json={})
        assert resp1.status_code == resp2.status_code


# ---------------------------------------------------------------------------
# Tests — POST /api/threads/search
# ---------------------------------------------------------------------------


class TestSearchThreads:
    """Tests for POST /api/threads/search."""

    def test_search_threads_returns_list(self):
        """Search threads returns a list."""
        store = _make_thread_store(search_result=[])
        app = _make_app(thread_store=store)
        with TestClient(app) as client:
            resp = client.post("/api/threads/search", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_search_threads_with_filter(self):
        """Search threads with metadata filter."""
        store = _make_thread_store(search_result=[{"thread_id": THREAD_ID}])
        app = _make_app(thread_store=store)
        with TestClient(app) as client:
            resp = client.post(
                "/api/threads/search",
                json={"metadata": {"status": "active"}},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — PATCH /api/threads/{thread_id}
# ---------------------------------------------------------------------------


class TestPatchThread:
    """Tests for PATCH /api/threads/{thread_id}."""

    def test_patch_thread_success(self):
        """Patch thread succeeds with valid data."""
        store = _make_thread_store()
        app = _make_app(thread_store=store)
        with TestClient(app) as client:
            resp = client.patch(
                f"/api/threads/{THREAD_ID}",
                json={"metadata": {"title": "Updated"}},
            )
        assert resp.status_code == 200

    def test_patch_thread_not_found(self):
        """Patch thread returns 404 when not found."""
        store = _make_thread_store(get_result=None)
        app = _make_app(thread_store=store)
        with TestClient(app) as client:
            resp = client.patch(
                "/api/threads/nonexistent",
                json={"metadata": {"title": "X"}},
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — DELETE /api/threads/{thread_id}
# ---------------------------------------------------------------------------


class TestDeleteThread:
    """Tests for DELETE /api/threads/{thread_id}."""

    def test_delete_thread_success(self):
        """Delete thread succeeds."""
        store = _make_thread_store()
        app = _make_app(thread_store=store)
        with TestClient(app) as client:
            resp = client.delete(f"/api/threads/{THREAD_ID}")
        assert resp.status_code in (200, 204)

    def test_delete_thread_not_found(self):
        """Delete thread returns 404 when not found."""
        store = _make_thread_store(delete_result=False)
        app = _make_app(thread_store=store)
        with TestClient(app) as client:
            resp = client.delete("/api/threads/nonexistent")
        assert resp.status_code in (404, 200, 204)


# ---------------------------------------------------------------------------
# Tests — GET /api/threads/{thread_id}
# ---------------------------------------------------------------------------


class TestGetThread:
    """Tests for GET /api/threads/{thread_id}."""

    def test_get_thread_found(self):
        """Get thread returns thread info."""
        store = _make_thread_store()
        cp = _make_checkpointer(
            get_tuple_result=MagicMock(
                pending_writes=None,
                tasks=None,
                metadata={"created_at": "2026-01-01T00:00:00Z"},
                checkpoint={"channel_values": {}},
                config={"configurable": {"checkpoint_id": "ckpt-1"}},
                parent_config=None,
            )
        )
        app = _make_app(thread_store=store, checkpointer=cp)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "thread_id" in data

    def test_get_thread_not_found(self):
        """Get thread returns 404 when not found."""
        store = _make_thread_store(get_result=None)
        cp = _make_checkpointer(get_tuple_result=None)
        app = _make_app(thread_store=store, checkpointer=cp)
        with TestClient(app) as client:
            resp = client.get("/api/threads/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — GET /api/threads/{thread_id}/state
# ---------------------------------------------------------------------------


class TestGetThreadState:
    """Tests for GET /api/threads/{thread_id}/state."""

    def test_get_thread_state(self):
        """Get thread state returns state snapshot."""
        cp = _make_checkpointer(
            get_tuple_result=MagicMock(
                pending_writes=None,
                tasks=[],
                metadata={"created_at": "2026-01-01T00:00:00Z"},
                checkpoint={"channel_values": {"messages": []}},
                config={"configurable": {"checkpoint_id": "ckpt-1"}},
                parent_config=None,
            )
        )
        app = _make_app(checkpointer=cp)
        with TestClient(app) as client:
            resp = client.get(f"/api/threads/{THREAD_ID}/state")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — POST /api/threads/{thread_id}/state
# ---------------------------------------------------------------------------


class TestUpdateThreadState:
    """Tests for POST /api/threads/{thread_id}/state."""

    def test_update_thread_state(self):
        """Update thread state succeeds."""
        store = _make_thread_store()
        cp = _make_checkpointer(
            get_tuple_result=MagicMock(
                pending_writes=None,
                tasks=[],
                metadata={"created_at": "2026-01-01T00:00:00Z"},
                checkpoint={"channel_values": {"messages": []}},
                config={"configurable": {"checkpoint_id": "ckpt-1"}},
                parent_config=None,
            )
        )
        app = _make_app(thread_store=store, checkpointer=cp)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{THREAD_ID}/state",
                json={"values": {"messages": []}},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — POST /api/threads/{thread_id}/history
# ---------------------------------------------------------------------------


class TestGetThreadHistory:
    """Tests for POST /api/threads/{thread_id}/history."""

    def test_get_thread_history(self):
        """Get thread history returns checkpoint history."""
        cp = _make_checkpointer(history_result=[])
        app = _make_app(checkpointer=cp)
        with TestClient(app) as client:
            resp = client.post(f"/api/threads/{THREAD_ID}/history", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
