"""Tests for the tools management router (backend/app/gateway/routers/tools.py).

Covers:
- GET /api/tools — list all tools
- GET /api/tools/groups — list tool groups
- GET /api/tools/{tool_name} — get tool detail
- POST /api/tools/{tool_name}/test — test-execute a tool
- PUT /api/tools/{tool_name}/config — update tool config
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


def _make_tool_info(
    name: str = "test_tool",
    description: str = "A test tool",
    group: str = "test",
    requires_network: bool = False,
    configurable: bool = True,
    config_schema: dict | None = None,
    param_schema: dict | None = None,
    config: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=description,
        group=group,
        requires_network=requires_network,
        configurable=configurable,
        config_schema=config_schema or {},
        param_schema=param_schema or {},
        config=config or {},
    )


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

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_tools_returns_all(self, mock_registry_fn):
        """List tools returns all registered tools."""
        registry = MagicMock()
        registry.list_all.return_value = [
            _make_tool_info(name="tool_a"),
            _make_tool_info(name="tool_b"),
        ]
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["tools"]) == 2

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_tools_with_search(self, mock_registry_fn):
        """List tools with search parameter uses registry.search."""
        registry = MagicMock()
        registry.search.return_value = [_make_tool_info(name="matching_tool")]
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools?search=matching")

        assert resp.status_code == 200
        registry.search.assert_called_once_with("matching")

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_tools_with_group_filter(self, mock_registry_fn):
        """List tools with group parameter uses registry.list_by_group."""
        registry = MagicMock()
        registry.list_by_group.return_value = [_make_tool_info(name="grouped_tool")]
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools?group=file")

        assert resp.status_code == 200
        registry.list_by_group.assert_called_once_with("file")


# ---------------------------------------------------------------------------
# List tool groups
# ---------------------------------------------------------------------------


class TestListToolGroups:
    """Tests for GET /api/tools/groups."""

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_list_groups_returns_grouped_tools(self, mock_registry_fn):
        """List groups returns tools grouped by group name."""
        registry = MagicMock()
        registry.list_all.return_value = [
            _make_tool_info(name="read_file", group="file"),
            _make_tool_info(name="write_file", group="file"),
            _make_tool_info(name="web_search", group="web"),
        ]
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools/groups")

        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert set(data["groups"]["file"]) == {"read_file", "write_file"}
        assert data["groups"]["web"] == ["web_search"]


# ---------------------------------------------------------------------------
# Get tool detail
# ---------------------------------------------------------------------------


class TestGetToolDetail:
    """Tests for GET /api/tools/{tool_name}."""

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_get_tool_detail_success(self, mock_registry_fn):
        """Get tool detail returns tool info."""
        registry = MagicMock()
        registry.get.return_value = _make_tool_info(name="my_tool", description="desc")
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/tools/my_tool")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "my_tool"
        assert data["description"] == "desc"

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_get_tool_detail_not_found(self, mock_registry_fn):
        """Get tool detail returns 404 for nonexistent tool."""
        registry = MagicMock()
        registry.get.return_value = None
        mock_registry_fn.return_value = registry

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
    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_test_tool_success(self, mock_registry_fn, mock_config, mock_get_tools):
        """Test-execute tool succeeds with valid tool."""
        registry = MagicMock()
        registry.get.return_value = _make_tool_info(name="my_tool")
        mock_registry_fn.return_value = registry

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

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_test_tool_not_found(self, mock_registry_fn):
        """Test-execute returns 404 for nonexistent tool."""
        registry = MagicMock()
        registry.get.return_value = None
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.post(
            "/api/tools/nonexistent/test",
            json={"params": {}},
        )

        assert resp.status_code == 404

    @patch("ideer.tools.tools.get_available_tools")
    @patch("app.gateway.routers.tools.get_app_config")
    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_test_tool_execution_failure(self, mock_registry_fn, mock_config, mock_get_tools):
        """Test-execute handles tool execution failure gracefully."""
        registry = MagicMock()
        registry.get.return_value = _make_tool_info(name="my_tool")
        mock_registry_fn.return_value = registry

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


# ---------------------------------------------------------------------------
# Update tool config
# ---------------------------------------------------------------------------


class TestUpdateToolConfig:
    """Tests for PUT /api/tools/{tool_name}/config."""

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_update_config_success(self, mock_registry_fn):
        """Update config succeeds for configurable tool."""
        registry = MagicMock()
        registry.get.return_value = _make_tool_info(name="my_tool", configurable=True)
        registry.update_config.return_value = True
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/tools/my_tool/config",
            json={"config": {"key": "value"}},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_update_config_tool_not_found(self, mock_registry_fn):
        """Update config returns 404 for nonexistent tool."""
        registry = MagicMock()
        registry.get.return_value = None
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/tools/nonexistent/config",
            json={"config": {}},
        )

        assert resp.status_code == 404

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_update_config_not_configurable(self, mock_registry_fn):
        """Update config returns 400 for non-configurable tool."""
        registry = MagicMock()
        registry.get.return_value = _make_tool_info(name="my_tool", configurable=False)
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/tools/my_tool/config",
            json={"config": {"key": "value"}},
        )

        assert resp.status_code == 400
        assert "not configurable" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.tools.get_tool_registry")
    def test_update_config_invalid_config(self, mock_registry_fn):
        """Update config returns 400 when registry rejects config."""
        registry = MagicMock()
        registry.get.return_value = _make_tool_info(name="my_tool", configurable=True)
        registry.update_config.return_value = False
        mock_registry_fn.return_value = registry

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/tools/my_tool/config",
            json={"config": {"invalid_key": "value"}},
        )

        assert resp.status_code == 400
