"""Authorization decorators and context for iDeer.

Inspired by LangGraph Auth system: https://github.com/langchain-ai/langgraph/blob/main/libs/sdk-py/langgraph_sdk/auth/__init__.py

**Usage:**

1. Use ``@require_auth`` on routes that need authentication
2. Use ``@require_permission("resource", "action", filter_key=...)`` for permission checks
3. The decorator chain processes from bottom to top

**Example:**

    @router.get("/{thread_id}")
    @require_auth
    @require_permission("threads", "read", owner_check=True)
    async def get_thread(thread_id: str, request: Request):
        # User is authenticated and has threads:read permission
        ...

**Permission Model:**

- threads:read   - View thread
- threads:write  - Create/update thread
- threads:delete - Delete thread
- runs:create   - Run agent
- runs:read     - View run
- runs:cancel   - Cancel run

**RBAC Permission Model (software factory):**

- ``require_role(*roles)``: decorator requiring one of the given roles
- ``check_resource_access(user, ...)``: visibility-based read access
- ``check_resource_modify(user, ...)``: ownership-based write access (owner only)
- ``filter_visible_resources(items, user)``: bulk-filter a list of resources
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from fastapi import HTTPException, Request, status

from deerflow.authz.principal import build_principal_from_context
from deerflow.authz.provider import AuthorizationProvider, AuthzDecision, AuthzRequest
from deerflow.authz.runtime import resolve_authorization_provider
from deerflow.config.authorization_config import AuthorizationConfig

if TYPE_CHECKING:
    from app.agentplatform.rbac_models import UserModel
    from app.gateway.auth.models import User
    from deerflow.config.app_config import AppConfig

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


# Permission constants
class Permissions:
    """Permission constants for resource:action format."""

    # Threads
    THREADS_READ = "threads:read"
    THREADS_WRITE = "threads:write"
    THREADS_DELETE = "threads:delete"

    # Runs
    RUNS_CREATE = "runs:create"
    RUNS_READ = "runs:read"
    RUNS_CANCEL = "runs:cancel"

    # Assistants
    ASSISTANTS_READ = "assistants:read"

    # Models
    MODELS_READ = "models:read"


class AuthContext:
    """Authentication context for the current request.

    Stored in request.state.auth after require_auth decoration.

    Attributes:
        user: The authenticated user, or None if anonymous
        permissions: List of permission strings (e.g., "threads:read")
    """

    __slots__ = ("user", "permissions")

    def __init__(self, user: User | None = None, permissions: list[str] | None = None):
        self.user = user
        self.permissions = permissions or []

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.user is not None

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if context has permission for resource:action.

        Args:
            resource: Resource name (e.g., "threads")
            action: Action name (e.g., "read")

        Returns:
            True if user has permission
        """
        permission = f"{resource}:{action}"
        return permission in self.permissions

    def require_user(self) -> User:
        """Get user or raise 401.

        Raises:
            HTTPException 401 if not authenticated
        """
        if not self.user:
            raise HTTPException(status_code=401, detail="Authentication required")
        return self.user


def get_auth_context(request: Request) -> AuthContext | None:
    """Get AuthContext from request state."""
    return getattr(request.state, "auth", None)


def require_cancel_permission_if(request: Request, can_cancel: bool) -> None:
    """Require ``runs:cancel`` when a request carries cancellation capability."""
    if not can_cancel:
        return
    auth = getattr(request.state, "auth", None)
    if auth is not None and not auth.has_permission("runs", "cancel"):
        raise HTTPException(status_code=403, detail="Permission denied: runs:cancel")


_ALL_PERMISSIONS: list[str] = [
    Permissions.THREADS_READ,
    Permissions.THREADS_WRITE,
    Permissions.THREADS_DELETE,
    Permissions.RUNS_CREATE,
    Permissions.RUNS_READ,
    Permissions.RUNS_CANCEL,
    Permissions.ASSISTANTS_READ,
    Permissions.MODELS_READ,
]


def _make_test_request_stub() -> Any:
    """Create a minimal request-like object for direct unit calls.

    Used when decorated route handlers are invoked without FastAPI's
    request injection. Includes fields accessed by auth helpers.
    """
    return SimpleNamespace(state=SimpleNamespace(), cookies={}, _ideer_test_bypass_auth=True)


def _get_route_authorization_config() -> AuthorizationConfig:
    """Return hot-reloaded route authorization settings."""
    from deerflow.config.app_config import get_app_config

    try:
        return get_app_config().authorization
    except (FileNotFoundError, RuntimeError):
        return AuthorizationConfig()


_route_provider_cache: dict[str, AuthorizationProvider] = {}
_route_provider_config_id: int | None = None
_route_provider_config_sig: str | None = None


def _get_cached_route_provider(config: AuthorizationConfig) -> AuthorizationProvider | None:
    """Resolve and cache the configured route authorization provider."""
    global _route_provider_config_id, _route_provider_config_sig
    config_id = id(config)
    if config_id == _route_provider_config_id and _route_provider_cache:
        return _route_provider_cache.get("provider")
    sig = repr(sorted(config.model_dump().items()))
    if sig == _route_provider_config_sig and _route_provider_cache:
        _route_provider_config_id = config_id
        return _route_provider_cache.get("provider")
    _route_provider_cache.clear()
    provider = resolve_authorization_provider(config)
    if provider is not None:
        _route_provider_cache["provider"] = provider
    _route_provider_config_id = config_id
    _route_provider_config_sig = sig
    return provider


async def resolve_route_permissions(user: User, *, is_internal: bool) -> list[str]:
    """Return route permissions for *user*, evaluating each action independently."""
    config = _get_route_authorization_config()
    if config.enabled is not True:
        return list(_ALL_PERMISSIONS)
    try:
        provider = _get_cached_route_provider(config)
        if provider is None:
            raise ValueError("authorization is enabled but provider resolution returned None")
    except Exception:
        logger.warning("Failed to resolve authorization provider for Gateway routes", exc_info=True)
        return [] if config.fail_closed else list(_ALL_PERMISSIONS)

    from app.gateway.internal_auth import INTERNAL_SYSTEM_ROLE

    user_role = getattr(user, "system_role", None)
    if user_role == INTERNAL_SYSTEM_ROLE:
        user_role = None
    principal = build_principal_from_context(
        {
            "user_id": str(user.id),
            "user_role": user_role,
            "oauth_provider": getattr(user, "oauth_provider", None),
            "oauth_id": getattr(user, "oauth_id", None),
            "is_internal": is_internal,
        },
        default_role=config.default_role,
    )

    async def _evaluate(permission: str) -> str | None:
        _, action = permission.split(":", maxsplit=1)
        request = AuthzRequest(principal=principal, resource="route", action=action, target=permission)
        try:
            decision = await provider.aauthorize(request)
            if not isinstance(decision, AuthzDecision):
                raise TypeError("AuthorizationProvider.aauthorize must return AuthzDecision")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Authorization provider failed while evaluating route permission %s", permission, exc_info=True)
            return permission if not config.fail_closed else None
        return permission if decision.allow else None

    results = await asyncio.gather(*[_evaluate(permission) for permission in _ALL_PERMISSIONS])
    return [permission for permission in results if permission is not None]


def _route_authz_context(user: User, *, is_internal: bool) -> dict:
    """Build the shared Principal context dict for a request-scoped user.

    Applies the ``INTERNAL_SYSTEM_ROLE → None`` pop so internal callers fall
    under ``default_role`` (mirrors ``inject_authenticated_user_context``).
    Used by ``resolve_model_authorization`` and ``authorize_sandbox_for_request``
    so every route-level authorization path builds the identity the same way.
    """
    from app.gateway.internal_auth import INTERNAL_SYSTEM_ROLE

    user_role = getattr(user, "system_role", None)
    if user_role == INTERNAL_SYSTEM_ROLE:
        user_role = None
    return {
        "user_id": str(user.id),
        "user_role": user_role,
        "oauth_provider": getattr(user, "oauth_provider", None),
        "oauth_id": getattr(user, "oauth_id", None),
        "is_internal": is_internal,
    }


def authorize_sandbox_for_request(
    user: User,
    *,
    is_internal: bool,
    app_config: AppConfig | None,
) -> None:
    """Check ``sandbox:execute`` for a Gateway request before sandbox acquisition.

    Thin wrapper over the harness-level ``authorize_sandbox_execution`` that
    builds the Principal from the request-scoped ``user`` — the same identity
    construction as ``resolve_model_authorization`` (including the
    ``INTERNAL_SYSTEM_ROLE → None`` pop). Raises
    :class:`~deerflow.sandbox.exceptions.SandboxAuthorizationError` on deny or
    on provider-resolution failure under ``fail_closed``; callers translate
    that into skipping the sandbox sync (not an HTTP error, since the primary
    operation — e.g. file upload — can proceed without it).

    No-op when ``authorization.enabled`` is false.
    """
    from deerflow.authz.sandbox_authz import authorize_sandbox_execution
    from deerflow.sandbox.exceptions import SandboxAuthorizationError

    config = _get_route_authorization_config()
    if config.enabled is not True:
        return

    context = _route_authz_context(user, is_internal=is_internal)

    try:
        authorize_sandbox_execution(
            context=context,
            app_config=app_config,
        )
    except SandboxAuthorizationError:
        raise
    except Exception:
        # Defense-in-depth: provider resolution and authorize() errors are
        # already converted to SandboxAuthorizationError (or allowed under
        # fail-open) one layer down inside authorize_sandbox_execution, so this
        # normally only catches config-read failures here (e.g. get_config()
        # raising in a config-less environment). Those must not 500 the
        # upload/artifact route — degrade per fail_closed instead.
        logger.warning("Failed to resolve authorization provider for sandbox:execute", exc_info=True)
        if config.fail_closed:
            raise SandboxAuthorizationError(role=context.get("user_role")) from None


@dataclass(slots=True)
class SandboxRequestLease:
    """One Gateway request's process-local use of a sandbox client."""

    sandbox: object | None
    sandbox_id: str | None
    denied: bool
    owner_id: str | None
    provider: object | None

    async def release(self) -> None:
        """Drop the request holder without bypassing concurrent executions."""
        if self.owner_id is None or self.provider is None:
            return
        from deerflow.sandbox.lease import get_sandbox_lease_manager

        owner_id = self.owner_id
        self.owner_id = None
        await get_sandbox_lease_manager(self.provider).release_async(owner_id)


async def try_acquire_sandbox_for_request(
    request: Request,
    sandbox_provider,
    thread_id: str,
    *,
    user_id: str,
    app_config: AppConfig | None,
    owner_prefix: str = "gateway",
    release_on_last: bool = True,
) -> SandboxRequestLease:
    """Gate + acquire the thread sandbox for a Gateway sync path.

    Single entry point for the uploads/artifacts sandbox-sync paths so the
    deny/skip semantics live in one place: runs the ``sandbox:execute`` gate
    for the request's user, then acquires the sandbox under a unique request
    holder. Callers must await :meth:`SandboxRequestLease.release` after their
    last client operation.

    - denied role → no sandbox/owner and ``denied=True``: acquisition was skipped by policy;
      the primary operation (upload / artifact edit) proceeds without the
      sandbox copy.
    - allowed → ``sandbox`` is the acquired instance, or ``sandbox is None`` when
      the provider lost it right after acquiring (infrastructure error —
      callers surface it as 500 / RuntimeError respectively, since that is
      not a policy decision).
    - ``request is None`` (direct-call tests) and unresolvable users skip the
      gate — same fail-open semantics as the models routes' anonymous bypass.
    """
    from deerflow.sandbox.exceptions import SandboxAuthorizationError

    try:
        from app.gateway.deps import get_optional_user_from_request

        user = await get_optional_user_from_request(request) if request is not None else None
        if user is not None:
            authorize_sandbox_for_request(user, is_internal=_is_internal_caller(request, user), app_config=app_config)
    except SandboxAuthorizationError:
        logger.info("Sandbox sync skipped: sandbox execution not permitted for this caller (thread_id=%s)", thread_id)
        return SandboxRequestLease(
            sandbox=None,
            sandbox_id=None,
            denied=True,
            owner_id=None,
            provider=None,
        )

    from deerflow.sandbox.lease import get_sandbox_lease_manager

    owner_id = f"{owner_prefix}:{uuid.uuid4()}"
    sandbox_id = await get_sandbox_lease_manager(sandbox_provider).acquire_async(
        owner_id,
        thread_id,
        user_id=user_id,
        release_on_last=release_on_last,
    )
    return SandboxRequestLease(
        sandbox=sandbox_provider.get(sandbox_id),
        sandbox_id=sandbox_id,
        denied=False,
        owner_id=owner_id,
        provider=sandbox_provider,
    )


def _is_internal_caller(request: Request, user: Any) -> bool:
    """Determine if the request originates from a trusted internal caller.

    Checks three signals (any one suffices):
    1. ``request.state.auth_source == AUTH_SOURCE_INTERNAL`` (set by AuthMiddleware).
    2. ``user.system_role == INTERNAL_SYSTEM_ROLE`` (synthetic internal user).
    3. The request carries a valid internal auth token header (decorator-only path
       where AuthMiddleware may not have stamped ``auth_source`` yet).
    """
    from app.gateway.auth_disabled import AUTH_SOURCE_INTERNAL
    from app.gateway.internal_auth import INTERNAL_AUTH_HEADER_NAME, INTERNAL_SYSTEM_ROLE, is_valid_internal_auth_token

    if getattr(getattr(request, "state", None), "auth_source", None) == AUTH_SOURCE_INTERNAL:
        return True
    if getattr(user, "system_role", None) == INTERNAL_SYSTEM_ROLE:
        return True
    # Decorator-only path: check the internal token header directly.
    internal_token = request.headers.get(INTERNAL_AUTH_HEADER_NAME) if hasattr(request, "headers") else None
    if internal_token and is_valid_internal_auth_token(internal_token):
        return True
    return False


_RBAC_IDENTITY_ATTR = "_ideer_rbac_user"


def _stash_rbac_identity(request: Request, *, user_id: str, department_id: str | None, role: str) -> None:
    """Cache the resolved RBAC identity on the request for this request only."""
    request.state._ideer_rbac_user = {
        "user_id": user_id,
        "department_id": department_id,
        "role": role,
    }


def _cached_rbac_identity(request: Request, user_id: str) -> dict[str, Any] | None:
    """Return the cached RBAC identity when it belongs to ``user_id``."""
    cached = getattr(getattr(request, "state", None), _RBAC_IDENTITY_ATTR, None)
    if not isinstance(cached, dict) or cached.get("user_id") != user_id:
        return None
    return cached


async def _authenticate(request: Request) -> AuthContext:
    """Authenticate request and return AuthContext.

    Delegates to deps.get_optional_user_from_request() for the JWT→User pipeline.
    Returns AuthContext with user=None for anonymous requests.

    Permission mapping by role:
    - super_admin / department_admin / user: all permissions
    - viewer: read-only (threads:read, runs:read)
    """
    from app.agentplatform.rbac_models import UserRole
    from app.gateway.deps import get_optional_user_from_request

    user = await get_optional_user_from_request(request)
    if user is None:
        return AuthContext(user=None, permissions=[])

    # BUG-06: Map roles to permissions instead of granting all
    _VIEWER_PERMISSIONS: list[str] = [
        Permissions.THREADS_READ,
        Permissions.RUNS_READ,
    ]

    try:
        from sqlalchemy import select

        from app.agentplatform.rbac_models import UserModel
        from deerflow.persistence.engine import get_session_factory

        sf = get_session_factory()
        if sf is None:
            raise RuntimeError("Database not initialized")
        async with sf() as session:
            stmt = select(UserModel).where(UserModel.id == str(user.id))
            result = await session.execute(stmt)
            rbac_user = result.scalar_one_or_none()
            if rbac_user is None:
                rbac_user = UserModel(
                    id=str(user.id),
                    username=getattr(user, "email", str(user.id)),
                    role=UserRole.USER.value,
                    department_id=None,
                )
                session.add(rbac_user)
                await session.commit()
                await session.refresh(rbac_user)
                logger.info("Auto-created RBAC user %s with role %s", user.id, rbac_user.role)
            if rbac_user.disabled:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
            try:
                role = UserRole(rbac_user.role)
            except (TypeError, ValueError):
                logger.error("Invalid role '%s' for user %s, defaulting to viewer permissions", rbac_user.role, user.id)
                role = UserRole.VIEWER
            # T2: cache the resolved identity on the request so downstream
            # run preparation (alias resolve, canonical freeze) reuses it
            # instead of issuing duplicate UserModel SELECTs.
            _stash_rbac_identity(
                request,
                user_id=str(user.id),
                department_id=str(rbac_user.department_id) if rbac_user.department_id is not None else None,
                role=str(rbac_user.role),
            )
            if role == UserRole.VIEWER:
                return AuthContext(user=user, permissions=_VIEWER_PERMISSIONS)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        # Fail-closed: RBAC lookup failed (DB down, etc.) — deny access
        # rather than granting full permissions.  A DB outage should not
        # become a privilege-escalation vector.  Log at error level so
        # operators are alerted to the degraded state.
        logger.error("RBAC lookup failed for user %s, denying access: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service temporarily unavailable",
        )

    # Authenticated non-viewer RBAC roles get the normal write-capable set.
    return AuthContext(user=user, permissions=_ALL_PERMISSIONS)


def require_auth[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """Decorator that authenticates the request and enforces authentication.

    Independently raises HTTP 401 for unauthenticated requests, regardless of
    whether ``AuthMiddleware`` is present in the ASGI stack. Sets the resolved
    ``AuthContext`` on ``request.state.auth`` for downstream handlers.

    Must be placed ABOVE other decorators (executes after them).

    Usage:
        @router.get("/{thread_id}")
        @require_auth  # Bottom decorator (executes first after permission check)
        @require_permission("threads", "read")
        async def get_thread(thread_id: str, request: Request):
            auth: AuthContext = request.state.auth
            ...

    Raises:
        HTTPException: 401 if the request is unauthenticated.
        ValueError: If 'request' parameter is missing.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        request = kwargs.get("request")
        if request is None and args:
            # FastAPI may pass request as a positional argument in some
            # decorator stacking scenarios.  Fall back to positional lookup.
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            if params and params[0] == "request":
                request = args[0]
                kwargs["request"] = request
                args = args[1:]
        if request is None:
            # Unit tests may call decorated handlers directly without a
            # FastAPI Request object. Inject a minimal request stub when
            # the wrapped function declares `request`.
            if "request" in inspect.signature(func).parameters:
                kwargs["request"] = _make_test_request_stub()
            else:
                raise ValueError("require_auth decorator requires 'request' parameter")
            request = kwargs["request"]

        if isinstance(request, Request) and getattr(request, "_ideer_test_bypass_auth", False):
            logger.error("SECURITY: _ideer_test_bypass_auth set on real Request object -- ignoring")
            # Don't bypass -- fall through to normal auth

        if getattr(request, "_ideer_test_bypass_auth", False):
            return await func(*args, **kwargs)

        # Authenticate and set context
        auth_context = await _authenticate(request)
        request.state.auth = auth_context

        if not auth_context.is_authenticated:
            raise HTTPException(status_code=401, detail="Authentication required")

        return await func(*args, **kwargs)

    return wrapper


def require_permission(
    resource: str,
    action: str,
    owner_check: bool = False,
    require_existing: bool = False,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that checks permission for resource:action.

    Must be used AFTER @require_auth.

    Args:
        resource: Resource name (e.g., "threads", "runs")
        action: Action name (e.g., "read", "write", "delete")
        owner_check: If True, validates that the current user owns the resource.
                     Requires 'thread_id' path parameter and performs ownership check.
        require_existing: Only meaningful with ``owner_check=True``. If True, a
                          missing ``threads_meta`` row counts as a denial (404)
                          instead of "untracked legacy thread, allow". Use on
                          **destructive / mutating** routes (DELETE, PATCH,
                          state-update) so a deleted thread can't be re-targeted
                          by another user via the missing-row code path.

    Usage:
        # Read-style: legacy untracked threads are allowed
        @require_permission("threads", "read", owner_check=True)
        async def get_thread(thread_id: str, request: Request):
            ...

        # Destructive: thread row MUST exist and be owned by caller
        @require_permission("threads", "delete", owner_check=True, require_existing=True)
        async def delete_thread(thread_id: str, request: Request):
            ...

    Raises:
        HTTPException 401: If authentication required but user is anonymous
        HTTPException 403: If user lacks permission
        HTTPException 404: If owner_check=True but user doesn't own the thread
        ValueError: If owner_check=True but 'thread_id' parameter is missing
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = kwargs.get("request")
            if request is None and args:
                # FastAPI may pass request as a positional argument in some
                # decorator stacking scenarios.  Fall back to positional lookup.
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if params and params[0] == "request":
                    request = args[0]
                    kwargs["request"] = request
                    args = args[1:]
            if request is None:
                # Unit tests may call decorated route handlers directly without
                # constructing a FastAPI Request object. Inject a minimal stub
                # when the wrapped function declares `request`.
                if "request" in inspect.signature(func).parameters:
                    kwargs["request"] = _make_test_request_stub()
                else:
                    raise ValueError(f"require_permission decorator requires 'request' parameter on {func.__qualname__}")
                request = kwargs["request"]

            if isinstance(request, Request) and getattr(request, "_ideer_test_bypass_auth", False):
                logger.error("SECURITY: _ideer_test_bypass_auth set on real Request object -- ignoring")
                # Don't bypass -- fall through to normal auth

            if getattr(request, "_ideer_test_bypass_auth", False):
                return await func(*args, **kwargs)

            auth: AuthContext = getattr(request.state, "auth", None)
            if auth is None:
                auth = await _authenticate(request)
                request.state.auth = auth

            if not auth.is_authenticated:
                raise HTTPException(status_code=401, detail="Authentication required")

            # Check permission
            if not auth.has_permission(resource, action):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {resource}:{action}",
                )

            # Owner check for thread-specific resources.
            #
            # 2.0-rc moved thread metadata into the SQL persistence layer
            # (``threads_meta`` table). We verify ownership via
            # ``ThreadMetaStore.check_access``: it returns True for
            # missing rows (untracked legacy thread) and for rows whose
            # ``user_id`` is NULL (shared / pre-auth data), so this is
            # strict-deny rather than strict-allow — only an *existing*
            # row with a *different* user_id triggers 404.
            if owner_check:
                thread_id = kwargs.get("thread_id")
                if thread_id is None:
                    raise ValueError("require_permission with owner_check=True requires 'thread_id' parameter")

                from app.gateway.deps import get_thread_store

                thread_store = get_thread_store(request)
                allowed = await thread_store.check_access(
                    thread_id,
                    str(auth.user.id),
                    require_existing=require_existing,
                )
                if not allowed:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Thread {thread_id} not found",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# RBAC permission checking for iDeer software factory
# ---------------------------------------------------------------------------


def _find_user_param(func: Callable) -> str:
    """Find the name of the parameter annotated as UserModel.

    Inspects the function signature to locate the user parameter dynamically,
    so require_role does not hardcode ``current_user`` as the parameter name.
    Falls back to ``"current_user"`` if no annotated parameter is found.
    """
    try:
        for name, param in inspect.signature(func).parameters.items():
            ann = param.annotation
            # Handle string annotations (from __future__ annotations)
            if isinstance(ann, str) and "UserModel" in ann:
                return name
            # Handle resolved type annotations
            if hasattr(ann, "__name__") and ann.__name__ == "UserModel":
                return name
    except (ValueError, TypeError):
        logger.debug("Failed to inspect function signature for UserModel parameter", exc_info=True)
    return "current_user"


def require_role(*roles: str):
    """Decorator: require the current user to have one of the specified roles.

    Finds the user parameter by inspecting the function's type annotations
    (looks for a parameter annotated as ``UserModel``). Falls back to
    ``current_user`` if no annotated parameter is found.

    Usage::

        @require_role("super_admin", "department_admin")
        async def admin_endpoint(current_user: UserModel = Depends(...)):
            ...
    """

    def decorator(func: Callable) -> Callable:
        user_param = _find_user_param(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_user = kwargs.get(user_param)
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            if current_user.role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires role: {', '.join(roles)}",
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def check_resource_access(
    user: UserModel,
    resource_owner_id: str | None,
    resource_department_id: str | None,
    resource_visibility: str,
) -> bool:
    """Check if *user* can read a resource based on RBAC visibility rules.

    Rules (in evaluation order):
    1. ``super_admin`` -- always allowed.
    2. Owner -- always allowed for own resources.
    3. ``public`` visibility -- allowed for everyone.
    4. ``department`` visibility -- allowed if user belongs to the same department.
    5. ``private`` visibility -- only owner and super_admin.

    Returns ``True`` when access is granted, ``False`` otherwise.
    """
    from app.agentplatform.rbac_models import ResourceVisibility, UserRole

    # super_admin: access everything
    if user.role == UserRole.SUPER_ADMIN:
        return True

    # Owner: always access own resources
    if resource_owner_id and user.id == resource_owner_id:
        return True

    # Public resources: everyone can access
    if resource_visibility == ResourceVisibility.PUBLIC:
        return True

    # Department resources: same department
    if resource_visibility == ResourceVisibility.DEPARTMENT:
        if user.department_id and resource_department_id and user.department_id == resource_department_id:
            return True

    return False


def check_resource_modify(
    user: UserModel,
    resource_owner_id: str | None,
    resource_department_id: str | None,
) -> bool:
    """Check if *user* can modify (edit/delete) a resource.

    Rules:
    1. Owner -- can modify own resources.

    Returns ``True`` when modification is allowed, ``False`` otherwise.
    """
    # Owner: modify own resources
    if resource_owner_id and user.id == resource_owner_id:
        return True

    return False


def filter_visible_resources(items: list, user: UserModel) -> list:
    """Filter a list of resources by visibility rules.

    Each item in *items* is expected to have ``owner_id``, ``department_id``,
    and ``visibility`` attributes (as plain attributes or via ``getattr``
    defaults).
    """
    return [
        item
        for item in items
        if check_resource_access(
            user,
            getattr(item, "owner_id", None),
            getattr(item, "department_id", None),
            getattr(item, "visibility", "private"),
        )
    ]


# ---------------------------------------------------------------------------
# FastAPI dependencies for RBAC user resolution
# ---------------------------------------------------------------------------


async def get_current_rbac_user(request: Request) -> UserModel:
    """FastAPI dependency: resolve the authenticated user to a ``UserModel``.

    Reads the ``User`` object already stamped on ``request.state.user`` by
    AuthMiddleware (JWT decoded once, no redundant work) and looks up the
    corresponding RBAC ``UserModel``. A valid request subject must already
    exist in both the authentication and RBAC user tables.

    Raises:
        HTTPException 401 if the request is not authenticated.
    """
    from app.agentplatform.rbac_models import UserModel, UserRole
    from deerflow.persistence.engine import get_session_factory

    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        from sqlalchemy import select

        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await session.execute(stmt)
        rbac_user = result.scalar_one_or_none()

        if rbac_user is not None and rbac_user.disabled:
            raise HTTPException(status_code=403, detail="User account is disabled")

        if rbac_user is None:
            logger.error("Authenticated user %s has no RBAC profile", user_id)
            raise HTTPException(status_code=403, detail="Authenticated user has no RBAC profile")

    # P2-AUTH-05: Validate role is a valid enum value
    try:
        UserRole(rbac_user.role)
    except ValueError:
        logger.error("Invalid role '%s' for user %s, defaulting to viewer", rbac_user.role, rbac_user.id)
        rbac_user.role = UserRole.VIEWER

    return rbac_user


async def get_optional_rbac_user(request: Request) -> UserModel | None:
    """Like ``get_current_rbac_user`` but returns ``None`` for unauthenticated requests."""
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    try:
        return await get_current_rbac_user(request)
    except HTTPException as e:
        # Only swallow 401 (unauthenticated) — let callers see "no user".
        # Re-raise 403 (disabled) and everything else (500 DB errors, etc.)
        # so disabled users cannot silently access optional-auth endpoints.
        if e.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        return None
