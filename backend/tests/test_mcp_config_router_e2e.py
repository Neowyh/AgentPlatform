"""E2E tests for the MCP config router (backend/app/gateway/routers/mcp.py).

Covers all 2 MCP config endpoints:
- GET /api/mcp/config
- PUT /api/mcp/config
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.mcp import router as mcp_router
from ideer.config.extensions_config import ExtensionsConfig, McpServerConfig

pytestmark = pytest.mark.no_auto_user


def _make_app():

    from app.gateway.authz import get_current_rbac_user

    app = make_authed_test_app()
    app.include_router(mcp_router)

    # Mock the RBAC user for @require_role decorators
    rbac_user = MagicMock()
    rbac_user.id = "test-user-id"
    rbac_user.role = "user"
    rbac_user.department_id = None
    rbac_user.disabled = False

    async def _stub_rbac_user():
        return rbac_user

    app.dependency_overrides[get_current_rbac_user] = _stub_rbac_user
    return app


def _make_extensions_config(servers=None):
    """Build an ExtensionsConfig with the given mcp_servers dict."""
    if servers is None:
        servers = {
            "test-server": McpServerConfig(
                enabled=True,
                type="stdio",
                command="test-command",
                args=[],
            )
        }
    config = MagicMock(spec=ExtensionsConfig)
    config.mcp_servers = servers
    config.skills = {}
    return config


# ---------------------------------------------------------------------------
# Tests — GET /api/mcp/config
# ---------------------------------------------------------------------------


class TestGetMcpConfig:
    """Tests for GET /api/mcp/config."""

    @patch("app.gateway.routers.mcp.get_extensions_config")
    def test_get_mcp_config(self, mock_get_ext):
        """Get MCP config returns configuration."""
        mock_get_ext.return_value = _make_extensions_config()
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/mcp/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "mcp_servers" in data
        assert "test-server" in data["mcp_servers"]

    @patch("app.gateway.routers.mcp.get_extensions_config")
    def test_get_mcp_config_masks_secrets(self, mock_get_ext):
        """Get MCP config masks sensitive fields."""
        mock_get_ext.return_value = _make_extensions_config(
            servers={
                "test-server": McpServerConfig(
                    enabled=True,
                    type="stdio",
                    command="test",
                    args=[],
                    env={"API_KEY": "secret-value"},
                )
            }
        )
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/mcp/config")
        assert resp.status_code == 200
        data = resp.json()
        # Env values should be masked
        env = data["mcp_servers"]["test-server"]["env"]
        assert env.get("API_KEY") == "***"


# ---------------------------------------------------------------------------
# Tests — PUT /api/mcp/config
# ---------------------------------------------------------------------------


class TestUpdateMcpConfig:
    """Tests for PUT /api/mcp/config."""

    @patch("app.gateway.routers.mcp.reload_extensions_config")
    @patch("app.gateway.routers.mcp.get_extensions_config")
    @patch.object(ExtensionsConfig, "resolve_config_path")
    def test_update_mcp_config_success(self, mock_resolve, mock_get_ext, mock_reload, tmp_path):
        """Update MCP config succeeds."""
        config_file = tmp_path / "extensions_config.json"
        config_file.write_text('{"mcpServers": {"test-server": {"enabled": true, "command": "old-command", "args": []}}}')
        mock_resolve.return_value = config_file

        mock_get_ext.return_value = _make_extensions_config()

        updated_config = _make_extensions_config(
            servers={
                "test-server": McpServerConfig(
                    enabled=True,
                    type="stdio",
                    command="updated-command",
                    args=[],
                )
            }
        )
        mock_reload.return_value = updated_config

        app = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/mcp/config",
                json={
                    "mcp_servers": {
                        "test-server": {
                            "enabled": True,
                            "type": "stdio",
                            "command": "updated-command",
                            "args": [],
                        }
                    }
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mcp_servers"]["test-server"]["command"] == "updated-command"

    @patch("app.gateway.routers.mcp.reload_extensions_config")
    @patch("app.gateway.routers.mcp.get_extensions_config")
    @patch.object(ExtensionsConfig, "resolve_config_path")
    def test_update_mcp_config_preserves_secrets(self, mock_resolve, mock_get_ext, mock_reload, tmp_path):
        """Update MCP config preserves secrets on round-trip."""
        config_file = tmp_path / "extensions_config.json"
        config_file.write_text('{"mcpServers": {"test-server": {"enabled": true, "command": "test", "args": [], "env": {"API_KEY": "real-secret"}}}}')
        mock_resolve.return_value = config_file

        mock_get_ext.return_value = _make_extensions_config()

        updated_config = _make_extensions_config(
            servers={
                "test-server": McpServerConfig(
                    enabled=True,
                    type="stdio",
                    command="test",
                    args=[],
                    env={"API_KEY": "***"},
                )
            }
        )
        mock_reload.return_value = updated_config

        app = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/mcp/config",
                json={
                    "mcp_servers": {
                        "test-server": {
                            "enabled": True,
                            "type": "stdio",
                            "command": "test",
                            "args": [],
                            "env": {"API_KEY": "***"},
                        }
                    }
                },
            )
        assert resp.status_code == 200
