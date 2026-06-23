"""Tests for memory router error paths (backend/app/gateway/routers/memory.py).

Covers previously uncovered lines:
  - Lines 194-195: OSError in clear_memory
  - Lines 220-223: ValueError and OSError in create_memory_fact_endpoint
  - Lines 245-246: OSError in delete_memory_fact_endpoint
  - Lines 277-278: OSError in update_memory_fact_endpoint
  - Lines 311-312: OSError in import_memory
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.memory import router as memory_router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATCH_PREFIX = "app.gateway.routers.memory"


def _make_rbac_user(user_id: str = "user-1"):
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = user_id
    user.role = "user"
    user.department_id = None
    user.disabled = False
    return user


def _build_app() -> FastAPI:
    """Build a test FastAPI app with stub auth and the memory router."""
    app = FastAPI()
    app.include_router(memory_router)

    async def _stub_current():
        return _make_rbac_user()

    app.dependency_overrides[get_current_rbac_user] = _stub_current
    return app


@pytest.fixture()
def app():
    return _build_app()


# ---------------------------------------------------------------------------
# Tests — clear_memory OSError (lines 194-195)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_memory_oserror(app: FastAPI):
    """Lines 194-195: DELETE /memory raises 500 when clear_memory_data raises OSError."""
    with patch(f"{_PATCH_PREFIX}.clear_memory_data", side_effect=OSError("disk full")):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/memory")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to clear memory data."


# ---------------------------------------------------------------------------
# Tests — create_memory_fact ValueError + OSError (lines 220-223)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_fact_value_error_confidence(app: FastAPI):
    """Lines 220-221: POST /memory/facts returns 400 when updater raises ValueError('confidence')."""
    with patch(
        f"{_PATCH_PREFIX}.create_memory_fact",
        side_effect=ValueError("confidence"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/memory/facts",
                json={"content": "test fact", "category": "context", "confidence": 0.5},
            )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid confidence value; must be between 0 and 1."


@pytest.mark.asyncio
async def test_create_fact_value_error_empty(app: FastAPI):
    """Lines 220-221: POST /memory/facts returns 400 when updater raises ValueError with other message."""
    with patch(
        f"{_PATCH_PREFIX}.create_memory_fact",
        side_effect=ValueError("content"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/memory/facts",
                json={"content": "test fact", "category": "context", "confidence": 0.5},
            )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Memory fact content cannot be empty."


@pytest.mark.asyncio
async def test_create_fact_oserror(app: FastAPI):
    """Lines 222-223: POST /memory/facts returns 500 when updater raises OSError."""
    with patch(
        f"{_PATCH_PREFIX}.create_memory_fact",
        side_effect=OSError("write failed"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/memory/facts",
                json={"content": "test fact", "category": "context", "confidence": 0.5},
            )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to create memory fact."


# ---------------------------------------------------------------------------
# Tests — delete_memory_fact_endpoint OSError (lines 245-246)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_fact_oserror(app: FastAPI):
    """Lines 245-246: DELETE /memory/facts/{id} returns 500 when delete_memory_fact raises OSError."""
    with patch(
        f"{_PATCH_PREFIX}.delete_memory_fact",
        side_effect=OSError("io error"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/memory/facts/fact-123")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to delete memory fact."


# ---------------------------------------------------------------------------
# Tests — update_memory_fact_endpoint ValueError + OSError (lines 273-278)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_fact_oserror(app: FastAPI):
    """Lines 277-278: PATCH /memory/facts/{id} returns 500 when update_memory_fact raises OSError."""
    with patch(
        f"{_PATCH_PREFIX}.update_memory_fact",
        side_effect=OSError("disk error"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/memory/facts/fact-456",
                json={"content": "updated"},
            )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to update memory fact."


@pytest.mark.asyncio
async def test_update_fact_value_error_confidence(app: FastAPI):
    """Lines 273-274: PATCH /memory/facts/{id} returns 400 when updater raises ValueError('confidence')."""
    with patch(
        f"{_PATCH_PREFIX}.update_memory_fact",
        side_effect=ValueError("confidence"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/memory/facts/fact-456",
                json={"content": "updated", "confidence": 0.8},
            )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid confidence value; must be between 0 and 1."


@pytest.mark.asyncio
async def test_update_fact_value_error_empty(app: FastAPI):
    """Lines 273-274: PATCH /memory/facts/{id} returns 400 when updater raises ValueError with other message."""
    with patch(
        f"{_PATCH_PREFIX}.update_memory_fact",
        side_effect=ValueError("content"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/memory/facts/fact-456",
                json={"content": "updated"},
            )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Memory fact content cannot be empty."


@pytest.mark.asyncio
async def test_update_fact_key_error_not_found(app: FastAPI):
    """Lines 275-276: PATCH /memory/facts/{id} returns 404 when updater raises KeyError."""
    with patch(
        f"{_PATCH_PREFIX}.update_memory_fact",
        side_effect=KeyError("missing-fact"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/memory/facts/missing-fact",
                json={"content": "updated"},
            )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Tests — import_memory OSError (lines 311-312)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_memory_oserror(app: FastAPI):
    """Lines 311-312: POST /memory/import returns 500 when import_memory_data raises OSError."""
    with patch(
        f"{_PATCH_PREFIX}.import_memory_data",
        side_effect=OSError("write protected"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/memory/import",
                json={"version": "1.0", "lastUpdated": "", "facts": []},
            )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to import memory data."


# ---------------------------------------------------------------------------
# Tests — delete_memory_fact KeyError (lines 243-244)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_fact_key_error_not_found(app: FastAPI):
    """Lines 243-244: DELETE /memory/facts/{id} returns 404 when updater raises KeyError."""
    with patch(
        f"{_PATCH_PREFIX}.delete_memory_fact",
        side_effect=KeyError("gone-fact"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/memory/facts/gone-fact")

    assert resp.status_code == 404
    assert "gone-fact" in resp.json()["detail"]
    assert "not found" in resp.json()["detail"]
