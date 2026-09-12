from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.gateway import authz
from app.gateway.authz import require_permission
from app.gateway.deps import get_config, get_optional_user_from_request
from deerflow.authz.principal import build_principal_from_context
from deerflow.authz.provider import AuthzRequest
from deerflow.config.app_config import AppConfig

router = APIRouter(prefix="/api", tags=["models"])


async def _authorized_model_names(request: Request, config: AppConfig) -> set[str] | None:
    """Return the model names visible to the request, or ``None`` for all."""
    auth_config = authz._get_route_authorization_config()
    if not auth_config.enabled:
        return None
    user = await get_optional_user_from_request(request)
    if user is None:
        return None
    try:
        provider = authz._get_cached_route_provider(auth_config)
        if provider is None:
            raise RuntimeError("authorization provider unavailable")
        principal = build_principal_from_context(
            {"user_id": str(user.id), "user_role": getattr(user, "system_role", None)},
            default_role=auth_config.default_role,
        )
        names = [model.name for model in config.models]
        allowed = provider.filter_resources(principal, "model", names)
        if not isinstance(allowed, list):
            raise TypeError("AuthorizationProvider.filter_resources must return list[str]")
        return set(allowed)
    except Exception:
        if auth_config.fail_closed:
            return set()
        return None


async def _authorize_model_use(request: Request, model_name: str, user: object, auth_config: object) -> bool | None:
    """Evaluate per-model use while preserving the configured failure mode."""
    try:
        provider = authz._get_cached_route_provider(auth_config)
        if provider is None:
            raise RuntimeError("authorization provider unavailable")
        principal = build_principal_from_context(
            {"user_id": str(user.id), "user_role": getattr(user, "system_role", None)},
            default_role=auth_config.default_role,
        )
        result = provider.aauthorize(AuthzRequest(principal=principal, resource="model", action="use", target=model_name))
        decision = await result if hasattr(result, "__await__") else result
        return bool(decision.allow)
    except Exception:
        if auth_config.fail_closed:
            return False
        return None


class ModelResponse(BaseModel):
    """Response model for model information."""

    name: str = Field(..., description="Unique identifier for the model")
    model: str = Field(..., description="Actual provider model identifier")
    display_name: str | None = Field(None, description="Human-readable name")
    description: str | None = Field(None, description="Model description")
    supports_thinking: bool = Field(default=False, description="Whether model supports thinking mode")
    supports_reasoning_effort: bool = Field(default=False, description="Whether model supports reasoning effort")


class TokenUsageResponse(BaseModel):
    """Token usage display configuration."""

    enabled: bool = Field(default=False, description="Whether token usage display is enabled")


class ModelsListResponse(BaseModel):
    """Response model for listing all models."""

    models: list[ModelResponse]
    token_usage: TokenUsageResponse


@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="List All Models",
    description="Retrieve a list of all available AI models configured in the system.",
)
@require_permission("models", "read")
async def list_models(request: Request, config: AppConfig = Depends(get_config)) -> ModelsListResponse:
    """List all available models from configuration.

    Returns model information suitable for frontend display,
    excluding sensitive fields like API keys and internal configuration.

    Returns:
        A list of all configured models with their metadata and token usage display settings.

    Example Response:
        ```json
        {
            "models": [
                {
                    "name": "gpt-4",
                    "model": "gpt-4",
                    "display_name": "GPT-4",
                    "description": "OpenAI GPT-4 model",
                    "supports_thinking": false,
                    "supports_reasoning_effort": false
                },
                {
                    "name": "claude-3-opus",
                    "model": "claude-3-opus",
                    "display_name": "Claude 3 Opus",
                    "description": "Anthropic Claude 3 Opus model",
                    "supports_thinking": true,
                    "supports_reasoning_effort": false
                }
            ],
            "token_usage": {
                "enabled": true
            }
        }
        ```
    """
    allowed_names = await _authorized_model_names(request, config)
    models = [
        ModelResponse(
            name=model.name,
            model=model.model,
            display_name=model.display_name,
            description=model.description,
            supports_thinking=model.supports_thinking,
            supports_reasoning_effort=model.supports_reasoning_effort,
        )
        for model in config.models
        if allowed_names is None or model.name in allowed_names
    ]
    return ModelsListResponse(
        models=models,
        token_usage=TokenUsageResponse(enabled=config.token_usage.enabled),
    )


@router.get(
    "/models/{model_name}",
    response_model=ModelResponse,
    summary="Get Model Details",
    description="Retrieve detailed information about a specific AI model by its name.",
)
@require_permission("models", "read")
async def get_model(request: Request, model_name: str, config: AppConfig = Depends(get_config)) -> ModelResponse:
    """Get a specific model by name.

    Args:
        model_name: The unique name of the model to retrieve.

    Returns:
        Model information if found.

    Raises:
        HTTPException: 404 if model not found.

    Example Response:
        ```json
        {
            "name": "gpt-4",
            "display_name": "GPT-4",
            "description": "OpenAI GPT-4 model",
            "supports_thinking": false
        }
        ```
    """
    model = config.get_model_config(model_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    auth_config = authz._get_route_authorization_config()
    user = await get_optional_user_from_request(request) if auth_config.enabled else None
    if user is not None:
        allowed = await _authorize_model_use(request, model_name, user, auth_config)
        if allowed is False:
            raise HTTPException(status_code=403, detail="Model access denied")

    allowed_names = await _authorized_model_names(request, config)
    if allowed_names is not None and model_name not in allowed_names:
        raise HTTPException(status_code=403, detail="Model access denied")

    return ModelResponse(
        name=model.name,
        model=model.model,
        display_name=model.display_name,
        description=model.description,
        supports_thinking=model.supports_thinking,
        supports_reasoning_effort=model.supports_reasoning_effort,
    )
