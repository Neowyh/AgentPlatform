"""Tests for the admin management router (backend/app/gateway/routers/admin.py).

Covers:
- GET /api/admin/stats — admin dashboard statistics
- GET /api/admin/users — list users with filters
- PUT /api/admin/users/{user_id}/role — update user role
- DELETE /api/admin/users/{user_id} — disable user
- GET /api/admin/departments — list departments
- POST /api/admin/departments — create department
- PUT /api/admin/departments/{dept_id} — update department
- DELETE /api/admin/departments/{dept_id} — delete department
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.admin import router as admin_router
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str = "admin-1",
    role: str = "super_admin",
    department_id: str | None = None,
    disabled: bool = False,
) -> MagicMock:
    """Create a mock RBAC user."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = disabled
    user.created_at = None
    user.last_login = None
    user.username = f"user-{user_id}"
    return user


def _make_app(current_user: MagicMock | None = None) -> FastAPI:
    """Create a test FastAPI app with admin router and stubbed auth."""
    app = FastAPI()
    app.include_router(admin_router)

    user = current_user or _make_rbac_user()

    async def _stub_current_user():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current_user
    return app


def _mock_session(user_model_results=None, dept_model_results=None, count_results=None, resource_type_counts=None):
    """Create a mock SQLAlchemy session with configurable results."""
    session = AsyncMock()

    # Configure execute to return different results based on the statement
    async def _execute(stmt):
        stmt_str = str(stmt)
        result = MagicMock()

        # Resource metadata group query (must check before generic count)
        if "resource_metadata" in stmt_str:
            result.all = MagicMock(return_value=resource_type_counts or [])
            return result

        # Count queries
        if "count" in stmt_str.lower():
            result.scalar = MagicMock(return_value=count_results if count_results is not None else 0)
            return result

        # User queries
        if "users_ext" in stmt_str:
            if user_model_results is not None:
                if isinstance(user_model_results, list):
                    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=user_model_results)))
                else:
                    result.scalar_one_or_none = MagicMock(return_value=user_model_results)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        # Department queries
        if "departments" in stmt_str:
            if dept_model_results is not None:
                if isinstance(dept_model_results, list):
                    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=dept_model_results)))
                else:
                    result.scalar_one_or_none = MagicMock(return_value=dept_model_results)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        # Default
        result.scalar_one_or_none = MagicMock(return_value=None)
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        return result

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()

    return session


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------


class TestAdminStats:
    """Tests for GET /api/admin/stats."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_get_stats_returns_counts(self, mock_sf):
        """Stats endpoint returns user and department counts."""
        session = _mock_session(count_results=5)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "total_departments" in data

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_get_stats_no_database(self, mock_sf):
        """Stats endpoint returns 500 when database not initialized."""
        mock_sf.return_value = None

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/stats")

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# User management endpoints
# ---------------------------------------------------------------------------


class TestAdminUserManagement:
    """Tests for user management endpoints."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_returns_paginated(self, mock_sf):
        """List users returns paginated results."""
        user1 = _make_rbac_user(user_id="u1")
        user2 = _make_rbac_user(user_id="u2")

        session = _mock_session(user_model_results=[user1, user2], count_results=2)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/users")

        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_invalid_role_filter(self, mock_sf):
        """List users rejects invalid role filter."""
        session = _mock_session()
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/users?role=invalid_role")

        assert resp.status_code == 400
        assert "Invalid role filter" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_user_role_success(self, mock_sf):
        """Update user role succeeds for valid request."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.USER

        session = _mock_session(user_model_results=target_user, count_results=3)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/admin/users/target-1/role",
            json={"role": "department_admin"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["new_role"] == "department_admin"

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_user_role_invalid_role(self, mock_sf):
        """Update user role rejects invalid role value."""
        session = _mock_session()
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/admin/users/target-1/role",
            json={"role": "invalid_role"},
        )

        assert resp.status_code == 400

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_user_role_user_not_found(self, mock_sf):
        """Update user role returns 404 for nonexistent user."""
        session = _mock_session(user_model_results=None)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/admin/users/nonexistent/role",
            json={"role": "user"},
        )

        assert resp.status_code == 404

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_prevent_demoting_last_super_admin(self, mock_sf):
        """Cannot demote the last active super_admin."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.SUPER_ADMIN

        # Only 1 super_admin exists
        session = _mock_session(user_model_results=target_user, count_results=1)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/admin/users/target-1/role",
            json={"role": "user"},
        )

        assert resp.status_code == 400
        assert "last active super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_success(self, mock_sf):
        """Disable user succeeds for valid request."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.USER

        session = _mock_session(user_model_results=target_user, count_results=3)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_cannot_disable_self(self, mock_sf):
        """Cannot disable yourself."""
        admin_user = _make_rbac_user(user_id="admin-1")

        app = _make_app(current_user=admin_user)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/admin-1")

        assert resp.status_code == 400
        assert "Cannot disable yourself" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_not_found(self, mock_sf):
        """Disable user returns 404 for nonexistent user."""
        session = _mock_session(user_model_results=None)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/nonexistent")

        assert resp.status_code == 404

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_last_super_admin_blocked(self, mock_sf):
        """Cannot disable the last active super_admin."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.SUPER_ADMIN

        session = _mock_session(user_model_results=target_user, count_results=1)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1")

        assert resp.status_code == 400
        assert "last active super_admin" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Department management endpoints
# ---------------------------------------------------------------------------


class TestAdminDepartmentManagement:
    """Tests for department management endpoints."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_success(self, mock_sf):
        """List departments returns paginated results."""
        dept = MagicMock()
        dept.id = "dept-1"
        dept.name = "Engineering"
        dept.description = "Engineering team"
        dept.created_at = None

        session = _mock_session(dept_model_results=[dept], count_results=1)
        # Also mock the member count query
        session.execute = AsyncMock(side_effect=lambda stmt: _mock_dept_execute(stmt, [dept], 1))
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/departments")

        assert resp.status_code == 200
        data = resp.json()
        assert "departments" in data
        assert "total" in data

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_success(self, mock_sf):
        """Create department succeeds with valid name."""
        session = _mock_session()
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.post(
            "/api/admin/departments",
            json={"name": "Engineering", "description": "Eng team"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Engineering"
        assert "id" in data

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_empty_name(self, mock_sf):
        """Create department rejects empty name."""
        session = _mock_session()
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.post(
            "/api/admin/departments",
            json={"name": "   ", "description": "test"},
        )

        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_success(self, mock_sf):
        """Update department succeeds."""
        dept = MagicMock()
        dept.id = "dept-1"
        dept.name = "Old Name"
        dept.description = "Old desc"

        # Use a call counter to distinguish dept lookup vs duplicate check
        call_count = {"n": 0}

        async def _execute_update(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # First call: find dept by id
                result.scalar_one_or_none = MagicMock(return_value=dept)
            else:
                # Second call: duplicate name check — no duplicate
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute_update)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/admin/departments/dept-1",
            json={"name": "New Name"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_not_found(self, mock_sf):
        """Update department returns 404 for nonexistent department."""
        session = _mock_session(dept_model_results=None)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/admin/departments/nonexistent",
            json={"name": "New Name"},
        )

        assert resp.status_code == 404

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_success(self, mock_sf):
        """Delete department succeeds when no active members."""
        dept = MagicMock()
        dept.id = "dept-1"

        session = _mock_session(dept_model_results=dept, count_results=0)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/departments/dept-1")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_with_members_blocked(self, mock_sf):
        """Cannot delete department with active members."""
        dept = MagicMock()
        dept.id = "dept-1"

        session = _mock_session(dept_model_results=dept, count_results=3)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/departments/dept-1")

        assert resp.status_code == 400
        assert "members" in resp.json()["detail"].lower()


def _mock_dept_execute(stmt, departments, total_count):
    """Helper for department list queries with member counts."""
    result = MagicMock()
    stmt_str = str(stmt)

    if "count" in stmt_str.lower() and "group_by" not in stmt_str.lower():
        result.scalar = MagicMock(return_value=total_count)
    elif "group_by" in stmt_str.lower():
        result.all = MagicMock(return_value=[])
    else:
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=departments)))
    return result


# ---------------------------------------------------------------------------
# department_admin permission tests
# ---------------------------------------------------------------------------


class TestDepartmentAdminPermissions:
    """Tests for department_admin scoped user management."""

    def _dept_admin(self, user_id="dept-admin-1", dept_id="dept-1"):
        return _make_rbac_user(user_id=user_id, role="department_admin", department_id=dept_id)

    def _user_in_dept(self, user_id="user-1", dept_id="dept-1", role="user"):
        u = MagicMock()
        u.id = user_id
        u.role = role
        u.department_id = dept_id
        u.disabled = False
        u.username = f"user-{user_id}"
        u.created_at = None
        u.last_login = None
        u.department = None
        return u

    # --- list_users ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_own_department(self, mock_sf):
        """department_admin sees only own department users."""
        admin = self._dept_admin()
        u1 = self._user_in_dept("u1")
        u2 = self._user_in_dept("u2")

        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=2)
            elif "users_ext" in stmt_str:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[u1, u2])))
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.get("/api/admin/users")

        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_no_department(self, mock_sf):
        """department_admin without department_id sees empty list."""
        admin = _make_rbac_user(user_id="dept-admin-no-dept", role="department_admin", department_id=None)

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.get("/api/admin/users")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["users"] == []

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_ignores_department_id_param(self, mock_sf):
        """department_admin's department_id param is overridden."""
        admin = self._dept_admin(dept_id="dept-A")
        u1 = self._user_in_dept("u1", dept_id="dept-A")

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=1)
            elif "users_ext" in stmt_str:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[u1])))
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.get("/api/admin/users?department_id=dept-B")

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_role_super_admin_returns_empty(self, mock_sf):
        """department_admin filtering by role=super_admin returns empty."""
        admin = self._dept_admin()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=0)
            elif "users_ext" in stmt_str:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.get("/api/admin/users?role=super_admin")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    # --- update_user_role ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_own_department_user(self, mock_sf):
        """department_admin can change role of own department user."""
        admin = self._dept_admin()
        target = self._user_in_dept("target-1", dept_id="dept-1", role="user")

        session = _mock_session(user_model_results=target, count_results=3)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/target-1/role", json={"role": "viewer"})

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_cannot_change_self(self, mock_sf):
        """department_admin cannot change own role."""
        admin = self._dept_admin(user_id="self-admin")

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/self-admin/role", json={"role": "user"})

        assert resp.status_code == 400
        assert "Cannot change your own role" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_cannot_modify_super_admin(self, mock_sf):
        """department_admin cannot modify super_admin."""
        admin = self._dept_admin()
        target = self._user_in_dept("sa-1", dept_id="dept-1", role="super_admin")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/sa-1/role", json={"role": "user"})

        assert resp.status_code == 403
        assert "super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_cannot_modify_other_dept_admin(self, mock_sf):
        """department_admin cannot modify another department_admin."""
        admin = self._dept_admin()
        target = self._user_in_dept("other-admin", dept_id="dept-1", role="department_admin")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/other-admin/role", json={"role": "user"})

        assert resp.status_code == 403
        assert "department_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_cannot_promote_to_super_admin(self, mock_sf):
        """department_admin cannot promote to super_admin."""
        admin = self._dept_admin()
        target = self._user_in_dept("target-1", dept_id="dept-1", role="user")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/target-1/role", json={"role": "super_admin"})

        assert resp.status_code == 403
        assert "super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_cannot_modify_cross_department(self, mock_sf):
        """department_admin cannot modify user in different department."""
        admin = self._dept_admin(dept_id="dept-A")
        target = self._user_in_dept("target-1", dept_id="dept-B", role="user")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/target-1/role", json={"role": "viewer"})

        assert resp.status_code == 403
        assert "department" in resp.json()["detail"].lower()

    # --- disable_user ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_own_department_user(self, mock_sf):
        """department_admin can disable user in own department."""
        admin = self._dept_admin()
        target = self._user_in_dept("target-1", dept_id="dept-1", role="user")

        session = _mock_session(user_model_results=target, count_results=3)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_cannot_disable_super_admin(self, mock_sf):
        """department_admin cannot disable super_admin."""
        admin = self._dept_admin()
        target = self._user_in_dept("sa-1", dept_id="dept-1", role="super_admin")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/sa-1")

        assert resp.status_code == 403
        assert "super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_cannot_disable_other_dept_admin(self, mock_sf):
        """department_admin cannot disable another department_admin."""
        admin = self._dept_admin()
        target = self._user_in_dept("other-admin", dept_id="dept-1", role="department_admin")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/other-admin")

        assert resp.status_code == 403
        assert "department_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_cannot_disable_cross_department(self, mock_sf):
        """department_admin cannot disable user in different department."""
        admin = self._dept_admin(dept_id="dept-A")
        target = self._user_in_dept("target-1", dept_id="dept-B", role="user")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1")

        assert resp.status_code == 403
        assert "department" in resp.json()["detail"].lower()
