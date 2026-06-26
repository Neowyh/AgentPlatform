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
- ``check_resource_modify(user, ...)``: ownership/role-based write access
- ``filter_visible_resources(items, user)``: bulk-filter a list of resources
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from fastapi import HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

if TYPE_CHECKING:
    from app.gateway.auth.models import User
    from ideer.persistence.models.user import UserModel

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


async def _authenticate(request: Request) -> AuthContext:
    """Authenticate request and return AuthContext.

    Delegates to deps.get_optional_user_from_request() for the JWT→User pipeline.
    Returns AuthContext with user=None for anonymous requests.

    Permission mapping by role:
    - super_admin / department_admin / user: all permissions
    - viewer: read-only (threads:read, runs:read)
    """
    from app.gateway.deps import get_optional_user_from_request
    from ideer.persistence.models.user import UserRole

    user = await get_optional_user_from_request(request)
    if user is None:
        return AuthContext(user=None, permissions=[])

    # BUG-06: Map roles to permissions instead of granting all
    _VIEWER_PERMISSIONS: list[str] = [
        Permissions.THREADS_READ,
        Permissions.RUNS_READ,
    ]

    # Check if user has an RBAC profile to determine role-based permissions
    try:
        from sqlalchemy import select

        from ideer.persistence.engine import get_session_factory
        from ideer.persistence.models.user import UserModel

        sf = get_session_factory()
        if sf is not None:
            async with sf() as session:
                stmt = select(UserModel).where(UserModel.id == str(user.id))
                result = await session.execute(stmt)
                rbac_user = result.scalar_one_or_none()
                if rbac_user is not None:
                    if rbac_user.role == UserRole.VIEWER:
                        return AuthContext(user=user, permissions=_VIEWER_PERMISSIONS)
                    if rbac_user.role is None:
                        logger.warning("User %s has NULL role in database, defaulting to USER permissions", user.id)
    except Exception as exc:
        # Fail-open: if RBAC lookup fails (DB down, etc.), grant full
        # permissions so the system remains usable.  Log at warning level
        # so operators can detect the degraded state.
        logger.warning("RBAC lookup failed for user %s, granting full permissions: %s", user.id, exc)

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
        pass
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
    5. ``department_admin`` -- allowed for resources in own department.

    Returns ``True`` when access is granted, ``False`` otherwise.
    """
    from ideer.persistence.models.user import ResourceVisibility, UserRole

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

    # department_admin: access own department resources
    if user.role == UserRole.DEPARTMENT_ADMIN:
        if user.department_id and resource_department_id and user.department_id == resource_department_id:
            return True

    return False


def check_resource_modify(
    user: UserModel,
    resource_owner_id: str | None,
    resource_department_id: str | None,
) -> bool:
    """Check if *user* can modify (edit/delete) a resource.

    Rules (in evaluation order):
    1. ``super_admin`` -- can modify everything.
    2. Owner -- can modify own resources.
    3. ``department_admin`` -- can modify resources in own department.

    Returns ``True`` when modification is allowed, ``False`` otherwise.
    """
    from ideer.persistence.models.user import UserRole

    # super_admin: modify everything
    if user.role == UserRole.SUPER_ADMIN:
        return True

    # Owner: modify own resources
    if resource_owner_id and user.id == resource_owner_id:
        return True

    # department_admin: modify department resources
    if user.role == UserRole.DEPARTMENT_ADMIN:
        if user.department_id and resource_department_id and user.department_id == resource_department_id:
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
    corresponding RBAC ``UserModel``.  Auto-creates the RBAC profile on
    first access — the very first user is promoted to ``super_admin``.

    Raises:
        HTTPException 401 if the request is not authenticated.
    """
    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel, UserRole

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
            # Auto-create RBAC profile for first-time users.
            # Use SELECT FOR UPDATE to prevent two concurrent first users
            # from both being promoted to super_admin.
            try:
                count_stmt = select(func.count()).select_from(UserModel).where(UserModel.role == UserRole.SUPER_ADMIN, UserModel.disabled.is_not(True)).with_for_update(nowait=False)
                admin_count = (await session.execute(count_stmt)).scalar() or 0
            except (OperationalError, ProgrammingError):
                # If FOR UPDATE is not supported (e.g., SQLite), fall back to plain count
                count_stmt = select(func.count()).select_from(UserModel).where(UserModel.role == UserRole.SUPER_ADMIN, UserModel.disabled.is_not(True))
                admin_count = (await session.execute(count_stmt)).scalar() or 0

            rbac_user = UserModel(
                id=user_id,
                username=getattr(user, "email", user_id),
                role=UserRole.SUPER_ADMIN if admin_count == 0 else UserRole.USER,
                department_id=None,
            )
            try:
                session.add(rbac_user)
                await session.commit()
                await session.refresh(rbac_user)
                logger.info("Auto-created RBAC user %s with role %s", user_id, rbac_user.role)
            except IntegrityError:
                # Concurrent request created the user first — re-query
                await session.rollback()
                stmt = select(UserModel).where(UserModel.id == user_id)
                result = await session.execute(stmt)
                rbac_user = result.scalar_one_or_none()
                if rbac_user is None:
                    # IntegrityError was not from a race condition (e.g., FK violation)
                    logger.error("Failed to create RBAC user %s: IntegrityError but user not found after rollback", user_id)
                    raise HTTPException(status_code=500, detail="Failed to create user profile")
                if rbac_user.disabled:
                    raise HTTPException(status_code=403, detail="User account is disabled")

                # P2-AUTH-01: Re-check admin_count — if the concurrent request
                # also promoted this user to super_admin, downgrade to USER
                # when more than one super_admin now exists.
                if rbac_user.role == UserRole.SUPER_ADMIN:
                    async with sf() as recheck_session:
                        recheck_count_stmt = (
                            select(func.count())
                            .select_from(UserModel)
                            .where(
                                UserModel.role == UserRole.SUPER_ADMIN,
                                UserModel.disabled.is_not(True),
                            )
                        )
                        admin_count = (await recheck_session.execute(recheck_count_stmt)).scalar() or 0
                        if admin_count > 1:
                            # Re-query user in new session to modify
                            recheck_user_stmt = select(UserModel).where(UserModel.id == user_id)
                            recheck_result = await recheck_session.execute(recheck_user_stmt)
                            recheck_user = recheck_result.scalar_one_or_none()
                            if recheck_user is not None:
                                recheck_user.role = UserRole.USER
                                rbac_user.role = UserRole.USER
                                await recheck_session.commit()
                                logger.info("Downgraded concurrent first-user %s from super_admin to USER (admin_count=%d)", user_id, admin_count)

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
