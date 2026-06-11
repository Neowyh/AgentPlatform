"""Tests for RBAC visibility and modify-permission functions in authz.py.

Covers:
- check_resource_access() — RBAC visibility-based read access
- check_resource_modify() — ownership/role-based write access
- filter_visible_resources() — bulk filtering
- _find_user_param() — decorator parameter inspection
- require_role() — role-based decorator
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.gateway.authz import (
    _find_user_param,
    check_resource_access,
    check_resource_modify,
    filter_visible_resources,
    require_role,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    user_id: str = "user-1",
    role: str = "user",
    department_id: str | None = None,
    disabled: bool = False,
) -> MagicMock:
    """Create a mock UserModel with the given attributes."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = disabled
    return user


# ---------------------------------------------------------------------------
# check_resource_access
# ---------------------------------------------------------------------------


class TestCheckResourceAccess:
    """Tests for RBAC visibility-based read access."""

    def test_super_admin_can_access_any_resource(self):
        """super_admin always has access regardless of visibility."""
        user = _make_user(role="super_admin")
        assert check_resource_access(user, "other-user", "dept-1", "private") is True

    def test_owner_can_access_own_resource(self):
        """Owner can access their own resource regardless of visibility."""
        user = _make_user(user_id="owner-1", role="user")
        assert check_resource_access(user, "owner-1", "dept-1", "private") is True

    def test_owner_can_access_own_public_resource(self):
        """Owner can access own public resource."""
        user = _make_user(user_id="owner-1", role="user")
        assert check_resource_access(user, "owner-1", None, "public") is True

    def test_any_user_can_access_public_resource(self):
        """Any authenticated user can access public resources."""
        user = _make_user(user_id="stranger", role="user")
        assert check_resource_access(user, "other-user", "dept-1", "public") is True

    def test_user_cannot_access_private_resource_of_others(self):
        """Regular user cannot access private resources owned by others."""
        user = _make_user(user_id="user-1", role="user", department_id="dept-1")
        assert check_resource_access(user, "other-user", "dept-1", "private") is False

    def test_user_can_access_department_resource_same_dept(self):
        """User can access department-visible resource in same department."""
        user = _make_user(user_id="user-1", role="user", department_id="dept-1")
        assert check_resource_access(user, "other-user", "dept-1", "department") is True

    def test_user_cannot_access_department_resource_different_dept(self):
        """User cannot access department-visible resource in different department."""
        user = _make_user(user_id="user-1", role="user", department_id="dept-1")
        assert check_resource_access(user, "other-user", "dept-2", "department") is False

    def test_department_admin_can_access_department_resource(self):
        """department_admin can access resources in own department."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id="dept-1")
        assert check_resource_access(user, "other-user", "dept-1", "department") is True

    def test_department_admin_cannot_access_other_department_resource(self):
        """department_admin cannot access resources in different department."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id="dept-1")
        assert check_resource_access(user, "other-user", "dept-2", "department") is False

    def test_department_admin_can_access_private_in_own_dept(self):
        """department_admin can access private resources in own department (via dept_admin rule)."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id="dept-1")
        # Private visibility, but department_admin rule applies for same dept
        assert check_resource_access(user, "other-user", "dept-1", "private") is True

    def test_department_admin_cannot_access_private_in_other_dept(self):
        """department_admin cannot access private resources in different department."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id="dept-1")
        assert check_resource_access(user, "other-user", "dept-2", "private") is False

    def test_user_without_department_cannot_access_department_resource(self):
        """User without department_id cannot access department resources."""
        user = _make_user(user_id="user-1", role="user", department_id=None)
        assert check_resource_access(user, "other-user", "dept-1", "department") is False

    def test_resource_without_department_id(self):
        """Resource without department_id: department visibility denies access."""
        user = _make_user(user_id="user-1", role="user", department_id="dept-1")
        assert check_resource_access(user, "other-user", None, "department") is False

    def test_owner_without_department_id(self):
        """Owner can access even without department_id matching."""
        user = _make_user(user_id="owner-1", role="user", department_id=None)
        assert check_resource_access(user, "owner-1", "dept-1", "private") is True


# ---------------------------------------------------------------------------
# check_resource_modify
# ---------------------------------------------------------------------------


class TestCheckResourceModify:
    """Tests for ownership/role-based write access."""

    def test_super_admin_can_modify_any_resource(self):
        """super_admin can modify any resource."""
        user = _make_user(role="super_admin")
        assert check_resource_modify(user, "other-user", "dept-1") is True

    def test_owner_can_modify_own_resource(self):
        """Owner can modify own resource."""
        user = _make_user(user_id="owner-1", role="user")
        assert check_resource_modify(user, "owner-1", "dept-1") is True

    def test_user_cannot_modify_others_resource(self):
        """Regular user cannot modify resources owned by others."""
        user = _make_user(user_id="user-1", role="user", department_id="dept-1")
        assert check_resource_modify(user, "other-user", "dept-1") is False

    def test_department_admin_can_modify_department_resource(self):
        """department_admin can modify resources in own department."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id="dept-1")
        assert check_resource_modify(user, "other-user", "dept-1") is True

    def test_department_admin_cannot_modify_other_department_resource(self):
        """department_admin cannot modify resources in different department."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id="dept-1")
        assert check_resource_modify(user, "other-user", "dept-2") is False

    def test_department_admin_without_department_id(self):
        """department_admin without department_id cannot modify via dept rule."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id=None)
        assert check_resource_modify(user, "other-user", "dept-1") is False

    def test_resource_without_department_id(self):
        """Resource without department_id: dept_admin rule doesn't apply."""
        user = _make_user(user_id="admin-1", role="department_admin", department_id="dept-1")
        assert check_resource_modify(user, "other-user", None) is False

    def test_user_role_cannot_modify(self):
        """Regular user role cannot modify others' resources."""
        user = _make_user(user_id="user-1", role="user")
        assert check_resource_modify(user, "other-user", "dept-1") is False


# ---------------------------------------------------------------------------
# filter_visible_resources
# ---------------------------------------------------------------------------


class TestFilterVisibleResources:
    """Tests for bulk filtering of resources by visibility."""

    def _make_item(self, owner_id: str, department_id: str | None, visibility: str) -> SimpleNamespace:
        return SimpleNamespace(owner_id=owner_id, department_id=department_id, visibility=visibility)

    def test_super_admin_sees_all(self):
        """super_admin sees all resources."""
        user = _make_user(role="super_admin")
        items = [
            self._make_item("a", "dept-1", "private"),
            self._make_item("b", "dept-2", "department"),
            self._make_item("c", None, "public"),
        ]
        assert len(filter_visible_resources(items, user)) == 3

    def test_user_sees_only_accessible(self):
        """Regular user sees own + public + same-department resources."""
        user = _make_user(user_id="user-1", role="user", department_id="dept-1")
        items = [
            self._make_item("user-1", "dept-1", "private"),  # own → visible
            self._make_item("other", "dept-1", "department"),  # same dept → visible
            self._make_item("other", "dept-2", "department"),  # diff dept → hidden
            self._make_item("other", None, "public"),  # public → visible
            self._make_item("other", "dept-1", "private"),  # other's private → hidden
        ]
        result = filter_visible_resources(items, user)
        assert len(result) == 3

    def test_empty_list(self):
        """Empty list returns empty."""
        user = _make_user(role="super_admin")
        assert filter_visible_resources([], user) == []

    def test_items_without_visibility_default_to_private(self):
        """Items without visibility attribute default to 'private'."""
        user = _make_user(user_id="user-1", role="user")
        item = SimpleNamespace(owner_id="other-user", department_id=None)
        # No visibility attribute → defaults to "private"
        assert len(filter_visible_resources([item], user)) == 0

    def test_owner_sees_own_private(self):
        """Owner sees own private resources."""
        user = _make_user(user_id="owner-1", role="user")
        items = [
            self._make_item("owner-1", None, "private"),
            self._make_item("other", None, "private"),
        ]
        result = filter_visible_resources(items, user)
        assert len(result) == 1
        assert result[0].owner_id == "owner-1"


# ---------------------------------------------------------------------------
# _find_user_param
# ---------------------------------------------------------------------------


class TestFindUserParam:
    """Tests for decorator parameter inspection."""

    def test_finds_annotated_param(self):
        """Finds parameter annotated as UserModel."""

        async def handler(current_user: UserModel = None):  # noqa: F821
            pass

        # With string annotation containing UserModel
        assert _find_user_param(handler) == "current_user"

    def test_falls_back_to_current_user(self):
        """Falls back to 'current_user' when no UserModel annotation found."""

        async def handler(request=None):
            pass

        assert _find_user_param(handler) == "current_user"

    def test_finds_custom_param_name(self):
        """Finds parameter with custom name annotated as UserModel."""

        async def handler(admin_user: UserModel = None):  # noqa: F821
            pass

        assert _find_user_param(handler) == "admin_user"


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------


class TestRequireRole:
    """Tests for role-based decorator."""

    @pytest.mark.asyncio
    async def test_allows_matching_role(self):
        """User with matching role passes through."""

        @require_role("super_admin")
        async def endpoint(current_user=None):
            return "ok"

        mock_user = MagicMock()
        mock_user.role = "super_admin"
        result = await endpoint(current_user=mock_user)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_rejects_wrong_role(self):
        """User with wrong role gets 403."""

        @require_role("super_admin")
        async def endpoint(current_user=None):
            return "ok"

        mock_user = MagicMock()
        mock_user.role = "user"
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=mock_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_missing_user(self):
        """Missing user gets 401."""

        @require_role("super_admin")
        async def endpoint(current_user=None):
            return "ok"

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_multiple_roles(self):
        """Decorator accepts multiple valid roles."""

        @require_role("super_admin", "department_admin")
        async def endpoint(current_user=None):
            return "ok"

        for role in ("super_admin", "department_admin"):
            mock_user = MagicMock()
            mock_user.role = role
            result = await endpoint(current_user=mock_user)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_rejects_role_not_in_list(self):
        """User role not in the allowed list gets 403."""

        @require_role("super_admin", "department_admin")
        async def endpoint(current_user=None):
            return "ok"

        mock_user = MagicMock()
        mock_user.role = "user"
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=mock_user)
        assert exc_info.value.status_code == 403
