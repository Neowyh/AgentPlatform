import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.gateway.authz import get_current_rbac_user, require_role
from deerflow.config.extensions_config import ExtensionsConfig, McpTaskToolsetConfig, get_extensions_config, reload_extensions_config
from ideer.persistence.models.user import UserModel, UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["mcp"])


class McpUserScopedAuthConfigResponse(BaseModel):
    """Per-user credential injection configuration for an MCP server."""

    enabled: bool = Field(default=True, description="Whether user-scoped credential injection is enabled")
    header: str = Field(default="Authorization", description="HTTP header to set with the resolved user credential")
    users: dict[str, str] = Field(default_factory=dict, description="Map of DeerFlow user id to credential header value")
    on_missing: Literal["deny", "passthrough"] = Field(default="deny", description="Behavior when the calling user has no mapped credential")
    model_config = ConfigDict(extra="allow")

    @field_validator("header")
    @classmethod
    def _validate_header_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_auth.header must not be empty")
        return value


class McpOAuthConfigResponse(BaseModel):
    """OAuth configuration for an MCP server."""

    enabled: bool = Field(default=True, description="Whether OAuth token injection is enabled")
    token_url: str = Field(default="", description="OAuth token endpoint URL")
    grant_type: Literal["client_credentials", "refresh_token"] = Field(default="client_credentials", description="OAuth grant type")
    client_id: str | None = Field(default=None, description="OAuth client ID")
    client_secret: str | None = Field(default=None, description="OAuth client secret")
    refresh_token: str | None = Field(default=None, description="OAuth refresh token")
    scope: str | None = Field(default=None, description="OAuth scope")
    audience: str | None = Field(default=None, description="OAuth audience")
    token_field: str = Field(default="access_token", description="Token response field containing access token")
    token_type_field: str = Field(default="token_type", description="Token response field containing token type")
    expires_in_field: str = Field(default="expires_in", description="Token response field containing expires-in seconds")
    default_token_type: str = Field(default="Bearer", description="Default token type when response omits token_type")
    refresh_skew_seconds: int = Field(default=60, description="Refresh this many seconds before expiry")
    extra_token_params: dict[str, str] = Field(default_factory=dict, description="Additional form params sent to token endpoint")


class McpServerConfigResponse(BaseModel):
    """Response model for MCP server configuration."""

    enabled: bool = Field(default=True, description="Whether this MCP server is enabled")
    type: str = Field(default="stdio", description="Transport type: 'stdio', 'sse', or 'http'")
    command: str | None = Field(default=None, description="Command to execute to start the MCP server (for stdio type)")
    args: list[str] = Field(default_factory=list, description="Arguments to pass to the command (for stdio type)")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables for the MCP server")
    url: str | None = Field(default=None, description="URL of the MCP server (for sse or http type)")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers to send (for sse or http type)")
    oauth: McpOAuthConfigResponse | None = Field(default=None, description="OAuth configuration for MCP HTTP/SSE servers")
    user_auth: McpUserScopedAuthConfigResponse | None = Field(default=None, description="Per-user credential injection for MCP HTTP/SSE servers")
    task_toolsets: list[McpTaskToolsetConfig] = Field(
        default_factory=list,
        description="Durable MCP submit/status/cancel tool groups",
    )
    description: str = Field(default="", description="Human-readable description of what this MCP server provides")

    @field_validator("headers")
    @classmethod
    def _validate_header_names(cls, value: dict[str, str]) -> dict[str, str]:
        seen: dict[str, str] = {}
        for header_name in value:
            lowered = header_name.lower()
            if lowered in seen:
                raise ValueError(f"headers maps the same HTTP header under two spellings ({seen[lowered]!r} and {header_name!r}); header names are case-insensitive")
            seen[lowered] = header_name
        return value


class McpConfigResponse(BaseModel):
    """Response model for MCP configuration."""

    mcp_servers: dict[str, McpServerConfigResponse] = Field(
        default_factory=dict,
        description="Map of MCP server name to configuration",
    )


class McpConfigUpdateRequest(BaseModel):
    """Request model for updating MCP configuration."""

    mcp_servers: dict[str, McpServerConfigResponse] = Field(
        ...,
        description="Map of MCP server name to configuration",
    )


_MASKED_VALUE = "***"
_SENSITIVE_EXTRA_KEY_RE = re.compile(
    r"(^|_)(api_key|apikey|access_key|private_key|client_secret|secret|token|password|passwd|credential|credentials|authorization|bearer)(_|$)",
    re.IGNORECASE,
)


def _normalize_config_key(key: str) -> str:
    with_boundaries = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", key)
    with_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", with_boundaries)
    return re.sub(r"[^a-z0-9]+", "_", with_boundaries.lower()).strip("_")


def _is_sensitive_extra_key(key: str) -> bool:
    return bool(_SENSITIVE_EXTRA_KEY_RE.search(_normalize_config_key(key)))


def _mask_sensitive_extra_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _MASKED_VALUE if _is_sensitive_extra_key(str(key)) else _mask_sensitive_extra_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_mask_sensitive_extra_value(item) for item in value]
    return value


def _merge_extra_value_preserving_masked(key: str, incoming_value: Any, existing_value: Any, *, existing_present: bool) -> Any:
    if incoming_value == _MASKED_VALUE and _is_sensitive_extra_key(key):
        if existing_present:
            return existing_value
        raise HTTPException(status_code=400, detail=f"Cannot set extra config key '{key}' to masked value '***'; provide a real value.")
    if isinstance(incoming_value, dict) and isinstance(existing_value, dict):
        return {nested_key: _merge_extra_value_preserving_masked(str(nested_key), nested_value, existing_value.get(nested_key), existing_present=nested_key in existing_value) for nested_key, nested_value in incoming_value.items()}
    if isinstance(incoming_value, list) and isinstance(existing_value, list) and len(incoming_value) == len(existing_value):
        if all(isinstance(item, dict) for item in incoming_value + existing_value):

            def _identity(item: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
                return tuple(sorted((str(key), value) for key, value in item.items() if not _is_sensitive_extra_key(str(key))))

            incoming_ids = [_identity(item) for item in incoming_value]
            existing_ids = [_identity(item) for item in existing_value]
            if incoming_ids != existing_ids and sorted(incoming_ids) == sorted(existing_ids) and any(_MASKED_VALUE in item.values() for item in incoming_value):
                raise HTTPException(status_code=400, detail=f"Cannot reorder masked extra config array '{key}'; send the stored order or provide real values.")
        return [_merge_extra_value_preserving_masked(key, nested, existing_value[index], existing_present=True) for index, nested in enumerate(incoming_value)]
    return incoming_value


def _mask_server_config(server: McpServerConfigResponse) -> McpServerConfigResponse:
    """Return a copy of server config with sensitive fields masked.

    Masks env values, header values, and removes OAuth secrets so they
    are not exposed through the GET API endpoint.
    """
    masked_env = {k: _MASKED_VALUE for k in server.env}
    masked_headers = {k: _MASKED_VALUE for k in server.headers}
    masked_oauth = None
    if server.oauth is not None:
        masked_oauth = server.oauth.model_copy(
            update={
                "client_secret": None,
                "refresh_token": None,
            }
        )
    masked_user_auth = None
    if server.user_auth is not None:
        masked_user_auth = server.user_auth.model_copy(
            update={
                "users": {key: _MASKED_VALUE for key in server.user_auth.users},
                **{key: _MASKED_VALUE if _is_sensitive_extra_key(key) else _mask_sensitive_extra_value(value) for key, value in (server.user_auth.model_extra or {}).items()},
            }
        )
    return server.model_copy(
        update={
            "env": masked_env,
            "headers": masked_headers,
            "oauth": masked_oauth,
            "user_auth": masked_user_auth,
        }
    )


def _merge_preserving_secrets(
    incoming: McpServerConfigResponse,
    existing: McpServerConfigResponse,
    *,
    preserve_omitted_fields: bool = True,
) -> McpServerConfigResponse:
    """Merge incoming config with existing, preserving secrets masked by GET.

    When the frontend toggles ``enabled`` it round-trips the full config:
    GET (masked) → modify enabled → PUT (masked values sent back).
    This function ensures masked values (``***``) are replaced with the
    real secrets from the current on-disk config.

    ``***`` is only accepted for keys that already exist in *existing*.
    New keys must provide a real value.

    For OAuth secrets, ``None`` means "preserve the existing stored value"
    so masked GET responses can be safely round-tripped. To explicitly clear
    a stored secret, clients may send an empty string, which is converted
    to ``None`` before persisting.
    """
    merged_env = {}
    for k, v in incoming.env.items():
        if v == _MASKED_VALUE:
            if k in existing.env:
                merged_env[k] = existing.env[k]
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot set env key '{k}' to masked value '***'; provide a real value.",
                )
        else:
            merged_env[k] = v

    merged_headers = {}
    for k, v in incoming.headers.items():
        if v == _MASKED_VALUE:
            if k in existing.headers:
                merged_headers[k] = existing.headers[k]
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot set header '{k}' to masked value '***'; provide a real value.",
                )
        else:
            merged_headers[k] = v

    merged_oauth = incoming.oauth
    if incoming.oauth is not None and existing.oauth is not None:
        # None = preserve (masked round-trip), "" = explicitly clear, else = new value
        merged_client_secret = existing.oauth.client_secret if incoming.oauth.client_secret is None else (None if incoming.oauth.client_secret == "" else incoming.oauth.client_secret)
        merged_refresh_token = existing.oauth.refresh_token if incoming.oauth.refresh_token is None else (None if incoming.oauth.refresh_token == "" else incoming.oauth.refresh_token)
        merged_oauth = incoming.oauth.model_copy(
            update={
                "client_secret": merged_client_secret,
                "refresh_token": merged_refresh_token,
            }
        )
    return incoming.model_copy(
        update={
            "env": merged_env,
            "headers": merged_headers,
            "oauth": merged_oauth,
            "user_auth": _merge_user_auth(incoming, existing, preserve_omitted_fields=preserve_omitted_fields),
        }
    )


def _merge_user_auth(
    incoming: McpServerConfigResponse,
    existing: McpServerConfigResponse,
    *,
    preserve_omitted_fields: bool,
) -> McpUserScopedAuthConfigResponse | None:
    """Merge caller credential configuration without losing masked secrets."""
    if "user_auth" not in incoming.model_fields_set:
        return existing.user_auth if preserve_omitted_fields else None
    incoming_auth = incoming.user_auth
    if incoming_auth is None:
        return None
    existing_auth = existing.user_auth
    if not preserve_omitted_fields or existing_auth is None:
        base: dict[str, Any] = {}
    else:
        base = {
            "enabled": existing_auth.enabled,
            "header": existing_auth.header,
            "users": existing_auth.users,
            "on_missing": existing_auth.on_missing,
            **(existing_auth.model_extra or {}),
        }
    fields_set = incoming_auth.model_fields_set
    for field_name in ("enabled", "header", "on_missing"):
        if field_name in fields_set or not preserve_omitted_fields:
            base[field_name] = getattr(incoming_auth, field_name)
    if "users" in fields_set or not preserve_omitted_fields:
        old_users = existing_auth.users if existing_auth is not None else {}
        merged_users: dict[str, str] = {}
        for user_id, value in incoming_auth.users.items():
            if value == _MASKED_VALUE:
                if user_id not in old_users:
                    raise HTTPException(status_code=400, detail=f"Cannot set user_auth credential for '{user_id}' to masked value '***'; provide a real value.")
                merged_users[user_id] = old_users[user_id]
            else:
                merged_users[user_id] = value
        base["users"] = merged_users
    for key, value in (incoming_auth.model_extra or {}).items():
        old_extra = (existing_auth.model_extra or {}).get(key) if existing_auth is not None else None
        base[key] = _merge_extra_value_preserving_masked(key, value, old_extra, existing_present=existing_auth is not None and key in (existing_auth.model_extra or {}))
    return McpUserScopedAuthConfigResponse(**base)


@router.get(
    "/mcp/config",
    response_model=McpConfigResponse,
    summary="Get MCP Configuration",
    description="Retrieve the current Model Context Protocol (MCP) server configurations.",
)
async def get_mcp_configuration() -> McpConfigResponse:
    """Get the current MCP configuration.

    Returns:
        The current MCP configuration with all servers.

    Example:
        ```json
        {
            "mcp_servers": {
                "github": {
                    "enabled": true,
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "***"},
                    "description": "GitHub MCP server for repository operations"
                }
            }
        }
        ```
    """
    config = get_extensions_config()

    servers = {name: _mask_server_config(McpServerConfigResponse(**server.model_dump())) for name, server in config.mcp_servers.items()}
    return McpConfigResponse(mcp_servers=servers)


@router.put(
    "/mcp/config",
    response_model=McpConfigResponse,
    summary="Update MCP Configuration",
    description="Update Model Context Protocol (MCP) server configurations and save to file.",
)
@require_role(UserRole.SUPER_ADMIN)
async def update_mcp_configuration(
    request: McpConfigUpdateRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> McpConfigResponse:
    """Update the MCP configuration.

    This will:
    1. Save the new configuration to the mcp_config.json file
    2. Reload the configuration cache
    3. Reset MCP tools cache to trigger reinitialization

    Args:
        request: The new MCP configuration to save.

    Returns:
        The updated MCP configuration.

    Raises:
        HTTPException: 500 if the configuration file cannot be written.

    Example Request:
        ```json
        {
            "mcp_servers": {
                "github": {
                    "enabled": true,
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "$GITHUB_TOKEN"},
                    "description": "GitHub MCP server for repository operations"
                }
            }
        }
        ```
    """
    try:
        # Get the current config path (or determine where to save it)
        config_path = ExtensionsConfig.resolve_config_path()

        # If no config file exists, create one in the parent directory (project root)
        if config_path is None:
            config_path = Path.cwd().parent / "extensions_config.json"
            logger.info(f"No existing extensions config found. Creating new config at: {config_path}")

        # Load current config to preserve skills
        current_config = get_extensions_config()

        # Load raw (un-resolved) JSON from disk to use as the merge source.
        # This preserves $VAR placeholders in env values and top-level keys
        # like mcpInterceptors that would otherwise be lost.
        raw_servers: dict[str, dict] = {}
        raw_other_keys: dict = {}
        if config_path is not None and config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                raw_data = json.load(f)
            raw_servers = raw_data.get("mcpServers", {})
            # Preserve any top-level keys beyond mcpServers/skills
            for key, value in raw_data.items():
                if key not in ("mcpServers", "skills"):
                    raw_other_keys[key] = value

        # Merge incoming server configs with raw on-disk secrets
        merged_servers: dict[str, McpServerConfigResponse] = {}
        for name, incoming in request.mcp_servers.items():
            raw_server = raw_servers.get(name)
            if raw_server is not None:
                merged_servers[name] = _merge_preserving_secrets(
                    incoming,
                    McpServerConfigResponse(**raw_server),
                )
            else:
                merged_servers[name] = incoming

        # Build config data preserving all top-level keys from the original file
        config_data = dict(raw_other_keys)
        config_data["mcpServers"] = {name: server.model_dump() for name, server in merged_servers.items()}
        config_data["skills"] = {name: {"enabled": skill.enabled} for name, skill in current_config.skills.items()}

        # Write the configuration to file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        logger.info(f"MCP configuration updated and saved to: {config_path}")

        # NOTE: No need to reload/reset cache here - LangGraph Server (separate process)
        # will detect config file changes via mtime and reinitialize MCP tools automatically

        # Reload the configuration and update the global cache
        reloaded_config = reload_extensions_config()
        servers = {name: _mask_server_config(McpServerConfigResponse(**server.model_dump())) for name, server in reloaded_config.mcp_servers.items()}
        return McpConfigResponse(mcp_servers=servers)

    except Exception as e:
        logger.error(f"Failed to update MCP configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update MCP configuration: {str(e)}")
