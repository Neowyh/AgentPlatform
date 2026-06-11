"""E2E tests for the auth router (backend/app/gateway/routers/auth.py).

Covers all 9 auth endpoints:
- POST /api/v1/auth/login/local
- POST /api/v1/auth/register
- POST /api/v1/auth/logout
- POST /api/v1/auth/change-password
- GET /api/v1/auth/me
- GET /api/v1/auth/setup-status
- POST /api/v1/auth/initialize
- GET /api/v1/auth/oauth/{provider}
- GET /api/v1/auth/callback/{provider}

The endpoints in auth.py are inline — they don't delegate to standalone
helper functions.  We mock at the *internal dependency* level:

  * ``get_local_provider``  — the LocalAuthProvider singleton
  * ``get_current_user_from_request`` — cookie → User lookup (for /me, /change-password)
  * ``create_access_token``  — JWT creation
  * ``_set_session_cookie``  — cookie setter (avoid cookie side-effects)
  * ``get_auth_config``      — token expiry for login response
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.auth.models import User
from app.gateway.routers.auth import router as auth_router

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
):
    """Return a fully-populated User suitable for mocking."""
    return User(
        id=user_id or uuid4(),
        email=email,
        password_hash="$2b$12$fakehashedpassword",
        system_role=system_role,
        needs_setup=needs_setup,
        token_version=token_version,
    )


def _mock_auth_config(token_expiry_days=7):
    """Return a mock AuthConfig with the needed attribute."""
    cfg = MagicMock()
    cfg.token_expiry_days = token_expiry_days
    return cfg


# Shared patchers so every test is isolated.
def _patch_provider(*, authenticate_return=None, create_user_return=None, count_admin=0):
    """Return a mock LocalAuthProvider with pre-configured async methods.

    ``authenticate_return`` and ``create_user_return`` are always set
    (even when ``None``) so the mock never falls through to an auto-
    created AsyncMock whose truthiness would confuse the endpoint logic.
    """
    provider = MagicMock()
    provider.authenticate = AsyncMock(return_value=authenticate_return)
    provider.create_user = AsyncMock(return_value=create_user_return)
    provider.count_admin_users = AsyncMock(return_value=count_admin)
    provider.update_user = AsyncMock()
    provider.get_user_by_email = AsyncMock(return_value=None)
    return provider


# ---------------------------------------------------------------------------
# Tests — POST /api/v1/auth/login/local
# ---------------------------------------------------------------------------


class TestLoginLocal:
    """Tests for POST /api/v1/auth/login/local."""

    def test_login_success(self):
        """Login succeeds with valid credentials."""
        user = _fake_user()
        provider = _patch_provider(authenticate_return=user)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth.create_access_token", return_value="fake-jwt"),
            patch("app.gateway.routers.auth._set_session_cookie"),
            patch("app.gateway.routers.auth.get_auth_config", return_value=_mock_auth_config()),
            patch("app.gateway.routers.auth._get_client_ip", return_value="127.0.0.1"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/login/local",
                    data={"username": "test@example.com", "password": "ValidPass123!"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "expires_in" in data
        assert data["needs_setup"] is False

    def test_login_invalid_credentials(self):
        """Login fails with invalid credentials."""
        provider = _patch_provider(authenticate_return=None)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="127.0.0.1"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/login/local",
                    data={"username": "test@example.com", "password": "wrong"},
                )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests — POST /api/v1/auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    def test_register_success(self):
        """Register succeeds with valid data."""
        user = _fake_user(email="new@example.com", system_role="user")
        provider = _patch_provider(create_user_return=user)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth.create_access_token", return_value="fake-jwt"),
            patch("app.gateway.routers.auth._set_session_cookie"),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/register",
                    json={"email": "new@example.com", "password": "ValidPass123!"},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["system_role"] == "user"

    def test_register_duplicate_email(self):
        """Register fails with duplicate email."""
        provider = _patch_provider()
        provider.create_user = AsyncMock(side_effect=ValueError("Email already registered"))

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/register",
                    json={"email": "existing@example.com", "password": "ValidPass123!"},
                )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests — POST /api/v1/auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_success(self):
        """Logout clears session cookie."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Successfully logged out"


# ---------------------------------------------------------------------------
# Tests — POST /api/v1/auth/change-password
# ---------------------------------------------------------------------------


class TestChangePassword:
    """Tests for POST /api/v1/auth/change-password."""

    @patch("app.gateway.routers.auth._set_session_cookie")
    @patch("app.gateway.routers.auth.create_access_token", return_value="new-jwt")
    def test_change_password_success(self, _mock_token, _mock_cookie):
        """Change password succeeds with valid data."""
        user = _fake_user()
        provider = _patch_provider()
        provider.update_user = AsyncMock()

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch(
                "app.gateway.auth.password.verify_password_async",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.gateway.auth.password.hash_password_async",
                new_callable=AsyncMock,
                return_value="$2b$12$newhash",
            ),
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

        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

    def test_change_password_wrong_current(self):
        """Change password fails with wrong current password."""
        user = _fake_user()

        with (
            patch("app.gateway.routers.auth.get_current_user_from_request", new_callable=AsyncMock, return_value=user),
            patch(
                "app.gateway.auth.password.verify_password_async",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "WrongPass123!",
                        "new_password": "NewPass123!",
                    },
                )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests — GET /api/v1/auth/me
# ---------------------------------------------------------------------------


class TestGetMe:
    """Tests for GET /api/v1/auth/me."""

    def test_get_me_authenticated(self):
        """Get me returns current user info."""
        user = _fake_user(email="me@example.com", system_role="user")

        with patch(
            "app.gateway.routers.auth.get_current_user_from_request",
            new_callable=AsyncMock,
            return_value=user,
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"
        assert data["system_role"] == "user"


# ---------------------------------------------------------------------------
# Tests — GET /api/v1/auth/setup-status
# ---------------------------------------------------------------------------


class TestSetupStatus:
    """Tests for GET /api/v1/auth/setup-status."""

    def test_setup_status_needs_setup(self):
        """Setup status returns needs_setup=True when no admin exists."""
        provider = _patch_provider(count_admin=0)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.1"),
            patch("app.gateway.routers.auth._SETUP_STATUS_CACHE", {}),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is True

    def test_setup_status_already_setup(self):
        """Setup status returns needs_setup=False when admin exists."""
        provider = _patch_provider(count_admin=1)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
            patch("app.gateway.routers.auth._get_client_ip", return_value="10.0.0.2"),
            patch("app.gateway.routers.auth._SETUP_STATUS_CACHE", {}),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/setup-status")

        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is False


# ---------------------------------------------------------------------------
# Tests — POST /api/v1/auth/initialize
# ---------------------------------------------------------------------------


class TestInitializeAdmin:
    """Tests for POST /api/v1/auth/initialize."""

    @patch("app.gateway.routers.auth._set_session_cookie")
    @patch("app.gateway.routers.auth.create_access_token", return_value="admin-jwt")
    def test_initialize_success(self, _mock_token, _mock_cookie):
        """Initialize admin succeeds on first call."""
        user = _fake_user(email="admin@example.com", system_role="admin")
        provider = _patch_provider(create_user_return=user, count_admin=0)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/initialize",
                    json={"email": "admin@example.com", "password": "AdminPass123!"},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "admin@example.com"
        assert data["system_role"] == "admin"

    def test_initialize_already_done(self):
        """Initialize admin fails when already initialized."""
        provider = _patch_provider(count_admin=1)

        with (
            patch("app.gateway.routers.auth.get_local_provider", return_value=provider),
        ):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/initialize",
                    json={"email": "admin@example.com", "password": "AdminPass123!"},
                )

        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests — OAuth endpoints (placeholders)
# ---------------------------------------------------------------------------


class TestOAuth:
    """Tests for OAuth endpoints (currently placeholders)."""

    def test_oauth_login_placeholder(self):
        """OAuth login endpoint returns 501 (not implemented)."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/auth/oauth/google")
        assert resp.status_code == 501

    def test_oauth_callback_placeholder(self):
        """OAuth callback endpoint returns 501 (not implemented)."""
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/auth/callback/google", params={"code": "x", "state": "y"})
        assert resp.status_code == 501
