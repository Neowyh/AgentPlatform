"""CSRF protection middleware for FastAPI.

Per RFC-001:
State-changing operations require CSRF protection.
"""

import os
import secrets
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.gateway.auth.session_cookie_state import SESSION_COOKIE_MAX_AGE_STATE_ATTR
from app.gateway.auth_disabled import is_auth_disabled
from app.gateway.request_path import get_request_route_path

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_LENGTH = 64  # bytes
_CSRF_EXEMPT_EXACT_PATHS = frozenset({"/api/v1/auth/me", "/api/webhooks/github"})
_CSRF_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


def is_secure_request(request: Request) -> bool:
    """Detect whether the original client request was made over HTTPS."""
    return _request_scheme(request) == "https"


def generate_csrf_token() -> str:
    """Generate a secure random CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def auth_csrf_cookie_settings(request: Request) -> tuple[bool, int | None]:
    """Return secure and max-age settings shared by auth handlers."""
    secure = is_secure_request(request)
    if not secure:
        return secure, None
    try:
        from app.gateway.auth.config import get_auth_config

        max_age = get_auth_config().token_expiry_days * 24 * 60 * 60
    except (OSError, RuntimeError, ValueError):
        # Failed login responses have no session policy to copy. Keep the
        # documented seven-day default without making an auth error depend on
        # configuration initialization.
        max_age = 7 * 24 * 60 * 60
    return secure, max_age


def should_check_csrf(request: Request) -> bool:
    """Determine if a request needs CSRF validation.

    CSRF is checked for state-changing methods (POST, PUT, DELETE, PATCH).
    GET, HEAD, OPTIONS, and TRACE are exempt per RFC 7231.
    """
    if request.method not in _CSRF_STATE_CHANGING_METHODS:
        return False

    path = _request_path(request)
    if path in _CSRF_EXEMPT_EXACT_PATHS:
        return False
    return True


def _request_path(request: Request) -> str:
    """Return the mounted application's raw path without proxy prefixes.

    ``request.url.path`` may normalize percent-encoded delimiters before this
    check runs.  Exemption matching must use the raw path so an encoded newline
    or query delimiter cannot become an auth endpoint.  Starlette exposes the
    mount prefix separately as ``root_path``; remove it before comparing child
    routes.
    """
    scope = getattr(request, "scope", None)
    if not isinstance(scope, dict):
        # Lightweight unit-test doubles may only provide ``url.path``.
        return str(request.url.path).rstrip("/")
    return get_request_route_path(request).rstrip("/")


_AUTH_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/auth/login/local",
        "/api/v1/auth/logout",
        "/api/v1/auth/register",
        "/api/v1/auth/initialize",
    }
)


def is_auth_endpoint(request: Request) -> bool:
    """Check if the request is to an auth endpoint.

    Auth endpoints don't need CSRF validation on first call (no token).
    """
    return _request_path(request) in _AUTH_EXEMPT_PATHS


def _host_with_optional_port(hostname: str, port: int | None, scheme: str) -> str:
    """Return normalized host[:port], omitting default ports."""
    host = hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    if port is None or (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        return host
    return f"{host}:{port}"


def _normalize_origin(origin: str) -> str | None:
    """Return a normalized scheme://host[:port] origin, or None for invalid input."""
    try:
        parsed = urlsplit(origin.strip())
        port = parsed.port
    except ValueError:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        return None

    # Browser Origin is only scheme/host/port. Reject URL-shaped or credentialed values.
    if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        return None

    return f"{scheme}://{_host_with_optional_port(parsed.hostname, port, scheme)}"


def _configured_cors_origins() -> set[str]:
    """Return explicit configured browser origins that may call auth routes."""
    origins = set()
    for raw_origin in os.environ.get("GATEWAY_CORS_ORIGINS", "").split(","):
        origin = raw_origin.strip()
        if not origin or origin == "*":
            continue
        normalized = _normalize_origin(origin)
        if normalized:
            origins.add(normalized)
    return origins


def get_configured_cors_origins() -> set[str]:
    """Return normalized explicit browser origins from GATEWAY_CORS_ORIGINS."""
    return _configured_cors_origins()


# Run-creating routes return the run id in this non-safelisted response header;
# split-origin browser clients need it exposed for the LangGraph SDK.
CORS_EXPOSED_HEADERS: tuple[str, ...] = ("Content-Location", "X-Trace-Id")


def _first_header_value(value: str | None) -> str | None:
    """Return the first value from a comma-separated proxy header."""
    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None


def _forwarded_param(request: Request, name: str) -> str | None:
    """Extract a parameter from the first RFC 7239 Forwarded header entry."""
    forwarded = _first_header_value(request.headers.get("forwarded"))
    if not forwarded:
        return None

    for part in forwarded.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key.lower() == name:
            return value.strip().strip('"') or None
    return None


def _request_scheme(request: Request) -> str:
    """Resolve the original request scheme from trusted proxy headers."""
    scheme = _forwarded_param(request, "proto") or _first_header_value(request.headers.get("x-forwarded-proto")) or request.url.scheme
    return scheme.lower()


def _request_origin(request: Request) -> str | None:
    """Build the origin for the URL the browser is targeting."""
    scheme = _request_scheme(request)
    host = _forwarded_param(request, "host") or _first_header_value(request.headers.get("x-forwarded-host")) or request.headers.get("host") or request.url.netloc

    forwarded_port = _first_header_value(request.headers.get("x-forwarded-port"))
    if forwarded_port and ":" not in host.rsplit("]", 1)[-1]:
        host = f"{host}:{forwarded_port}"

    return _normalize_origin(f"{scheme}://{host}")


def is_allowed_auth_origin(request: Request) -> bool:
    """Allow auth POSTs only from the same origin or explicit configured origins.

    Login/register/initialize are exempt from the double-submit token because
    first-time browser clients do not have a CSRF token yet. They still create
    a session cookie, so browser requests with a hostile Origin header must be
    rejected to prevent login CSRF / session fixation. Requests without Origin
    are allowed for non-browser clients such as curl and mobile integrations.
    """
    origin = request.headers.get("origin")
    if not origin:
        return True

    normalized_origin = _normalize_origin(origin)
    if normalized_origin is None:
        return False

    request_origin = _request_origin(request)
    return normalized_origin in _configured_cors_origins() or (request_origin is not None and normalized_origin == request_origin)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware that implements CSRF protection using Double Submit Cookie pattern."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        _is_auth = is_auth_endpoint(request)
        csrf_disabled = is_auth_disabled()
        # Bearer/PAT credentials are authenticated by AuthMiddleware. Let even
        # malformed bearer headers reach that layer so callers receive 401
        # instead of a misleading CSRF 403; valid bearer requests are not
        # browser-cookie state changes and do not need double-submit tokens.
        bearer_present = request.headers.get("authorization") is not None

        # Auth endpoints still enforce the origin policy even when a bearer
        # header is present; otherwise a stolen or malformed token could be
        # used to bypass the browser-origin boundary. Non-auth API requests
        # keep the bearer fast path below so invalid tokens reach AuthMiddleware.
        if not csrf_disabled and should_check_csrf(request) and _is_auth and not is_allowed_auth_origin(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-site auth request denied."},
            )

        if not csrf_disabled and not bearer_present and should_check_csrf(request) and not _is_auth:
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
            header_token = request.headers.get(CSRF_HEADER_NAME)

            if not cookie_token or not header_token:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing. Include X-CSRF-Token header."},
                )

            if not secrets.compare_digest(cookie_token, header_token):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token mismatch."},
                )

        response = await call_next(request)

        # For auth endpoints that set up session, also set CSRF cookie
        if _is_auth and request.method == "POST":
            # Generate a new CSRF token for the session
            csrf_token = generate_csrf_token()
            is_https = is_secure_request(request)
            # A successful auth handler has already resolved remember_me and
            # stamped the exact access-token lifetime on request.state. Keep
            # the double-submit cookie in lockstep; unauthenticated failures
            # retain the short auth-cookie fallback policy.
            max_age = getattr(request.state, SESSION_COOKIE_MAX_AGE_STATE_ATTR, None)
            if not hasattr(request.state, SESSION_COOKIE_MAX_AGE_STATE_ATTR):
                _, max_age = auth_csrf_cookie_settings(request)
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=csrf_token,
                httponly=False,  # Must be JS-readable for Double Submit Cookie pattern
                secure=is_https,
                samesite="strict",
                max_age=max_age,
            )

        return response


def get_csrf_token(request: Request) -> str | None:
    """Get the CSRF token from the current request's cookies.

    This is useful for server-side rendering where you need to embed
    token in forms or headers.
    """
    return request.cookies.get(CSRF_COOKIE_NAME)
