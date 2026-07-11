"""Auth router edge behavior for session cookies, client IPs, and setup status."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.gateway.routers.auth import (
    _get_client_ip,
    _set_session_cookie,
    _validate_strong_password,
)
from app.gateway.routers.auth import (
    router as auth_router,
)

pytestmark = pytest.mark.no_auto_user


def _make_app():
    app = FastAPI()
    app.include_router(auth_router)
    return app


# ---------------------------------------------------------------------------
# Strong password validation
# ---------------------------------------------------------------------------


class TestValidateStrongPassword:
    def test_returns_value_for_non_common_password(self):
        """Non-common password should be returned as-is."""
        result = _validate_strong_password("MyStr0ng!Pass")
        assert result == "MyStr0ng!Pass"

    def test_raises_for_common_password(self):
        """Common password should raise ValueError."""
        with pytest.raises(ValueError, match="too common"):
            _validate_strong_password("password")

    def test_case_insensitive_rejection(self):
        """Common password with different case should raise."""
        with pytest.raises(ValueError, match="too common"):
            _validate_strong_password("PASSWORD")

    def test_register_request_rejects_common(self):
        """RegisterRequest model should reject common passwords."""
        from pydantic import ValidationError

        from app.gateway.routers.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(email="test@example.com", password="password123")

    def test_register_request_accepts_strong(self):
        """RegisterRequest model should accept strong passwords."""
        from app.gateway.routers.auth import RegisterRequest

        req = RegisterRequest(email="test@example.com", password="MyStr0ng!Pass")
        assert req.password == "MyStr0ng!Pass"

    def test_change_password_request_rejects_common(self):
        """ChangePasswordRequest should reject common new passwords."""
        from pydantic import ValidationError

        from app.gateway.routers.auth import ChangePasswordRequest

        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="OldPass123!",
                new_password="password123",
            )

    def test_initialize_admin_request_rejects_common(self):
        """InitializeAdminRequest should reject common passwords."""
        from pydantic import ValidationError

        from app.gateway.routers.auth import InitializeAdminRequest

        with pytest.raises(ValidationError):
            InitializeAdminRequest(email="admin@example.com", password="password123")


# ---------------------------------------------------------------------------
# Session cookie attributes
# ---------------------------------------------------------------------------


class TestSetSessionCookie:
    def test_https_sets_secure_and_max_age(self):
        """HTTPS request should set secure=True and max_age."""
        response = Response()
        mock_request = MagicMock()
        mock_request.headers = {"x-forwarded-proto": "https"}

        config = MagicMock()
        config.token_expiry_days = 7

        with (
            patch("app.gateway.routers.auth.get_auth_config", return_value=config),
            patch("app.gateway.routers.auth.is_secure_request", return_value=True),
        ):
            _set_session_cookie(response, "test-token", mock_request)

        # Check that the cookie was set with the expected attributes
        cookies = response.headers.get("set-cookie", "")
        assert "access_token=test-token" in cookies
        assert "httponly" in cookies.lower()
        assert "secure" in cookies.lower()
        assert "samesite=strict" in cookies.lower()

    def test_http_no_secure_no_max_age(self):
        """HTTP request should set secure=False and no max_age."""
        response = Response()
        mock_request = MagicMock()

        config = MagicMock()
        config.token_expiry_days = 7

        with (
            patch("app.gateway.routers.auth.get_auth_config", return_value=config),
            patch("app.gateway.routers.auth.is_secure_request", return_value=False),
        ):
            _set_session_cookie(response, "test-token", mock_request)

        cookies = response.headers.get("set-cookie", "")
        assert "access_token=test-token" in cookies
        assert "httponly" in cookies.lower()


# ---------------------------------------------------------------------------
# Client IP extraction
# ---------------------------------------------------------------------------


class TestGetClientIpValueError:
    def test_peer_host_not_parseable_ip(self, monkeypatch):
        """When peer_host is not a valid IP, fall through to return peer_host."""
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "not-an-ip"
        req.headers = {"x-real-ip": "1.2.3.4"}
        assert _get_client_ip(req) == "not-an-ip"

    def test_peer_host_is_none(self):
        """When request.client is None, return 'unknown'."""
        req = MagicMock()
        req.client = None
        req.headers = {}
        assert _get_client_ip(req) == "unknown"

    def test_no_trusted_proxies_returns_peer_host(self, monkeypatch):
        """Without trusted proxies, return peer host directly."""
        monkeypatch.delenv("AUTH_TRUSTED_PROXIES", raising=False)
        req = MagicMock()
        req.client.host = "192.168.1.1"
        req.headers = {"x-real-ip": "10.0.0.1"}
        assert _get_client_ip(req) == "192.168.1.1"

    def test_peer_not_in_trusted_range(self, monkeypatch):
        """When peer is not in trusted range, X-Real-IP is ignored."""
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "192.168.1.1"
        req.headers = {"x-real-ip": "5.6.7.8"}
        assert _get_client_ip(req) == "192.168.1.1"

    def test_peer_in_trusted_range_with_real_ip(self, monkeypatch):
        """When peer is in trusted range and X-Real-IP is set, return X-Real-IP."""
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "10.5.6.7"
        req.headers = {"x-real-ip": "1.2.3.4"}
        assert _get_client_ip(req) == "1.2.3.4"


# ---------------------------------------------------------------------------
# Setup-status cache behavior inside the inflight guard
# ---------------------------------------------------------------------------


class TestSetupStatusCacheInsideGuard:
    def test_cache_hit_inside_inflight_guard(self):
        """Second cache check (inside inflight guard) returns cached result."""
        import app.gateway.routers.auth as auth_mod

        provider = MagicMock()
        provider.count_admin_users = AsyncMock(return_value=1)
        now = time.time()
        cached_result = {"needs_setup": False}

        # Simulate: first .get() returns None (outside guard),
        # second .get() returns cached (inside guard)
        call_count = {"n": 0}

        def _fake_get(key, default=None):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return default  # miss outside guard
            return (now, cached_result)  # hit inside guard

        cache_mock = MagicMock()
        cache_mock.get = MagicMock(side_effect=_fake_get)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.50"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache_mock),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", {}),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", asyncio.Lock()),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is False

    def test_setup_status_needs_setup_not_cached(self):
        """needs_setup=True result should NOT be cached (only False is cached)."""
        import app.gateway.routers.auth as auth_mod

        provider = MagicMock()
        provider.count_admin_users = AsyncMock(return_value=0)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.51"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", {}),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", {}),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", asyncio.Lock()),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is True

    def test_setup_status_first_cache_hit(self):
        """Lines 406-408: First cache check (before inflight guard) returns cached result."""
        import app.gateway.routers.auth as auth_mod

        cached_result = {"needs_setup": False}
        cache = {"10.0.0.60": (time.time(), cached_result)}

        with (
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.60"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", {}),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", asyncio.Lock()),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is False
