"""Authentication for trusted Gateway internal callers."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from types import SimpleNamespace

from ideer.runtime.user_context import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

INTERNAL_AUTH_HEADER_NAME = "X-IDeer-Internal-Token"
INTERNAL_AUTH_ENV_VAR = "IDEER_INTERNAL_AUTH_TOKEN"

_internal_token: str | None = None


def _get_internal_token() -> str:
    """Return (and cache) the internal auth token.

    Priority:
    1. Explicit ``IDEER_INTERNAL_AUTH_TOKEN`` env var (always honoured).
    2. Deterministic derivation from ``AUTH_JWT_SECRET`` so that all workers
       sharing the same JWT secret automatically agree on an internal token.
    3. Random fallback (single-worker dev mode only).

    Lazily evaluated so that ``AUTH_JWT_SECRET`` (set by ``get_auth_config()``
    during startup) is available even when this module is imported early.
    """
    global _internal_token
    if _internal_token is not None:
        return _internal_token

    token = os.environ.get(INTERNAL_AUTH_ENV_VAR)
    if token:
        _internal_token = token
        return _internal_token

    # P2-AUTH-03: derive from JWT_SECRET for multi-worker consistency
    jwt_secret = os.environ.get("AUTH_JWT_SECRET", "")
    if jwt_secret:
        _internal_token = hashlib.sha256(f"{jwt_secret}:internal-auth".encode()).hexdigest()[:43]
        logger.info("IDEER_INTERNAL_AUTH_TOKEN not set — derived deterministically from AUTH_JWT_SECRET")
        return _internal_token

    # NOTE: AUTH_JWT_SECRET is set by get_auth_config() during startup.
    # If this function is called before startup completes, the random
    # fallback will be cached and all subsequent calls will use it.
    # This is safe for single-worker dev but will break multi-worker
    # deployments if startup ordering is not respected.
    logger.warning("IDEER_INTERNAL_AUTH_TOKEN not set and AUTH_JWT_SECRET is empty -- using auto-generated token (will not persist across restarts). Ensure get_auth_config() is called before any internal auth usage.")
    _internal_token = secrets.token_urlsafe(32)
    return _internal_token


def create_internal_auth_headers() -> dict[str, str]:
    """Return headers that authenticate trusted Gateway internal calls."""
    return {INTERNAL_AUTH_HEADER_NAME: _get_internal_token()}


def is_valid_internal_auth_token(token: str | None) -> bool:
    """Return True when *token* matches this Gateway worker's internal token."""
    return bool(token) and secrets.compare_digest(token, _get_internal_token())


def get_internal_user():
    """Return the synthetic user used for trusted internal channel calls."""
    return SimpleNamespace(id=DEFAULT_USER_ID, system_role="internal")
