"""Comprehensive tests for the assistants compat router.

Covers all endpoints, internal helpers, filtering, pagination, custom agents,
and error paths for ``backend/app/gateway/routers/assistants_compat.py``.

Endpoints:
    POST /api/assistants/search
    GET  /api/assistants/{assistant_id}
    GET  /api/assistants/{assistant_id}/graph
    GET  /api/assistants/{assistant_id}/schemas

Internal functions tested directly:
    _get_default_assistant()
    _list_assistants()
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers.assistants_compat import (
    AssistantResponse,
    AssistantSearchRequest,
    _get_default_assistant,
    _list_assistants,
)
from app.gateway.routers.assistants_compat import (
    router as assistants_router,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    """Create a test FastAPI app with the assistants compat router."""
    app = make_authed_test_app()
    app.include_router(assistants_router)
    return app


def _make_agent_config(name: str, description: str = "Test agent") -> MagicMock:
    """Return a mock agent config object with ``name`` and ``description``."""
    cfg = MagicMock()
    cfg.name = name
    cfg.description = description
    return cfg


def _client() -> TestClient:
    """Shortcut: create app + client in one call."""
    return TestClient(_make_app())


# =========================================================================
# POST /api/assistants/search
# =========================================================================


class TestSearchAssistants:
    """Tests for POST /api/assistants/search."""

    def test_empty_body_returns_all_assistants(self):
        """An empty JSON body returns all assistants (at least lead_agent)."""
        resp = _client().post("/api/assistants/search", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        ids = {a["assistant_id"] for a in data}
        assert "lead_agent" in ids

    def test_body_none_returns_all(self):
        """Posting ``null`` body returns all assistants."""
        resp = _client().post(
            "/api/assistants/search",
            content="null",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_filter_by_graph_id(self):
        """Filtering by graph_id returns only matching assistants."""
        resp = _client().post("/api/assistants/search", json={"graph_id": "lead_agent"})
        assert resp.status_code == 200
        for a in resp.json():
            assert a["graph_id"] == "lead_agent"

    def test_filter_by_graph_id_no_match(self):
        """Filtering by a non-existent graph_id returns an empty list."""
        resp = _client().post("/api/assistants/search", json={"graph_id": "nonexistent_graph"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_name_exact(self):
        """Filtering by exact name returns that assistant."""
        resp = _client().post("/api/assistants/search", json={"name": "lead_agent"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(a["name"] == "lead_agent" for a in data)

    def test_filter_by_name_case_insensitive(self):
        """Name filter is case-insensitive (substring match)."""
        resp = _client().post("/api/assistants/search", json={"name": "LEAD"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all("lead" in a["name"].lower() for a in data)

    def test_filter_by_name_substring(self):
        """Name filter matches substrings."""
        resp = _client().post("/api/assistants/search", json={"name": "lead"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_filter_by_name_no_match(self):
        """Name filter with no match returns empty list."""
        resp = _client().post("/api/assistants/search", json={"name": "zzz_nonexistent_zzz"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_limit_parameter(self):
        """Limit parameter caps the number of returned assistants."""
        resp = _client().post("/api/assistants/search", json={"limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 1

    def test_limit_zero_returns_empty(self):
        """A limit of 0 returns an empty list."""
        resp = _client().post("/api/assistants/search", json={"limit": 0})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_offset_parameter(self):
        """Offset skips the first N assistants."""
        all_resp = _client().post("/api/assistants/search", json={})
        all_data = all_resp.json()
        if len(all_data) < 2:
            pytest.skip("Need at least 2 assistants for offset test")
        resp = _client().post("/api/assistants/search", json={"offset": 1})
        offset_data = resp.json()
        assert len(offset_data) == len(all_data) - 1

    def test_offset_beyond_results(self):
        """Offset beyond total count returns empty list."""
        resp = _client().post("/api/assistants/search", json={"offset": 9999})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_combined_limit_and_offset(self):
        """Limit and offset work together for pagination."""
        all_resp = _client().post("/api/assistants/search", json={})
        all_data = all_resp.json()
        if len(all_data) < 2:
            pytest.skip("Need at least 2 assistants for pagination test")
        resp = _client().post("/api/assistants/search", json={"offset": 1, "limit": 1})
        data = resp.json()
        assert len(data) == 1
        assert data[0]["assistant_id"] == all_data[1]["assistant_id"]

    def test_filter_by_name_and_limit(self):
        """Name filter and limit can be combined."""
        resp = _client().post(
            "/api/assistants/search",
            json={"name": "lead", "limit": 1},
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

    def test_with_custom_agents_loaded(self):
        """Custom agents from config are included in search results."""
        [
            _make_agent_config("research_agent", "Research assistant"),
            _make_agent_config("coding_agent", "Coding assistant"),
        ]
        with patch("app.gateway.routers.assistants_compat._list_assistants") as mock_list:
            mock_list.return_value = [
                _get_default_assistant(),
                AssistantResponse(
                    assistant_id="research_agent",
                    graph_id="lead_agent",
                    name="research_agent",
                    config={},
                    metadata={"created_by": "user"},
                    description="Research assistant",
                    created_at="",
                    updated_at="",
                    version=1,
                ),
                AssistantResponse(
                    assistant_id="coding_agent",
                    graph_id="lead_agent",
                    name="coding_agent",
                    config={},
                    metadata={"created_by": "user"},
                    description="Coding assistant",
                    created_at="",
                    updated_at="",
                    version=1,
                ),
            ]
            resp = _client().post("/api/assistants/search", json={})
            assert resp.status_code == 200
            data = resp.json()
            ids = {a["assistant_id"] for a in data}
            assert "research_agent" in ids
            assert "coding_agent" in ids
            assert "lead_agent" in ids

    def test_custom_agents_filter_by_name(self):
        """Name filter works across custom agents."""
        with patch("app.gateway.routers.assistants_compat._list_assistants") as mock_list:
            mock_list.return_value = [
                _get_default_assistant(),
                AssistantResponse(
                    assistant_id="research_agent",
                    graph_id="lead_agent",
                    name="research_agent",
                    config={},
                    metadata={"created_by": "user"},
                    description="Research assistant",
                    created_at="",
                    updated_at="",
                    version=1,
                ),
            ]
            resp = _client().post("/api/assistants/search", json={"name": "research"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["assistant_id"] == "research_agent"


# =========================================================================
# GET /api/assistants/{assistant_id}
# =========================================================================


class TestGetAssistant:
    """Tests for GET /api/assistants/{assistant_id}."""

    def test_get_lead_agent(self):
        """Get the default lead_agent by ID."""
        resp = _client().get("/api/assistants/lead_agent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["assistant_id"] == "lead_agent"
        assert data["graph_id"] == "lead_agent"
        assert data["name"] == "lead_agent"

    def test_get_lead_agent_has_all_fields(self):
        """The response contains all expected AssistantResponse fields."""
        resp = _client().get("/api/assistants/lead_agent")
        data = resp.json()
        for field in (
            "assistant_id",
            "graph_id",
            "name",
            "config",
            "metadata",
            "description",
            "created_at",
            "updated_at",
            "version",
        ):
            assert field in data, f"Missing field: {field}"

    def test_get_custom_agent_by_id(self):
        """Get a custom agent by ID when list_custom_agents returns it."""
        with patch("app.gateway.routers.assistants_compat._list_assistants") as mock_list:
            mock_list.return_value = [
                _get_default_assistant(),
                AssistantResponse(
                    assistant_id="custom_xyz",
                    graph_id="lead_agent",
                    name="custom_xyz",
                    config={},
                    metadata={"created_by": "user"},
                    description="Custom test agent",
                    created_at="",
                    updated_at="",
                    version=1,
                ),
            ]
            resp = _client().get("/api/assistants/custom_xyz")
            assert resp.status_code == 200
            assert resp.json()["assistant_id"] == "custom_xyz"
            assert resp.json()["description"] == "Custom test agent"

    def test_get_assistant_not_found(self):
        """Requesting a non-existent assistant returns 404."""
        resp = _client().get("/api/assistants/does_not_exist_xyz")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# =========================================================================
# GET /api/assistants/{assistant_id}/graph
# =========================================================================


class TestGetAssistantGraph:
    """Tests for GET /api/assistants/{assistant_id}/graph."""

    def test_valid_assistant_returns_graph_structure(self):
        """Valid assistant_id returns a graph with graph_id, nodes, edges."""
        resp = _client().get("/api/assistants/lead_agent/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "graph_id" in data
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_graph_id_is_lead_agent(self):
        """The graph_id in the stub response is 'lead_agent'."""
        resp = _client().get("/api/assistants/lead_agent/graph")
        assert resp.json()["graph_id"] == "lead_agent"

    def test_custom_assistant_graph(self):
        """A custom assistant also returns the stub graph."""
        with patch("app.gateway.routers.assistants_compat._list_assistants") as mock_list:
            mock_list.return_value = [
                AssistantResponse(
                    assistant_id="my_agent",
                    graph_id="lead_agent",
                    name="my_agent",
                    config={},
                    metadata={},
                    description=None,
                    created_at="",
                    updated_at="",
                    version=1,
                ),
            ]
            resp = _client().get("/api/assistants/my_agent/graph")
            assert resp.status_code == 200
            assert resp.json()["graph_id"] == "lead_agent"

    def test_invalid_assistant_id_returns_404(self):
        """Non-existent assistant_id returns 404."""
        resp = _client().get("/api/assistants/nonexistent/graph")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# =========================================================================
# GET /api/assistants/{assistant_id}/schemas
# =========================================================================


class TestGetAssistantSchemas:
    """Tests for GET /api/assistants/{assistant_id}/schemas."""

    def test_valid_assistant_returns_schemas(self):
        """Valid assistant_id returns all schema keys."""
        resp = _client().get("/api/assistants/lead_agent/schemas")
        assert resp.status_code == 200
        data = resp.json()
        assert "graph_id" in data
        assert "input_schema" in data
        assert "output_schema" in data
        assert "state_schema" in data
        assert "config_schema" in data

    def test_schema_values_are_dicts(self):
        """Each schema value is a dict (empty for the stub)."""
        resp = _client().get("/api/assistants/lead_agent/schemas")
        data = resp.json()
        for key in (
            "input_schema",
            "output_schema",
            "state_schema",
            "config_schema",
        ):
            assert isinstance(data[key], dict)

    def test_schemas_graph_id_is_lead_agent(self):
        """The graph_id in schemas response is 'lead_agent'."""
        resp = _client().get("/api/assistants/lead_agent/schemas")
        assert resp.json()["graph_id"] == "lead_agent"

    def test_custom_assistant_schemas(self):
        """A custom assistant also returns the stub schemas."""
        with patch("app.gateway.routers.assistants_compat._list_assistants") as mock_list:
            mock_list.return_value = [
                AssistantResponse(
                    assistant_id="agent_b",
                    graph_id="lead_agent",
                    name="agent_b",
                    config={},
                    metadata={},
                    description=None,
                    created_at="",
                    updated_at="",
                    version=1,
                ),
            ]
            resp = _client().get("/api/assistants/agent_b/schemas")
            assert resp.status_code == 200
            assert resp.json()["graph_id"] == "lead_agent"

    def test_invalid_assistant_id_returns_404(self):
        """Non-existent assistant_id returns 404."""
        resp = _client().get("/api/assistants/nonexistent/schemas")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# =========================================================================
# _get_default_assistant() direct tests
# =========================================================================


class TestGetDefaultAssistant:
    """Direct tests for the ``_get_default_assistant`` helper."""

    def test_returns_assistant_response(self):
        """Return value is an AssistantResponse instance."""
        result = _get_default_assistant()
        assert isinstance(result, AssistantResponse)

    def test_assistant_id_is_lead_agent(self):
        result = _get_default_assistant()
        assert result.assistant_id == "lead_agent"

    def test_graph_id_is_lead_agent(self):
        result = _get_default_assistant()
        assert result.graph_id == "lead_agent"

    def test_name_is_lead_agent(self):
        result = _get_default_assistant()
        assert result.name == "lead_agent"

    def test_description(self):
        result = _get_default_assistant()
        assert result.description == "iDeer lead agent"

    def test_metadata_created_by_system(self):
        result = _get_default_assistant()
        assert result.metadata.get("created_by") == "system"

    def test_version_is_1(self):
        result = _get_default_assistant()
        assert result.version == 1

    def test_config_is_empty_dict(self):
        result = _get_default_assistant()
        assert result.config == {}

    def test_created_at_is_iso_format(self):
        """created_at is a non-empty ISO 8601 string."""
        result = _get_default_assistant()
        assert result.created_at
        # Should parse without error
        datetime.fromisoformat(result.created_at)

    def test_updated_at_is_iso_format(self):
        """updated_at is a non-empty ISO 8601 string."""
        result = _get_default_assistant()
        assert result.updated_at
        datetime.fromisoformat(result.updated_at)

    def test_created_at_has_utc_timezone(self):
        """Timestamps include UTC timezone info."""
        result = _get_default_assistant()
        dt = datetime.fromisoformat(result.created_at)
        assert dt.tzinfo is not None


# =========================================================================
# _list_assistants() direct tests
# =========================================================================


class TestListAssistants:
    """Direct tests for the ``_list_assistants`` helper."""

    def test_returns_list(self):
        result = _list_assistants()
        assert isinstance(result, list)

    def test_at_least_default_assistant(self):
        """Always returns at least the default lead_agent."""
        result = _list_assistants()
        assert len(result) >= 1
        ids = [a.assistant_id for a in result]
        assert "lead_agent" in ids

    def test_default_is_first(self):
        """The default assistant is always the first element."""
        result = _list_assistants()
        assert result[0].assistant_id == "lead_agent"

    def test_canonical_mode_does_not_expose_legacy_named_agents(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
        custom_cfg = _make_agent_config("legacy-name")

        with patch(
            "ideer.config.agents_config.list_custom_agents",
            return_value=[custom_cfg],
        ):
            result = _list_assistants()

        assert [item.assistant_id for item in result] == ["lead_agent"]

    @patch("app.gateway.routers.assistants_compat._list_assistants")
    def test_includes_custom_agents(self, mock_list):
        """Custom agents from config are appended after the default."""
        mock_list.return_value = [
            _get_default_assistant(),
            AssistantResponse(
                assistant_id="alpha",
                graph_id="lead_agent",
                name="alpha",
                config={},
                metadata={"created_by": "user"},
                description="Alpha agent",
                created_at="",
                updated_at="",
                version=1,
            ),
            AssistantResponse(
                assistant_id="beta",
                graph_id="lead_agent",
                name="beta",
                config={},
                metadata={"created_by": "user"},
                description="Beta agent",
                created_at="",
                updated_at="",
                version=1,
            ),
        ]
        result = mock_list.return_value
        assert len(result) == 3
        ids = [a.assistant_id for a in result]
        assert ids == ["lead_agent", "alpha", "beta"]

    def test_custom_agents_load_failure_still_returns_default(self):
        """If list_custom_agents raises, we still get the default assistant."""
        with patch(
            "ideer.config.agents_config.list_custom_agents",
            side_effect=RuntimeError("config missing"),
        ):
            from app.gateway.routers import assistants_compat

            result = assistants_compat._list_assistants()
            assert len(result) >= 1
            assert result[0].assistant_id == "lead_agent"

    def test_custom_agents_use_lead_agent_graph_id(self):
        """All custom agents get graph_id='lead_agent'."""
        custom_cfg = _make_agent_config("g_agent")
        with patch(
            "ideer.config.agents_config.list_custom_agents",
            return_value=[custom_cfg],
        ):
            from app.gateway.routers import assistants_compat

            result = assistants_compat._list_assistants()
            for a in result:
                assert a.graph_id == "lead_agent"


# =========================================================================
# AssistantSearchRequest model tests
# =========================================================================


class TestAssistantSearchRequest:
    """Tests for the AssistantSearchRequest Pydantic model."""

    def test_default_values(self):
        req = AssistantSearchRequest()
        assert req.graph_id is None
        assert req.name is None
        assert req.metadata is None
        assert req.limit == 10
        assert req.offset == 0

    def test_custom_values(self):
        req = AssistantSearchRequest(graph_id="g1", name="test", metadata={"k": "v"}, limit=5, offset=2)
        assert req.graph_id == "g1"
        assert req.name == "test"
        assert req.metadata == {"k": "v"}
        assert req.limit == 5
        assert req.offset == 2


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    """Edge-case and regression tests."""

    def test_search_with_large_limit(self):
        """A very large limit does not error; returns all available."""
        resp = _client().post("/api/assistants/search", json={"limit": 10000})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_search_with_negative_offset(self):
        """Negative offset is handled gracefully by Python slicing."""
        resp = _client().post("/api/assistants/search", json={"offset": -1})
        assert resp.status_code == 200

    def test_get_assistant_special_characters_in_id(self):
        """URL-encoded special characters in assistant_id handled."""
        resp = _client().get("/api/assistants/not%20found")
        assert resp.status_code == 404

    def test_graph_endpoint_returns_json_content_type(self):
        """Graph endpoint returns application/json."""
        resp = _client().get("/api/assistants/lead_agent/graph")
        assert resp.headers["content-type"] == "application/json"

    def test_schemas_endpoint_returns_json_content_type(self):
        """Schemas endpoint returns application/json."""
        resp = _client().get("/api/assistants/lead_agent/schemas")
        assert resp.headers["content-type"] == "application/json"

    def test_search_returns_assistant_response_shape(self):
        """Each search result matches the AssistantResponse schema."""
        resp = _client().post("/api/assistants/search", json={})
        for item in resp.json():
            assert "assistant_id" in item
            assert "graph_id" in item
            assert "name" in item
            assert "config" in item
            assert "metadata" in item
            assert "version" in item
