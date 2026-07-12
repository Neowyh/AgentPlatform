"""Additional tests for app.gateway.routers.auth — coverage gaps."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.gateway.auth.errors import AuthErrorCode
from app.gateway.auth.models import User
from app.gateway.routers.auth import (
    _check_rate_limit,
    _get_client_ip,
    _record_login_failure,
    _trusted_proxies,
)
from app.gateway.routers.auth import (
    router as auth_router,
)

pytestmark = pytest.mark.no_auto_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app():
    """Build a minimal FastAPI app with the auth router mounted."""
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
    """Return a fully-populated User suitable for mocking."""
    from uuid import uuid4

    return User(
        id=user_id or uuid4(),
        email=email,
        password_hash=password_hash,
        system_role=system_role,
        needs_setup=needs_setup,
        token_version=token_version,
    )


def _patch_provider(*, authenticate_return=None, create_user_return=None, count_admin=0):
    """Return a mock LocalAuthProvider with pre-configured async methods."""
    provider = MagicMock()
    provider.authenticate = AsyncMock(return_value=authenticate_return)
    provider.create_user = AsyncMock(return_value=create_user_return)
    provider.count_admin_users = AsyncMock(return_value=count_admin)
    provider.update_user = AsyncMock()
    provider.get_user_by_email = AsyncMock(return_value=None)
    return provider


def _mock_auth_config(token_expiry_days=7):
    """Return a mock AuthConfig with the needed attribute."""
    cfg = MagicMock()
    cfg.token_expiry_days = token_expiry_days
    return cfg


# ---------------------------------------------------------------------------
# Line 348: change_password — OAuth user (password_hash is None)
# ---------------------------------------------------------------------------


class TestChangePasswordOAuthUser:
    """Line 348: OAuth users cannot change password."""

    def test_oauth_user_cannot_change_password(self):
        """User with password_hash=None raises 400."""
        user = _fake_user(password_hash=None)

        with patch(
            "app.gateway.routers.auth.get_current_user_from_request",
            new_callable=AsyncMock,
            return_value=user,
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewPass123!",
                    },
                )

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["code"] == AuthErrorCode.INVALID_CREDENTIALS
        assert "OAuth" in detail["message"]


# ---------------------------------------------------------------------------
# Lines 357-360: change_password — new_email conflicts with another user
# ---------------------------------------------------------------------------


class TestChangePasswordEmailConflict:
    """Lines 357-360: new_email already in use by another user."""

    def test_new_email_already_in_use(self):
        """Providing a new_email that belongs to another user raises 400."""
        user = _fake_user()
        other_id = uuid4()
        provider = MagicMock()
        existing_user = _fake_user(email="taken@example.com", user_id=other_id)
        provider.get_user_by_email = AsyncMock(return_value=existing_user)

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
        detail = resp.json()["detail"]
        assert detail["code"] == AuthErrorCode.EMAIL_ALREADY_EXISTS
        assert "Email already in use" in detail["message"]


# ---------------------------------------------------------------------------
# Line 368: change_password — needs_setup cleared when new_email provided
# ---------------------------------------------------------------------------


class TestChangePasswordClearsNeedsSetup:
    """Line 368: needs_setup flag is cleared when new_email is provided."""

    @patch("app.gateway.routers.auth._set_session_cookie")
    @patch("app.gateway.routers.auth.create_access_token", return_value="new-jwt")
    def test_needs_setup_cleared_with_new_email(self, _mock_token, _mock_cookie):
        """needs_setup=False after change-password with new_email on setup user."""
        user = _fake_user(needs_setup=True)
        provider = MagicMock()
        provider.get_user_by_email = AsyncMock(return_value=None)
        provider.update_user = AsyncMock()

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.auth.password.verify_password_async", new_callable=AsyncMock, return_value=True),
            patch("app.gateway.auth.password.hash_password_async", new_callable=AsyncMock, return_value="$2b$12$newhash"),
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
        provider.update_user.assert_awaited_once_with(user)


# ---------------------------------------------------------------------------
# Lines 415-417: setup_status — cache hit after waiting for inflight guard
# ---------------------------------------------------------------------------


class TestSetupStatusCachedAfterInflightWait:
    """Lines 415-417: Re-check cache after acquiring inflight guard."""

    def test_cache_hit_after_inflight_wait(self):
        """Inside the inflight guard, the second cache check finds a fresh entry."""
        import app.gateway.routers.auth as auth_mod

        provider = _patch_provider(count_admin=1)
        inflight: dict = {}
        guard = asyncio.Lock()

        # Build a cache that returns None on the first .get() (outside guard)
        # and returns a fresh cached result on the second .get() (inside guard).
        cached_result = {"needs_setup": False}
        call_count = {"n": 0}

        def _fake_get(key, default=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return default  # first check outside guard: miss
            return (time.time(), cached_result)  # second check inside guard: hit

        cache_mock = MagicMock()
        cache_mock.get = MagicMock(side_effect=_fake_get)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.10"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache_mock),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", inflight),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", guard),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is False


# ---------------------------------------------------------------------------
# Lines 423-430: setup_status — cache eviction when dict is full
# ---------------------------------------------------------------------------


class TestSetupStatusCacheEviction:
    """Lines 423-430: Evict stale entries when cache is full, then evict half by time."""

    def test_eviction_stale_entries(self):
        """Cache eviction removes stale entries when at capacity."""
        import app.gateway.routers.auth as auth_mod

        provider = _patch_provider(count_admin=1)
        now = time.time()
        cache: dict = {}
        inflight: dict = {}
        guard = asyncio.Lock()

        # Fill cache to capacity with stale (expired) entries
        for i in range(auth_mod._MAX_TRACKED_SETUP_STATUS_IPS):
            cache[f"stale-{i}"] = (now - auth_mod._SETUP_STATUS_CACHE_TTL_SECONDS - 100, {"needs_setup": False})

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.99"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", inflight),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", guard),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_setup"] is True

    def test_eviction_half_by_time(self):
        """Cache eviction removes half by time when still full after stale removal."""
        import app.gateway.routers.auth as auth_mod

        provider = _patch_provider(count_admin=1)
        now = time.time()
        cache: dict = {}
        inflight: dict = {}
        guard = asyncio.Lock()

        # Fill cache with active (non-stale) entries so stale eviction does nothing
        for i in range(auth_mod._MAX_TRACKED_SETUP_STATUS_IPS):
            cache[f"active-{i}"] = (now, {"needs_setup": False})

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.99"),
            patch.object(auth_mod, "_SETUP_STATUS_CACHE", cache),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT", inflight),
            patch.object(auth_mod, "_SETUP_STATUS_INFLIGHT_GUARD", guard),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_setup"] is True
        # After eviction, cache should be at most half full + the new entry
        assert len(cache) < auth_mod._MAX_TRACKED_SETUP_STATUS_IPS


# ---------------------------------------------------------------------------
# Lines 482-484: initialize_admin — ValueError race condition
# ---------------------------------------------------------------------------


class TestInitializeAdminRace:
    """Lines 482-484: create_user ValueError during initialize raises 409."""

    def test_initialize_race_condition(self):
        """Concurrent create_user raising ValueError triggers 409."""
        provider = _patch_provider(count_admin=0)
        session = AsyncMock()
        context = AsyncMock()
        context.__aenter__ = AsyncMock(return_value=session)
        context.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._count_active_super_admin_users", new_callable=AsyncMock, return_value=0),
            patch("app.gateway.routers.auth.get_session_factory", return_value=MagicMock(return_value=context)),
            patch("app.gateway.routers.auth.create_auth_user_with_rbac", new_callable=AsyncMock, side_effect=IntegrityError("insert", {}, Exception())),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/initialize",
                    json={"email": "admin@example.com", "password": "AdminPass123!"},
                )

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["code"] == AuthErrorCode.SYSTEM_ALREADY_INITIALIZED
        assert "System already initialized" in detail["message"]


# ---------------------------------------------------------------------------
# Line 506: oauth_login — unsupported provider
# ---------------------------------------------------------------------------


class TestOAuthUnsupportedProvider:
    """Line 506: Unsupported OAuth provider returns 400."""

    def test_unsupported_provider(self):
        """OAuth login with unsupported provider returns 400."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/auth/oauth/twitter")

        assert resp.status_code == 400
        assert "Unsupported OAuth provider" in resp.json()["detail"]

    def test_supported_provider_returns_501(self):
        """OAuth login with supported provider still returns 501 (not implemented)."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/auth/oauth/github")

        assert resp.status_code == 501


# ---------------------------------------------------------------------------
# _trusted_proxies
# ---------------------------------------------------------------------------


class TestTrustedProxies:
    def test_empty_env(self, monkeypatch):
        monkeypatch.delenv("AUTH_TRUSTED_PROXIES", raising=False)
        assert _trusted_proxies() == []

    def test_single_ip(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.1")
        nets = _trusted_proxies()
        assert len(nets) == 1

    def test_cidr_range(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        nets = _trusted_proxies()
        assert len(nets) == 1

    def test_multiple_entries(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8,192.168.1.0/24")
        nets = _trusted_proxies()
        assert len(nets) == 2

    def test_invalid_entry_skipped(self, monkeypatch, caplog):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "not-an-ip,10.0.0.0/8")
        nets = _trusted_proxies()
        assert len(nets) == 1
        assert "ignoring invalid entry" in caplog.text

    def test_empty_entries_ignored(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", ",,,")
        nets = _trusted_proxies()
        assert len(nets) == 0

    def test_whitespace_entries_stripped(self, monkeypatch):
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", " 10.0.0.0/8 , 192.168.1.1 ")
        nets = _trusted_proxies()
        assert len(nets) == 2


# ---------------------------------------------------------------------------
# _get_client_ip — additional edge cases
# ---------------------------------------------------------------------------


class TestGetClientIp:
    def test_trusted_proxy_with_invalid_peer_host(self, monkeypatch):
        """Non-parseable peer_host should fall through to return peer_host."""
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "unknown"
        req.headers = {"x-real-ip": "1.2.3.4"}
        assert _get_client_ip(req) == "unknown"

    def test_empty_x_real_ip_with_trusted_proxy(self, monkeypatch):
        """Empty X-Real-IP should fall through to peer host."""
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "10.5.6.7"
        req.headers = {"x-real-ip": ""}
        assert _get_client_ip(req) == "10.5.6.7"

    def test_whitespace_x_real_ip_with_trusted_proxy(self, monkeypatch):
        """Whitespace-only X-Real-IP should fall through to peer host."""
        monkeypatch.setenv("AUTH_TRUSTED_PROXIES", "10.0.0.0/8")
        req = MagicMock()
        req.client.host = "10.5.6.7"
        req.headers = {"x-real-ip": "   "}
        assert _get_client_ip(req) == "10.5.6.7"


# ---------------------------------------------------------------------------
# _check_rate_limit — additional edge cases
# ---------------------------------------------------------------------------


class TestCheckRateLimit:
    def test_expired_lockout_allows(self):
        """After lockout period expires, IP should be allowed again."""
        from app.gateway.routers.auth import _login_attempts

        _login_attempts.clear()
        ip = "10.99.99.99"
        # Simulate 5 failures with expired lockout
        _login_attempts[ip] = (5, time.time() - 1)
        _check_rate_limit(ip)  # Should not raise (lockout expired)
        assert ip not in _login_attempts

    def test_lockout_not_yet_expired(self):
        from app.gateway.routers.auth import _login_attempts

        _login_attempts.clear()
        ip = "10.99.99.98"
        _login_attempts[ip] = (5, time.time() + 300)
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit(ip)
        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# _record_login_failure — eviction
# ---------------------------------------------------------------------------


class TestRecordLoginFailure:
    def test_eviction_when_dict_full(self):
        from app.gateway.routers.auth import _MAX_TRACKED_IPS, _login_attempts

        _login_attempts.clear()
        # Fill dict to capacity with expired lockouts
        now = time.time()
        for i in range(_MAX_TRACKED_IPS):
            _login_attempts[f"ip-{i}"] = (5, now - 100)
        # This should trigger eviction
        _record_login_failure("new-ip")
        assert "new-ip" in _login_attempts

    def test_eviction_when_still_full(self):
        from app.gateway.routers.auth import _MAX_TRACKED_IPS, _login_attempts

        _login_attempts.clear()
        now = time.time()
        # Fill with active lockouts (not expired)
        for i in range(_MAX_TRACKED_IPS):
            _login_attempts[f"ip-{i}"] = (5, now + 300)
        # Trigger eviction — should evict cheapest-to-lose half
        _record_login_failure("new-ip")
        assert "new-ip" in _login_attempts
        assert len(_login_attempts) <= _MAX_TRACKED_IPS

    def test_lockout_triggered_at_max(self):
        from app.gateway.routers.auth import _MAX_LOGIN_ATTEMPTS, _login_attempts

        _login_attempts.clear()
        ip = "test-ip"
        for _ in range(_MAX_LOGIN_ATTEMPTS):
            _record_login_failure(ip)
        fail_count, lock_until = _login_attempts[ip]
        assert fail_count == _MAX_LOGIN_ATTEMPTS
        assert lock_until > time.time()

    def test_below_max_no_lockout(self):
        from app.gateway.routers.auth import _MAX_LOGIN_ATTEMPTS, _login_attempts

        _login_attempts.clear()
        ip = "test-ip2"
        for _ in range(_MAX_LOGIN_ATTEMPTS - 1):
            _record_login_failure(ip)
        fail_count, lock_until = _login_attempts[ip]
        assert fail_count == _MAX_LOGIN_ATTEMPTS - 1
        assert lock_until == 0.0


# ---------------------------------------------------------------------------
# _password_is_common
# ---------------------------------------------------------------------------


class TestPasswordIsCommon:
    def test_common_password(self):
        from app.gateway.routers.auth import _password_is_common

        assert _password_is_common("password") is True

    def test_not_common(self):
        from app.gateway.routers.auth import _password_is_common

        assert _password_is_common("Tr0ub4dor&3-Horse") is False

    def test_case_insensitive(self):
        from app.gateway.routers.auth import _password_is_common

        assert _password_is_common("PASSWORD") is True
        assert _password_is_common("Password123") is True
