"""E2E tests for the tools router (backend/app/gateway/routers/tools.py).

Covers all 5 tools endpoints:
- GET /api/tools
- GET /api/tools/groups
- GET /api/tools/{tool_name}
- POST /api/tools/{tool_name}/test
- PUT /api/tools/{tool_name}/config
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.tools import router as tools_router

pytestmark = pytest.mark.no_auto_user


def _make_user(role: str = "user") -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    user.role = role
    user.department_id = None
    user.disabled = False
    return user


def _make_app(role: str = "user", tool_registry=None):
    user = _make_user(role=role)
    app = make_authed_test_app()
    app.include_router(tools_router)

    async def _stub():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub
    if tool_registry is not None:
        app.state.tool_registry = tool_registry
    return app, user


# ---------------------------------------------------------------------------
# Tests — GET /api/tools
# ---------------------------------------------------------------------------


class TestListTools:
    """Tests for GET /api/tools."""

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_tools_returns_list(self, mock_registry):
        """List tools returns a list of tools wrapped in a dict."""
        mock_registry.return_value.list_all.return_value = []
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert "tools" in body
        assert isinstance(body["tools"], list)

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_tools_with_group_filter(self, mock_registry):
        """List tools with group filter."""
        mock_registry.return_value.list_by_group.return_value = []
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools?group=search")
        assert resp.status_code == 200

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_tools_with_search(self, mock_registry):
        """List tools with search filter."""
        mock_registry.return_value.search.return_value = []
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools?search=web")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — GET /api/tools/groups
# ---------------------------------------------------------------------------


class TestListToolGroups:
    """Tests for GET /api/tools/groups."""

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_tool_groups(self, mock_registry):
        """List tool groups returns a dict with a 'groups' key."""
        mock_tool_1 = MagicMock()
        mock_tool_1.name = "web_search"
        mock_tool_1.group = "search"
        mock_tool_2 = MagicMock()
        mock_tool_2.name = "sandbox_exec"
        mock_tool_2.group = "sandbox"
        mock_tool_3 = MagicMock()
        mock_tool_3.name = "util"
        mock_tool_3.group = "utility"
        mock_registry.return_value.list_all.return_value = [mock_tool_1, mock_tool_2, mock_tool_3]
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools/groups")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert "groups" in body
        assert isinstance(body["groups"], dict)


# ---------------------------------------------------------------------------
# Tests — GET /api/tools/{tool_name}
# ---------------------------------------------------------------------------


class TestGetToolDetail:
    """Tests for GET /api/tools/{tool_name}."""

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_get_tool_found(self, mock_registry):
        """Get tool returns tool details."""
        mock_tool = MagicMock()
        mock_tool.name = "web_search"
        mock_tool.description = "Search the web"
        mock_tool.group = "search"
        mock_tool.requires_network = True
        mock_tool.configurable = False
        mock_tool.config_schema = {}
        mock_tool.param_schema = {"type": "object", "properties": {}}
        mock_tool.config = {}
        mock_registry.return_value.get.return_value = mock_tool
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools/web_search")
        assert resp.status_code == 200
        assert resp.json()["name"] == "web_search"

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_get_tool_not_found(self, mock_registry):
        """Get tool returns 404 when not found."""
        mock_registry.return_value.get.return_value = None
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — POST /api/tools/{tool_name}/test
# ---------------------------------------------------------------------------


class TestTestTool:
    """Tests for POST /api/tools/{tool_name}/test."""

    @patch("ideer.tools.tools.get_available_tools")
    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_test_tool_success(self, mock_registry, mock_get_available_tools):
        """Test tool executes successfully."""
        # Mock the registry.get to return a tool_info (for the first lookup)
        mock_tool_info = MagicMock()
        mock_tool_info.name = "test_tool"
        mock_tool_info.configurable = False
        mock_registry.return_value.get.return_value = mock_tool_info

        # Mock the actual tool instance returned by get_available_tools
        mock_instance = MagicMock()
        mock_instance.name = "test_tool"
        mock_instance.ainvoke = AsyncMock(return_value={"result": "success"})
        mock_get_available_tools.return_value = [mock_instance]

        app, _ = _make_app(role="department_admin")
        with TestClient(app) as client:
            resp = client.post(
                "/api/tools/test_tool/test",
                json={"params": {"key": "value"}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["tool"] == "test_tool"

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_test_tool_not_found(self, mock_registry):
        """Test tool returns 404 when tool not found."""
        mock_registry.return_value.get.return_value = None
        app, _ = _make_app(role="department_admin")
        with TestClient(app) as client:
            resp = client.post(
                "/api/tools/nonexistent/test",
                json={"params": {}},
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — PUT /api/tools/{tool_name}/config
# ---------------------------------------------------------------------------


class TestUpdateToolConfig:
    """Tests for PUT /api/tools/{tool_name}/config."""

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_update_tool_config_success(self, mock_registry):
        """Update tool config succeeds."""
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.configurable = True
        mock_registry.return_value.get.return_value = mock_tool
        mock_registry.return_value.update_config.return_value = True
        app, _ = _make_app(role="super_admin")
        with TestClient(app) as client:
            resp = client.put(
                "/api/tools/test_tool/config",
                json={"config": {"enabled": True, "settings": {}}},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_update_tool_config_not_found(self, mock_registry):
        """Update tool config returns 404 when tool not found."""
        mock_registry.return_value.get.return_value = None
        app, _ = _make_app(role="super_admin")
        with TestClient(app) as client:
            resp = client.put(
                "/api/tools/nonexistent/config",
                json={"config": {"enabled": True}},
            )
        assert resp.status_code == 404
