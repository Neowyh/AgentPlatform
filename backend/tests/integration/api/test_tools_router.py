"""Tests for the tools management router (backend/app/gateway/routers/tools.py).

Covers:
- GET /api/tools — list all tools
- GET /api/tools/{tool_name} — get tool detail
- POST /api/tools/{tool_name}/test — test-execute a tool
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers import tools as tools_module

ToolTestRequest = tools_module.ToolTestRequest
_load_tool_meta = tools_module._load_tool_meta
get_tool_detail = tools_module.get_tool_detail
list_tools = tools_module.list_tools
tools_router = tools_module.router


class _MockToolSchema(BaseModel):
    pass


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


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, *, resource=None, rows=None):
        self._resource = resource
        self._rows = [] if rows is None else rows

    def scalar_one_or_none(self):
        return self._resource

    def scalars(self):
        return _ScalarRows(self._rows)


def _session_factory(session):
    sf = MagicMock()
    sf.return_value.__aenter__ = AsyncMock(return_value=session)
    sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf


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
            SimpleNamespace(name="tool_a", description="Tool A", get_input_schema=lambda: _MockToolSchema),
            SimpleNamespace(name="tool_b", description="Tool B", get_input_schema=lambda: _MockToolSchema),
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
            SimpleNamespace(name="matching_tool", description="A matching tool", get_input_schema=lambda: _MockToolSchema),
            SimpleNamespace(name="other_tool", description="Something else", get_input_schema=lambda: _MockToolSchema),
        ]

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools?search=matching")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["tools"][0]["name"] == "matching_tool"

    @pytest.mark.asyncio
    async def test_list_tools_filters_private_metadata_for_anonymous_user(self):
        private_meta = MagicMock(resource_id="private_tool", visibility="private", owner_id="owner", department_id=None)
        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(rows=[private_meta]))

        with (
            patch("app.gateway.routers.tools.get_app_config", return_value=MagicMock()),
            patch(
                "app.gateway.routers.tools.get_available_tools",
                return_value=[
                    SimpleNamespace(name="public_tool", description="Public", get_input_schema=lambda: {}),
                    SimpleNamespace(name="private_tool", description="Private", get_input_schema=lambda: {}),
                ],
            ),
            patch("app.gateway.routers.tools.get_session_factory", return_value=_session_factory(session)),
        ):
            data = await list_tools(current_user=None)

        assert data["total"] == 1
        assert data["tools"][0]["name"] == "public_tool"

    @pytest.mark.asyncio
    async def test_list_tools_continues_when_metadata_batch_load_fails(self):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("database error"))

        with (
            patch("app.gateway.routers.tools.get_app_config", return_value=MagicMock()),
            patch(
                "app.gateway.routers.tools.get_available_tools",
                return_value=[SimpleNamespace(name="public_tool", description="", get_input_schema=lambda: {})],
            ),
            patch("app.gateway.routers.tools.get_session_factory", return_value=_session_factory(session)),
        ):
            data = await list_tools(current_user=None)

        assert data["total"] == 1


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
            SimpleNamespace(name="my_tool", description="desc", get_input_schema=lambda: _MockToolSchema),
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

    @pytest.mark.asyncio
    async def test_load_tool_meta_returns_db_metadata_and_handles_failure(self):
        resource = MagicMock(visibility="department", owner_id="u1", department_id="dept-1")
        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result(resource=resource))

        with patch("app.gateway.routers.tools.get_session_factory", return_value=_session_factory(session)):
            assert await _load_tool_meta("search") == {
                "visibility": "department",
                "owner_id": "u1",
                "department_id": "dept-1",
            }

        session.execute = AsyncMock(side_effect=RuntimeError("database error"))
        with patch("app.gateway.routers.tools.get_session_factory", return_value=_session_factory(session)):
            assert await _load_tool_meta("search") == {}

    @pytest.mark.asyncio
    async def test_get_tool_detail_denies_private_tool_to_anonymous_user(self):
        with (
            patch("app.gateway.routers.tools.get_app_config", return_value=MagicMock()),
            patch(
                "app.gateway.routers.tools.get_available_tools",
                return_value=[SimpleNamespace(name="private_tool", description="", get_input_schema=lambda: {})],
            ),
            patch("app.gateway.routers.tools._load_tool_meta", new=AsyncMock(return_value={"visibility": "private"})),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_tool_detail("private_tool", current_user=None)

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_tool_detail_denies_when_authenticated_user_lacks_access(self):
        with (
            patch("app.gateway.routers.tools.get_app_config", return_value=MagicMock()),
            patch(
                "app.gateway.routers.tools.get_available_tools",
                return_value=[SimpleNamespace(name="private_tool", description="", get_input_schema=lambda: {})],
            ),
            patch("app.gateway.routers.tools._load_tool_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": "other"})),
            patch("app.gateway.routers.tools.check_resource_access", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_tool_detail("private_tool", current_user=_make_rbac_user(user_id="u1"))

        assert exc.value.status_code == 404


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

    @pytest.mark.asyncio
    async def test_test_tool_denies_when_user_lacks_access(self):
        with (
            patch("app.gateway.routers.tools._load_tool_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": "other"})),
            patch("app.gateway.routers.tools.check_resource_access", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc:
                await tools_module.test_tool("private_tool", ToolTestRequest(params={}), current_user=_make_rbac_user(user_id="u1"))

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_test_tool_wraps_unexpected_loader_failure(self):
        with (
            patch("app.gateway.routers.tools._load_tool_meta", new=AsyncMock(return_value={})),
            patch("app.gateway.routers.tools.check_resource_access", return_value=True),
            patch("app.gateway.routers.tools.get_app_config", side_effect=RuntimeError("config error")),
        ):
            with pytest.raises(HTTPException) as exc:
                await tools_module.test_tool("my_tool", ToolTestRequest(params={}), current_user=_make_rbac_user())

        assert exc.value.status_code == 500
