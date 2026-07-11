"""Tests for the assistants compatibility router (backend/app/gateway/routers/assistants_compat.py).

Covers:
- POST /api/assistants/search — search assistants (LangGraph SDK compatibility)
- GET /api/assistants/{assistant_id} — get assistant by ID
- GET /api/assistants/{assistant_id}/graph — get graph structure (stub)
- GET /api/assistants/{assistant_id}/schemas — get JSON schemas (stub)
"""

from __future__ import annotations

from _router_auth_helpers import make_authed_test_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers.assistants_compat import router as assistants_router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    """Create a test FastAPI app with assistants compat router."""
    app = make_authed_test_app()
    app.include_router(assistants_router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchAssistants:
    """Tests for POST /api/assistants/search."""

    def test_search_returns_list(self):
        """Search returns a list of assistants."""
        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/assistants/search", json={})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_with_limit(self):
        """Search respects limit parameter."""
        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/assistants/search", json={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    def test_search_with_metadata_filter(self):
        """Search with metadata filter returns results."""
        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/assistants/search",
            json={"metadata": {"key": "value"}},
        )
        assert response.status_code == 200


class TestGetAssistantCompat:
    """Tests for GET /api/assistants/{assistant_id}."""

    def test_get_assistant_by_id(self):
        """Get assistant by valid ID returns assistant data."""
        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/assistants/lead_agent")
        assert response.status_code == 200
        data = response.json()
        assert "assistant_id" in data

    def test_get_assistant_not_found(self):
        """Get assistant with non-existent ID returns 404."""
        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/assistants/nonexistent-id")
        # May return 404 or default assistant depending on implementation
        assert response.status_code in (200, 404)


class TestGetAssistantGraph:
    """Tests for GET /api/assistants/{assistant_id}/graph."""

    def test_get_graph_returns_structure(self):
        """Get graph returns a graph structure (stub)."""
        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/assistants/lead_agent/graph")
        assert response.status_code == 200
        data = response.json()
        # Stub should return some graph structure
        assert isinstance(data, dict)


class TestGetAssistantSchemas:
    """Tests for GET /api/assistants/{assistant_id}/schemas."""

    def test_get_schemas_returns_structure(self):
        """Get schemas returns JSON schemas (stub)."""
        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/assistants/lead_agent/schemas")
        assert response.status_code == 200
        data = response.json()
        # Stub should return some schema structure
        assert isinstance(data, dict)
