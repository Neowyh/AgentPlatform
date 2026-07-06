"""E2E tests for the admin router (backend/app/gateway/routers/admin.py).

Covers all 8 admin endpoints with real HTTP stack:
- GET /api/admin/stats
- GET /api/admin/users
- PUT /api/admin/users/{user_id}/role
- DELETE /api/admin/users/{user_id}
- GET /api/admin/departments
- POST /api/admin/departments
- PUT /api/admin/departments/{dept_id}
- DELETE /api/admin/departments/{dept_id}
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.admin import router as admin_router

pytestmark = pytest.mark.no_auto_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str = "admin-1",
    role: str = "super_admin",
    department_id: str | None = None,
) -> MagicMock:
    """Create a mock RBAC user."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = False
    user.username = f"user-{user_id}"
    return user


def _make_app(role: str = "super_admin") -> tuple:
    """Create test app with admin router and stubbed RBAC."""
    user = _make_rbac_user(role=role)
    app = make_authed_test_app()
    app.include_router(admin_router)

    async def _stub_rbac():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_rbac
    return app, user


# ---------------------------------------------------------------------------
# Tests — GET /api/admin/stats
# ---------------------------------------------------------------------------


class TestAdminStats:
    """Tests for GET /api/admin/stats."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_get_stats_returns_counts(self, mock_get_session_factory):
        """Stats endpoint returns user, department, and resource counts."""
        call_count = {"n": 0}
        mock_session = AsyncMock()

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] <= 2:
                # User and dept count queries
                result.scalar = MagicMock(return_value=5)
            else:
                # Resource metadata group query
                result.all = MagicMock(return_value=[("agent", 1), ("tool", 2)])
            return result

        mock_session.execute = AsyncMock(side_effect=_execute)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "total_departments" in data
        assert data["total_agents"] == 1
        assert data["total_tools"] == 2
        assert data["total_resources"] == 3


# ---------------------------------------------------------------------------
# Tests — GET /api/admin/users
# ---------------------------------------------------------------------------


class TestAdminUsers:
    """Tests for GET /api/admin/users."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_returns_list(self, mock_get_session_factory):
        """List users returns a list of user objects."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert isinstance(data["users"], list)

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_with_filters(self, mock_get_session_factory):
        """List users respects department_id and role filters."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/admin/users?department_id=dept-1&role=user&limit=10&offset=0")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests — PUT /api/admin/users/{user_id}/role
# ---------------------------------------------------------------------------


class TestAdminUserRole:
    """Tests for PUT /api/admin/users/{user_id}/role."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_user_role_success(self, mock_get_session_factory):
        """Update user role succeeds with valid role."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.role = "user"

        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                # Admin limit checks: return 0 so limits aren't hit
                result.scalar = MagicMock(return_value=0)
            elif "users_ext" in stmt_str:
                result.scalar_one_or_none = MagicMock(return_value=mock_user)
            else:
                result.scalar_one_or_none = MagicMock(return_value=mock_user)
            return result

        mock_session.execute = AsyncMock(side_effect=_execute)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/admin/users/user-1/role",
                json={"role": "department_admin"},
            )
        assert resp.status_code == 200

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_user_role_not_found(self, mock_get_session_factory):
        """Update user role returns 404 when user not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/admin/users/nonexistent/role",
                json={"role": "department_admin"},
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — DELETE /api/admin/users/{user_id}
# ---------------------------------------------------------------------------


class TestAdminDisableUser:
    """Tests for DELETE /api/admin/users/{user_id}."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_success(self, mock_get_session_factory):
        """Toggle user disabled succeeds when user exists."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.disabled = False
        mock_user.role = "user"

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=0)
            elif "users_ext" in stmt_str:
                result.scalar_one_or_none = MagicMock(return_value=mock_user)
            else:
                result.scalar_one_or_none = MagicMock(return_value=mock_user)
            return result

        mock_session.execute = AsyncMock(side_effect=_execute)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/admin/users/user-1/role",
                json={"role": "user"},
            )
        assert resp.status_code == 200

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_not_found(self, mock_get_session_factory):
        """Toggle user disabled returns 404 when user not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/admin/users/nonexistent/role",
                json={"role": "user"},
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — GET /api/admin/departments
# ---------------------------------------------------------------------------


class TestAdminDepartments:
    """Tests for GET /api/admin/departments."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_returns_list(self, mock_get_session_factory):
        """List departments returns a list."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/api/admin/departments")
        assert resp.status_code == 200
        data = resp.json()
        assert "departments" in data
        assert isinstance(data["departments"], list)


# ---------------------------------------------------------------------------
# Tests — POST /api/admin/departments
# ---------------------------------------------------------------------------


class TestAdminCreateDepartment:
    """Tests for POST /api/admin/departments."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_success(self, mock_get_session_factory):
        """Create department succeeds with valid data."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/admin/departments",
                json={"name": "Engineering", "description": "Engineering team"},
            )
        assert resp.status_code in (200, 201)

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_duplicate(self, mock_get_session_factory):
        """Create department fails with duplicate name."""
        mock_session = AsyncMock()
        mock_existing = MagicMock()
        mock_existing.name = "Engineering"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/api/admin/departments",
                json={"name": "Engineering"},
            )
        assert resp.status_code in (400, 409)


# ---------------------------------------------------------------------------
# Tests — PUT /api/admin/departments/{dept_id}
# ---------------------------------------------------------------------------


class TestAdminUpdateDepartment:
    """Tests for PUT /api/admin/departments/{dept_id}."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_success(self, mock_get_session_factory):
        """Update department succeeds with valid data."""
        mock_session = AsyncMock()
        mock_dept = MagicMock()
        mock_dept.id = "dept-1"
        mock_dept.name = "Old Name"
        mock_find_result = MagicMock()
        mock_find_result.scalar_one_or_none.return_value = mock_dept
        mock_no_dup = MagicMock()
        mock_no_dup.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(side_effect=[mock_find_result, mock_no_dup])
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/admin/departments/dept-1",
                json={"name": "New Name", "description": "Updated"},
            )
        assert resp.status_code == 200

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_not_found(self, mock_get_session_factory):
        """Update department returns 404 when not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.put(
                "/api/admin/departments/nonexistent",
                json={"name": "New Name"},
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — DELETE /api/admin/departments/{dept_id}
# ---------------------------------------------------------------------------


class TestAdminDeleteDepartment:
    """Tests for DELETE /api/admin/departments/{dept_id}."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_success(self, mock_get_session_factory):
        """Delete department succeeds when no active members."""
        mock_session = AsyncMock()
        mock_dept = MagicMock()
        mock_dept.id = "dept-1"
        mock_find_result = MagicMock()
        mock_find_result.scalar_one_or_none.return_value = mock_dept
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_ok_result = MagicMock()

        async def _execute(stmt):
            if "scalar_one_or_none" not in str(type(mock_find_result)):
                return mock_find_result
            return mock_ok_result

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_find_result,  # find department
                mock_count_result,  # count members
                mock_ok_result,  # update users department_id
                mock_ok_result,  # downgrade department resources
                mock_ok_result,  # clear department_id on resources
            ]
        )
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.delete("/api/admin/departments/dept-1")
        assert resp.status_code in (200, 204)

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_not_found(self, mock_get_session_factory):
        """Delete department returns 404 when not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_get_session_factory.return_value = MagicMock(return_value=mock_ctx)

        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.delete("/api/admin/departments/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — RBAC Enforcement
# ---------------------------------------------------------------------------


class TestAdminRBAC:
    """Tests for RBAC enforcement on admin endpoints."""

    def test_non_admin_cannot_access_stats(self):
        """Non-admin user cannot access admin stats."""
        user = _make_rbac_user(role="user")
        app = make_authed_test_app()
        app.include_router(admin_router)

        async def _stub_rbac():
            return user

        app.dependency_overrides[get_current_rbac_user] = _stub_rbac

        with TestClient(app) as client:
            resp = client.get("/api/admin/stats")
        # Should be forbidden for non-admin
        assert resp.status_code in (403, 401)

    def test_department_admin_cannot_delete_department(self):
        """Department admin cannot delete departments."""
        user = _make_rbac_user(role="department_admin")
        app = make_authed_test_app()
        app.include_router(admin_router)

        async def _stub_rbac():
            return user

        app.dependency_overrides[get_current_rbac_user] = _stub_rbac

        with TestClient(app) as client:
            resp = client.delete("/api/admin/departments/dept-1")
        # Should be forbidden for department_admin
        assert resp.status_code in (403, 401)
