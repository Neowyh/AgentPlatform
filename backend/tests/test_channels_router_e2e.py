"""E2E tests for the channels router (backend/app/gateway/routers/channels.py).

Covers all 2 channels endpoints:
- GET /api/channels/
- POST /api/channels/{name}/restart
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.routers.channels import router as channels_router

pytestmark = pytest.mark.no_auto_user


def _make_app():
    app = make_authed_test_app()
    app.include_router(channels_router)
    return app


def _make_channel_service(
    status_result=None,
    restart_result=True,
):
    """Build a mock ChannelService matching the real interface."""
    service = MagicMock()
    service.get_status = MagicMock(
        return_value=status_result
        or {
            "service_running": True,
            "channels": {
                "dingtalk": {"enabled": True, "running": True},
                "slack": {"enabled": False, "running": False},
            },
        }
    )
    service.restart_channel = AsyncMock(return_value=restart_result)
    return service


# ---------------------------------------------------------------------------
# Tests — GET /api/channels/
# ---------------------------------------------------------------------------


class TestGetChannelsStatus:
    """Tests for GET /api/channels/."""

    def test_get_channels_status(self):
        """Get channels status returns status for all channels."""
        service = _make_channel_service()
        with patch("app.channels.service.get_channel_service", return_value=service):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/channels/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "service_running" in data
        assert "channels" in data

    def test_get_channels_status_empty(self):
        """Get channels status returns service_running=false when no service is running."""
        with patch("app.channels.service.get_channel_service", return_value=None):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/channels/")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"service_running": False, "channels": {}}


# ---------------------------------------------------------------------------
# Tests — POST /api/channels/{name}/restart
# ---------------------------------------------------------------------------


class TestRestartChannel:
    """Tests for POST /api/channels/{name}/restart."""

    def test_restart_channel_success(self):
        """Restart channel succeeds."""
        service = _make_channel_service(restart_result=True)
        with patch("app.channels.service.get_channel_service", return_value=service):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post("/api/channels/dingtalk/restart")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_restart_channel_not_found(self):
        """Restart channel returns success=False with 200 when channel not found."""
        service = _make_channel_service(restart_result=False)
        with patch("app.channels.service.get_channel_service", return_value=service):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post("/api/channels/nonexistent/restart")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
