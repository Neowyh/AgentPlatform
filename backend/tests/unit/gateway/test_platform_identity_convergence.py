"""Platform identity convergence contract tests.

The platform role (``users_ext``) is the only authorization source. These
tests pin the seams the plan calls out:

- an auth row still carrying legacy ``admin`` must yield only the platform
  role's permissions (viewer stays read-only, super_admin stays full);
- a missing / invalid / disabled platform profile denies access on every
  entry point (middleware route permissions, decorators, admin gate);
- the run context role comes from the server-side identity cache, never from
  the client or the legacy auth-table value.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _session_factory(rbac_row):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = rbac_row
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_session)


def _session_factory_scalar(scalar_value):
    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=scalar_value)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_session)


def _auth_request(role_on_auth_row="admin", source="session"):
    """A session-authenticated request whose auth row still says 'admin'."""
    user = SimpleNamespace(id="legacy-admin", email="legacy@test.com", system_role=role_on_auth_row)
    request = MagicMock()
    request.state = SimpleNamespace(user=user, auth_source=source)
    return request, user


# ---------------------------------------------------------------------------
# _authenticate — the decorator entry point
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_admin_auth_row_with_viewer_platform_role_is_read_only():
    """The plan's headline regression: auth 'admin' + platform viewer → viewer."""
    from app.gateway.authz import Permissions, _authenticate

    request, user = _auth_request()
    rbac_row = SimpleNamespace(id="legacy-admin", role="viewer", department_id=None, disabled=False)
    with (
        patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
        patch("deerflow.persistence.engine.get_session_factory", return_value=_session_factory(rbac_row)),
    ):
        ctx = await _authenticate(request)

    assert ctx.has_permission("threads", "read") is True
    assert ctx.has_permission("threads", "write") is False
    assert Permissions.THREADS_WRITE not in ctx.permissions


@pytest.mark.asyncio
async def test_platform_super_admin_with_user_auth_row_gets_all_permissions():
    """auth 'user' + platform super_admin → full permissions (no downgrade)."""
    from app.gateway.authz import Permissions, _authenticate

    request, user = _auth_request(role_on_auth_row="user")
    rbac_row = SimpleNamespace(id="legacy-admin", role="super_admin", department_id=None, disabled=False)
    with (
        patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=user),
        patch("deerflow.persistence.engine.get_session_factory", return_value=_session_factory(rbac_row)),
    ):
        ctx = await _authenticate(request)

    assert ctx.has_permission("threads", "write") is True
    assert Permissions.THREADS_WRITE in ctx.permissions


# ---------------------------------------------------------------------------
# middleware route permissions — the AuthContext the permission-less routes use
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_grants_viewer_only_route_permissions_for_viewer_profile():
    from app.gateway.authz import resolve_route_permissions

    config = MagicMock(enabled=False)
    with patch("app.gateway.authz._get_route_authorization_config", return_value=config):
        # Disabled config short-circuits; exercise the platform-role plumbing
        # through the enabled path instead.
        pass

    from app.gateway.authz import Permissions
    from deerflow.authz.rbac import RbacAuthorizationProvider

    provider = RbacAuthorizationProvider(
        roles={
            "viewer": {"routes": {"allow": [Permissions.THREADS_READ]}},
            "super_admin": {"routes": {"allow": [Permissions.THREADS_WRITE]}},
        }
    )
    request, user = _auth_request()
    with patch("app.gateway.authz._get_route_authorization_config", return_value=MagicMock(enabled=False)):
        pass

    # Direct check of the platform-role handoff used by the middleware.
    with (
        patch("app.gateway.authz._get_route_authorization_config", return_value=MagicMock(enabled=False)),
    ):
        pass

    # The middleware resolves identity then passes role to resolve_route_permissions.
    from app.gateway.authz import resolve_platform_identity

    rbac_row = SimpleNamespace(id="legacy-admin", role="viewer", department_id=None, disabled=False)
    with patch("deerflow.persistence.engine.get_session_factory", return_value=_session_factory(rbac_row)):
        identity = await resolve_platform_identity(request, user)
    assert identity["role"] == "viewer"

    enabled = MagicMock(enabled=True, fail_closed=True, default_role="user")
    with (
        patch("app.gateway.authz._get_route_authorization_config", return_value=enabled),
        patch("app.gateway.authz._get_cached_route_provider", return_value=provider),
    ):
        viewer_permissions = await resolve_route_permissions(user, is_internal=False, platform_role="viewer")
    assert Permissions.THREADS_WRITE not in viewer_permissions


@pytest.mark.asyncio
async def test_middleware_route_permissions_never_read_auth_row_role():
    """With authorization enabled, an auth-row 'admin' yields nothing on its own."""
    from app.gateway.authz import Permissions, resolve_route_permissions
    from deerflow.authz.rbac import RbacAuthorizationProvider

    provider = RbacAuthorizationProvider(
        roles={
            "admin": {"routes": {"allow": [Permissions.THREADS_WRITE]}},
        }
    )
    enabled = MagicMock(enabled=True, fail_closed=True, default_role="user")
    user = SimpleNamespace(id="legacy-admin", system_role="admin")
    with (
        patch("app.gateway.authz._get_route_authorization_config", return_value=enabled),
        patch("app.gateway.authz._get_cached_route_provider", return_value=provider),
    ):
        permissions = await resolve_route_permissions(user, is_internal=False, platform_role=None)

    # platform_role=None → default_role 'user' → no policy entry → fail closed
    assert Permissions.THREADS_WRITE not in permissions


# ---------------------------------------------------------------------------
# admin gate (skills/mcp/integrations/channels/subagents)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_gate_requires_super_admin_platform_role():
    from app.gateway.deps import is_admin_user

    request, user = _auth_request()  # auth row says 'admin'
    rbac_row = SimpleNamespace(id="legacy-admin", role="user", department_id=None, disabled=False)
    with patch("deerflow.persistence.engine.get_session_factory", return_value=_session_factory(rbac_row)):
        assert await is_admin_user(request) is False


@pytest.mark.asyncio
async def test_admin_gate_accepts_super_admin_platform_profile():
    from app.gateway.deps import is_admin_user

    request, user = _auth_request(role_on_auth_row="user")
    rbac_row = SimpleNamespace(id="legacy-admin", role="super_admin", department_id=None, disabled=False)
    with patch("deerflow.persistence.engine.get_session_factory", return_value=_session_factory(rbac_row)):
        assert await is_admin_user(request) is True


@pytest.mark.asyncio
async def test_admin_gate_denies_pat_credentials():
    from app.gateway.auth_disabled import AUTH_SOURCE_PAT
    from app.gateway.deps import is_admin_user

    request, user = _auth_request(source=AUTH_SOURCE_PAT)
    assert await is_admin_user(request) is False


# ---------------------------------------------------------------------------
# run context — client cannot forge the role
# ---------------------------------------------------------------------------


def test_run_context_role_comes_from_identity_cache_not_client():
    from app.gateway.services import build_run_config, inject_authenticated_user_context

    request = SimpleNamespace(
        state=SimpleNamespace(
            auth_source="session",
            user=SimpleNamespace(id="legacy-admin", system_role="admin", oauth_provider=None, oauth_id=None),
            _ideer_rbac_user={"user_id": "legacy-admin", "role": "viewer", "department_id": None},
        )
    )
    config = build_run_config("thread-conv", None, None)
    inject_authenticated_user_context(config, request)
    assert config["context"]["user_role"] == "viewer"


def test_run_context_without_identity_cache_has_no_role():
    """No platform identity resolved → no role is stamped (no auth-row fallback)."""
    from app.gateway.services import build_run_config, inject_authenticated_user_context

    request = SimpleNamespace(
        state=SimpleNamespace(
            auth_source="session",
            user=SimpleNamespace(id="embedded", system_role="admin", oauth_provider=None, oauth_id=None),
        )
    )
    config = build_run_config("thread-conv", None, None)
    inject_authenticated_user_context(config, request)
    assert "user_role" not in config["context"]


# ---------------------------------------------------------------------------
# disabled / missing profiles deny at the shared resolver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_profile_denies_access():
    from app.gateway.authz import resolve_platform_identity

    request, user = _auth_request()
    rbac_row = SimpleNamespace(id="legacy-admin", role="user", department_id=None, disabled=True)
    with patch("deerflow.persistence.engine.get_session_factory", return_value=_session_factory(rbac_row)):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_platform_identity(request, user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_profile_denies_access():
    from app.gateway.authz import resolve_platform_identity

    request, user = _auth_request()
    with patch("deerflow.persistence.engine.get_session_factory", return_value=_session_factory(None)):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_platform_identity(request, user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_db_failure_degrades_to_503():
    from app.gateway.authz import resolve_platform_identity

    request, user = _auth_request()
    sf = MagicMock(side_effect=RuntimeError("DB down"))
    with patch("deerflow.persistence.engine.get_session_factory", return_value=sf):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_platform_identity(request, user)
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_identity_is_cached_per_request():
    """The second resolution on the same request issues no extra SELECT."""
    from app.gateway.authz import resolve_platform_identity

    request, user = _auth_request()
    rbac_row = SimpleNamespace(id="legacy-admin", role="user", department_id="dept-1", disabled=False)
    sf = _session_factory(rbac_row)
    with patch("deerflow.persistence.engine.get_session_factory", return_value=sf):
        await resolve_platform_identity(request, user)
        await resolve_platform_identity(request, user)
    assert sf.call_count == 1


@pytest.mark.asyncio
async def test_trusted_sources_skip_platform_resolution():
    """Internal and auth-disabled sources never impersonate a platform role."""
    from app.gateway.auth_disabled import AUTH_SOURCE_AUTH_DISABLED
    from app.gateway.authz import resolve_platform_identity

    for source in ("internal", AUTH_SOURCE_AUTH_DISABLED):
        request, user = _auth_request(source=source)
        with patch("deerflow.persistence.engine.get_session_factory", side_effect=AssertionError("must not query")):
            assert await resolve_platform_identity(request, user) is None
