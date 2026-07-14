"""Tests for app.gateway.routers.auth -- all remaining coverage gaps.

Self-contained file that covers all missed lines to reach 98%+ coverage.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.auth.errors import AuthErrorCode
from app.gateway.auth.models import User
from app.gateway.routers.auth import (
    _check_rate_limit,
    _get_client_ip,
    _login_attempts,
    _record_login_failure,
    _record_login_success,
    _trusted_proxies,
    _validate_strong_password,
)
from app.gateway.routers.auth import (
    router as auth_router,
)

pytestmark = pytest.mark.no_auto_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _auth_db(tmp_path):
    from app.gateway import deps
    from ideer.persistence.engine import close_engine, init_engine

    asyncio.run(init_engine("sqlite", url=f"sqlite+aiosqlite:///{tmp_path}/auth_router_gaps.db", sqlite_dir=str(tmp_path)))
    deps._cached_local_provider = None
    deps._cached_repo = None
    try:
        yield
    finally:
        deps._cached_local_provider = None
        deps._cached_repo = None
        asyncio.run(close_engine())


def _make_app():
    app = FastAPI()
    app.include_router(auth_router)
    return app


def _fake_user(
    *,
    user_id=None,
    email="test@example.com",
    system_role="user",
    needs_setup=False,
    token_version=0,
    password_hash="$2b$12$fakehashedpassword",
):
    return User(
        id=user_id or uuid4(),
        email=email,
        password_hash=password_hash,
        system_role=system_role,
        needs_setup=needs_setup,
        token_version=token_version,
    )


def _mock_auth_config(token_expiry_days=7):
    cfg = MagicMock()
    cfg.token_expiry_days = token_expiry_days
    return cfg


# ---------------------------------------------------------------------------
# Line 103: _validate_strong_password
# ---------------------------------------------------------------------------


class TestValidateStrongPassword:
    def test_returns_value_for_non_common(self):
        assert _validate_strong_password("MyStr0ng!Pass") == "MyStr0ng!Pass"

    def test_raises_for_common(self):
        with pytest.raises(ValueError, match="too common"):
            _validate_strong_password("password")


# ---------------------------------------------------------------------------
# Lines 176-185: _get_client_ip -- trusted proxy with real IP
# ---------------------------------------------------------------------------


class TestGetClientIp:
    def test_trusted_proxy_returns_real_ip(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "10.5.6.7"
        req.headers = {"x-real-ip": "203.0.113.42"}
        assert _get_client_ip(req) == "203.0.113.42"

    def test_peer_not_in_trusted(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "192.168.1.1"
        req.headers = {"x-real-ip": "5.6.7.8"}
        assert _get_client_ip(req) == "192.168.1.1"

    def test_no_trusted_proxies(self, monkeypatch):
        monkeypatch.delenv("AUTH_TRUSTED_PROXIES", raising=False)
        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.headers = {"x-real-ip": "203.0.113.42"}
        assert _get_client_ip(req) == "127.0.0.1"

    def test_no_client(self):
        req = MagicMock()
        req.client = None
        req.headers = {}
        assert _get_client_ip(req) == "unknown"

    def test_peer_host_not_parseable(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "not-an-ip"
        req.headers = {"x-real-ip": "1.2.3.4"}
        assert _get_client_ip(req) == "not-an-ip"

    def test_empty_real_ip_with_trusted_proxy(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "10.5.6.7"
        req.headers = {"x-real-ip": ""}
        assert _get_client_ip(req) == "10.5.6.7"


# ---------------------------------------------------------------------------
# Lines 213-221, 231-238: _trusted_proxies and _check_rate_limit
# ---------------------------------------------------------------------------


class TestTrustedProxies:
    def test_empty_env(self, monkeypatch):
        monkeypatch.delenv("AUTH_TRUSTED_PROXIES", raising=False)
        assert _trusted_proxies() == []

    def test_single_ip(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.1")
        assert len(_trusted_proxies()) == 1

    def test_invalid_entry_skipped(self, monkeypatch, caplog):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "not-an-ip,10.0.0.0/8")
        nets = _trusted_proxies()
        assert len(nets) == 1

    def test_empty_entries_ignored(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", ",,,")
        assert _trusted_proxies() == []


class TestCheckRateLimit:
    def test_no_record(self):
        _login_attempts.clear()
        _check_rate_limit("10.99.99.99")  # Should not raise

    def test_expired_lockout_allows(self):
        _login_attempts.clear()
        ip = "10.99.99.98"
        _login_attempts[ip] = (5, time.time() - 1)
        _check_rate_limit(ip)  # Should not raise
        assert ip not in _login_attempts

    def test_lockout_not_expired(self):
        _login_attempts.clear()
        ip = "10.99.99.97"
        _login_attempts[ip] = (5, time.time() + 300)
        with pytest.raises(Exception) as exc_info:
            _check_rate_limit(ip)
        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# Lines 248-257, 263-265: _record_login_failure eviction
# ---------------------------------------------------------------------------


class TestRecordLoginFailure:
    def test_new_ip(self):
        _login_attempts.clear()
        _record_login_failure("new-ip")
        assert "new-ip" in _login_attempts

    def test_existing_ip_increments(self):
        _login_attempts.clear()
        ip = "test-ip"
        _record_login_failure(ip)
        _record_login_failure(ip)
        assert _login_attempts[ip][0] == 2

    def test_lockout_at_max(self):
        from app.gateway.routers.auth import _MAX_LOGIN_ATTEMPTS

        _login_attempts.clear()
        ip = "lockout-ip"
        for _ in range(_MAX_LOGIN_ATTEMPTS):
            _record_login_failure(ip)
        fail_count, lock_until = _login_attempts[ip]
        assert fail_count == _MAX_LOGIN_ATTEMPTS
        assert lock_until > time.time()

    def test_eviction_when_dict_full(self):
        from app.gateway.routers.auth import _MAX_TRACKED_IPS

        _login_attempts.clear()
        now = time.time()
        for i in range(_MAX_TRACKED_IPS):
            _login_attempts[f"ip-{i}"] = (5, now - 100)
        _record_login_failure("new-ip")
        assert "new-ip" in _login_attempts

    def test_eviction_when_still_full(self):
        from app.gateway.routers.auth import _MAX_TRACKED_IPS

        _login_attempts.clear()
        now = time.time()
        for i in range(_MAX_TRACKED_IPS):
            _login_attempts[f"ip-{i}"] = (5, now + 300)
        _record_login_failure("new-ip")
        assert "new-ip" in _login_attempts
        assert len(_login_attempts) <= _MAX_TRACKED_IPS


class TestRecordLoginSuccess:
    def test_clears_counter(self):
        _login_attempts.clear()
        _login_attempts["ip"] = (3, 0.0)
        _record_login_success("ip")
        assert "ip" not in _login_attempts


# ---------------------------------------------------------------------------
# Lines 283-299: login_local endpoint
# ---------------------------------------------------------------------------


class TestLoginLocal:
    def test_login_success(self):
        user = _fake_user(needs_setup=False)
        provider = MagicMock()
        provider.authenticate = AsyncMock(return_value=user)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth.create_access_token", return_value="test-jwt"),
            patch("app.gateway.routers.auth.get_auth_config", return_value=_mock_auth_config(7)),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/login/local",
                    data={"username": "test@example.com", "password": "pass1234"},
                )

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is False
        assert resp.json()["expires_in"] == 7 * 24 * 3600

    def test_login_failure(self):
        provider = MagicMock()
        provider.authenticate = AsyncMock(return_value=None)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/login/local",
                    data={"username": "bad@example.com", "password": "wrong"},
                )

        assert resp.status_code == 401
        data = resp.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# Lines 312-323: register endpoint
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_success(self):
        user = _fake_user(email="new@example.com")
        provider = MagicMock()
        provider.create_user = AsyncMock(return_value=user)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth.create_access_token", return_value="reg-jwt"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/register",
                    json={"email": "new@example.com", "password": "StrongPass123!"},
                )

        assert resp.status_code == 201
        assert resp.json()["email"] == "new@example.com"

    def test_register_email_exists(self):
        app = _make_app()
        with TestClient(app) as client:
            client.post(
                "/api/v1/auth/register",
                json={"email": "existing@example.com", "password": "StrongPass123!"},
            )
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": "existing@example.com", "password": "StrongPass123!"},
            )

        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# Lines 329-330: logout endpoint
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout(self):
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Successfully logged out"


# ---------------------------------------------------------------------------
# Lines 348, 353-376: change_password endpoints
# ---------------------------------------------------------------------------


class TestChangePassword:
    def test_oauth_user_cannot_change(self):
        user = _fake_user(password_hash=None)

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={"current_password": "OldPass123!", "new_password": "NewPass123!"},
                )

        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == AuthErrorCode.INVALID_CREDENTIALS

    def test_wrong_current_password(self):
        user = _fake_user()

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("app.gateway.auth.password.verify_password_async", new_callable=AsyncMock, return_value=False),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={"current_password": "WrongPass!", "new_password": "NewPass123!"},
                )

        assert resp.status_code == 400
        assert "Current password is incorrect" in resp.json()["detail"]["message"]

    def test_email_conflict(self):
        user = _fake_user()
        other = _fake_user(user_id=uuid4(), email="taken@example.com")
        provider = MagicMock()
        provider.get_user_by_email = AsyncMock(return_value=other)

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.auth.password.verify_password_async", new_callable=AsyncMock, return_value=True),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewPass123!",
                        "new_email": "taken@example.com",
                    },
                )

        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == AuthErrorCode.EMAIL_ALREADY_EXISTS

    def test_success_with_email_and_setup_clear(self):
        user = _fake_user(needs_setup=True)
        provider = MagicMock()
        provider.get_user_by_email = AsyncMock(return_value=None)
        provider.update_user = AsyncMock()

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.auth.password.verify_password_async", new_callable=AsyncMock, return_value=True),
            patch("app.gateway.auth.password.hash_password_async", new_callable=AsyncMock, return_value="$2b$12$newhash"),
            patch("app.gateway.routers.auth.create_access_token", return_value="new-jwt"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewPass123!",
                        "new_email": "new@example.com",
                    },
                )

        assert resp.status_code == 200
        assert user.needs_setup is False
        assert user.email == "new@example.com"
        provider.update_user.assert_awaited_once()

    def test_success_without_email(self):
        user = _fake_user(needs_setup=False)
        provider = MagicMock()
        provider.update_user = AsyncMock()

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.auth.password.verify_password_async", new_callable=AsyncMock, return_value=True),
            patch("app.gateway.auth.password.hash_password_async", new_callable=AsyncMock, return_value="$2b$12$newhash"),
            patch("app.gateway.routers.auth.create_access_token", return_value="new-jwt"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={"current_password": "OldPass123!", "new_password": "NewPass123!"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Password changed successfully"
        provider.update_user.assert_awaited_once()

    def test_email_same_user_no_conflict(self):
        """Same user changing to their own email should not conflict."""
        user = _fake_user(email="same@example.com")
        provider = MagicMock()
        provider.get_user_by_email = AsyncMock(return_value=user)
        provider.update_user = AsyncMock()

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.auth.password.verify_password_async", new_callable=AsyncMock, return_value=True),
            patch("app.gateway.auth.password.hash_password_async", new_callable=AsyncMock, return_value="$2b$12$newhash"),
            patch("app.gateway.routers.auth.create_access_token", return_value="new-jwt"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewPass123!",
                        "new_email": "same@example.com",
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Password changed successfully"


# ---------------------------------------------------------------------------
# Lines 382-383: get_me endpoint
# ---------------------------------------------------------------------------


class TestGetMe:
    def test_get_me(self):
        user = _fake_user(email="me@example.com", system_role="admin", needs_setup=True)

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/me")

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "me@example.com"
        assert body["system_role"] == "user"
        assert body["needs_setup"] is True


# ---------------------------------------------------------------------------
# Lines 400-451: setup_status endpoint
# ---------------------------------------------------------------------------


class TestSetupStatus:
    def test_first_cache_hit(self):
        """Cache hit before entering guard."""
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

    def test_cache_hit_inside_guard(self):
        """Cache hit inside inflight guard after miss outside."""
        import app.gateway.routers.auth as auth_mod

        provider = MagicMock()
        provider.count_admin_users = AsyncMock(return_value=1)
        now = time.time()
        cached_result = {"needs_setup": False}

        call_count = {"n": 0}

        def _fake_get(key, default=None):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                return default
            return (now, cached_result)

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

    def test_needs_setup_true_not_cached(self):
        """needs_setup=True should NOT be cached."""
        import app.gateway.routers.auth as auth_mod

        provider = MagicMock()
        provider.count_admin_users = AsyncMock(return_value=0)

        cache: dict = {}

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.55"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", {}),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", asyncio.Lock()),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is True
        assert "10.0.0.55" not in cache

    def test_stale_cache_eviction(self):
        """Evict stale cache entries when at capacity."""
        import app.gateway.routers.auth as auth_mod

        provider = MagicMock()
        provider.count_admin_users = AsyncMock(return_value=1)
        now = time.time()
        cache: dict = {}
        for i in range(auth_mod._MAX_TRACKED_SETUP_STATUS_IPS):
            cache[f"stale-{i}"] = (now - auth_mod._SETUP_STATUS_CACHE_TTL_SECONDS - 100, {"needs_setup": False})

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.99"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", {}),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", asyncio.Lock()),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200

    def test_active_cache_eviction_half(self):
        """Evict half by time when still full after stale removal."""
        import app.gateway.routers.auth as auth_mod

        provider = MagicMock()
        provider.count_admin_users = AsyncMock(return_value=1)
        now = time.time()
        cache: dict = {}
        for i in range(auth_mod._MAX_TRACKED_SETUP_STATUS_IPS):
            cache[f"active-{i}"] = (now, {"needs_setup": False})

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.99"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", {}),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", asyncio.Lock()),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert len(cache) < auth_mod._MAX_TRACKED_SETUP_STATUS_IPS


# ---------------------------------------------------------------------------
# Lines 473-492: initialize_admin endpoint
# ---------------------------------------------------------------------------


class TestInitializeAdmin:
    def test_admin_exists_returns_409(self):
        with (
            patch("app.gateway.routers.auth._count_active_super_admin_users", new_callable=AsyncMock, return_value=1),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/initialize",
                    json={"email": "admin@example.com", "password": "AdminPass123!"},
                )

        assert resp.status_code == 409
        data = resp.json()
        assert "detail" in data

    def test_success(self):
        with (
            patch("app.gateway.routers.auth._count_active_super_admin_users", new_callable=AsyncMock, return_value=0),
            patch("app.gateway.routers.auth.create_access_token", return_value="admin-jwt"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/initialize",
                    json={"email": "admin@example.com", "password": "AdminPass123!"},
                )

        assert resp.status_code == 201
        assert resp.json()["email"] == "admin@example.com"
        assert resp.json()["system_role"] == "super_admin"

    def test_race_condition(self):
        """Concurrent duplicate auth user creation triggers 409."""
        app = _make_app()
        with TestClient(app) as client:
            client.post(
                "/api/v1/auth/register",
                json={"email": "admin@example.com", "password": "StrongPass123!"},
            )
            resp = client.post(
                "/api/v1/auth/initialize",
                json={"email": "admin@example.com", "password": "AdminPass123!"},
            )

        assert resp.status_code == 409
        data = resp.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# Lines 505-511, 524: OAuth endpoints
# ---------------------------------------------------------------------------


class TestOAuth:
    def test_unsupported_provider(self):
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/auth/oauth/twitter")
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_supported_provider_501(self):
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/auth/oauth/github")
        assert resp.status_code == 501
        data = resp.json()
        assert "detail" in data

    def test_callback_501(self):
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/auth/callback/github?code=abc&state=xyz")
        assert resp.status_code == 501
        data = resp.json()
        assert "detail" in data
