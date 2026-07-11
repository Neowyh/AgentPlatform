"""E2E tests for the agents router (backend/app/gateway/routers/agents.py).

Covers all 11 agent endpoints with real HTTP stack:
- GET /api/agents
- GET /api/agents/check
- GET /api/agents/{name}
- POST /api/agents
- PUT /api/agents/{name}
- DELETE /api/agents/{name}
- POST /api/agents/{name}/export
- POST /api/agents/import
- GET /api/agents/{name}/stats
- GET /api/user-profile
- PUT /api/user-profile
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.routers.agents import router as agents_router
from ideer.config.agents_api_config import AgentsApiConfig

pytestmark = pytest.mark.no_auto_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: str = "user-1", role: str = "user") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = None
    user.disabled = False
    return user


def _make_app(role: str = "user") -> tuple:
    user = _make_user(role=role)
    app = make_authed_test_app()
    app.include_router(agents_router)

    async def _stub():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub
    app.dependency_overrides[get_optional_rbac_user] = _stub
    return app, user


def _mock_agent_config(name: str = "test-agent", description: str = "Test") -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.description = description
    agent.model = None
    agent.tool_groups = None
    agent.skills = None
    agent.visibility = "private"
    agent.owner_id = "user-1"
    agent.department_id = None
    return agent


# ---------------------------------------------------------------------------
# Common patch targets
# ---------------------------------------------------------------------------

_API_CONFIG_PATCH = "app.gateway.routers.agents.get_agents_api_config"
_USER_ID_PATCH = "app.gateway.routers.agents.get_effective_user_id"
_PATHS_PATCH = "app.gateway.routers.agents.get_paths"
_LIST_PATCH = "app.gateway.routers.agents.list_custom_agents"
_LOAD_CONFIG_PATCH = "app.gateway.routers.agents.load_agent_config"
_LOAD_SOUL_PATCH = "app.gateway.routers.agents.load_agent_soul"
_SHARED_PATCH = "app.gateway.routers.agents._is_shared_only"
_META_PATCH = "app.gateway.routers.agents._load_agent_meta"


def _patch_agents_api_enabled():
    return patch(_API_CONFIG_PATCH, return_value=AgentsApiConfig(enabled=True))


# ---------------------------------------------------------------------------
# Tests — GET /api/agents
# ---------------------------------------------------------------------------


class TestListAgents:
    """Tests for GET /api/agents."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LIST_PATCH, return_value=[])
    def test_list_agents_returns_list(self, mock_list, mock_uid, mock_cfg):
        """List agents returns a list."""
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/agents")
        assert resp.status_code == 200
        assert isinstance(resp.json().get("agents", []), list)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LIST_PATCH)
    @patch(_SHARED_PATCH, return_value=False)
    @patch(_LOAD_SOUL_PATCH, return_value="# Test")
    def test_list_agents_with_results(self, mock_soul, mock_shared, mock_list, mock_uid, mock_cfg):
        """List agents returns agent data."""
        mock_list.return_value = [_mock_agent_config()]
        app, _ = _make_app()
        with TestClient(app) as client:
            with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
                resp = client.get("/api/agents")
        assert resp.status_code == 200
        assert len(resp.json().get("agents", [])) >= 1


# ---------------------------------------------------------------------------
# Tests — GET /api/agents/check
# ---------------------------------------------------------------------------


class TestCheckAgentName:
    """Tests for GET /api/agents/check."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_check_available_name(self, mock_paths, mock_uid, mock_cfg):
        """Check returns available=True for unused name."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/agents/check?name=new-agent")
        assert resp.status_code == 200
        assert resp.json().get("available") is True

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_check_unavailable_name(self, mock_paths, mock_uid, mock_cfg):
        """Check returns available=False for existing name."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=True))
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/agents/check?name=existing")
        assert resp.status_code == 200
        assert resp.json().get("available") is False


# ---------------------------------------------------------------------------
# Tests — GET /api/agents/{name}
# ---------------------------------------------------------------------------


class TestGetAgent:
    """Tests for GET /api/agents/{name}."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_SHARED_PATCH, return_value=False)
    @patch(_LOAD_SOUL_PATCH, return_value="# Test")
    def test_get_agent_found(self, mock_soul, mock_shared, mock_load, mock_uid, mock_cfg):
        """Get agent returns agent details."""
        mock_load.return_value = _mock_agent_config()
        app, _ = _make_app()
        with TestClient(app) as client:
            with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
                resp = client.get("/api/agents/test-agent")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-agent"

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, return_value=None)
    def test_get_agent_not_found(self, mock_load, mock_uid, mock_cfg):
        """Get agent returns 404 when not found."""
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/agents/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — POST /api/agents
# ---------------------------------------------------------------------------


class TestCreateAgent:
    """Tests for POST /api/agents."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_LOAD_SOUL_PATCH, return_value="# New")
    def test_create_agent_success(self, mock_soul, mock_load, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Create agent succeeds with valid data."""
        agent_dir = tmp_path / "user-1" / "agents" / "new-agent"
        legacy_dir = tmp_path / "agents" / "new-agent"

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths_obj.agent_dir.return_value = legacy_dir
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config(name="new-agent")

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/agents",
                json={"name": "new-agent", "description": "New", "soul": "# New"},
            )
        assert resp.status_code in (200, 201)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_create_agent_duplicate(self, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Create agent fails with duplicate name."""
        legacy_dir = tmp_path / "agents" / "existing"
        legacy_dir.mkdir(parents=True)

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = tmp_path / "user-1" / "agents" / "existing"
        mock_paths_obj.agent_dir.return_value = legacy_dir
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/agents",
                json={"name": "existing", "description": "Dup", "soul": "# Dup"},
            )
        assert resp.status_code in (400, 409)


# ---------------------------------------------------------------------------
# Tests — PUT /api/agents/{name}
# ---------------------------------------------------------------------------


class TestUpdateAgent:
    """Tests for PUT /api/agents/{name}."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_SHARED_PATCH, return_value=False)
    @patch(_LOAD_SOUL_PATCH, return_value="# Updated")
    def test_update_agent_success(self, mock_soul, mock_shared, mock_load, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Update agent succeeds."""
        agent_dir = tmp_path / "user-1" / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "config.yaml").write_text("name: test-agent\n")
        (agent_dir / "SOUL.md").write_text("# Test\n")

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config()

        app, _ = _make_app()
        with TestClient(app) as client:
            with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
                resp = client.put("/api/agents/test-agent", json={"description": "Updated", "version": 1})
        assert resp.status_code == 200

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, side_effect=FileNotFoundError)
    def test_update_agent_not_found(self, mock_load, mock_uid, mock_cfg):
        """Update agent returns 404 when not found."""
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put("/api/agents/nonexistent", json={"description": "X", "version": 1})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — DELETE /api/agents/{name}
# ---------------------------------------------------------------------------


class TestDeleteAgent:
    """Tests for DELETE /api/agents/{name}."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_delete_agent_success(self, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Delete agent succeeds."""
        agent_dir = tmp_path / "user-1" / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
                resp = client.delete("/api/agents/test-agent")
        assert resp.status_code in (200, 204)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_delete_agent_not_found(self, mock_paths, mock_uid, mock_cfg):
        """Delete agent returns 404 when not found."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.delete("/api/agents/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — POST /api/agents/{name}/export
# ---------------------------------------------------------------------------


class TestExportAgent:
    """Tests for POST /api/agents/{name}/export."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_SHARED_PATCH, return_value=False)
    def test_export_agent_success(self, mock_shared, mock_load, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Export agent returns JSON bundle."""
        agent_dir = tmp_path / "user-1" / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "config.yaml").write_text("name: test-agent\ndescription: Test\n")
        (agent_dir / "SOUL.md").write_text("# Test")

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config()

        app, _ = _make_app()
        with TestClient(app) as client:
            with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
                resp = client.post("/api/agents/test-agent/export")
        assert resp.status_code == 200
        assert "name" in resp.json()

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, return_value=None)
    def test_export_agent_not_found(self, mock_load, mock_uid, mock_cfg):
        """Export agent returns 404 when not found."""
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post("/api/agents/nonexistent/export")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — POST /api/agents/import
# ---------------------------------------------------------------------------


class TestImportAgent:
    """Tests for POST /api/agents/import."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_LOAD_SOUL_PATCH, return_value="# Imported")
    def test_import_agent_success(self, mock_soul, mock_load, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Import agent succeeds with valid bundle."""
        agent_dir = tmp_path / "user-1" / "agents" / "imported"

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config(name="imported")

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/agents/import",
                json={"name": "imported", "config": {"name": "imported"}, "soul_md": "# Import"},
            )
        assert resp.status_code in (200, 201)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_import_agent_invalid(self, mock_paths, mock_uid, mock_cfg):
        """Import agent fails with invalid data."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post("/api/agents/import", json={"invalid": "data"})
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Tests — GET /api/agents/{name}/stats
# ---------------------------------------------------------------------------


class TestGetAgentStats:
    """Tests for GET /api/agents/{name}/stats."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_SHARED_PATCH, return_value=False)
    def test_get_agent_stats(self, mock_shared, mock_load, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Get agent stats returns statistics."""
        agent_dir = tmp_path / "user-1" / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "config.yaml").write_text("name: test-agent\n")
        (agent_dir / "SOUL.md").write_text("# Test\n")

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config()

        app, _ = _make_app()
        with TestClient(app) as client:
            with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
                resp = client.get("/api/agents/test-agent/stats")
        assert resp.status_code == 200

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, return_value=None)
    def test_get_agent_stats_not_found(self, mock_load, mock_uid, mock_cfg):
        """Get agent stats returns 404 when not found."""
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/agents/nonexistent/stats")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — User Profile
# ---------------------------------------------------------------------------


class TestUserProfile:
    """Tests for GET/PUT /api/user-profile."""

    @_patch_agents_api_enabled()
    @patch(_PATHS_PATCH)
    def test_get_user_profile(self, mock_paths, mock_cfg, tmp_path):
        """Get user profile returns content."""
        user_md = tmp_path / "USER.md"
        user_md.write_text("# Profile")

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_md_file = user_md
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/user-profile")
        assert resp.status_code == 200

    @_patch_agents_api_enabled()
    @patch(_PATHS_PATCH)
    def test_update_user_profile(self, mock_paths, mock_cfg, tmp_path):
        """Update user profile succeeds."""
        user_md = tmp_path / "USER.md"

        mock_paths_obj = MagicMock()
        mock_paths_obj.base_dir = tmp_path
        mock_paths_obj.user_md_file = user_md
        mock_paths.return_value = mock_paths_obj

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put("/api/user-profile", json={"content": "# Updated"})
        assert resp.status_code == 200
