"""Tests for the models router (backend/app/gateway/routers/models.py).

Covers:
- GET /api/models — list all available AI models with metadata
- GET /api/models/{model_name} — get details for a specific model
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.deps import get_config
from app.gateway.routers.models import router as models_router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(mock_config: MagicMock) -> FastAPI:
    """Create a test FastAPI app with models router, overriding get_config dependency."""
    app = FastAPI()
    app.include_router(models_router)
    app.dependency_overrides[get_config] = lambda: mock_config
    return app


def _make_model_config(name: str, **kwargs) -> MagicMock:
    """Create a mock ModelConfig with the fields the router accesses."""
    model = MagicMock()
    model.name = name
    model.model = kwargs.get("model", name)
    model.display_name = kwargs.get("display_name", name)
    model.description = kwargs.get("description", None)
    model.supports_thinking = kwargs.get("supports_thinking", False)
    model.supports_reasoning_effort = kwargs.get("supports_reasoning_effort", False)
    return model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListModels:
    """Tests for GET /api/models."""

    def test_list_models_returns_list(self):
        """List models returns a ModelsListResponse with models and token_usage."""
        mock_config = MagicMock()
        mock_config.models = [
            _make_model_config("gpt-4", model="gpt-4", display_name="GPT-4"),
            _make_model_config("claude-3", model="claude-3", display_name="Claude 3"),
        ]
        mock_config.token_usage.enabled = True

        app = _make_app(mock_config)
        client = TestClient(app)
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) == 2
        assert data["token_usage"]["enabled"] is True

    def test_list_models_empty(self):
        """List models returns empty models list when no models configured."""
        mock_config = MagicMock()
        mock_config.models = []
        mock_config.token_usage.enabled = False

        app = _make_app(mock_config)
        client = TestClient(app)
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["models"], list)
        assert len(data["models"]) == 0


class TestGetModel:
    """Tests for GET /api/models/{model_name}."""

    def test_get_model_by_name(self):
        """Get model by valid name returns model details."""
        mock_model = _make_model_config("gpt-4", model="gpt-4", display_name="GPT-4", description="OpenAI GPT-4")
        mock_config = MagicMock()
        mock_config.get_model_config.return_value = mock_model

        app = _make_app(mock_config)
        client = TestClient(app)
        response = client.get("/api/models/gpt-4")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "gpt-4"
        assert data["model"] == "gpt-4"
        assert data["display_name"] == "GPT-4"

    def test_get_model_not_found(self):
        """Get model with non-existent name returns 404."""
        mock_config = MagicMock()
        mock_config.get_model_config.return_value = None

        app = _make_app(mock_config)
        client = TestClient(app)
        response = client.get("/api/models/nonexistent")
        assert response.status_code == 404
