"""Global authentication middleware — fail-closed safety net.

Rejects unauthenticated requests to non-public paths with 401. When a
request passes the cookie check, resolves the JWT payload to a real
``User`` object and stamps it into both ``request.state.user`` and the
``deerflow.runtime.user_context`` contextvar so that repository-layer
owner filtering works automatically via the sentinel pattern.

Fine-grained permission checks remain in authz.py decorators.
"""

import logging
import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.gateway.auth.errors import AuthErrorCode, AuthErrorResponse
from app.gateway.auth_disabled import (
    AUTH_SOURCE_AUTH_DISABLED,
    AUTH_SOURCE_INTERNAL,
    AUTH_SOURCE_PAT,
    AUTH_SOURCE_SESSION,
    get_auth_disabled_user,
    is_auth_disabled,
)
from app.gateway.authz import AuthContext, resolve_route_permissions
from app.gateway.internal_auth import INTERNAL_AUTH_HEADER_NAME, get_internal_user, is_valid_internal_auth_token
from app.gateway.request_path import get_request_route_path
from deerflow.runtime.user_context import reset_current_user, set_current_user

logger = logging.getLogger(__name__)

# Paths that never require authentication.
_PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/oauth/",
    "/api/v1/auth/callback/",
    "/api/webhooks/",
)

# Exact auth paths that are public (login/register/status check).
# /api/v1/auth/me, /api/v1/auth/change-password etc. are NOT public.
_PUBLIC_EXACT_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/auth/login/local",
        "/api/v1/auth/register",
        "/api/v1/auth/logout",
        "/api/v1/auth/setup-status",
        "/api/v1/auth/initialize",
        "/api/v1/auth/providers",
    }
)


def _is_public(path: str) -> bool:
    stripped = path.rstrip("/")
    if stripped in _PUBLIC_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    """Strict auth gate: reject requests without a valid session.

    Two-stage check for non-public paths:

    1. Cookie presence — return 401 NOT_AUTHENTICATED if missing
    2. JWT validation via ``get_optional_user_from_request`` — return 401
       TOKEN_INVALID if the token is absent, malformed, expired, or the
       signed user does not exist / is stale

    On success, stamps ``request.state.user`` and the
    ``deerflow.runtime.user_context`` contextvar so that repository-layer
    owner filters work downstream without every route needing a
    ``@require_auth`` decorator. Routes that need per-resource
    authorization (e.g. "user A cannot read user B's thread by guessing
    the URL") should additionally use ``@require_permission(...,
    owner_check=True)`` for explicit enforcement — but authentication
    itself is fully handled here.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if _is_public(get_request_route_path(request)):
            return await call_next(request)

        # T1 first-token timing: auth is the first pre-token segment.
        auth_started = time.perf_counter()

        internal_user = None
        if is_valid_internal_auth_token(request.headers.get(INTERNAL_AUTH_HEADER_NAME)):
            internal_user = get_internal_user()

        auth_source = AUTH_SOURCE_SESSION
        access_token = request.cookies.get("access_token")
        authorization = request.headers.get("authorization")
        pat_scopes: frozenset[str] = frozenset()

        if internal_user is not None:
            user = internal_user
            auth_source = AUTH_SOURCE_INTERNAL
        elif authorization is not None and not is_auth_disabled():
            from app.gateway.auth.pat import authenticate_pat, is_pat_allowed_route

            try:
                user, pat_scopes = await authenticate_pat(request.app, authorization)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            if not is_pat_allowed_route(request.method, get_request_route_path(request)):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "PAT credentials are not permitted on this route"},
                )
            auth_source = AUTH_SOURCE_PAT
        elif access_token:
            from app.gateway.deps import get_current_user_from_request

            try:
                user = await get_current_user_from_request(request)
            except HTTPException as exc:
                if not is_auth_disabled():
                    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
                user = get_auth_disabled_user()
                auth_source = AUTH_SOURCE_AUTH_DISABLED
        elif is_auth_disabled():
            user = get_auth_disabled_user()
            auth_source = AUTH_SOURCE_AUTH_DISABLED
        else:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": AuthErrorResponse(
                        code=AuthErrorCode.NOT_AUTHENTICATED,
                        message="Authentication required",
                    ).model_dump()
                },
            )

        request.state.user = user
        request.state.auth_source = auth_source

        # The platform identity (users_ext) is the only authorization source.
        # Trusted sources (internal/auth-disabled) return None and fall to the
        # provider default; session and PAT callers resolve — or are denied —
        # through the same fail-closed read the decorators reuse.
        from app.gateway.authz import resolve_platform_identity

        identity = await resolve_platform_identity(request, user)
        platform_role = identity.get("role") if identity is not None else None

        permissions = await resolve_route_permissions(
            user,
            is_internal=auth_source == AUTH_SOURCE_INTERNAL,
            platform_role=platform_role,
        )
        if auth_source == AUTH_SOURCE_PAT:
            permissions = [permission for permission in permissions if permission in pat_scopes]
        request.state.auth = AuthContext(user=user, permissions=permissions)
        logger.info(
            "first_token_timing stage=auth elapsed_ms=%.1f path=%s",
            (time.perf_counter() - auth_started) * 1000,
            get_request_route_path(request),
        )
        token = set_current_user(user)
        try:
            return await call_next(request)
        finally:
            reset_current_user(token)
