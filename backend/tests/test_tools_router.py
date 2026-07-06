"""Tests for the tools management router (backend/app/gateway/routers/tools.py).

Covers:
- GET /api/tools — list all tools
- GET /api/tools/{tool_name} — get tool detail
- POST /api/tools/{tool_name}/test — test-execute a tool
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.tools import router as tools_router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str = "admin-1",
    role: str = "super_admin",
    department_id: str | None = None,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = False
    return user


def _make_app(current_user: MagicMock | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(tools_router)

    user = current_user or _make_rbac_user()

    async def _stub_current_user():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current_user
    return app


# ---------------------------------------------------------------------------
# List tools
# ---------------------------------------------------------------------------


class TestListTools:
    """Tests for GET /api/tools."""

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_list_tools_returns_all(self, mock_get_tools, mock_config):
        """List tools returns all registered tools."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = [
            SimpleNamespace(name="tool_a", description="Tool A", get_input_schema=lambda: {"type": "object"}),
            SimpleNamespace(name="tool_b", description="Tool B", get_input_schema=lambda: {"type": "object"}),
        ]

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["tools"]) == 2

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_list_tools_with_search(self, mock_get_tools, mock_config):
        """List tools with search parameter filters results inline."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = [
            SimpleNamespace(name="matching_tool", description="A matching tool", get_input_schema=lambda: {"type": "object"}),
            SimpleNamespace(name="other_tool", description="Something else", get_input_schema=lambda: {"type": "object"}),
        ]

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools?search=matching")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["tools"][0]["name"] == "matching_tool"


# ---------------------------------------------------------------------------
# Get tool detail
# ---------------------------------------------------------------------------


class TestGetToolDetail:
    """Tests for GET /api/tools/{tool_name}."""

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_get_tool_detail_success(self, mock_get_tools, mock_config):
        """Get tool detail returns tool info."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = [
            SimpleNamespace(name="my_tool", description="desc", get_input_schema=lambda: {"type": "object"}),
        ]

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools/my_tool")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "my_tool"
        assert data["description"] == "desc"

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_get_tool_detail_not_found(self, mock_get_tools, mock_config):
        """Get tool detail returns 404 for nonexistent tool."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = []

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools/nonexistent")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test-execute tool
# ---------------------------------------------------------------------------


class TestToolExecution:
    """Tests for POST /api/tools/{tool_name}/test."""

    @patch("ideer.tools.tools.get_available_tools")
    @patch("app.gateway.routers.tools.get_app_config")
    def test_test_tool_success(self, mock_config, mock_get_tools):
        """Test-execute tool succeeds with valid tool."""
        mock_config.return_value = MagicMock()

        # Use SimpleNamespace so hasattr("ainvoke") returns False
        tool_instance = SimpleNamespace(
            name="my_tool",
            invoke=MagicMock(return_value="result"),
        )
        mock_get_tools.return_value = [tool_instance]

        app = _make_app()
        client = TestClient(app)
        resp = client.post(
            "/api/tools/my_tool/test",
            json={"params": {"key": "value"}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tool"] == "my_tool"

    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_available_tools")
    def test_test_tool_not_found(self, mock_get_tools, mock_config):
        """Test-execute returns 404 for nonexistent tool."""
        mock_config.return_value = MagicMock()
        mock_get_tools.return_value = []

        app = _make_app()
        client = TestClient(app)
        resp = client.post(
            "/api/tools/nonexistent/test",
            json={"params": {}},
        )

        assert resp.status_code == 404

    @patch("ideer.tools.tools.get_available_tools")
    @patch("app.gateway.routers.tools.get_app_config")
    def test_test_tool_execution_failure(self, mock_config, mock_get_tools):
        """Test-execute handles tool execution failure gracefully."""
        mock_config.return_value = MagicMock()

        # Use SimpleNamespace so hasattr("ainvoke") returns False
        tool_instance = SimpleNamespace(
            name="my_tool",
            invoke=MagicMock(side_effect=RuntimeError("execution failed")),
        )
        mock_get_tools.return_value = [tool_instance]

        app = _make_app()
        client = TestClient(app)
        resp = client.post(
            "/api/tools/my_tool/test",
            json={"params": {}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "error" in data
