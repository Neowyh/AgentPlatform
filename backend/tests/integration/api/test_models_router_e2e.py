"""E2E tests for the models router (backend/app/gateway/routers/models.py).

Covers:
- GET /api/models
- GET /api/models/{model_name}
- Sensitive field filtering (no API key in response)
- 404 for non-existent models
- Permission enforcement
- Response shape validation
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.gateway.authz import AuthContext, get_current_rbac_user, get_optional_rbac_user
from app.gateway.deps import get_config
from app.gateway.routers.models import router as models_router

pytestmark = pytest.mark.no_auto_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: str = "user") -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    user.role = role
    user.department_id = None
    user.disabled = False
    return user


def _make_app(role: str = "user"):
    """Build a test app with auth middleware and the models router."""
    user = _make_user(role=role)
    app = make_authed_test_app()
    app.include_router(models_router)

    async def _stub():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub
    app.dependency_overrides[get_optional_rbac_user] = _stub
    return app, user


def _make_app_with_config(cfg, role: str = "user"):
    """Build a test app with both auth overrides and config dependency override."""
    app, user = _make_app(role=role)
    app.dependency_overrides[get_config] = lambda: cfg
    return app, user


def _mock_model_config(
    name: str = "gpt-4",
    model: str = "gpt-4",
    display_name: str = "GPT-4",
    description: str = "OpenAI GPT-4",
    supports_thinking: bool = False,
    supports_reasoning_effort: bool = False,
):
    """Return a mock model config mimicking AppConfig.models items."""
    m = MagicMock()
    m.name = name
    m.model = model
    m.display_name = display_name
    m.description = description
    m.supports_thinking = supports_thinking
    m.supports_reasoning_effort = supports_reasoning_effort
    # Simulate sensitive fields that must NOT appear in API response
    m.api_key = "sk-secret-key-12345"
    m.api_base = "https://api.openai.com/v1"
    m.temperature = 0.7
    m.max_tokens = 4096
    return m


def _mock_token_usage(enabled: bool = True):
    tu = MagicMock()
    tu.enabled = enabled
    return tu


def _mock_config(models=None, token_usage_enabled: bool = True):
    """Return a mock AppConfig with models and token_usage."""
    cfg = MagicMock()
    cfg.models = models if models is not None else [_mock_model_config()]
    cfg.token_usage = _mock_token_usage(enabled=token_usage_enabled)
    cfg.get_model_config = MagicMock(side_effect=lambda name: next((m for m in (models or [_mock_model_config()]) if m.name == name), None))
    return cfg


# ---------------------------------------------------------------------------
# Tests — GET /api/models
# ---------------------------------------------------------------------------


class TestListModels:
    """Tests for GET /api/models."""

    def test_list_models_returns_models_and_token_usage(self):
        """Response contains 'models' list and 'token_usage' object."""
        cfg = _mock_config(models=[_mock_model_config()])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        body = resp.json()
        assert "models" in body
        assert "token_usage" in body
        assert isinstance(body["models"], list)
        assert isinstance(body["token_usage"], dict)

    def test_list_models_returns_all_fields(self):
        """Each model contains name, model, display_name, description, supports_thinking, supports_reasoning_effort."""
        cfg = _mock_config(
            models=[
                _mock_model_config(
                    name="claude-3-opus",
                    model="claude-3-opus",
                    display_name="Claude 3 Opus",
                    description="Anthropic Claude 3 Opus",
                    supports_thinking=True,
                    supports_reasoning_effort=False,
                ),
            ]
        )
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        m = resp.json()["models"][0]
        assert m["name"] == "claude-3-opus"
        assert m["model"] == "claude-3-opus"
        assert m["display_name"] == "Claude 3 Opus"
        assert m["description"] == "Anthropic Claude 3 Opus"
        assert m["supports_thinking"] is True
        assert m["supports_reasoning_effort"] is False

    def test_list_models_empty(self):
        """Empty model list returns empty array with token_usage still present."""
        cfg = _mock_config(models=[])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        body = resp.json()
        assert body["models"] == []
        assert "token_usage" in body
        assert isinstance(body["token_usage"]["enabled"], bool)

    def test_list_models_multiple(self):
        """Multiple models are all returned."""
        models = [
            _mock_model_config(name="gpt-4", display_name="GPT-4"),
            _mock_model_config(name="gpt-3.5-turbo", model="gpt-3.5-turbo", display_name="GPT-3.5 Turbo"),
            _mock_model_config(name="claude-3", model="claude-3", display_name="Claude 3"),
        ]
        cfg = _mock_config(models=models)
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        assert len(resp.json()["models"]) == 3

    def test_list_models_null_display_name_and_description(self):
        """Models with None display_name and description serialize correctly."""
        model = _mock_model_config(display_name=None, description=None)
        cfg = _mock_config(models=[model])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        m = resp.json()["models"][0]
        assert m["display_name"] is None
        assert m["description"] is None

    def test_list_models_token_usage_enabled(self):
        """Token usage reflects config value."""
        cfg = _mock_config(token_usage_enabled=True)
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        assert resp.json()["token_usage"]["enabled"] is True

    def test_list_models_token_usage_disabled(self):
        """Token usage reflects config value when disabled."""
        cfg = _mock_config(token_usage_enabled=False)
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        assert resp.json()["token_usage"]["enabled"] is False


# ---------------------------------------------------------------------------
# Tests — Sensitive field filtering
# ---------------------------------------------------------------------------


class TestSensitiveFieldFiltering:
    """Verify that API keys and internal config fields are NOT leaked."""

    def test_no_api_key_in_list_response(self):
        """GET /api/models must not expose api_key."""
        cfg = _mock_config(models=[_mock_model_config()])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        for m in resp.json()["models"]:
            assert "api_key" not in m

    def test_no_api_base_in_list_response(self):
        """GET /api/models must not expose api_base."""
        cfg = _mock_config(models=[_mock_model_config()])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        for m in resp.json()["models"]:
            assert "api_base" not in m

    def test_no_temperature_in_list_response(self):
        """GET /api/models must not expose temperature."""
        cfg = _mock_config(models=[_mock_model_config()])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        for m in resp.json()["models"]:
            assert "temperature" not in m

    def test_no_max_tokens_in_list_response(self):
        """GET /api/models must not expose max_tokens."""
        cfg = _mock_config(models=[_mock_model_config()])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        for m in resp.json()["models"]:
            assert "max_tokens" not in m

    def test_no_sensitive_fields_in_detail_response(self):
        """GET /api/models/{name} must not expose api_key, api_base, temperature, max_tokens."""
        model = _mock_model_config()
        cfg = _mock_config(models=[model])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get(f"/api/models/{model.name}")
        assert resp.status_code == 200
        body = resp.json()
        assert "api_key" not in body
        assert "api_base" not in body
        assert "temperature" not in body
        assert "max_tokens" not in body


# ---------------------------------------------------------------------------
# Tests — GET /api/models/{model_name}
# ---------------------------------------------------------------------------


class TestGetModelDetail:
    """Tests for GET /api/models/{model_name}."""

    def test_get_model_found(self):
        """Returns model details for existing model."""
        model = _mock_model_config(name="gpt-4", display_name="GPT-4")
        cfg = _mock_config(models=[model])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models/gpt-4")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "gpt-4"
        assert body["model"] == "gpt-4"
        assert body["display_name"] == "GPT-4"
        assert body["description"] == "OpenAI GPT-4"

    def test_get_model_supports_thinking(self):
        """Returns supports_thinking and supports_reasoning_effort flags."""
        model = _mock_model_config(
            name="claude-3-opus",
            supports_thinking=True,
            supports_reasoning_effort=True,
        )
        cfg = _mock_config(models=[model])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models/claude-3-opus")
        assert resp.status_code == 200
        body = resp.json()
        assert body["supports_thinking"] is True
        assert body["supports_reasoning_effort"] is True

    def test_get_model_not_found(self):
        """Returns 404 for non-existent model."""
        cfg = _mock_config(models=[])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models/nonexistent-model")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_model_not_found_message(self):
        """404 detail includes the model name."""
        cfg = _mock_config(models=[])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models/gpt-99")
        assert resp.status_code == 404
        assert "gpt-99" in resp.json()["detail"]

    def test_get_model_null_optional_fields(self):
        """Detail endpoint returns null for missing display_name and description."""
        model = _mock_model_config(display_name=None, description=None)
        cfg = _mock_config(models=[model])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get(f"/api/models/{model.name}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] is None
        assert body["description"] is None


# ---------------------------------------------------------------------------
# Tests — Permission enforcement
# ---------------------------------------------------------------------------


class TestPermissionEnforcement:
    """Verify auth middleware is required for model endpoints."""

    def _make_noauth_app(self):
        """Build a minimal app with no auth context stamped on requests."""
        cfg = _mock_config()

        class _NoAuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Callable) -> Response:
                return await call_next(request)

        app = FastAPI()
        app.add_middleware(_NoAuthMiddleware)
        app.dependency_overrides[get_config] = lambda: cfg
        app.include_router(models_router)
        return app

    def test_unauthenticated_list_denied(self):
        """GET /api/models without auth context is rejected."""
        app = self._make_noauth_app()
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 401

    def test_unauthenticated_detail_denied(self):
        """GET /api/models/{name} without auth context is rejected."""
        app = self._make_noauth_app()
        with TestClient(app) as client:
            resp = client.get("/api/models/gpt-4")
        assert resp.status_code == 401

    def test_authenticated_user_can_list_models(self):
        """Authenticated user with correct role can list models."""
        cfg = _mock_config()
        app, _ = _make_app_with_config(cfg, role="user")
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200

    def test_authenticated_user_can_get_model_detail(self):
        """Authenticated user can get model detail."""
        model = _mock_model_config()
        cfg = _mock_config(models=[model])
        app, _ = _make_app_with_config(cfg, role="user")
        with TestClient(app) as client:
            resp = client.get(f"/api/models/{model.name}")
        assert resp.status_code == 200

    def test_viewer_role_denied_models(self):
        """Viewer role (limited permissions) gets 403 on models:read."""
        cfg = _mock_config()
        app = FastAPI()
        app.dependency_overrides[get_config] = lambda: cfg

        viewer_user = _make_user(role="viewer")
        viewer_user.department_id = None

        async def _stub_viewer():
            return viewer_user

        app.dependency_overrides[get_current_rbac_user] = _stub_viewer
        app.dependency_overrides[get_optional_rbac_user] = _stub_viewer

        # Stamp auth context with viewer-only permissions (no models:read)
        class _ViewerAuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Callable) -> Response:
                from app.gateway.authz import Permissions

                request.state.user = viewer_user
                request.state.auth = AuthContext(
                    user=viewer_user,
                    permissions=[Permissions.THREADS_READ, Permissions.RUNS_READ],
                )
                return await call_next(request)

        app.add_middleware(_ViewerAuthMiddleware)
        app.include_router(models_router)

        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 403
        assert "models:read" in resp.json()["detail"]

    def test_viewer_role_denied_model_detail(self):
        """Viewer role gets 403 on GET /api/models/{name}."""
        cfg = _mock_config()
        app = FastAPI()
        app.dependency_overrides[get_config] = lambda: cfg

        viewer_user = _make_user(role="viewer")

        async def _stub_viewer():
            return viewer_user

        app.dependency_overrides[get_current_rbac_user] = _stub_viewer
        app.dependency_overrides[get_optional_rbac_user] = _stub_viewer

        class _ViewerAuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Callable) -> Response:
                from app.gateway.authz import Permissions

                request.state.user = viewer_user
                request.state.auth = AuthContext(
                    user=viewer_user,
                    permissions=[Permissions.THREADS_READ, Permissions.RUNS_READ],
                )
                return await call_next(request)

        app.add_middleware(_ViewerAuthMiddleware)
        app.include_router(models_router)

        with TestClient(app) as client:
            resp = client.get("/api/models/gpt-4")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests — Response shape validation
# ---------------------------------------------------------------------------


class TestResponseShape:
    """Verify response matches expected JSON schema."""

    def test_list_response_shape(self):
        """List response has exactly 'models' and 'token_usage' top-level keys."""
        cfg = _mock_config()
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"models", "token_usage"}

    def test_model_response_shape(self):
        """Each model has exactly the expected keys (no extra fields)."""
        cfg = _mock_config()
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        expected_keys = {"name", "model", "display_name", "description", "supports_thinking", "supports_reasoning_effort"}
        for m in resp.json()["models"]:
            assert set(m.keys()) == expected_keys

    def test_detail_response_shape(self):
        """Detail response has exactly the expected keys."""
        model = _mock_model_config()
        cfg = _mock_config(models=[model])
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get(f"/api/models/{model.name}")
        assert resp.status_code == 200
        expected_keys = {"name", "model", "display_name", "description", "supports_thinking", "supports_reasoning_effort"}
        assert set(resp.json().keys()) == expected_keys

    def test_token_usage_shape(self):
        """token_usage object contains only 'enabled' key."""
        cfg = _mock_config()
        app, _ = _make_app_with_config(cfg)
        with TestClient(app) as client:
            resp = client.get("/api/models")
        assert resp.status_code == 200
        assert set(resp.json()["token_usage"].keys()) == {"enabled"}
