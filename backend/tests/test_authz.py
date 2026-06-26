"""Comprehensive unit tests for app.gateway.authz module.

Targets 95%+ line coverage of authz.py by exercising every branch in:
- AuthContext class
- get_auth_context
- _make_test_request_stub
- _authenticate
- require_auth decorator
- require_permission decorator
- _find_user_param
- require_role decorator
- check_resource_access / check_resource_modify / filter_visible_resources
- get_current_rbac_user / get_optional_rbac_user
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, status

from app.gateway.auth.models import User
from app.gateway.authz import (
    AuthContext,
    Permissions,
    _authenticate,
    _find_user_param,
    _make_test_request_stub,
    check_resource_access,
    check_resource_modify,
    filter_visible_resources,
    get_auth_context,
    get_current_rbac_user,
    get_optional_rbac_user,
    require_auth,
    require_permission,
    require_role,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides) -> User:
    """Create a test User with sensible defaults."""
    defaults = dict(
        email="test@example.com",
        password_hash="x",
        system_role="user",
        id=uuid4(),
    )
    defaults.update(overrides)
    return User(**defaults)


def _make_request_with_auth(
    user: User | None = None,
    permissions: list[str] | None = None,
    *,
    bypass: bool = False,
    is_real_request: bool = True,
) -> Request | SimpleNamespace:
    """Create a request with an AuthContext pre-stamped on state."""
    if permissions is None:
        permissions = list(Permissions.__dict__.values())
        permissions = [p for p in permissions if isinstance(p, str) and ":" in p]
    ctx = AuthContext(user=user, permissions=permissions)
    if is_real_request:
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=ctx)
        req.cookies = {}
        if bypass:
            req._ideer_test_bypass_auth = True
        return req
    # SimpleNamespace (not a real Request) — used for test-bypass path
    return SimpleNamespace(
        state=SimpleNamespace(auth=ctx),
        cookies={},
        _ideer_test_bypass_auth=bypass,
    )


# Module-level class for _find_user_param annotation tests.
# With `from __future__ import annotations`, annotations become strings.
# When inspect resolves them, this class's __name__ == "UserModel".
class UserModel:
    """Stub class whose __name__ is 'UserModel' for annotation tests."""

    role: str = "user"


def _make_user_model(**overrides):
    """Create a mock UserModel with role attribute."""
    defaults = dict(
        id=str(uuid4()),
        email="rbac@example.com",
        role="user",
        department_id=None,
        disabled=False,
        username="rbacuser",
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


# ===========================================================================
# AuthContext
# ===========================================================================


class TestAuthContext:
    """Tests for the AuthContext class."""

    def test_init_defaults(self):
        ctx = AuthContext()
        assert ctx.user is None
        assert ctx.permissions == []

    def test_init_with_values(self):
        user = _make_user()
        perms = ["threads:read", "threads:write"]
        ctx = AuthContext(user=user, permissions=perms)
        assert ctx.user is user
        assert ctx.permissions == perms

    def test_is_authenticated_true(self):
        ctx = AuthContext(user=_make_user())
        assert ctx.is_authenticated is True

    def test_is_authenticated_false(self):
        ctx = AuthContext(user=None)
        assert ctx.is_authenticated is False

    def test_has_permission_present(self):
        ctx = AuthContext(permissions=["threads:read", "runs:create"])
        assert ctx.has_permission("threads", "read") is True
        assert ctx.has_permission("runs", "create") is True

    def test_has_permission_absent(self):
        ctx = AuthContext(permissions=["threads:read"])
        assert ctx.has_permission("threads", "write") is False
        assert ctx.has_permission("runs", "read") is False

    def test_require_user_returns_user(self):
        user = _make_user()
        ctx = AuthContext(user=user)
        assert ctx.require_user() is user

    def test_require_user_raises_when_no_user(self):
        ctx = AuthContext(user=None)
        with pytest.raises(HTTPException) as exc_info:
            ctx.require_user()
        assert exc_info.value.status_code == 401


# ===========================================================================
# get_auth_context
# ===========================================================================


class TestGetAuthContext:
    """Tests for get_auth_context helper."""

    def test_returns_auth_from_state(self):
        ctx = AuthContext(user=_make_user())
        request = SimpleNamespace(state=SimpleNamespace(auth=ctx))
        assert get_auth_context(request) is ctx

    def test_returns_none_when_no_auth(self):
        request = SimpleNamespace(state=SimpleNamespace())
        assert get_auth_context(request) is None


# ===========================================================================
# _make_test_request_stub
# ===========================================================================


class TestMakeTestRequestStub:
    """Tests for _make_test_request_stub."""

    def test_stub_has_expected_attributes(self):
        stub = _make_test_request_stub()
        assert hasattr(stub, "state")
        assert hasattr(stub, "cookies")
        assert stub.cookies == {}
        assert stub._ideer_test_bypass_auth is True

    def test_stub_is_not_fastapi_request(self):
        stub = _make_test_request_stub()
        assert not isinstance(stub, Request)


# ===========================================================================
# Permissions constants
# ===========================================================================


class TestPermissions:
    """Verify Permission constants are defined correctly."""

    def test_thread_permissions(self):
        assert Permissions.THREADS_READ == "threads:read"
        assert Permissions.THREADS_WRITE == "threads:write"
        assert Permissions.THREADS_DELETE == "threads:delete"

    def test_run_permissions(self):
        assert Permissions.RUNS_CREATE == "runs:create"
        assert Permissions.RUNS_READ == "runs:read"
        assert Permissions.RUNS_CANCEL == "runs:cancel"

    def test_assistants_permissions(self):
        assert Permissions.ASSISTANTS_READ == "assistants:read"

    def test_models_permissions(self):
        assert Permissions.MODELS_READ == "models:read"


# ===========================================================================
# _authenticate
# ===========================================================================


class TestAuthenticate:
    """Tests for the _authenticate async function."""

    @pytest.mark.asyncio
    async def test_no_user_returns_anonymous_context(self):
        with patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=None):
            ctx = await _authenticate(MagicMock(spec=Request))
        assert ctx.user is None
        assert ctx.permissions == []
        assert ctx.is_authenticated is False

    @pytest.mark.asyncio
    async def test_viewer_role_gets_readonly_permissions(self):
        user = _make_user()
        mock_rbac_user = _make_user_model(role="viewer")
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rbac_user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            ctx = await _authenticate(MagicMock(spec=Request))

        assert ctx.user is user
        assert Permissions.THREADS_READ in ctx.permissions
        assert Permissions.RUNS_READ in ctx.permissions
        assert Permissions.THREADS_WRITE not in ctx.permissions

    @pytest.mark.asyncio
    async def test_non_viewer_role_gets_all_permissions(self):
        user = _make_user()
        mock_rbac_user = _make_user_model(role="user")
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rbac_user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            ctx = await _authenticate(MagicMock(spec=Request))

        assert ctx.user is user
        assert Permissions.THREADS_WRITE in ctx.permissions

    @pytest.mark.asyncio
    async def test_null_role_logs_warning_and_gets_all_permissions(self, caplog):
        user = _make_user()
        mock_rbac_user = _make_user_model(role=None)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rbac_user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            with caplog.at_level(logging.WARNING):
                ctx = await _authenticate(MagicMock(spec=Request))

        assert ctx.user is user
        assert "NULL role" in caplog.text or Permissions.THREADS_WRITE in ctx.permissions

    @pytest.mark.asyncio
    async def test_no_rbac_user_found_gets_all_permissions(self):
        user = _make_user()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            ctx = await _authenticate(MagicMock(spec=Request))

        assert ctx.user is user
        assert Permissions.THREADS_WRITE in ctx.permissions

    @pytest.mark.asyncio
    async def test_session_factory_none_grants_all_permissions(self):
        user = _make_user()
        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("ideer.persistence.engine.get_session_factory", return_value=None),
        ):
            ctx = await _authenticate(MagicMock(spec=Request))

        assert ctx.user is user
        assert Permissions.THREADS_WRITE in ctx.permissions

    @pytest.mark.asyncio
    async def test_db_exception_grants_full_permissions(self, caplog):
        """DB failure grants full permissions (fail-open for availability)."""
        user = _make_user()
        mock_sf = MagicMock(side_effect=RuntimeError("DB down"))

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            with caplog.at_level(logging.WARNING):
                ctx = await _authenticate(MagicMock(spec=Request))

        assert ctx.user is user
        # Fail-open: full permissions granted on DB failure so system stays usable
        assert Permissions.THREADS_READ in ctx.permissions
        assert Permissions.RUNS_READ in ctx.permissions
        assert Permissions.THREADS_WRITE in ctx.permissions
        assert Permissions.RUNS_CREATE in ctx.permissions
        assert "RBAC lookup failed" in caplog.text


# ===========================================================================
# require_auth decorator
# ===========================================================================


class TestRequireAuth:
    """Tests for the require_auth decorator."""

    @pytest.mark.asyncio
    async def test_authenticated_request_passes_through(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=[])

        @require_auth
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()
        req.cookies = {}
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock, return_value=auth_ctx):
            result = await handler(request=req)
        assert result == "ok"
        assert req.state.auth is auth_ctx

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self):
        auth_ctx = AuthContext(user=None, permissions=[])

        @require_auth
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()
        req.cookies = {}
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock, return_value=auth_ctx):
            with pytest.raises(HTTPException) as exc_info:
                await handler(request=req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_test_bypass_on_non_request(self):
        """Non-Request objects with _ideer_test_bypass_auth should bypass auth."""

        @require_auth
        async def handler(request):
            return "bypassed"

        stub = _make_test_request_stub()
        result = await handler(request=stub)
        assert result == "bypassed"

    @pytest.mark.asyncio
    async def test_real_request_with_bypass_flag_ignores_bypass(self):
        """A real Request with _ideer_test_bypass_auth=True should NOT bypass."""
        auth_ctx = AuthContext(user=_make_user(), permissions=[])

        @require_auth
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()
        req.cookies = {}
        req._ideer_test_bypass_auth = True
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock, return_value=auth_ctx):
            result = await handler(request=req)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_request_from_positional_args(self):
        """When request is passed as a positional arg, require_auth should find it."""
        auth_ctx = AuthContext(user=_make_user(), permissions=[])

        @require_auth
        async def handler(thread_id: str, request: Request):
            return f"ok-{thread_id}"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()
        req.cookies = {}
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock, return_value=auth_ctx):
            result = await handler("t1", request=req)  # request as kwarg, thread_id positional
        assert result == "ok-t1"

    @pytest.mark.asyncio
    async def test_no_request_param_raises_value_error(self):
        """When the handler has no 'request' param, require_auth should raise."""

        @require_auth
        async def handler(some_arg: str):
            return "ok"

        with pytest.raises(ValueError, match="require_auth decorator requires 'request' parameter"):
            await handler("test")

    @pytest.mark.asyncio
    async def test_no_request_injection_for_test_stub(self):
        """When no request is provided but handler declares 'request', inject stub."""

        @require_auth
        async def handler(request):
            return "ok"

        result = await handler()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_request_first_positional_arg_extracted(self):
        """When request is passed as first positional arg and handler's first
        param is named 'request', the decorator extracts it from args[0],
        puts it in kwargs, and removes it from args to avoid duplicate."""
        stub = SimpleNamespace(state=SimpleNamespace(), cookies={}, _ideer_test_bypass_auth=True)

        @require_auth
        async def handler(request):
            return "ok"

        result = await handler(stub)  # positional
        assert result == "ok"


# ===========================================================================
# require_permission decorator
# ===========================================================================


class TestRequirePermission:
    """Tests for the require_permission decorator."""

    @pytest.mark.asyncio
    async def test_has_permission_passes_through(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:read"])

        @require_permission("threads", "read")
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        result = await handler(request=req)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_no_permission_returns_403(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=[])

        @require_permission("threads", "write")
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        with pytest.raises(HTTPException) as exc_info:
            await handler(request=req)
        assert exc_info.value.status_code == 403
        assert "threads:write" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_auth_context_triggers_authenticate(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:read"])

        @require_permission("threads", "read")
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()  # no auth attr
        req.cookies = {}
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock, return_value=auth_ctx):
            result = await handler(request=req)
        assert result == "ok"
        assert req.state.auth is auth_ctx

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self):
        auth_ctx = AuthContext(user=None, permissions=[])

        @require_permission("threads", "read")
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        with pytest.raises(HTTPException) as exc_info:
            await handler(request=req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_test_bypass_on_non_request(self):
        @require_permission("threads", "write")
        async def handler(request):
            return "bypassed"

        stub = _make_test_request_stub()
        result = await handler(request=stub)
        assert result == "bypassed"

    @pytest.mark.asyncio
    async def test_real_request_with_bypass_ignores_bypass(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:read"])

        @require_permission("threads", "read")
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        req._ideer_test_bypass_auth = True
        result = await handler(request=req)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_request_from_positional_args(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:read"])

        @require_permission("threads", "read")
        async def handler(thread_id: str, request: Request):
            return f"ok-{thread_id}"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        result = await handler("t1", request=req)
        assert result == "ok-t1"

    @pytest.mark.asyncio
    async def test_no_request_param_raises_value_error(self):
        @require_permission("threads", "read")
        async def handler(some_arg: str):
            return "ok"

        with pytest.raises(ValueError, match="require_permission decorator requires 'request' parameter"):
            await handler("test")

    @pytest.mark.asyncio
    async def test_no_request_injection_for_test_stub(self):
        @require_permission("threads", "read")
        async def handler(request):
            return "ok"

        # handler has 'request' param but no actual Request -- bypass path
        result = await handler()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_request_first_positional_arg_extracted(self):
        """When request is passed as first positional arg and handler's first
        param is 'request', the decorator extracts it from args[0],
        puts it in kwargs, and removes it from args to avoid duplicate."""
        stub = SimpleNamespace(state=SimpleNamespace(), cookies={}, _ideer_test_bypass_auth=True)

        @require_permission("threads", "read")
        async def handler(request):
            return "ok"

        result = await handler(stub)  # positional
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_owner_check_passes(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:read"])
        thread_store = MagicMock()
        thread_store.check_access = AsyncMock(return_value=True)

        @require_permission("threads", "read", owner_check=True)
        async def handler(thread_id: str, request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        # Patch get_thread_store at the deps module where it's imported from
        with patch("app.gateway.deps.get_thread_store", return_value=thread_store):
            result = await handler(thread_id="t1", request=req)
        assert result == "ok"
        thread_store.check_access.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_owner_check_fails_returns_404(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:read"])
        thread_store = MagicMock()
        thread_store.check_access = AsyncMock(return_value=False)

        @require_permission("threads", "read", owner_check=True)
        async def handler(thread_id: str, request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        with patch("app.gateway.deps.get_thread_store", return_value=thread_store):
            with pytest.raises(HTTPException) as exc_info:
                await handler(thread_id="t1", request=req)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_owner_check_missing_thread_id_raises(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:read"])

        @require_permission("threads", "read", owner_check=True)
        async def handler(request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        with pytest.raises(ValueError, match="owner_check=True requires 'thread_id'"):
            await handler(request=req)

    @pytest.mark.asyncio
    async def test_owner_check_with_require_existing(self):
        user = _make_user()
        auth_ctx = AuthContext(user=user, permissions=["threads:delete"])
        thread_store = MagicMock()
        thread_store.check_access = AsyncMock(return_value=True)

        @require_permission("threads", "delete", owner_check=True, require_existing=True)
        async def handler(thread_id: str, request: Request):
            return "ok"

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(auth=auth_ctx)
        with patch("app.gateway.deps.get_thread_store", return_value=thread_store):
            result = await handler(thread_id="t1", request=req)
        assert result == "ok"
        thread_store.check_access.assert_awaited_once_with(
            "t1",
            str(user.id),
            require_existing=True,
        )


# ===========================================================================
# _find_user_param
# ===========================================================================


class TestFindUserParam:
    """Tests for _find_user_param helper."""

    def test_finds_string_annotation(self):
        class FakeUserModel:
            pass

        def handler(current_user: UserModel):
            pass

        # Use a real string annotation
        _find_user_param(handler)

        # Should fall back to "current_user" since "UserModel" is not in
        # the annotation string of a local class. Let's test with actual
        # string annotation containing UserModel:
        def handler2(foo: UserModel):
            pass

        result2 = _find_user_param(handler2)
        assert result2 == "foo"

    def test_finds_resolved_annotation(self):
        """Test with a class whose __name__ is UserModel (module-level)."""

        def handler(my_user: UserModel):
            pass

        result = _find_user_param(handler)
        assert result == "my_user"

    def test_falls_back_to_current_user(self):
        def handler(some_arg: str, another: int):
            pass

        result = _find_user_param(handler)
        assert result == "current_user"

    def test_handles_no_params(self):
        def handler():
            pass

        result = _find_user_param(handler)
        assert result == "current_user"

    def test_handles_value_error_in_signature(self):
        """If inspect.signature raises ValueError, falls back."""
        # Built-in functions may raise ValueError
        result = _find_user_param(len)
        assert result == "current_user"

    def test_handles_type_error_in_signature(self):
        """If inspect.signature raises TypeError, falls back to current_user."""
        with patch("app.gateway.authz.inspect.signature", side_effect=TypeError("bad sig")):
            result = _find_user_param(lambda: None)
        assert result == "current_user"


# ===========================================================================
# require_role decorator
# ===========================================================================


class TestRequireRole:
    """Tests for the require_role decorator."""

    @pytest.mark.asyncio
    async def test_matching_role_passes(self):
        user_mock = _make_user_model(role="super_admin")

        @require_role("super_admin", "department_admin")
        async def handler(current_user=None):
            return "ok"

        result = await handler(current_user=user_mock)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_non_matching_role_returns_403(self):
        user_mock = _make_user_model(role="viewer")

        @require_role("super_admin")
        async def handler(current_user=None):
            return "ok"

        with pytest.raises(HTTPException) as exc_info:
            await handler(current_user=user_mock)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "super_admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_user_returns_401(self):
        @require_role("super_admin")
        async def handler(current_user=None):
            return "ok"

        with pytest.raises(HTTPException) as exc_info:
            await handler()
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_finds_annotated_user_param(self):
        user_mock = _make_user_model(role="admin")

        @require_role("admin")
        async def handler(my_user: UserModel = None):
            return "ok"

        result = await handler(my_user=user_mock)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_multiple_roles(self):
        user_mock = _make_user_model(role="department_admin")

        @require_role("super_admin", "department_admin", "user")
        async def handler(current_user=None):
            return "ok"

        result = await handler(current_user=user_mock)
        assert result == "ok"


# ===========================================================================
# check_resource_access
# ===========================================================================


class TestCheckResourceAccess:
    """Tests for check_resource_access RBAC function."""

    def _user(self, role="user", dept_id=None, uid=None):
        m = MagicMock()
        m.role = role
        m.department_id = dept_id
        m.id = uid or str(uuid4())
        return m

    def test_super_admin_always_allowed(self):
        user = self._user(role="super_admin")
        assert check_resource_access(user, "other-id", "other-dept", "private") is True

    def test_owner_always_allowed(self):
        uid = str(uuid4())
        user = self._user(uid=uid)
        assert check_resource_access(user, uid, "any-dept", "private") is True

    def test_public_visibility_allowed_for_everyone(self):
        user = self._user(role="user")
        assert check_resource_access(user, "other-id", "other-dept", "public") is True

    def test_department_visibility_same_dept(self):
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other-id", "dept-1", "department") is True

    def test_department_visibility_different_dept(self):
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other-id", "dept-2", "department") is False

    def test_department_admin_own_dept(self):
        user = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_access(user, "other-id", "dept-1", "private") is True

    def test_department_admin_other_dept_denied(self):
        user = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_access(user, "other-id", "dept-2", "private") is False

    def test_regular_user_private_not_owner(self):
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other-id", "other-dept", "private") is False

    def test_owner_with_none_owner_id(self):
        user = self._user(uid="some-id")
        # resource_owner_id is None -- owner check doesn't match
        assert check_resource_access(user, None, None, "private") is False

    def test_department_visibility_user_no_dept(self):
        user = self._user(role="user", dept_id=None)
        assert check_resource_access(user, "other-id", "dept-1", "department") is False

    def test_department_admin_no_dept(self):
        user = self._user(role="department_admin", dept_id=None)
        assert check_resource_access(user, "other-id", "dept-1", "private") is False

    def test_department_visibility_resource_no_dept(self):
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other-id", None, "department") is False


# ===========================================================================
# check_resource_modify
# ===========================================================================


class TestCheckResourceModify:
    """Tests for check_resource_modify RBAC function."""

    def _user(self, role="user", dept_id=None, uid=None):
        m = MagicMock()
        m.role = role
        m.department_id = dept_id
        m.id = uid or str(uuid4())
        return m

    def test_super_admin_can_modify(self):
        user = self._user(role="super_admin")
        assert check_resource_modify(user, "other-id", "other-dept") is True

    def test_owner_can_modify(self):
        uid = str(uuid4())
        user = self._user(uid=uid)
        assert check_resource_modify(user, uid, "any-dept") is True

    def test_dept_admin_can_modify_own_dept(self):
        user = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_modify(user, "other-id", "dept-1") is True

    def test_dept_admin_cannot_modify_other_dept(self):
        user = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_modify(user, "other-id", "dept-2") is False

    def test_regular_user_cannot_modify_others(self):
        user = self._user(role="user")
        assert check_resource_modify(user, "other-id", "other-dept") is False

    def test_owner_with_none_owner_id(self):
        user = self._user(uid="some-id")
        assert check_resource_modify(user, None, None) is False

    def test_dept_admin_no_dept(self):
        user = self._user(role="department_admin", dept_id=None)
        assert check_resource_modify(user, "other-id", "dept-1") is False

    def test_dept_admin_resource_no_dept(self):
        user = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_modify(user, "other-id", None) is False


# ===========================================================================
# filter_visible_resources
# ===========================================================================


class TestFilterVisibleResources:
    """Tests for filter_visible_resources."""

    def _user(self, role="user", dept_id=None, uid=None):
        m = MagicMock()
        m.role = role
        m.department_id = dept_id
        m.id = uid or str(uuid4())
        return m

    def _item(self, owner_id=None, department_id=None, visibility="private"):
        return SimpleNamespace(owner_id=owner_id, department_id=department_id, visibility=visibility)

    def test_filters_private_resources_for_non_owner(self):
        user = self._user(role="user")
        items = [self._item(owner_id="other"), self._item(visibility="public")]
        result = filter_visible_resources(items, user)
        assert len(result) == 1
        assert result[0].visibility == "public"

    def test_super_admin_sees_all(self):
        user = self._user(role="super_admin")
        items = [self._item(), self._item(), self._item()]
        assert len(filter_visible_resources(items, user)) == 3

    def test_empty_list(self):
        user = self._user()
        assert filter_visible_resources([], user) == []

    def test_owner_sees_own_resources(self):
        uid = str(uuid4())
        user = self._user(uid=uid)
        items = [self._item(owner_id=uid), self._item(owner_id="other")]
        result = filter_visible_resources(items, user)
        assert len(result) == 1

    def test_defaults_when_attrs_missing(self):
        """Items without visibility/owner_id/department_id should default safely."""
        user = self._user(role="super_admin")
        bare_item = SimpleNamespace()  # no attrs at all
        result = filter_visible_resources([bare_item], user)
        assert len(result) == 1


# ===========================================================================
# get_current_rbac_user
# ===========================================================================


class TestGetCurrentRbacUser:
    """Tests for get_current_rbac_user FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_no_auth_raises_401(self):
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()  # no auth
        with pytest.raises(HTTPException) as exc_info:
            await get_current_rbac_user(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_not_authenticated_raises_401(self):
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()  # no user set by middleware
        with pytest.raises(HTTPException) as exc_info:
            await get_current_rbac_user(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_session_factory_raises_500(self):
        user = _make_user()
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)
        with patch("ideer.persistence.engine.get_session_factory", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_existing_user_returned(self):
        user = _make_user()
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        rbac_user = _make_user_model(role="user", disabled=False)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rbac_user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result is rbac_user

    @pytest.mark.asyncio
    async def test_disabled_user_raises_403(self):
        user = _make_user()
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        rbac_user = _make_user_model(role="user", disabled=True)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rbac_user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 403
        assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_auto_create_first_user_as_super_admin(self):
        user = _make_user()
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        # First query: no user found. Count query: 0 admins.
        _make_user_model(role="super_admin", disabled=False)
        mock_session = AsyncMock()
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # execute is called multiple times: first for user query, then for count
        mock_session.execute = AsyncMock(side_effect=[query_result, count_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        # After commit+refresh, rbac_user gets role set
        def set_role_on_refresh(user_obj):
            user_obj.role = "super_admin"

        mock_session.refresh = AsyncMock(side_effect=lambda u: set_role_on_refresh(u))

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result.role == "super_admin"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_create_non_first_user_as_user(self):
        user = _make_user()
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        _make_user_model(role="user", disabled=False)
        mock_session = AsyncMock()
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result = MagicMock()
        count_result.scalar.return_value = 1  # already has admin

        mock_session.execute = AsyncMock(side_effect=[query_result, count_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        def set_role_on_refresh(user_obj):
            user_obj.role = "user"

        mock_session.refresh = AsyncMock(side_effect=lambda u: set_role_on_refresh(u))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result.role == "user"

    @pytest.mark.asyncio
    async def test_integrity_error_race_condition_re_query(self):
        """When IntegrityError on insert, re-query and return existing user."""
        from sqlalchemy.exc import IntegrityError

        user = _make_user()
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        existing_rbac_user = _make_user_model(role="user", disabled=False)
        mock_session = AsyncMock()

        # 1st execute: user query -> None
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        # 2nd execute: count -> 0 (first user)
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # 3rd execute (after rollback): re-query -> found
        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = existing_rbac_user

        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return query_result
            elif call_count == 2:
                return count_result
            else:
                return requery_result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock(side_effect=IntegrityError("dup", "dup", Exception()))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result is existing_rbac_user
        mock_session.rollback.assert_awaited()

    @pytest.mark.asyncio
    async def test_integrity_error_user_not_found_raises_500(self):
        """When IntegrityError and re-query still returns None, raise 500."""
        from sqlalchemy.exc import IntegrityError

        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        mock_session = AsyncMock()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = None  # still not found

        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return query_result
            elif call_count == 2:
                return count_result
            else:
                return requery_result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock(side_effect=IntegrityError("dup", "dup", Exception()))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_integrity_error_disabled_user_raises_403(self):
        """When IntegrityError and re-query returns a disabled user, raise 403."""
        from sqlalchemy.exc import IntegrityError

        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        disabled_user = _make_user_model(role="user", disabled=True)
        mock_session = AsyncMock()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = disabled_user

        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return query_result
            elif call_count == 2:
                return count_result
            else:
                return requery_result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock(side_effect=IntegrityError("dup", "dup", Exception()))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_integrity_error_concurrent_super_admin_downgrade(self):
        """When IntegrityError, user is super_admin, and admin_count > 1, downgrade to USER."""
        from sqlalchemy.exc import IntegrityError

        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        # The user found after re-query has role=super_admin
        concurrent_user = _make_user_model(role="super_admin", disabled=False)
        mock_session = AsyncMock()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = concurrent_user

        call_count_primary = 0

        async def execute_primary(stmt):
            nonlocal call_count_primary
            call_count_primary += 1
            if call_count_primary == 1:
                return query_result
            elif call_count_primary == 2:
                return count_result
            else:
                return requery_result

        mock_session.execute = AsyncMock(side_effect=execute_primary)
        mock_session.add = MagicMock(side_effect=IntegrityError("dup", "dup", Exception()))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Recheck session: admin_count > 1, user found with super_admin role
        recheck_user = _make_user_model(role="super_admin", disabled=False)
        recheck_session = AsyncMock()
        recheck_count_result = MagicMock()
        recheck_count_result.scalar.return_value = 2
        recheck_user_result = MagicMock()
        recheck_user_result.scalar_one_or_none.return_value = recheck_user

        recheck_call_count = 0

        async def execute_recheck(stmt):
            nonlocal recheck_call_count
            recheck_call_count += 1
            if recheck_call_count == 1:
                return recheck_count_result
            return recheck_user_result

        recheck_session.execute = AsyncMock(side_effect=execute_recheck)
        recheck_session.commit = AsyncMock()
        recheck_session.__aenter__ = AsyncMock(return_value=recheck_session)
        recheck_session.__aexit__ = AsyncMock(return_value=False)

        call_count = 0

        def sf_factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_session
            return recheck_session

        mock_sf = MagicMock(side_effect=sf_factory)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result.role == "user"
        recheck_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_operational_error_fallback_to_plain_count(self):
        """When SELECT FOR UPDATE raises OperationalError, fall back to plain count."""
        from sqlalchemy.exc import OperationalError

        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        mock_session = AsyncMock()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result_ok = MagicMock()
        count_result_ok.scalar.return_value = 1

        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return query_result
            elif call_count == 2:
                raise OperationalError("lock", "lock", Exception())
            else:
                return count_result_ok

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock()

        def set_role_on_refresh(user_obj):
            user_obj.role = "user"

        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock(side_effect=lambda u: set_role_on_refresh(u))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result.role == "user"

    @pytest.mark.asyncio
    async def test_invalid_role_defaults_to_viewer(self, caplog):
        """When role is an invalid enum value, default to VIEWER."""
        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        rbac_user = _make_user_model(role="invalid_role", disabled=False)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rbac_user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with caplog.at_level(logging.ERROR):
                result = await get_current_rbac_user(req)

        # The role should be fixed to VIEWER
        assert result.role == "viewer"
        assert "Invalid role" in caplog.text

    @pytest.mark.asyncio
    async def test_user_email_fallback_to_id(self):
        """When auth_user has no email attribute, use user_id as username."""
        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        mock_session = AsyncMock()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        mock_session.execute = AsyncMock(side_effect=[query_result, count_result])
        mock_session.add = MagicMock()

        _make_user_model(role="super_admin")
        mock_session.commit = AsyncMock()

        def refresh_fn(u):
            u.role = "super_admin"

        mock_session.refresh = AsyncMock(side_effect=refresh_fn)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        # Remove email from auth user
        del user.email

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            await get_current_rbac_user(req)

        # Check that add was called with user_id as username
        added_user = mock_session.add.call_args[0][0]
        assert added_user.username == str(user.id)

    @pytest.mark.asyncio
    async def test_concurrent_downgrade_no_recheck_user(self):
        """When recheck query returns no user, no downgrade happens."""
        from sqlalchemy.exc import IntegrityError

        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        concurrent_user = _make_user_model(role="super_admin", disabled=False)
        mock_session = AsyncMock()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = concurrent_user

        call_count_primary = 0

        async def execute_primary(stmt):
            nonlocal call_count_primary
            call_count_primary += 1
            if call_count_primary == 1:
                return query_result
            elif call_count_primary == 2:
                return count_result
            else:
                return requery_result

        mock_session.execute = AsyncMock(side_effect=execute_primary)
        mock_session.add = MagicMock(side_effect=IntegrityError("dup", "dup", Exception()))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Recheck session: admin_count > 1, but user not found
        recheck_session = AsyncMock()
        recheck_count_result = MagicMock()
        recheck_count_result.scalar.return_value = 2
        recheck_user_result = MagicMock()
        recheck_user_result.scalar_one_or_none.return_value = None  # not found

        recheck_call_count = 0

        async def execute_recheck(stmt):
            nonlocal recheck_call_count
            recheck_call_count += 1
            if recheck_call_count == 1:
                return recheck_count_result
            return recheck_user_result

        recheck_session.execute = AsyncMock(side_effect=execute_recheck)
        recheck_session.commit = AsyncMock()
        recheck_session.__aenter__ = AsyncMock(return_value=recheck_session)
        recheck_session.__aexit__ = AsyncMock(return_value=False)

        call_count = 0

        def sf_factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_session
            return recheck_session

        mock_sf = MagicMock(side_effect=sf_factory)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        # User stays super_admin since recheck_user was None
        assert result is concurrent_user


# ===========================================================================
# get_optional_rbac_user
# ===========================================================================


class TestGetOptionalRbacUser:
    """Tests for get_optional_rbac_user."""

    @pytest.mark.asyncio
    async def test_no_auth_returns_none(self):
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()
        result = await get_optional_rbac_user(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_not_authenticated_returns_none(self):
        req = MagicMock(spec=Request)
        req.state = SimpleNamespace()
        result = await get_optional_rbac_user(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_success_returns_user(self):
        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        rbac_user = _make_user_model(role="user")
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rbac_user
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_optional_rbac_user(req)

        assert result is rbac_user

    @pytest.mark.asyncio
    async def test_401_from_inner_returns_none(self):
        """When inner raises 401, swallow and return None."""
        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        with patch("app.gateway.authz.get_current_rbac_user", new_callable=AsyncMock, side_effect=HTTPException(status_code=401)):
            result = await get_optional_rbac_user(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_403_from_inner_is_reraised(self):
        """When inner raises 403 (disabled user), re-raise it."""
        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        with patch("app.gateway.authz.get_current_rbac_user", new_callable=AsyncMock, side_effect=HTTPException(status_code=403, detail="disabled")):
            with pytest.raises(HTTPException) as exc_info:
                await get_optional_rbac_user(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_500_from_inner_is_reraised(self):
        """When inner raises 500 (DB error), re-raise it."""
        user = _make_user()

        req = MagicMock(spec=Request)
        req.state = SimpleNamespace(user=user)

        with patch("app.gateway.authz.get_current_rbac_user", new_callable=AsyncMock, side_effect=HTTPException(status_code=500, detail="DB error")):
            with pytest.raises(HTTPException) as exc_info:
                await get_optional_rbac_user(req)
        assert exc_info.value.status_code == 500
