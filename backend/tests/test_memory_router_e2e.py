"""E2E tests for the memory router (backend/app/gateway/routers/memory.py).

Covers all 10 memory endpoints:
- GET /api/memory
- POST /api/memory/reload
- DELETE /api/memory
- POST /api/memory/facts
- DELETE /api/memory/facts/{fact_id}
- PATCH /api/memory/facts/{fact_id}
- GET /api/memory/export
- POST /api/memory/import
- GET /api/memory/config
- GET /api/memory/status
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.memory import router as memory_router

pytestmark = pytest.mark.no_auto_user

# Default empty memory response dict matching MemoryResponse shape.
_EMPTY_MEMORY = {
    "version": "1.0",
    "lastUpdated": "",
    "facts": [],
}

# Default memory config values matching MemoryConfigResponse shape.
_DEFAULT_CONFIG = {
    "enabled": True,
    "storage_path": ".ideer/memory.json",
    "debounce_seconds": 30,
    "max_facts": 100,
    "fact_confidence_threshold": 0.7,
    "injection_enabled": True,
    "max_injection_tokens": 2000,
}


def _make_config(cfg=None):
    """Build a ``MemoryConfigResponse``-compatible mock from a dict."""
    data = cfg or _DEFAULT_CONFIG
    obj = MagicMock()
    for k, v in data.items():
        setattr(obj, k, v)
    return obj


def _make_app():
    """Build a test app with the memory router.

    The router calls module-level functions from ``ideer.agents.memory.updater``
    and ``ideer.config.memory_config`` directly -- there is no store object on
    ``app.state``.  Each test patches those functions at their import location
    in the router module.
    """

    from app.gateway.authz import get_current_rbac_user

    app = make_authed_test_app()
    app.include_router(memory_router)

    # Mock the RBAC user for @require_role decorators
    rbac_user = MagicMock()
    rbac_user.id = "test-user-id"
    rbac_user.role = "user"
    rbac_user.department_id = None
    rbac_user.disabled = False

    async def _stub_rbac_user():
        return rbac_user

    app.dependency_overrides[get_current_rbac_user] = _stub_rbac_user
    return app


def _apply_patches(overrides=None, config_override=None):
    """Start all updater/config patches and return an ExitStack.

    Args:
        overrides: dict mapping updater function name to its return value.
        config_override: dict of config fields for ``get_memory_config``.

    Returns:
        (exit_stack, mock_objects) -- caller must close the stack when done.
    """
    overrides = overrides or {}
    cfg = config_override or _DEFAULT_CONFIG

    stack = ExitStack()
    mocks = {}
    for fn_name, default in [
        ("get_memory_data", _EMPTY_MEMORY),
        ("reload_memory_data", _EMPTY_MEMORY),
        ("clear_memory_data", _EMPTY_MEMORY),
        ("create_memory_fact", _EMPTY_MEMORY),
        ("delete_memory_fact", _EMPTY_MEMORY),
        ("update_memory_fact", _EMPTY_MEMORY),
        ("import_memory_data", _EMPTY_MEMORY),
    ]:
        p = patch(
            f"app.gateway.routers.memory.{fn_name}",
            return_value=overrides.get(fn_name, default),
        )
        mocks[fn_name] = stack.enter_context(p)

    p = patch(
        "app.gateway.routers.memory.get_memory_config",
        return_value=overrides.get("get_memory_config", _make_config(cfg)),
    )
    mocks["get_memory_config"] = stack.enter_context(p)

    return stack, mocks


# ---------------------------------------------------------------------------
# Tests -- GET /api/memory
# ---------------------------------------------------------------------------


class TestGetMemory:
    """Tests for GET /api/memory."""

    def test_get_memory_returns_data(self):
        """Get memory returns memory data."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.get("/api/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert "facts" in data


# ---------------------------------------------------------------------------
# Tests -- POST /api/memory/reload
# ---------------------------------------------------------------------------


class TestReloadMemory:
    """Tests for POST /api/memory/reload."""

    def test_reload_memory_success(self):
        """Reload memory succeeds."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.post("/api/memory/reload")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests -- DELETE /api/memory
# ---------------------------------------------------------------------------


class TestClearMemory:
    """Tests for DELETE /api/memory."""

    def test_clear_memory_success(self):
        """Clear memory succeeds."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.delete("/api/memory")
        assert resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Tests -- POST /api/memory/facts
# ---------------------------------------------------------------------------


class TestCreateMemoryFact:
    """Tests for POST /api/memory/facts."""

    def test_create_fact_success(self):
        """Create memory fact succeeds."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.post("/api/memory/facts", json={"content": "Test fact"})
        assert resp.status_code in (200, 201)

    def test_create_fact_with_category(self):
        """Create memory fact with category succeeds."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.post(
                "/api/memory/facts",
                json={"content": "Test fact", "category": "preference"},
            )
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# Tests -- DELETE /api/memory/facts/{fact_id}
# ---------------------------------------------------------------------------


class TestDeleteMemoryFact:
    """Tests for DELETE /api/memory/facts/{fact_id}."""

    def test_delete_fact_success(self):
        """Delete memory fact succeeds."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.delete("/api/memory/facts/fact-1")
        assert resp.status_code in (200, 204)

    def test_delete_fact_not_found(self):
        """Delete memory fact returns 404 when not found."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            with patch(
                "app.gateway.routers.memory.delete_memory_fact",
                side_effect=KeyError("notfound"),
            ):
                resp = client.delete("/api/memory/facts/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- PATCH /api/memory/facts/{fact_id}
# ---------------------------------------------------------------------------


class TestUpdateMemoryFact:
    """Tests for PATCH /api/memory/facts/{fact_id}."""

    def test_update_fact_success(self):
        """Update memory fact succeeds."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.patch(
                "/api/memory/facts/fact-1",
                json={"content": "Updated fact"},
            )
        assert resp.status_code == 200

    def test_update_fact_not_found(self):
        """Update memory fact returns 404 when not found."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            with patch(
                "app.gateway.routers.memory.update_memory_fact",
                side_effect=KeyError("notfound"),
            ):
                resp = client.patch(
                    "/api/memory/facts/nonexistent",
                    json={"content": "Updated"},
                )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- GET /api/memory/export
# ---------------------------------------------------------------------------


class TestExportMemory:
    """Tests for GET /api/memory/export."""

    def test_export_memory_returns_json(self):
        """Export memory returns JSON data."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.get("/api/memory/export")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Tests -- POST /api/memory/import
# ---------------------------------------------------------------------------


class TestImportMemory:
    """Tests for POST /api/memory/import."""

    def test_import_memory_success(self):
        """Import memory succeeds with valid data."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.post(
                "/api/memory/import",
                json={"facts": [{"id": "f1", "content": "Imported fact"}]},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests -- GET /api/memory/config
# ---------------------------------------------------------------------------


class TestGetMemoryConfig:
    """Tests for GET /api/memory/config."""

    def test_get_memory_config(self):
        """Get memory config returns configuration."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.get("/api/memory/config")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "enabled" in data


# ---------------------------------------------------------------------------
# Tests -- GET /api/memory/status
# ---------------------------------------------------------------------------


class TestGetMemoryStatus:
    """Tests for GET /api/memory/status."""

    def test_get_memory_status(self):
        """Get memory status returns config + data status."""
        app = _make_app()
        stack, _ = _apply_patches()
        with TestClient(app) as client, stack:
            resp = client.get("/api/memory/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data or "data" in data
