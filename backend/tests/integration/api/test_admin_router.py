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

import asyncio
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
    _count_call_index = [0]

    # Configure execute to return different results based on the statement
    async def _execute(stmt):
        stmt_str = str(stmt)
        result = MagicMock()

        # Count queries — return sequential values if a list is provided
        # Must check before resource_metadata to catch resource_metadata count queries
        if "count" in stmt_str.lower():
            if isinstance(count_results, list):
                val = count_results[_count_call_index[0] % len(count_results)]
                _count_call_index[0] += 1
            else:
                val = count_results if count_results is not None else 0
            result.scalar = MagicMock(return_value=val)
            return result

        # Resource metadata group query
        if "resource_metadata" in stmt_str:
            result.all = MagicMock(return_value=resource_type_counts or [])
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

    def test_create_user_writes_auth_user_role_as_user_and_rbac_role(self, tmp_path):
        """Admin-created super_admin stores permission only in users_ext."""
        from ideer.persistence.engine import close_engine, get_session_factory, init_engine
        from ideer.persistence.models.user import UserModel
        from ideer.persistence.user.model import UserRow

        asyncio.run(init_engine("sqlite", url=f"sqlite+aiosqlite:///{tmp_path}/admin_create.db", sqlite_dir=str(tmp_path)))
        try:
            app = _make_app()
            client = TestClient(app)
            resp = client.post(
                "/api/admin/users",
                json={
                    "email": "new-super@example.com",
                    "password": "Str0ng!Pass99",
                    "username": "new-super",
                    "role": "super_admin",
                },
            )

            assert resp.status_code == 201
            user_id = resp.json()["id"]

            async def _fetch_roles():
                sf = get_session_factory()
                assert sf is not None
                async with sf() as session:
                    auth_row = await session.get(UserRow, user_id)
                    rbac_user = await session.get(UserModel, user_id)
                return auth_row.system_role, rbac_user.role

            auth_role, rbac_role = asyncio.run(_fetch_roles())
            assert auth_role == "user"
            assert rbac_role == "super_admin"
        finally:
            asyncio.run(close_engine())

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
        """PUT /role persists a legal role without changing disabled status."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.USER
        target_user.disabled = False

        session = _mock_session(user_model_results=target_user)
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
        assert resp.json()["new_role"] == UserRole.DEPARTMENT_ADMIN
        assert resp.json()["role"] == UserRole.DEPARTMENT_ADMIN
        assert resp.json()["disabled"] is False
        assert target_user.role == UserRole.DEPARTMENT_ADMIN
        assert target_user.disabled is False

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_toggle_user_disabled_toggle(self, mock_sf):
        """Toggle user disabled status works."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.USER
        target_user.disabled = False

        session = _mock_session(user_model_results=target_user, count_results=[0])
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.patch("/api/admin/users/target-1/status")

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["disabled"] is True

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
    def test_update_user_role_cannot_demote_last_super_admin(self, mock_sf):
        """PUT /role preserves the last active super_admin."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.SUPER_ADMIN
        target_user.disabled = False

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
        assert target_user.role == UserRole.SUPER_ADMIN

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_user_role_can_demote_super_admin_when_another_is_active(self, mock_sf):
        """PUT /role permits a demotion when another active super_admin remains."""
        target_user = _make_rbac_user(user_id="target-1", role=UserRole.SUPER_ADMIN)
        session = _mock_session(user_model_results=target_user, count_results=2)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 200
        assert resp.json()["new_role"] == UserRole.USER
        assert target_user.role == UserRole.USER

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_toggle_user_status_success(self, mock_sf):
        """PATCH /status is the endpoint that changes disabled status."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.USER
        target_user.disabled = False

        session = _mock_session(user_model_results=target_user, count_results=[0])
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.patch("/api/admin/users/target-1/status")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_toggle_user_status_can_toggle_self(self, mock_sf):
        """Toggling yourself succeeds (no self-check in endpoint)."""
        admin_user = _make_rbac_user(user_id="admin-1")
        admin_user.disabled = False

        session = _mock_session(user_model_results=admin_user, count_results=3)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin_user)
        client = TestClient(app)
        resp = client.patch("/api/admin/users/admin-1/status")

        assert resp.status_code == 200

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_toggle_user_status_not_found(self, mock_sf):
        """PATCH /status returns 404 for nonexistent user."""
        session = _mock_session(user_model_results=None)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.patch("/api/admin/users/nonexistent/status")

        assert resp.status_code == 404

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_last_super_admin_blocked(self, mock_sf):
        """Cannot disable the last active super_admin."""
        target_user = MagicMock()
        target_user.id = "target-1"
        target_user.role = UserRole.SUPER_ADMIN
        target_user.disabled = False

        session = _mock_session(user_model_results=target_user, count_results=1)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.patch("/api/admin/users/target-1/status")

        assert resp.status_code == 400
        assert "last active super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_department_admin_can_keep_own_department_regular_user(self, mock_sf):
        """Department admins may only write the regular role inside their department."""
        target_user = _make_rbac_user(user_id="target-1", role=UserRole.USER, department_id="dept-1")
        session = _mock_session(user_model_results=target_user)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(_make_rbac_user(role=UserRole.DEPARTMENT_ADMIN, department_id="dept-1"))
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 200
        assert resp.json()["role"] == UserRole.USER
        assert target_user.disabled is False

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_department_admin_cannot_assign_privileged_role(self, mock_sf):
        """Department admins cannot promote a regular user."""
        target_user = _make_rbac_user(user_id="target-1", role=UserRole.USER, department_id="dept-1")
        session = _mock_session(user_model_results=target_user)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(_make_rbac_user(role=UserRole.DEPARTMENT_ADMIN, department_id="dept-1"))
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "department_admin"})

        assert resp.status_code == 403
        assert target_user.role == UserRole.USER

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_department_admin_cannot_change_viewer_role(self, mock_sf):
        """Department admins cannot change a viewer, even to the regular role."""
        target_user = _make_rbac_user(user_id="target-1", role=UserRole.VIEWER, department_id="dept-1")
        session = _mock_session(user_model_results=target_user)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(_make_rbac_user(role=UserRole.DEPARTMENT_ADMIN, department_id="dept-1"))
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 403
        assert target_user.role == UserRole.VIEWER

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_department_admin_cannot_change_cross_department_user(self, mock_sf):
        """Department admins cannot update users outside their department."""
        target_user = _make_rbac_user(user_id="target-1", role=UserRole.USER, department_id="dept-2")
        session = _mock_session(user_model_results=target_user)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(_make_rbac_user(role=UserRole.DEPARTMENT_ADMIN, department_id="dept-1"))
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 403
        assert target_user.role == UserRole.USER

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_department_admin_cannot_change_user_without_department(self, mock_sf):
        """Department admins cannot update unassigned users."""
        target_user = _make_rbac_user(user_id="target-1", role=UserRole.USER, department_id=None)
        session = _mock_session(user_model_results=target_user)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(_make_rbac_user(role=UserRole.DEPARTMENT_ADMIN, department_id="dept-1"))
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 403
        assert target_user.role == UserRole.USER

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_department_admin_without_department_cannot_change_user(self, mock_sf):
        """An unassigned department admin has no writable user scope."""
        target_user = _make_rbac_user(user_id="target-1", role=UserRole.USER, department_id="dept-1")
        session = _mock_session(user_model_results=target_user)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(_make_rbac_user(role=UserRole.DEPARTMENT_ADMIN, department_id=None))
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 403
        assert target_user.role == UserRole.USER


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
        """department_admin without a department retains global read access."""
        admin = _make_rbac_user(user_id="dept-admin-no-dept", role="department_admin", department_id=None)
        user = self._user_in_dept("global-user", dept_id="other-department")

        async def _execute(stmt):
            result = MagicMock()
            if "count" in str(stmt).lower():
                result.scalar.return_value = 1
            else:
                result.scalars.return_value.all.return_value = [user]
            return result

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf = MagicMock()
        sf.return_value.__aenter__ = AsyncMock(return_value=session)
        sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.get("/api/admin/users")

        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["users"][0]["id"] == "global-user"

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_applies_department_id_param(self, mock_sf):
        """department_admin global reads still honor an explicit department filter."""
        admin = self._dept_admin(dept_id="dept-A")
        u1 = self._user_in_dept("u1", dept_id="dept-B")
        queried_department_ids = []

        async def _execute(stmt):
            result = MagicMock()
            queried_department_ids.extend(value for value in stmt.compile().params.values() if value == "dept-B")
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
        assert resp.json()["users"][0]["department_id"] == "dept-B"
        assert queried_department_ids == ["dept-B", "dept-B"]

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
        """department_admin can retain the regular role of an own-department user."""
        admin = self._dept_admin()
        target = self._user_in_dept("target-1", dept_id="dept-1", role="user")

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["role"] == UserRole.USER

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_cannot_assign_viewer(self, mock_sf):
        """department_admin cannot assign a non-regular role."""
        admin = self._dept_admin(user_id="self-admin")
        target = self._user_in_dept("other-user", dept_id="dept-1", role="user")
        target.disabled = False

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/other-user/role", json={"role": "viewer"})

        assert resp.status_code == 403

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
        """department_admin cannot promote a regular user to super_admin."""
        admin = self._dept_admin()
        target = self._user_in_dept("target-1", dept_id="dept-1", role="user")
        target.disabled = False

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.put("/api/admin/users/target-1/role", json={"role": "super_admin"})

        assert resp.status_code == 403

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
        resp = client.put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 403
        assert "department" in resp.json()["detail"].lower()

    # --- disable_user ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_own_department_user(self, mock_sf):
        """department_admin can toggle user in own department."""
        admin = self._dept_admin()
        target = self._user_in_dept("target-1", dept_id="dept-1", role="user")
        target.disabled = False

        session = _mock_session(user_model_results=target)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.patch("/api/admin/users/target-1/status")

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
        resp = client.patch("/api/admin/users/sa-1/status")

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
        resp = client.patch("/api/admin/users/other-admin/status")

        assert resp.status_code == 403
        assert "department_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_cannot_disable_cross_department(self, mock_sf):
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
        resp = client.patch("/api/admin/users/target-1/status")

        assert resp.status_code == 403
        assert "department" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# User deletion endpoint
# ---------------------------------------------------------------------------


class TestDeleteUser:
    """Tests for DELETE /api/admin/users/{user_id}."""

    # -- Parameter validation (no DB needed) ---------------------------------

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_missing_strategy(self, mock_sf):
        """Returns 422 when resource_strategy is missing (FastAPI validation)."""
        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1")
        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_invalid_strategy(self, mock_sf):
        """Returns 400 for invalid resource_strategy value."""
        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1?resource_strategy=invalid")
        assert resp.status_code == 400
        assert "Invalid resource_strategy" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_transfer_missing_target(self, mock_sf):
        """Returns 400 when transfer strategy without target_user_id."""
        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1?resource_strategy=transfer")
        assert resp.status_code == 400
        assert "target_user_id is required" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_no_database(self, mock_sf):
        """Returns 500 when DB not initialized."""
        mock_sf.return_value = None
        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1?resource_strategy=delete")
        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    # -- Permission checks ---------------------------------------------------

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_requires_super_admin(self, mock_sf):
        """department_admin cannot delete users."""
        dept_admin = _make_rbac_user(role="department_admin")
        app = _make_app(current_user=dept_admin)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1?resource_strategy=delete")
        assert resp.status_code == 403

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_require_super_admin_user(self, mock_sf):
        """Regular user cannot delete users."""
        regular_user = _make_rbac_user(role="user")
        app = _make_app(current_user=regular_user)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/target-1?resource_strategy=delete")
        assert resp.status_code == 403

    # -- Service error handling ----------------------------------------------

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_not_found(self, mock_sf):
        """Nonexistent user returns 400."""
        session = _mock_session(user_model_results=None, count_results=0)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app()
        client = TestClient(app)
        resp = client.delete("/api/admin/users/nonexistent?resource_strategy=delete")
        assert resp.status_code == 400

    # -- Real SQLite integration tests ---------------------------------------

    def _setup_user_db(self, tmp_path):
        """Initialize a real SQLite engine and insert test user data.

        Returns (user_id, target_user_id) for use in tests.
        """
        from ideer.persistence.engine import get_session_factory, init_engine
        from ideer.persistence.models.user import UserModel, UserRole
        from ideer.persistence.user.model import UserRow

        db_url = f"sqlite+aiosqlite:///{tmp_path}/test_delete_user.db"

        async def _init():
            await init_engine("sqlite", url=db_url, sqlite_dir=str(tmp_path))

        asyncio.run(_init())

        user_id = "user-to-delete"
        target_user_id = "target-user"

        async def _insert():
            sf = get_session_factory()
            assert sf is not None
            async with sf() as session:
                session.add(UserRow(id=user_id, email="delete@test.com", system_role="user"))
                session.add(UserModel(id=user_id, username="delete-me", role=UserRole.USER, disabled=True))
                session.add(UserRow(id=target_user_id, email="target@test.com", system_role="user"))
                session.add(UserModel(id=target_user_id, username="target", role=UserRole.USER, disabled=False))
                await session.commit()

        asyncio.run(_insert())
        return user_id, target_user_id

    def _teardown_db(self):
        """Close the engine and clean up."""
        from ideer.persistence.engine import close_engine

        try:
            asyncio.run(close_engine())
        except Exception:
            pass

    def _make_admin_app(self):
        admin = _make_rbac_user(user_id="admin-1", role="super_admin")
        return _make_app(current_user=admin)

    def test_delete_user_soft_delete_integration(self, tmp_path, monkeypatch):
        """soft_delete strategy: metadata soft-deleted, user rows gone."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("IDEER_HOME", str(tmp_path))

        user_id, _ = self._setup_user_db(tmp_path)

        try:
            client = TestClient(self._make_admin_app())
            resp = client.delete(f"/api/admin/users/{user_id}?resource_strategy=soft_delete")

            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["user_id"] == user_id

            async def _verify():
                from ideer.persistence.engine import get_session_factory
                from ideer.persistence.models.user import UserModel
                from ideer.persistence.user.model import UserRow

                sf = get_session_factory()
                assert sf is not None
                async with sf() as session:
                    rbac = await session.get(UserModel, user_id)
                    auth = await session.get(UserRow, user_id)
                return rbac, auth

            rbac, auth = asyncio.run(_verify())
            assert rbac is None, "RBAC user row should be deleted"
            assert auth is None, "Auth user row should be deleted"
        finally:
            self._teardown_db()

    def test_delete_user_delete_integration(self, tmp_path, monkeypatch):
        """delete strategy: user rows gone, disk cleanup performed."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("IDEER_HOME", str(tmp_path))

        user_id, _ = self._setup_user_db(tmp_path)

        try:
            client = TestClient(self._make_admin_app())
            resp = client.delete(f"/api/admin/users/{user_id}?resource_strategy=delete")

            assert resp.status_code == 200
            assert resp.json()["success"] is True

            async def _verify():
                from ideer.persistence.engine import get_session_factory
                from ideer.persistence.models.user import UserModel
                from ideer.persistence.user.model import UserRow

                sf = get_session_factory()
                assert sf is not None
                async with sf() as session:
                    rbac = await session.get(UserModel, user_id)
                    auth = await session.get(UserRow, user_id)
                return rbac, auth

            rbac, auth = asyncio.run(_verify())
            assert rbac is None
            assert auth is None
        finally:
            self._teardown_db()

    def test_delete_user_transfer_integration(self, tmp_path, monkeypatch):
        """transfer strategy: resources reassigned, user rows gone."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("IDEER_HOME", str(tmp_path))

        user_id, target_id = self._setup_user_db(tmp_path)

        try:
            client = TestClient(self._make_admin_app())
            resp = client.delete(
                f"/api/admin/users/{user_id}?resource_strategy=transfer&target_user_id={target_id}",
            )

            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            self._teardown_db()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_user_self_delete_blocked(self, mock_sf):
        """Cannot delete your own account."""
        admin = _make_rbac_user(user_id="admin-1", role="super_admin")

        session = _mock_session(user_model_results=admin, count_results=2)
        sf_mock = MagicMock()
        sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = sf_mock

        app = _make_app(current_user=admin)
        client = TestClient(app)
        resp = client.delete("/api/admin/users/admin-1?resource_strategy=delete")
        assert resp.status_code == 400
        assert "Cannot delete your own account" in resp.json()["detail"]
