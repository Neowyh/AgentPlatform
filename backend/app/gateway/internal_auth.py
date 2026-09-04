"""Authentication for trusted Gateway internal callers."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from types import SimpleNamespace
from typing import Any

from deerflow.config.paths import make_safe_user_id
from ideer.runtime.user_context import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

INTERNAL_AUTH_HEADER_NAME = "X-IDeer-Internal-Token"
UPSTREAM_INTERNAL_AUTH_HEADER_NAME = "X-DeerFlow-Internal-Token"
INTERNAL_OWNER_USER_ID_HEADER_NAME = "X-DeerFlow-Owner-User-Id"
INTERNAL_AUTH_ENV_VAR = "IDEER_INTERNAL_AUTH_TOKEN"
UPSTREAM_INTERNAL_AUTH_ENV_VAR = "DEER_FLOW_INTERNAL_AUTH_TOKEN"
INTERNAL_SYSTEM_ROLE = "internal"

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


def create_internal_auth_headers(*, owner_user_id: str | None = None) -> dict[str, str]:
    """Return headers that authenticate trusted Gateway internal calls."""
    headers = {INTERNAL_AUTH_HEADER_NAME: _get_internal_token()}
    if owner_user_id:
        headers[INTERNAL_OWNER_USER_ID_HEADER_NAME] = owner_user_id
    return headers


def is_valid_internal_auth_token(token: str | None) -> bool:
    """Return True when *token* matches this Gateway worker's internal token."""
    return bool(token) and secrets.compare_digest(token, _get_internal_token())


def get_internal_user(owner_user_id: str | None = None):
    """Return the synthetic user used for trusted internal channel calls."""
    """Return the synthetic user used for trusted internal channel calls.

    When *owner_user_id* is provided (extracted from the
    ``X-DeerFlow-Owner-User-Id`` header), the synthetic user's ``.id``
    carries the actual channel owner instead of ``DEFAULT_USER_ID``.
    This ensures that ``get_effective_user_id()`` and downstream
    filesystem-path resolution (per-user custom skills, memory, thread
    data) use the correct identity for IM channel messages instead of
    falling back to ``"default"``.

    The owner id is normalized through :func:`make_safe_user_id` so that
    IM channel ids containing characters outside ``[A-Za-z0-9_-]`` (e.g.
    Feishu ``open_id`` prefixed with ``ou_`` and containing underscores
    that the rest of the system may treat as path separators, or
    Telegram chat ids like ``-1001234567890``) cannot be used to escape
    the per-user storage bucket or impersonate a different user via
    header value tricks (e.g. trailing slashes, ``..`` segments). The
    normalization is lossy but deterministic: two distinct raw inputs
    never share a safe id, so cross-user bleed is impossible.
    """
    effective_id = make_safe_user_id(owner_user_id) if owner_user_id else DEFAULT_USER_ID
    return SimpleNamespace(id=effective_id, system_role=INTERNAL_SYSTEM_ROLE)


def get_trusted_internal_owner_user_id(request: Any) -> str | None:
    """Return the owner override for a trusted internal request, if present.

    The header is ignored for normal browser/API callers. It is only honored
    after ``AuthMiddleware`` has validated the internal auth token and stamped
    the synthetic internal user onto ``request.state.user``.
    """
    user = getattr(getattr(request, "state", None), "user", None)
    if getattr(user, "system_role", None) != INTERNAL_SYSTEM_ROLE:
        return None

    owner_user_id = request.headers.get(INTERNAL_OWNER_USER_ID_HEADER_NAME)
    if not owner_user_id:
        return None
    owner_user_id = owner_user_id.strip()
    return owner_user_id or None
