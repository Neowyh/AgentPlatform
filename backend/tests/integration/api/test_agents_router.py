"""Tests for the agents router (backend/app/gateway/routers/agents.py).

Covers:
- GET /api/agents — list custom agents (filtered by visibility/RBAC)
- GET /api/agents/check — validate and check agent name availability
- GET /api/agents/{name} — get agent details + SOUL.md
- POST /api/agents — create new custom agent
- PUT /api/agents/{name} — update agent config and/or SOUL.md
- DELETE /api/agents/{name} — delete custom agent
- POST /api/agents/{name}/export — export agent as JSON
- POST /api/agents/import — import agent from JSON
- GET /api/agents/{name}/stats — agent statistics
- GET /api/user-profile — read global USER.md
- PUT /api/user-profile — write global USER.md
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.routers.agents import router as agents_router
from ideer.config.agents_api_config import AgentsApiConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str = "user-1",
    role: str = "user",
    department_id: str | None = None,
) -> MagicMock:
    """Create a mock RBAC user."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = False
    return user


def _make_app(current_user: MagicMock | None = None) -> FastAPI:
    """Create a test FastAPI app with agents router and stubbed auth."""
    app = FastAPI()
    app.include_router(agents_router)

    user = current_user or _make_rbac_user()

    async def _stub_current_user():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current_user
    app.dependency_overrides[get_optional_rbac_user] = _stub_current_user
    return app


def _mock_agent_config(name: str = "test-agent", description: str = "A test agent") -> MagicMock:
    """Create a mock AgentConfig."""
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
    """Patch get_agents_api_config to return enabled=True."""
    return patch(_API_CONFIG_PATCH, return_value=AgentsApiConfig(enabled=True))


# ---------------------------------------------------------------------------
# Tests — List Agents
# ---------------------------------------------------------------------------


class TestListAgents:
    """Tests for GET /api/agents."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LIST_PATCH, return_value=[])
    def test_list_agents_returns_list(self, mock_list, mock_uid, mock_cfg):
        """List agents returns a list of custom agents."""
        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("agents", []), list)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LIST_PATCH)
    @patch(_SHARED_PATCH, return_value=False)
    @patch(_LOAD_SOUL_PATCH, return_value="# Test Agent Soul")
    def test_list_agents_with_results(self, mock_soul, mock_shared, mock_list, mock_uid, mock_cfg):
        """List agents returns agent data when agents exist."""
        mock_list.return_value = [_mock_agent_config()]

        resource = MagicMock(
            resource_id="test-agent",
            visibility="public",
            owner_id="owner-X",
            department_id=None,
            is_favorited=False,
        )
        result = MagicMock()
        result.scalars.return_value.all.return_value = [resource]
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session_factory = MagicMock()
        session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        app = _make_app()
        client = TestClient(app)
        with patch("app.gateway.routers.agents.get_session_factory", return_value=session_factory):
            response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["agents"][0]["name"] == "test-agent"
        assert data["agents"][0]["visibility"] == "public"
        assert data["agents"][0]["owner_id"] == "owner-X"
        result.scalars.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — Check Agent Name
# ---------------------------------------------------------------------------


class TestCheckAgentName:
    """Tests for GET /api/agents/check."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_check_available_name(self, mock_paths, mock_uid, mock_cfg):
        """Check returns available status for unused name."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/agents/check?name=new-agent")
        assert response.status_code == 200
        data = response.json()
        assert data.get("available") is True

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_check_unavailable_name(self, mock_paths, mock_uid, mock_cfg):
        """Check returns unavailable status for existing name."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=True))
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/agents/check?name=existing-agent")
        assert response.status_code == 200
        data = response.json()
        assert data.get("available") is False


# ---------------------------------------------------------------------------
# Tests — Get Agent
# ---------------------------------------------------------------------------


class TestGetAgent:
    """Tests for GET /api/agents/{name}."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_SHARED_PATCH, return_value=False)
    @patch(_LOAD_SOUL_PATCH, return_value="# Test Agent")
    def test_get_agent_found(self, mock_soul, mock_shared, mock_load, mock_uid, mock_cfg):
        """Get agent returns agent details when found."""
        mock_load.return_value = _mock_agent_config()

        app = _make_app()
        client = TestClient(app)
        with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
            response = client.get("/api/agents/test-agent")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-agent"

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, return_value=None)
    def test_get_agent_not_found(self, mock_load, mock_uid, mock_cfg):
        """Get agent returns 404 when not found."""
        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/agents/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Create Agent
# ---------------------------------------------------------------------------


class TestCreateAgent:
    """Tests for POST /api/agents."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_LOAD_SOUL_PATCH, return_value="# New Agent")
    def test_create_agent_success(self, mock_soul, mock_load, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Create agent succeeds with valid data."""
        agent_dir = tmp_path / "user-1" / "agents" / "new-agent"
        legacy_dir = tmp_path / "agents" / "new-agent"

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths_obj.agent_dir.return_value = legacy_dir
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config(name="new-agent")

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/agents",
            json={
                "name": "new-agent",
                "description": "A new agent",
                "soul": "# New Agent",
            },
        )
        assert response.status_code in (200, 201)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_create_agent_duplicate(self, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Create agent fails with duplicate name."""
        agent_dir = tmp_path / "user-1" / "agents" / "existing-agent"
        legacy_dir = tmp_path / "agents" / "existing-agent"
        legacy_dir.mkdir(parents=True)

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths_obj.agent_dir.return_value = legacy_dir
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/agents",
            json={
                "name": "existing-agent",
                "description": "Duplicate",
                "soul": "# Duplicate",
            },
        )
        assert response.status_code in (400, 409)


# ---------------------------------------------------------------------------
# Tests — Update Agent
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
        """Update agent succeeds with valid data."""
        agent_dir = tmp_path / "user-1" / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "config.yaml").write_text("name: test-agent\n")
        (agent_dir / "SOUL.md").write_text("# Test\n")

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config()

        app = _make_app()
        client = TestClient(app)
        with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
            response = client.put(
                "/api/agents/test-agent",
                json={"description": "Updated description", "version": 1},
            )
        assert response.status_code == 200

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, side_effect=FileNotFoundError)
    def test_update_agent_not_found(self, mock_load, mock_uid, mock_cfg):
        """Update agent returns 404 when not found."""
        app = _make_app()
        client = TestClient(app)
        response = client.put(
            "/api/agents/nonexistent",
            json={"description": "Updated", "version": 1},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Delete Agent
# ---------------------------------------------------------------------------


class TestDeleteAgent:
    """Tests for DELETE /api/agents/{name}."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_delete_agent_success(self, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Delete agent succeeds when agent exists."""
        agent_dir = tmp_path / "user-1" / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
            response = client.delete("/api/agents/test-agent")
        assert response.status_code in (200, 204)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_delete_agent_not_found(self, mock_paths, mock_uid, mock_cfg):
        """Delete agent returns 404 when not found."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        response = client.delete("/api/agents/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Export Agent
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
        (agent_dir / "config.yaml").write_text("name: test-agent\ndescription: A test agent\n")
        (agent_dir / "SOUL.md").write_text("# Test")

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config()

        app = _make_app()
        client = TestClient(app)
        with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
            response = client.post("/api/agents/test-agent/export")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, return_value=None)
    def test_export_agent_not_found(self, mock_load, mock_uid, mock_cfg):
        """Export agent returns 404 when not found."""
        app = _make_app()
        client = TestClient(app)
        response = client.post("/api/agents/nonexistent/export")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Import Agent
# ---------------------------------------------------------------------------


class TestImportAgent:
    """Tests for POST /api/agents/import."""

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    @patch(_LOAD_CONFIG_PATCH)
    @patch(_LOAD_SOUL_PATCH, return_value="# Imported")
    def test_import_agent_success(self, mock_soul, mock_load, mock_paths, mock_uid, mock_cfg, tmp_path):
        """Import agent succeeds with valid JSON bundle."""
        agent_dir = tmp_path / "user-1" / "agents" / "imported-agent"

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_agent_dir.return_value = agent_dir
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        mock_load.return_value = _mock_agent_config(name="imported-agent")

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/agents/import",
            json={
                "name": "imported-agent",
                "config": {"name": "imported-agent"},
                "soul_md": "# Imported",
                "metadata": {},
            },
        )
        assert response.status_code in (200, 201)

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_PATHS_PATCH)
    def test_import_agent_invalid(self, mock_paths, mock_uid, mock_cfg):
        """Import agent fails with invalid data."""
        mock_paths_obj = MagicMock()
        mock_paths_obj.agent_dir.return_value = MagicMock(exists=MagicMock(return_value=False))
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/api/agents/import",
            json={"invalid": "data"},
        )
        assert response.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Tests — Agent Stats
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

        app = _make_app()
        client = TestClient(app)
        with patch(_META_PATCH, new=AsyncMock(return_value={"visibility": "private", "owner_id": "user-1"})):
            response = client.get("/api/agents/test-agent/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_runs" in data or "runs" in data or "name" in data

    @_patch_agents_api_enabled()
    @patch(_USER_ID_PATCH, return_value="user-1")
    @patch(_LOAD_CONFIG_PATCH, return_value=None)
    def test_get_agent_stats_not_found(self, mock_load, mock_uid, mock_cfg):
        """Get agent stats returns 404 when agent not found."""
        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/agents/nonexistent/stats")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — User Profile
# ---------------------------------------------------------------------------


class TestUserProfile:
    """Tests for GET/PUT /api/user-profile."""

    @_patch_agents_api_enabled()
    @patch(_PATHS_PATCH)
    def test_get_user_profile(self, mock_paths, mock_cfg, tmp_path):
        """Get user profile returns USER.md content."""
        user_md = tmp_path / "USER.md"
        user_md.write_text("# User Profile\nSome content")

        mock_paths_obj = MagicMock()
        mock_paths_obj.user_md_file = user_md
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        response = client.get("/api/user-profile")
        assert response.status_code == 200

    @_patch_agents_api_enabled()
    @patch(_PATHS_PATCH)
    def test_update_user_profile(self, mock_paths, mock_cfg, tmp_path):
        """Update user profile writes USER.md content."""
        user_md = tmp_path / "USER.md"

        mock_paths_obj = MagicMock()
        mock_paths_obj.base_dir = tmp_path
        mock_paths_obj.user_md_file = user_md
        mock_paths.return_value = mock_paths_obj

        app = _make_app()
        client = TestClient(app)
        response = client.put(
            "/api/user-profile",
            json={"content": "# Updated Profile"},
        )
        assert response.status_code == 200
