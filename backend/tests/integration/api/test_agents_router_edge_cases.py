"""Additional tests for the agents router (backend/app/gateway/routers/agents.py).

Covers gaps not addressed by existing test files:
- _validate_agent_name: valid/invalid names
- _normalize_agent_name: case normalization
- _require_agents_api_enabled: disabled API returns 403
- list_agents: error handling
- get_agent: 404, generic exception
- create_agent: invalid name
- update_agent: shared read-only template denial
- delete_agent: shared read-only template denial
- export_agent: not found
- import_agent: duplicate, invalid name
- get_user_profile: no USER.md, empty file, error handling
- update_user_profile: error handling
- check_agent_name: invalid name, taken in shared
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.routers.agents import (
    _normalize_agent_name,
    _validate_agent_name,
)
from app.gateway.routers.agents import (
    router as agents_router,
)
from ideer.config.agents_api_config import AgentsApiConfig
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_API_PATCH = "app.gateway.routers.agents.get_agents_api_config"
_UID_PATCH = "app.gateway.routers.agents.get_effective_user_id"
_PATHS_PATCH = "app.gateway.routers.agents.get_paths"
_LIST_PATCH = "app.gateway.routers.agents.list_custom_agents"
_LOAD_PATCH = "app.gateway.routers.agents.load_agent_config"
_LOAD_SOUL_PATCH = "app.gateway.routers.agents.load_agent_soul"
_SHARED_PATCH = "app.gateway.routers.agents._is_shared_only"
_META_PATCH = "app.gateway.routers.agents._load_agent_meta"


def _make_rbac_user(
    user_id: str = "user-1",
    role: str = UserRole.USER,
    department_id: str | None = None,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = False
    return user


def _make_app(current_user=None):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(agents_router)
    user = current_user or _make_rbac_user()

    async def _stub_current():
        return user

    async def _stub_optional():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current
    app.dependency_overrides[get_optional_rbac_user] = _stub_optional
    return TestClient(app, raise_server_exceptions=False)


def _mock_agent(name="test-agent", desc="A test agent"):
    agent = MagicMock()
    agent.name = name
    agent.description = desc
    agent.model = None
    agent.tool_groups = None
    agent.skills = None
    return agent


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestValidateAgentName:
    def test_valid_name(self):
        _validate_agent_name("my-agent-123")

    def test_invalid_name_with_spaces(self):
        with pytest.raises(HTTPException) as exc:
            _validate_agent_name("my agent")
        assert exc.value.status_code == 422

    def test_invalid_name_with_special_chars(self):
        with pytest.raises(HTTPException) as exc:
            _validate_agent_name("agent@name")
        assert exc.value.status_code == 422


class TestNormalizeAgentName:
    def test_lowercases(self):
        assert _normalize_agent_name("MyAgent") == "myagent"

    def test_preserves_already_lowercase(self):
        assert _normalize_agent_name("my-agent") == "my-agent"


# ---------------------------------------------------------------------------
# Endpoint tests using context managers for patches
# ---------------------------------------------------------------------------


class TestRequireAgentsApiEnabled:
    def test_list_agents_disabled(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=False)):
            client = _make_app()
            resp = client.get("/api/agents")
            assert resp.status_code == 403
            assert "AGENTS_API_DISABLED" in str(resp.json()["detail"])

    def test_get_agent_disabled(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=False)):
            client = _make_app()
            resp = client.get("/api/agents/some-agent")
            assert resp.status_code == 403

    def test_check_name_disabled(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=False)):
            client = _make_app()
            resp = client.get("/api/agents/check?name=test")
            assert resp.status_code == 403

    def test_create_agent_disabled(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=False)):
            client = _make_app()
            resp = client.post("/api/agents", json={"name": "test", "soul": ""})
            assert resp.status_code == 403

    def test_delete_agent_disabled(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=False)):
            client = _make_app()
            resp = client.delete("/api/agents/test")
            assert resp.status_code == 403

    def test_user_profile_disabled(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=False)):
            client = _make_app()
            resp = client.get("/api/user-profile")
            assert resp.status_code == 403


class TestListAgents:
    def test_list_empty(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_LIST_PATCH, return_value=[]):
            client = _make_app()
            resp = client.get("/api/agents")
            assert resp.status_code == 200
            assert resp.json()["agents"] == []

    def test_list_error_returns_500(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_LIST_PATCH, side_effect=RuntimeError("db error")):
            client = _make_app()
            resp = client.get("/api/agents")
            assert resp.status_code == 500


class TestGetAgent:
    def test_not_found(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_LOAD_PATCH, side_effect=FileNotFoundError):
            client = _make_app()
            resp = client.get("/api/agents/nonexistent")
            assert resp.status_code == 404

    def test_generic_exception(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_LOAD_PATCH, side_effect=Exception("unexpected")):
            client = _make_app()
            resp = client.get("/api/agents/test-agent")
            assert resp.status_code == 500

    def test_visibility_denied_for_private_agent(self):
        """Non-owner cannot see a private agent."""
        other_user = _make_rbac_user(user_id="user-2", role=UserRole.USER)
        with (
            patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)),
            patch(_UID_PATCH, return_value="user-2"),
            patch(_LOAD_PATCH, return_value=_mock_agent()),
            patch(_SHARED_PATCH, return_value=False),
            patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})),
            patch(_LOAD_SOUL_PATCH, return_value=""),
        ):
            client = _make_app(current_user=other_user)
            resp = client.get("/api/agents/test-agent")
            assert resp.status_code == 404


class TestCreateAgent:
    def test_invalid_name(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"):
            client = _make_app()
            resp = client.post("/api/agents", json={"name": "invalid name!", "soul": ""})
            assert resp.status_code == 422

    def test_visibility_forced_to_private(self):
        """Visibility is always forced to private on create."""
        with (
            patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)),
            patch(_UID_PATCH, return_value="user-1"),
            patch(_PATHS_PATCH) as mock_paths,
            patch(_LOAD_PATCH, return_value=_mock_agent()),
        ):
            paths_obj = MagicMock()
            paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            mock_paths.return_value = paths_obj

            client = _make_app(current_user=_make_rbac_user(role=UserRole.USER))
            resp = client.post("/api/agents", json={"name": "test-agent", "soul": "", "visibility": "public"})
            assert resp.status_code in (200, 201)
            data = resp.json()
            assert data.get("visibility") in (None, "private")


class TestUpdateAgent:
    def test_shared_read_only_agent(self):
        """Returns 409 when trying to update a shared read-only template."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_LOAD_PATCH, return_value=_mock_agent("shared-agent")), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.put("/api/agents/shared-agent", json={"description": "updated", "version": 1})
            assert resp.status_code == 409
            assert "read-only" in resp.json()["detail"]

    def test_visibility_ignored_in_update(self):
        """Visibility field is ignored in update endpoint."""
        with (
            patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)),
            patch(_UID_PATCH, return_value="user-1"),
            patch(_LOAD_PATCH, return_value=_mock_agent()),
            patch(_PATHS_PATCH) as mock_paths,
            patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})),
            patch(_SHARED_PATCH, return_value=False),
        ):
            paths_obj = MagicMock()
            paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_paths.return_value = paths_obj

            client = _make_app(current_user=_make_rbac_user(role=UserRole.USER))
            resp = client.put("/api/agents/test-agent", json={"visibility": "public", "version": 1})
            assert resp.status_code == 200
            assert resp.json().get("visibility") in (None, "private")


class TestDeleteAgent:
    def test_shared_read_only_agent(self):
        """Returns 409 when trying to delete a shared read-only template."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.delete("/api/agents/shared-agent")
            assert resp.status_code == 409
            assert "read-only" in resp.json()["detail"]

    def test_delete_not_found(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.delete("/api/agents/nonexistent")
            assert resp.status_code == 404


class TestExportAgent:
    def test_not_found(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_LOAD_PATCH, side_effect=FileNotFoundError):
            client = _make_app()
            resp = client.post("/api/agents/nonexistent/export")
            assert resp.status_code == 404


class TestImportAgent:
    def test_duplicate_agent(self):
        """Returns 409 when importing an agent that already exists."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.post(
                "/api/agents/import",
                json={"name": "existing-agent", "config": {}, "soul": ""},
            )
            assert resp.status_code == 409

    def test_visibility_ignored_in_import(self):
        """Visibility field is ignored in import endpoint (always private)."""
        with (
            patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)),
            patch(_UID_PATCH, return_value="user-1"),
            patch(_PATHS_PATCH) as mock_paths,
            patch(_LOAD_PATCH, return_value=_mock_agent()),
        ):
            paths_obj = MagicMock()
            paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            mock_paths.return_value = paths_obj

            client = _make_app(current_user=_make_rbac_user(role=UserRole.USER))
            resp = client.post(
                "/api/agents/import",
                json={"name": "test-agent", "config": {}, "soul": "", "visibility": "public"},
            )
            assert resp.status_code in (200, 201)
            assert resp.json().get("visibility") in (None, "private")

    def test_invalid_name(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"):
            client = _make_app()
            resp = client.post(
                "/api/agents/import",
                json={"name": "invalid name!", "config": {}, "soul": ""},
            )
            assert resp.status_code == 422


class TestUserProfile:
    def test_get_no_file(self):
        """Returns content=None when USER.md doesn't exist."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.user_md_file = MagicMock(exists=MagicMock(return_value=False))
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.get("/api/user-profile")
            assert resp.status_code == 200
            assert resp.json()["content"] is None

    def test_get_empty_file(self):
        """Returns content=None when USER.md is empty."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.user_md_file = MagicMock(
                exists=MagicMock(return_value=True),
                read_text=MagicMock(return_value="  \n  "),
            )
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.get("/api/user-profile")
            assert resp.status_code == 200
            assert resp.json()["content"] is None

    def test_get_error_returns_500(self):
        """Returns 500 on read error."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.user_md_file = MagicMock(
                exists=MagicMock(return_value=True),
                read_text=MagicMock(side_effect=PermissionError("denied")),
            )
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.get("/api/user-profile")
            assert resp.status_code == 500

    def test_update_error_returns_500(self):
        """Returns 500 on write error."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.base_dir = MagicMock()
            paths_obj.user_md_file = MagicMock(
                write_text=MagicMock(side_effect=PermissionError("denied")),
            )
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.put("/api/user-profile", json={"content": "test"})
            assert resp.status_code == 500


class TestCheckAgentName:
    def test_invalid_name(self):
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"):
            client = _make_app()
            resp = client.get("/api/agents/check?name=invalid name")
            assert resp.status_code == 422

    def test_taken_in_shared(self):
        """Name is taken if it exists in the shared directory."""
        with patch(_API_PATCH, return_value=AgentsApiConfig(enabled=True)), patch(_UID_PATCH, return_value="user-1"), patch(_PATHS_PATCH) as mock_paths:
            paths_obj = MagicMock()
            paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
            paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_paths.return_value = paths_obj

            client = _make_app()
            resp = client.get("/api/agents/check?name=taken-name")
            assert resp.status_code == 200
            assert resp.json()["available"] is False
