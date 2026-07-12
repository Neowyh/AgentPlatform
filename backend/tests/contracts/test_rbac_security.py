"""RBAC security boundary tests — edge cases and attack surfaces.

Validates:
  - Empty/None role edge cases
  - Disabled user edge cases
  - Cross-department boundary cases
  - Role hierarchy verification
  - Null/invalid role handling
  - Missing resource owner/department edge cases

These tests focus on the authz.py security primitives directly, not on
router-level integration (which is covered by test_rbac_permission_matrix*
and test_permission_model_coverage).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from conftest import _make_rbac_user
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.gateway.authz import (
    _authenticate,
    check_resource_access,
    check_resource_modify,
    filter_visible_resources,
    get_current_rbac_user,
    get_optional_rbac_user,
    require_role,
)
from ideer.persistence.models.user import UserRole

# =====================================================================
# A) Role Hierarchy
# =====================================================================


class TestRoleHierarchy:
    """Verify role hierarchy ordering: super_admin > dept_admin > user > viewer."""

    ROLE_LEVELS = {
        UserRole.VIEWER: 0,
        UserRole.USER: 1,
        UserRole.DEPARTMENT_ADMIN: 2,
        UserRole.SUPER_ADMIN: 3,
    }

    def test_role_levels_ordered(self):
        """Verify the numeric ordering of roles matches expected hierarchy."""
        assert self.ROLE_LEVELS[UserRole.VIEWER] < self.ROLE_LEVELS[UserRole.USER]
        assert self.ROLE_LEVELS[UserRole.USER] < self.ROLE_LEVELS[UserRole.DEPARTMENT_ADMIN]
        assert self.ROLE_LEVELS[UserRole.DEPARTMENT_ADMIN] < self.ROLE_LEVELS[UserRole.SUPER_ADMIN]

    def test_super_admin_can_access_any_visibility(self):
        """super_admin bypasses all visibility checks."""
        for vis in ("private", "department", "public"):
            user = _make_rbac_user(role="super_admin")
            assert check_resource_access(user, "someone-else", "other-dept", vis) is True

    def test_dept_admin_follows_same_rules_as_user_for_access(self):
        """department_admin has same visibility rules as user (no super_admin bypass)."""
        admin = _make_rbac_user(role="department_admin", department_id="dept-1", user_id="admin-1")
        user = _make_rbac_user(role="user", department_id="dept-1", user_id="user-1")

        for usr in (admin, user):
            # Private (not owner): denied for both
            assert check_resource_access(usr, "other", "dept-1", "private") is False
            # Department (same dept): allowed for both
            assert check_resource_access(usr, "other", "dept-1", "department") is True
            # Department (diff dept): denied for both
            assert check_resource_access(usr, "other", "dept-2", "department") is False

    def test_modify_is_owner_only_regardless_of_role(self):
        """check_resource_modify returns True only for owner, regardless of role."""
        owner_id = str(uuid4())
        for role in ("viewer", "user", "department_admin", "super_admin"):
            owner = _make_rbac_user(role=role, user_id=owner_id)
            non_owner = _make_rbac_user(role=role, user_id="other")

            assert check_resource_modify(owner, owner_id, "dept-1") is True
            assert check_resource_modify(non_owner, owner_id, "dept-1") is False


# =====================================================================
# B) Empty / None Role Edge Cases
# =====================================================================


class TestEmptyNoneRole:
    """Edge cases for missing, None, or empty-string roles."""

    @pytest.mark.asyncio
    async def test_require_role_with_none_role(self):
        """User with None role gets 403 from require_role."""

        @require_role(UserRole.SUPER_ADMIN)
        async def endpoint(current_user=None):
            return "ok"

        user = _make_rbac_user(role=None)  # type: ignore[arg-type]
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_role_with_empty_string_role(self):
        """User with empty-string role gets 403 from require_role."""

        @require_role(UserRole.SUPER_ADMIN)
        async def endpoint(current_user=None):
            return "ok"

        user = _make_rbac_user(role="")
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=user)
        assert exc_info.value.status_code == 403

    def test_none_role_check_resource_access(self):
        """User with None role is treated like any non-super-admin role."""
        user = _make_rbac_user(role=None)  # type: ignore[arg-type]
        # Private (not owner): denied
        assert check_resource_access(user, "other", "dept-1", "private") is False
        # Public: allowed for all
        assert check_resource_access(user, "other", None, "public") is True
        # Department without dept_id: denied
        assert check_resource_access(user, "other", "dept-1", "department") is False

    def test_none_role_check_resource_modify(self):
        """User with None role cannot modify others' resources."""
        user = _make_rbac_user(role=None)  # type: ignore[arg-type]
        assert check_resource_modify(user, "other", "dept-1") is False
        # Owner with None role can still modify own resource
        owner_id = str(user.id)
        assert check_resource_modify(user, owner_id, "dept-1") is True

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_role_grants_permissions(self):
        """_authenticate grants full permissions for user role."""
        auth_user = MagicMock()
        auth_user.id = str(uuid4())

        rbac_user = _make_rbac_user(role="user")
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = rbac_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=auth_user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            ctx = await _authenticate(req)

        assert ctx.has_permission("threads", "write") is True
        assert ctx.has_permission("threads", "read") is True


# =====================================================================
# C) Disabled User Edge Cases
# =====================================================================


class TestDisabledUserEdgeCases:
    """Verify disabled user handling in all security paths."""

    @pytest.mark.asyncio
    async def test_disabled_user_raises_403(self):
        """get_current_rbac_user raises 403 for disabled user."""
        req = MagicMock()
        req.state = type("S", (), {"user": MagicMock(id=str(uuid4()))})()

        disabled_user = _make_rbac_user(role="user", disabled=True)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = disabled_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 403
        assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_disabled_super_admin_still_denied(self):
        """A disabled super_admin is still denied."""
        req = MagicMock()
        req.state = type("S", (), {"user": MagicMock(id=str(uuid4()))})()

        disabled_sa = _make_rbac_user(role="super_admin", disabled=True)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = disabled_sa

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_optional_rbac_user_re_raises_403(self):
        """get_optional_rbac_user re-raises 403 for disabled user (not None)."""
        req = MagicMock()
        req.state = type("S", (), {"user": MagicMock(id=str(uuid4()))})()

        disabled_user = _make_rbac_user(role="user", disabled=True)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = disabled_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_optional_rbac_user(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_disabled_user_not_returned_by_authentication(self):
        """Disabled user should be detectable in the authenticate path."""
        auth_user = MagicMock()
        auth_user.id = str(uuid4())

        disabled_user = _make_rbac_user(role="user", disabled=True)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = disabled_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=auth_user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate(req)
        assert exc_info.value.status_code == 403


# =====================================================================
# D) Cross-Department Boundary Cases
# =====================================================================


class TestCrossDepartmentBoundary:
    """Verify department isolation is enforced across all check paths."""

    def test_user_cross_dept_private_blocked(self):
        """User cannot access private resource in another department."""
        user = _make_rbac_user(role="user", department_id="dept-A")
        assert check_resource_access(user, "other", "dept-B", "private") is False

    def test_user_cross_dept_department_blocked(self):
        """User cannot access department resource in another department."""
        user = _make_rbac_user(role="user", department_id="dept-A")
        assert check_resource_access(user, "other", "dept-B", "department") is False

    def test_dept_admin_cross_dept_private_blocked(self):
        """department_admin cannot access private resource in another department."""
        admin = _make_rbac_user(role="department_admin", department_id="dept-A")
        assert check_resource_access(admin, "other", "dept-B", "private") is False

    def test_dept_admin_cross_dept_department_blocked(self):
        """department_admin cannot access department resource in another department."""
        admin = _make_rbac_user(role="department_admin", department_id="dept-A")
        assert check_resource_access(admin, "other", "dept-B", "department") is False

    def test_user_without_dept_accesses_nothing_department(self):
        """User without department cannot access ANY department resource."""
        user = _make_rbac_user(role="user", department_id=None)
        for resource_dept in ("dept-A", "dept-B", None):
            assert check_resource_access(user, "other", resource_dept, "department") is False

    def test_resource_without_dept_id_blocks_department_access(self):
        """Resource without department_id blocks department-visibility access."""
        user = _make_rbac_user(role="user", department_id="dept-A")
        assert check_resource_access(user, "other", None, "department") is False

    def test_owner_cross_dept_still_accessible(self):
        """Owner can access own resource regardless of department mismatch."""
        uid = str(uuid4())
        user = _make_rbac_user(role="user", user_id=uid, department_id="dept-A")
        # Own resource in different department
        assert check_resource_access(user, uid, "dept-B", "private") is True
        assert check_resource_access(user, uid, "dept-B", "department") is True

    def test_filter_visible_cross_dept(self):
        """filter_visible_resources correctly filters cross-department resources."""
        uid = str(uuid4())
        user = _make_rbac_user(role="user", user_id=uid, department_id="dept-A")
        items = [
            type("R", (), {"owner_id": "other", "department_id": "dept-A", "visibility": "department"}),
            type("R", (), {"owner_id": "other", "department_id": "dept-B", "visibility": "department"}),
            type("R", (), {"owner_id": "other", "department_id": None, "visibility": "department"}),
            type("R", (), {"owner_id": uid, "department_id": "dept-B", "visibility": "private"}),
            type("R", (), {"owner_id": "other", "department_id": None, "visibility": "public"}),
        ]
        visible = filter_visible_resources(items, user)
        assert len(visible) == 3  # dept-A dept + own private + public


# =====================================================================
# E) Missing Resource Metadata Edge Cases
# =====================================================================


class TestMissingResourceMetadata:
    """Edge cases for resources with missing owner/department info."""

    def test_resource_with_no_owner_id(self):
        """Resource with None owner_id: owner check returns False."""
        user = _make_rbac_user(user_id="user-1")
        assert check_resource_modify(user, None, "dept-1") is False

    def test_resource_with_no_visibility_defaults_private(self):
        """filter_visible_resources defaults missing visibility to 'private'."""
        user = _make_rbac_user(role="user", user_id="user-1", department_id="dept-1")
        item = type("R", (), {"owner_id": "other", "department_id": "dept-1"})
        # No visibility attr → getattr defaults to private → denied for non-owner
        result = filter_visible_resources([item], user)
        assert len(result) == 0

    def test_resource_no_owner_public_accessible(self):
        """Public resource is accessible even without owner."""
        user = _make_rbac_user(role="user")
        assert check_resource_access(user, None, None, "public") is True

    def test_resource_no_owner_private_denied(self):
        """Private resource without owner is denied to non-super-admin."""
        user = _make_rbac_user(role="user")
        assert check_resource_access(user, None, None, "private") is False


# =====================================================================
# F) require_role Security Edge Cases
# =====================================================================


class TestRequireRoleSecurityEdgeCases:
    """Security-focused edge cases for the require_role decorator."""

    @pytest.mark.asyncio
    async def test_require_role_no_user_raises_401(self):
        """Missing user (None) raises 401, not 403."""

        @require_role(UserRole.SUPER_ADMIN)
        async def endpoint(current_user=None):
            return "ok"

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=None)
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_wrong_role_raises_403(self):
        """Wrong role raises 403 with descriptive message."""

        @require_role(UserRole.SUPER_ADMIN)
        async def endpoint(current_user=None):
            return "ok"

        user = _make_rbac_user(role="user")
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=user)
        assert exc_info.value.status_code == 403
        assert "Requires role" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_multi_role_accepts_any(self):
        """Multi-role decorator accepts any of the listed roles."""

        @require_role(UserRole.USER, UserRole.SUPER_ADMIN)
        async def endpoint(current_user=None):
            return "ok"

        for role in ("user", "super_admin"):
            user = _make_rbac_user(role=role)
            result = await endpoint(current_user=user)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_require_role_rejects_unlisted_role(self):
        """Role not in allowed list gets 403."""

        @require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
        async def endpoint(current_user=None):
            return "ok"

        user = _make_rbac_user(role="user")
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_role_case_sensitive(self):
        """Role comparison is case-sensitive."""

        @require_role(UserRole.SUPER_ADMIN)
        async def endpoint(current_user=None):
            return "ok"

        user = _make_rbac_user(role="Super_Admin")
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_role_empty_allowed_list_denies_all(self):
        """Empty role list should deny everyone."""

        @require_role()
        async def endpoint(current_user=None):
            return "ok"

        user = _make_rbac_user(role="super_admin")
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=user)
        assert exc_info.value.status_code == 403


# =====================================================================
# G) get_current_rbac_user Edge Cases
# =====================================================================


class TestGetCurrentRbacUserEdgeCases:
    """Edge cases for the get_current_rbac_user dependency."""

    @pytest.mark.asyncio
    async def test_no_user_on_request_raises_401(self):
        """Request without user attribute raises 401."""
        req = MagicMock()
        req.state = type("S", (), {})()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_rbac_user(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_session_factory_raises_500(self):
        """No session factory raises 500."""
        req = MagicMock()
        req.state = type("S", (), {"user": MagicMock(id=str(uuid4()))})()
        with patch("ideer.persistence.engine.get_session_factory", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_operational_error_raises_503(self):
        """OperationalError during _authenticate raises 503."""
        auth_user = MagicMock()
        auth_user.id = str(uuid4())
        mock_sf = MagicMock(side_effect=OperationalError("conn", {}, Exception()))
        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=auth_user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate(req)
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_programming_error_raises_503(self):
        """ProgrammingError during _authenticate raises 503."""
        auth_user = MagicMock()
        auth_user.id = str(uuid4())
        mock_sf = MagicMock(side_effect=ProgrammingError("sql", {}, Exception()))
        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=auth_user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate(req)
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_none_role_in_db_defaults_to_viewer_permissions(self):
        """A NULL role has only the viewer read permission set."""
        auth_user = MagicMock()
        auth_user.id = str(uuid4())

        null_role_user = MagicMock()
        null_role_user.role = None
        null_role_user.disabled = False

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = null_role_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch("app.gateway.deps.get_optional_user_from_request", new_callable=AsyncMock, return_value=auth_user),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            ctx = await _authenticate(req)
        assert ctx.has_permission("threads", "read") is True
        assert ctx.has_permission("threads", "write") is False


# =====================================================================
# H) get_optional_rbac_user Edge Cases
# =====================================================================


class TestGetOptionalRbacUserEdgeCases:
    """Edge cases for the get_optional_rbac_user dependency."""

    @pytest.mark.asyncio
    async def test_no_user_returns_none_coro(self):
        """Awaiting get_optional_rbac_user without user returns None."""
        req = MagicMock()
        req.state = type("S", (), {})()
        result = await get_optional_rbac_user(req)
        assert result is None
