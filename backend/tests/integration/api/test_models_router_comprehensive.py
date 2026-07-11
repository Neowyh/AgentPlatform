"""Comprehensive tests for the models router (backend/app/gateway/routers/models.py).

Covers every code path in the router module:
- Pydantic response models: ModelResponse, TokenUsageResponse, ModelsListResponse
- GET /api/models  -- list all available AI models with metadata
- GET /api/models/{model_name} -- get details for a specific model

Uses the existing `_router_auth_helpers.make_authed_test_app` pattern with
TestClient, overriding `get_config` dependency with a mock ``AppConfig``.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.deps import get_config
from app.gateway.routers.models import (
    ModelResponse,
    ModelsListResponse,
    TokenUsageResponse,
)
from app.gateway.routers.models import (
    router as models_router,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(mock_config: MagicMock) -> FastAPI:
    """Create a test FastAPI app with models router, overriding get_config dependency."""
    app = make_authed_test_app()
    app.include_router(models_router)
    app.dependency_overrides[get_config] = lambda: mock_config
    return app


def _make_model_config(
    name: str,
    *,
    model: str | None = None,
    display_name: str | None = None,
    description: str | None = None,
    supports_thinking: bool = False,
    supports_reasoning_effort: bool = False,
) -> MagicMock:
    """Create a mock ModelConfig with the fields the router accesses."""
    cfg = MagicMock()
    cfg.name = name
    cfg.model = model if model is not None else name
    cfg.display_name = display_name
    cfg.description = description
    cfg.supports_thinking = supports_thinking
    cfg.supports_reasoning_effort = supports_reasoning_effort
    return cfg


def _make_config(*model_cfgs: MagicMock, token_usage_enabled: bool = False) -> MagicMock:
    """Build a mock ``AppConfig`` with the given model configs and token_usage setting."""
    config = MagicMock()
    config.models = list(model_cfgs)
    config.token_usage.enabled = token_usage_enabled
    return config


# ===========================================================================
# Pydantic Model Unit Tests
# ===========================================================================


class TestModelResponse:
    """Unit tests for the ModelResponse Pydantic model."""

    def test_required_fields_only(self):
        """ModelResponse can be constructed with only required fields."""
        resp = ModelResponse(name="gpt-4", model="gpt-4")
        assert resp.name == "gpt-4"
        assert resp.model == "gpt-4"
        assert resp.display_name is None
        assert resp.description is None
        assert resp.supports_thinking is False
        assert resp.supports_reasoning_effort is False

    def test_all_fields_explicit(self):
        """ModelResponse accepts all fields explicitly."""
        resp = ModelResponse(
            name="claude-3-opus",
            model="claude-3-opus-20240229",
            display_name="Claude 3 Opus",
            description="Anthropic's most capable model",
            supports_thinking=True,
            supports_reasoning_effort=True,
        )
        assert resp.name == "claude-3-opus"
        assert resp.model == "claude-3-opus-20240229"
        assert resp.display_name == "Claude 3 Opus"
        assert resp.description == "Anthropic's most capable model"
        assert resp.supports_thinking is True
        assert resp.supports_reasoning_effort is True

    def test_display_name_none(self):
        """display_name defaults to None when not provided."""
        resp = ModelResponse(name="x", model="x")
        assert resp.display_name is None

    def test_description_none(self):
        """description defaults to None when not provided."""
        resp = ModelResponse(name="x", model="x")
        assert resp.description is None

    def test_supports_thinking_default(self):
        """supports_thinking defaults to False."""
        resp = ModelResponse(name="x", model="x")
        assert resp.supports_thinking is False

    def test_supports_reasoning_effort_default(self):
        """supports_reasoning_effort defaults to False."""
        resp = ModelResponse(name="x", model="x")
        assert resp.supports_reasoning_effort is False

    def test_serialization_roundtrip(self):
        """ModelResponse survives JSON serialization and deserialization."""
        original = ModelResponse(
            name="gpt-4",
            model="gpt-4-turbo",
            display_name="GPT-4 Turbo",
            description="Fast and capable",
            supports_thinking=False,
            supports_reasoning_effort=True,
        )
        data = original.model_dump()
        restored = ModelResponse(**data)
        assert restored == original

    def test_json_serializable(self):
        """ModelResponse can be serialized to JSON string."""
        resp = ModelResponse(name="x", model="y", supports_thinking=True)
        json_str = resp.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "x"
        assert parsed["model"] == "y"
        assert parsed["supports_thinking"] is True

    def test_missing_required_name_raises(self):
        """ModelResponse requires the 'name' field."""
        with pytest.raises(Exception):
            ModelResponse(model="x")

    def test_missing_required_model_raises(self):
        """ModelResponse requires the 'model' field."""
        with pytest.raises(Exception):
            ModelResponse(name="x")


class TestTokenUsageResponse:
    """Unit tests for the TokenUsageResponse Pydantic model."""

    def test_default_enabled_false(self):
        """TokenUsageResponse defaults to enabled=False."""
        resp = TokenUsageResponse()
        assert resp.enabled is False

    def test_enabled_true(self):
        """TokenUsageResponse accepts enabled=True."""
        resp = TokenUsageResponse(enabled=True)
        assert resp.enabled is True

    def test_enabled_false_explicit(self):
        """TokenUsageResponse accepts explicit enabled=False."""
        resp = TokenUsageResponse(enabled=False)
        assert resp.enabled is False

    def test_serialization(self):
        """TokenUsageResponse serializes correctly."""
        resp = TokenUsageResponse(enabled=True)
        data = resp.model_dump()
        assert data == {"enabled": True}

    def test_deserialization(self):
        """TokenUsageResponse deserializes from dict."""
        resp = TokenUsageResponse(**{"enabled": True})
        assert resp.enabled is True


class TestModelsListResponse:
    """Unit tests for the ModelsListResponse Pydantic model."""

    def test_empty_models_list(self):
        """ModelsListResponse accepts an empty models list."""
        resp = ModelsListResponse(
            models=[],
            token_usage=TokenUsageResponse(enabled=False),
        )
        assert resp.models == []
        assert resp.token_usage.enabled is False

    def test_with_models(self):
        """ModelsListResponse accepts a list of ModelResponse."""
        m1 = ModelResponse(name="a", model="a")
        m2 = ModelResponse(name="b", model="b")
        resp = ModelsListResponse(
            models=[m1, m2],
            token_usage=TokenUsageResponse(enabled=True),
        )
        assert len(resp.models) == 2
        assert resp.models[0].name == "a"
        assert resp.models[1].name == "b"
        assert resp.token_usage.enabled is True

    def test_serialization_roundtrip(self):
        """ModelsListResponse survives JSON roundtrip."""
        original = ModelsListResponse(
            models=[
                ModelResponse(
                    name="gpt-4",
                    model="gpt-4",
                    display_name="GPT-4",
                    supports_thinking=True,
                ),
            ],
            token_usage=TokenUsageResponse(enabled=True),
        )
        data = original.model_dump()
        restored = ModelsListResponse(**data)
        assert len(restored.models) == 1
        assert restored.models[0].name == "gpt-4"
        assert restored.token_usage.enabled is True


# ===========================================================================
# GET /api/models  (list_models)
# ===========================================================================


class TestListModels:
    """Tests for GET /api/models."""

    def test_returns_200(self):
        """GET /api/models returns HTTP 200."""
        config = _make_config()
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        assert resp.status_code == 200

    def test_empty_models_list(self):
        """Returns empty models list when no models configured."""
        config = _make_config(token_usage_enabled=False)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        data = resp.json()
        assert data["models"] == []
        assert data["token_usage"]["enabled"] is False

    def test_single_model(self):
        """Returns a single model with correct fields."""
        mc = _make_model_config(
            "gpt-4",
            model="gpt-4",
            display_name="GPT-4",
            description="OpenAI GPT-4",
            supports_thinking=False,
            supports_reasoning_effort=False,
        )
        config = _make_config(mc, token_usage_enabled=True)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        data = resp.json()
        assert len(data["models"]) == 1
        m = data["models"][0]
        assert m["name"] == "gpt-4"
        assert m["model"] == "gpt-4"
        assert m["display_name"] == "GPT-4"
        assert m["description"] == "OpenAI GPT-4"
        assert m["supports_thinking"] is False
        assert m["supports_reasoning_effort"] is False
        assert data["token_usage"]["enabled"] is True

    def test_multiple_models(self):
        """Returns all configured models in order."""
        mc1 = _make_model_config("gpt-4", model="gpt-4", display_name="GPT-4")
        mc2 = _make_model_config("claude-3", model="claude-3", display_name="Claude 3")
        mc3 = _make_model_config("gemini-pro", model="gemini-pro", display_name="Gemini Pro")
        config = _make_config(mc1, mc2, mc3)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        data = resp.json()
        assert len(data["models"]) == 3
        assert data["models"][0]["name"] == "gpt-4"
        assert data["models"][1]["name"] == "claude-3"
        assert data["models"][2]["name"] == "gemini-pro"

    def test_model_with_thinking_support(self):
        """Model with supports_thinking=True is returned correctly."""
        mc = _make_model_config(
            "claude-3-opus",
            model="claude-3-opus-20240229",
            display_name="Claude 3 Opus",
            supports_thinking=True,
        )
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["supports_thinking"] is True
        assert m["supports_reasoning_effort"] is False

    def test_model_with_reasoning_effort_support(self):
        """Model with supports_reasoning_effort=True is returned correctly."""
        mc = _make_model_config("o1", model="o1", supports_reasoning_effort=True)
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["supports_thinking"] is False
        assert m["supports_reasoning_effort"] is True

    def test_model_with_both_thinking_and_reasoning_effort(self):
        """Model with both supports_thinking and supports_reasoning_effort."""
        mc = _make_model_config(
            "o3",
            model="o3",
            supports_thinking=True,
            supports_reasoning_effort=True,
        )
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["supports_thinking"] is True
        assert m["supports_reasoning_effort"] is True

    def test_model_with_null_display_name(self):
        """Model with display_name=None returns null in JSON."""
        mc = _make_model_config("anon-model", model="anon-model", display_name=None)
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["display_name"] is None

    def test_model_with_null_description(self):
        """Model with description=None returns null in JSON."""
        mc = _make_model_config("x", model="x", description=None)
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["description"] is None

    def test_model_with_all_null_optionals(self):
        """Model with both display_name and description as None."""
        mc = _make_model_config("bare", model="bare")
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["display_name"] is None
        assert m["description"] is None
        assert m["supports_thinking"] is False
        assert m["supports_reasoning_effort"] is False

    def test_model_name_differs_from_model_id(self):
        """name and model fields can differ."""
        mc = _make_model_config(
            "my-gpt",
            model="gpt-4-turbo-2024-04-09",
            display_name="My GPT",
        )
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["name"] == "my-gpt"
        assert m["model"] == "gpt-4-turbo-2024-04-09"

    def test_token_usage_enabled_true(self):
        """token_usage.enabled reflects config value True."""
        config = _make_config(token_usage_enabled=True)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        assert resp.json()["token_usage"]["enabled"] is True

    def test_token_usage_enabled_false(self):
        """token_usage.enabled reflects config value False."""
        config = _make_config(token_usage_enabled=False)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        assert resp.json()["token_usage"]["enabled"] is False

    def test_response_matches_models_list_response_schema(self):
        """Response body matches the ModelsListResponse schema."""
        mc = _make_model_config("m1", model="m1", display_name="M1")
        config = _make_config(mc, token_usage_enabled=True)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        data = resp.json()
        # Top-level keys
        assert set(data.keys()) == {"models", "token_usage"}
        # Model entry keys
        expected_model_keys = {
            "name",
            "model",
            "display_name",
            "description",
            "supports_thinking",
            "supports_reasoning_effort",
        }
        for m in data["models"]:
            assert set(m.keys()) == expected_model_keys
        # Token usage keys
        assert set(data["token_usage"].keys()) == {"enabled"}

    def test_response_content_type(self):
        """Response content type is application/json."""
        config = _make_config()
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        assert "application/json" in resp.headers["content-type"]

    def test_many_models(self):
        """Handles a large number of models without error."""
        models = [_make_model_config(f"model-{i}", model=f"model-{i}") for i in range(50)]
        config = _make_config(*models)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        assert resp.status_code == 200
        assert len(resp.json()["models"]) == 50

    def test_model_with_empty_string_display_name(self):
        """Model with empty string display_name is passed through."""
        mc = _make_model_config("x", model="x", display_name="")
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        # Empty string is distinct from None
        assert m["display_name"] == ""

    def test_model_with_empty_string_description(self):
        """Model with empty string description is passed through."""
        mc = _make_model_config("x", model="x", description="")
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["description"] == ""

    def test_model_with_special_characters_in_name(self):
        """Model names with special characters are handled correctly."""
        mc = _make_model_config(
            "gpt-4-turbo/2024-04-09",
            model="gpt-4-turbo/2024-04-09",
            display_name="GPT-4 Turbo (April)",
        )
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["name"] == "gpt-4-turbo/2024-04-09"
        assert m["display_name"] == "GPT-4 Turbo (April)"

    def test_model_with_long_description(self):
        """Model with a very long description is handled correctly."""
        long_desc = "A" * 5000
        mc = _make_model_config("x", model="x", description=long_desc)
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        assert resp.json()["models"][0]["description"] == long_desc

    def test_model_with_unicode_fields(self):
        """Model with unicode characters in fields is handled correctly."""
        mc = _make_model_config(
            "model-zh",
            model="model-zh",
            display_name="中文模型",
            description="支持中文的模型",
        )
        config = _make_config(mc)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["display_name"] == "中文模型"
        assert m["description"] == "支持中文的模型"


# ===========================================================================
# GET /api/models/{model_name}  (get_model)
# ===========================================================================


class TestGetModel:
    """Tests for GET /api/models/{model_name}."""

    def test_returns_200_for_existing_model(self):
        """GET /api/models/{model_name} returns 200 for a known model."""
        mc = _make_model_config(
            "gpt-4",
            model="gpt-4",
            display_name="GPT-4",
            description="OpenAI GPT-4",
        )
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/gpt-4")
        assert resp.status_code == 200

    def test_returns_correct_model_data(self):
        """Returned model data matches the config."""
        mc = _make_model_config(
            "claude-3-opus",
            model="claude-3-opus-20240229",
            display_name="Claude 3 Opus",
            description="Anthropic's most capable model",
            supports_thinking=True,
            supports_reasoning_effort=False,
        )
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/claude-3-opus")
        data = resp.json()
        assert data["name"] == "claude-3-opus"
        assert data["model"] == "claude-3-opus-20240229"
        assert data["display_name"] == "Claude 3 Opus"
        assert data["description"] == "Anthropic's most capable model"
        assert data["supports_thinking"] is True
        assert data["supports_reasoning_effort"] is False

    def test_returns_404_for_missing_model(self):
        """GET /api/models/{model_name} returns 404 when model not found."""
        config = _make_config()
        config.get_model_config.return_value = None
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/nonexistent")
        assert resp.status_code == 404

    def test_404_error_detail_message(self):
        """404 response includes the model name in the error detail."""
        config = _make_config()
        config.get_model_config.return_value = None
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/missing-model")
        data = resp.json()
        assert "missing-model" in data["detail"]

    def test_404_error_detail_format(self):
        """404 detail is a string containing the model name."""
        config = _make_config()
        config.get_model_config.return_value = None
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/bad-name")
        assert resp.json()["detail"] == "Model 'bad-name' not found"

    def test_get_model_with_thinking_support(self):
        """Model with supports_thinking=True is returned correctly."""
        mc = _make_model_config("o1", model="o1", supports_thinking=True, supports_reasoning_effort=True)
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/o1")
        data = resp.json()
        assert data["supports_thinking"] is True
        assert data["supports_reasoning_effort"] is True

    def test_get_model_with_null_optionals(self):
        """Model with None display_name and description returns null."""
        mc = _make_model_config("bare", model="bare")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/bare")
        data = resp.json()
        assert data["display_name"] is None
        assert data["description"] is None
        assert data["supports_thinking"] is False
        assert data["supports_reasoning_effort"] is False

    def test_get_model_name_differs_from_model_id(self):
        """name and model fields can differ on single model retrieval."""
        mc = _make_model_config(
            "my-claude",
            model="claude-3-opus-20240229",
            display_name="My Claude",
        )
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/my-claude")
        data = resp.json()
        assert data["name"] == "my-claude"
        assert data["model"] == "claude-3-opus-20240229"

    def test_get_model_calls_config_with_correct_name(self):
        """get_model_config is called with the model_name from the URL."""
        config = _make_config()
        config.get_model_config.return_value = None
        app = _make_app(config)
        client = TestClient(app)
        client.get("/api/models/some-model")
        config.get_model_config.assert_called_once_with("some-model")

    def test_get_model_with_special_characters_in_name(self):
        """Model names with special URL characters work correctly."""
        mc = _make_model_config(
            "gpt-4-turbo",
            model="gpt-4-turbo-2024-04-09",
        )
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/gpt-4-turbo")
        assert resp.status_code == 200
        assert resp.json()["name"] == "gpt-4-turbo"

    def test_get_model_with_url_encoded_name(self):
        """URL-encoded model names are decoded correctly."""
        mc = _make_model_config("my model", model="my model")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/my%20model")
        assert resp.status_code == 200
        # FastAPI decodes the path parameter
        config.get_model_config.assert_called_once_with("my model")

    def test_get_model_404_for_url_encoded_missing(self):
        """URL-encoded nonexistent model returns 404."""
        config = _make_config()
        config.get_model_config.return_value = None
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/not%20found")
        assert resp.status_code == 404
        config.get_model_config.assert_called_once_with("not found")

    def test_response_content_type_json(self):
        """Single model response has application/json content type."""
        mc = _make_model_config("x", model="x")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/x")
        assert "application/json" in resp.headers["content-type"]

    def test_response_matches_model_response_schema(self):
        """Response body keys match ModelResponse schema."""
        mc = _make_model_config(
            "m1",
            model="m1",
            display_name="M1",
            description="desc",
            supports_thinking=True,
            supports_reasoning_effort=True,
        )
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/m1")
        data = resp.json()
        expected_keys = {
            "name",
            "model",
            "display_name",
            "description",
            "supports_thinking",
            "supports_reasoning_effort",
        }
        assert set(data.keys()) == expected_keys

    def test_get_model_with_empty_string_display_name(self):
        """Empty string display_name is passed through, not converted to None."""
        mc = _make_model_config("x", model="x", display_name="")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/x")
        assert resp.json()["display_name"] == ""

    def test_get_model_with_empty_string_description(self):
        """Empty string description is passed through, not converted to None."""
        mc = _make_model_config("x", model="x", description="")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/x")
        assert resp.json()["description"] == ""

    def test_get_model_with_unicode_name(self):
        """Unicode model name in URL path works correctly."""
        mc = _make_model_config("中文模型", model="中文模型")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/中文模型")
        assert resp.status_code == 200
        config.get_model_config.assert_called_once_with("中文模型")

    def test_get_model_with_long_description(self):
        """Long description is returned without truncation."""
        long_desc = "B" * 5000
        mc = _make_model_config("x", model="x", description=long_desc)
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/x")
        assert resp.json()["description"] == long_desc
        assert len(resp.json()["description"]) == 5000

    def test_get_model_boolean_fields_both_false(self):
        """Both boolean fields default to False."""
        mc = _make_model_config("x", model="x", supports_thinking=False, supports_reasoning_effort=False)
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/x")
        data = resp.json()
        assert data["supports_thinking"] is False
        assert data["supports_reasoning_effort"] is False


# ===========================================================================
# Router Configuration Tests
# ===========================================================================


class TestRouterConfiguration:
    """Tests verifying router prefix and tags are correctly configured."""

    def test_router_prefix(self):
        """Router prefix is '/api'."""
        assert models_router.prefix == "/api"

    def test_router_tags(self):
        """Router tags include 'models'."""
        assert "models" in models_router.tags

    def test_router_has_list_models_route(self):
        """Router has a GET /models route."""
        paths = [r.path for r in models_router.routes if hasattr(r, "path")]
        assert any("/models" in p for p in paths)

    def test_router_has_get_model_route(self):
        """Router has a GET /models/{model_name} route."""
        has_param_route = any("model_name" in r.path for r in models_router.routes if hasattr(r, "path"))
        assert has_param_route


# ===========================================================================
# Edge Cases and Integration-Style Tests
# ===========================================================================


class TestListModelsEdgeCases:
    """Edge case tests for GET /api/models."""

    def test_models_list_preserves_order(self):
        """Models are returned in the same order as configured."""
        names = [f"model-{i}" for i in range(20)]
        models = [_make_model_config(n, model=n) for n in names]
        config = _make_config(*models)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        returned_names = [m["name"] for m in resp.json()["models"]]
        assert returned_names == names

    def test_duplicate_model_names_returned(self):
        """Duplicate model names in config are returned as-is (no dedup)."""
        mc1 = _make_model_config("same", model="v1")
        mc2 = _make_model_config("same", model="v2")
        config = _make_config(mc1, mc2)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        models = resp.json()["models"]
        assert len(models) == 2
        assert models[0]["model"] == "v1"
        assert models[1]["model"] == "v2"

    def test_list_models_iterates_over_config_models(self):
        """list_models iterates over config.models, not some other attribute."""
        config = MagicMock()
        config.models = [
            _make_model_config("a", model="a"),
            _make_model_config("b", model="b"),
        ]
        config.token_usage.enabled = False
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        assert len(resp.json()["models"]) == 2

    def test_token_usage_reflected_per_request(self):
        """token_usage.enabled is read from config on each request."""
        mc = _make_model_config("x", model="x")
        config = _make_config(mc, token_usage_enabled=True)
        app = _make_app(config)
        client = TestClient(app)
        # First request
        resp1 = client.get("/api/models")
        assert resp1.json()["token_usage"]["enabled"] is True
        # Modify config
        config.token_usage.enabled = False
        resp2 = client.get("/api/models")
        assert resp2.json()["token_usage"]["enabled"] is False


class TestGetModelEdgeCases:
    """Edge case tests for GET /api/models/{model_name}."""

    def test_get_model_passes_model_name_to_config(self):
        """The exact URL path segment is passed to get_model_config."""
        config = _make_config()
        config.get_model_config.return_value = None
        app = _make_app(config)
        client = TestClient(app)
        client.get("/api/models/exact-name")
        config.get_model_config.assert_called_once_with("exact-name")

    def test_get_model_404_is_http_exception(self):
        """The 404 for missing model is a proper HTTP error response."""
        config = _make_config()
        config.get_model_config.return_value = None
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/nope")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_get_model_returns_only_requested_model(self):
        """Only the requested model's data is returned, not a list."""
        mc = _make_model_config("target", model="target", display_name="Target")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/target")
        data = resp.json()
        # Should be a flat object, not wrapped in a list
        assert isinstance(data, dict)
        assert data["name"] == "target"

    def test_get_model_multiple_sequential_requests(self):
        """Multiple sequential get_model calls work correctly."""
        mc1 = _make_model_config("a", model="a")
        mc2 = _make_model_config("b", model="b")
        config = _make_config()
        app = _make_app(config)
        client = TestClient(app)

        config.get_model_config.return_value = mc1
        resp1 = client.get("/api/models/a")
        assert resp1.json()["name"] == "a"

        config.get_model_config.return_value = mc2
        resp2 = client.get("/api/models/b")
        assert resp2.json()["name"] == "b"

    def test_get_model_404_then_success(self):
        """A 404 followed by a successful request works correctly."""
        mc = _make_model_config("exists", model="exists")
        config = _make_config()
        app = _make_app(config)
        client = TestClient(app)

        config.get_model_config.return_value = None
        resp1 = client.get("/api/models/missing")
        assert resp1.status_code == 404

        config.get_model_config.return_value = mc
        resp2 = client.get("/api/models/exists")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "exists"

    def test_get_model_with_numeric_name(self):
        """Model name that looks like a number works correctly."""
        mc = _make_model_config("42", model="42")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/42")
        assert resp.status_code == 200
        assert resp.json()["name"] == "42"

    def test_get_model_with_dot_in_name(self):
        """Model name with dots works correctly."""
        mc = _make_model_config("gpt.4.turbo", model="gpt.4.turbo")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/gpt.4.turbo")
        assert resp.status_code == 200
        assert resp.json()["name"] == "gpt.4.turbo"

    def test_get_model_with_underscore_in_name(self):
        """Model name with underscores works correctly."""
        mc = _make_model_config("gpt_4_turbo", model="gpt_4_turbo")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/gpt_4_turbo")
        assert resp.status_code == 200
        assert resp.json()["name"] == "gpt_4_turbo"

    def test_get_model_with_colon_in_name(self):
        """Model name with colon works correctly."""
        mc = _make_model_config("provider:model", model="provider:model")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models/provider:model")
        assert resp.status_code == 200
        assert resp.json()["name"] == "provider:model"


# ===========================================================================
# Field-by-Field Coverage Tests
# ===========================================================================


class TestFieldCoverage:
    """Ensure every field in ModelResponse is exercised with non-default values."""

    def test_name_field(self):
        """name field is correctly returned."""
        mc = _make_model_config("test-name", model="m")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        assert client.get("/api/models/test-name").json()["name"] == "test-name"

    def test_model_field(self):
        """model field is correctly returned."""
        mc = _make_model_config("n", model="actual-model-id")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        assert client.get("/api/models/n").json()["model"] == "actual-model-id"

    def test_display_name_field(self):
        """display_name field is correctly returned."""
        mc = _make_model_config("n", model="n", display_name="Human Readable")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        assert client.get("/api/models/n").json()["display_name"] == "Human Readable"

    def test_description_field(self):
        """description field is correctly returned."""
        mc = _make_model_config("n", model="n", description="A detailed description")
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        assert client.get("/api/models/n").json()["description"] == "A detailed description"

    def test_supports_thinking_true(self):
        """supports_thinking=True is correctly returned."""
        mc = _make_model_config("n", model="n", supports_thinking=True)
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        assert client.get("/api/models/n").json()["supports_thinking"] is True

    def test_supports_reasoning_effort_true(self):
        """supports_reasoning_effort=True is correctly returned."""
        mc = _make_model_config("n", model="n", supports_reasoning_effort=True)
        config = _make_config(mc)
        config.get_model_config.return_value = mc
        app = _make_app(config)
        client = TestClient(app)
        assert client.get("/api/models/n").json()["supports_reasoning_effort"] is True

    def test_all_fields_in_list_endpoint(self):
        """All ModelResponse fields are present in list endpoint for each model."""
        mc = _make_model_config(
            "full",
            model="full-v2",
            display_name="Full Model",
            description="All fields set",
            supports_thinking=True,
            supports_reasoning_effort=True,
        )
        config = _make_config(mc, token_usage_enabled=True)
        app = _make_app(config)
        client = TestClient(app)
        resp = client.get("/api/models")
        m = resp.json()["models"][0]
        assert m["name"] == "full"
        assert m["model"] == "full-v2"
        assert m["display_name"] == "Full Model"
        assert m["description"] == "All fields set"
        assert m["supports_thinking"] is True
        assert m["supports_reasoning_effort"] is True
