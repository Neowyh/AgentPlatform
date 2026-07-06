"""E2E tests for the tools router (backend/app/gateway/routers/tools.py).

Covers:
- GET /api/tools
- GET /api/tools/{tool_name}
- POST /api/tools/{tool_name}/test
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
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
    app.dependency_overrides[get_optional_rbac_user] = _stub
    if tool_registry is not None:
        app.state.tool_registry = tool_registry
    return app, user


# ---------------------------------------------------------------------------
# Tests — GET /api/tools
# ---------------------------------------------------------------------------


class TestListTools:
    """Tests for GET /api/tools."""

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_list_tools_returns_list(self, mock_get_tools, mock_config):
        """List tools returns a list of tools wrapped in a dict."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = []
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert "tools" in body
        assert isinstance(body["tools"], list)

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_list_tools_with_search(self, mock_get_tools, mock_config):
        """List tools with search filter."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = []
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools?search=web")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — GET /api/tools/{tool_name}
# ---------------------------------------------------------------------------


class TestGetToolDetail:
    """Tests for GET /api/tools/{tool_name}."""

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_get_tool_found(self, mock_get_tools, mock_config):
        """Get tool returns tool details."""
        mock_config.return_value = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "web_search"
        mock_tool.description = "Search the web"
        mock_tool.get_input_schema.return_value = {"type": "object", "properties": {}}
        mock_get_tools.return_value = [mock_tool]
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/tools/web_search")
        assert resp.status_code == 200
        assert resp.json()["name"] == "web_search"

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_get_tool_not_found(self, mock_get_tools, mock_config):
        """Get tool returns 404 when not found."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = []
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
    @patch("app.gateway.routers.tools.get_app_config")
    def test_test_tool_success(self, mock_config, mock_get_available_tools):
        """Test tool executes successfully."""
        mock_config.return_value = MagicMock()

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

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_test_tool_not_found(self, mock_get_tools, mock_config):
        """Test tool returns 404 when tool not found."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = []
        app, _ = _make_app(role="department_admin")
        with TestClient(app) as client:
            resp = client.post(
                "/api/tools/nonexistent/test",
                json={"params": {}},
            )
        assert resp.status_code == 404
