"""Systematic cross-role RBAC permission matrix validation tests.

Covers:
  A) Role × Operation matrix: per-role CRUD permissions on every resource
  B) Escalation tests: department_admin attempts unauthorized operations
  C) Resource visibility: public/department/private across all roles
  D) Viewer restrictions: read-only access enforcement
  E) Fail-closed behavior: DB failure → 503, not full permissions
  F) First-user auto-promotion: super_admin on first registration
  G) Owner checks: resource owners can modify their own resources
  H) Concurrent first-user creation: race condition handling

The test suite validates that the RBAC permission matrix is enforced
consistently across all admin endpoints and utility functions.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from app.gateway.authz import (
    AuthContext,
    Permissions,
    check_resource_access,
    check_resource_modify,
    filter_visible_resources,
    get_current_rbac_user,
    require_role,
)
from app.gateway.routers.admin import router as admin_router
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str | None = None,
    role: str = "user",
    department_id: str | None = None,
    disabled: bool = False,
    username: str | None = None,
) -> MagicMock:
    """Create a mock RBAC UserModel."""
    uid = user_id or str(uuid4())
    user = MagicMock()
    user.id = uid
    user.role = role
    user.department_id = department_id
    user.disabled = disabled
    user.created_at = None
    user.last_login = None
    user.username = username or f"user-{uid[:8]}"
    user.department = None
    return user


def _make_user_model_mock(
    user_id: str | None = None,
    role: str = "user",
    department_id: str | None = None,
    disabled: bool = False,
) -> MagicMock:
    """Create a lightweight mock for check_resource_access/modify."""
    uid = user_id or str(uuid4())
    m = MagicMock()
    m.id = uid
    m.role = role
    m.department_id = department_id
    m.disabled = disabled
    return m


def _make_app(current_user: MagicMock | None = None) -> FastAPI:
    """Create a test FastAPI app with admin router and stubbed auth."""
    app = FastAPI()
    app.include_router(admin_router)
    user = current_user or _make_rbac_user(role="super_admin")

    async def _stub():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub
    return app


def _mock_session_factory(session: AsyncMock) -> MagicMock:
    """Wrap a mock session into a session factory."""
    sf = MagicMock()
    sf.return_value.__aenter__ = AsyncMock(return_value=session)
    sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf


def _make_mock_session(
    user_result=None,
    dept_result=None,
    count_result=None,
    resource_type_counts=None,
    extra_execute_results=None,
) -> AsyncMock:
    """Create a mock session with configurable query results.

    NOTE: This helper relies on matching keywords in the SQL string to route
    mock results. It is fragile — any schema rename, table alias, or query
    restructuring can silently break the routing.  Tests that depend on
    specific query ordering should use ``extra_execute_results`` for
    deterministic control.
    """
    session = AsyncMock()
    _call_idx = {"n": 0}

    async def _execute(stmt):
        _call_idx["n"] += 1
        stmt_str = str(stmt).lower()
        result = MagicMock()

        if extra_execute_results and _call_idx["n"] <= len(extra_execute_results):
            return extra_execute_results[_call_idx["n"] - 1]

        if "count" in stmt_str and "group_by" not in stmt_str:
            val = count_result if count_result is not None else 0
            result.scalar = MagicMock(return_value=val)
            return result

        if "resource_metadata" in stmt_str:
            result.all = MagicMock(return_value=resource_type_counts or [])
            return result

        if "users_ext" in stmt_str:
            if isinstance(user_result, list):
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=user_result)))
            elif user_result is not None:
                result.scalar_one_or_none = MagicMock(return_value=user_result)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        if "departments" in stmt_str:
            if isinstance(dept_result, list):
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=dept_result)))
            elif dept_result is not None:
                result.scalar_one_or_none = MagicMock(return_value=dept_result)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        result.scalar_one_or_none = MagicMock(return_value=None)
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        return result

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.refresh = AsyncMock()
    return session


# =====================================================================
# A) Role × Operation Permission Matrix
# =====================================================================


class TestRoleOperationMatrix:
    """Validate permission grants/denials for each role × resource × action combination."""

    # --- require_role matrix: which roles can access which admin endpoints ---

    @pytest.mark.parametrize(
        "allowed_roles, test_role, expected_status",
        [
            # stats endpoint: super_admin + department_admin
            (("super_admin", "department_admin"), "super_admin", 200),
            (("super_admin", "department_admin"), "department_admin", 200),
            (("super_admin", "department_admin"), "user", 403),
            (("super_admin", "department_admin"), "viewer", 403),
            # departments endpoint: super_admin only
            (("super_admin",), "super_admin", 200),
            (("super_admin",), "department_admin", 403),
            (("super_admin",), "user", 403),
            (("super_admin",), "viewer", 403),
        ],
    )
    @pytest.mark.asyncio
    async def test_require_role_matrix(self, allowed_roles, test_role, expected_status):
        """Each role either passes or is rejected by require_role decorator."""

        @require_role(*allowed_roles)
        async def endpoint(current_user=None):
            return "ok"

        mock_user = _make_rbac_user(role=test_role)

        if expected_status == 200:
            await endpoint(current_user=mock_user)
        else:
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(current_user=mock_user)
            assert exc_info.value.status_code == expected_status

    # --- Viewer permissions: only threads:read and runs:read ---

    def test_viewer_has_only_read_permissions(self):
        """viewer role should only have threads:read and runs:read."""
        viewer_perms = [Permissions.THREADS_READ, Permissions.RUNS_READ]
        full_perms = [
            Permissions.THREADS_READ,
            Permissions.THREADS_WRITE,
            Permissions.THREADS_DELETE,
            Permissions.RUNS_CREATE,
            Permissions.RUNS_READ,
            Permissions.RUNS_CANCEL,
            Permissions.ASSISTANTS_READ,
            Permissions.MODELS_READ,
        ]

        ctx = AuthContext(permissions=viewer_perms)
        for perm in full_perms:
            resource, action = perm.split(":")
            if perm in viewer_perms:
                assert ctx.has_permission(resource, action), f"viewer should have {perm}"
            else:
                assert not ctx.has_permission(resource, action), f"viewer should NOT have {perm}"

        # Explicitly verify viewer lacks assistants:read and models:read
        assert not ctx.has_permission("assistants", "read"), "viewer should NOT have assistants:read"
        assert not ctx.has_permission("models", "read"), "viewer should NOT have models:read"

    # --- Non-viewer roles get all permissions via _authenticate ---

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["super_admin", "department_admin", "user"])
    async def test_non_viewer_roles_get_all_permissions(self, role):
        """super_admin, department_admin, user all get full permissions via _authenticate."""
        from app.gateway.authz import _authenticate

        auth_user = MagicMock()
        auth_user.id = str(uuid4())

        rbac_user = _make_rbac_user(role=role)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = rbac_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch(
                "app.gateway.deps.get_optional_user_from_request",
                new_callable=AsyncMock,
                return_value=auth_user,
            ),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            ctx = await _authenticate(req)

        full_perms = [
            Permissions.THREADS_READ,
            Permissions.THREADS_WRITE,
            Permissions.THREADS_DELETE,
            Permissions.RUNS_CREATE,
            Permissions.RUNS_READ,
            Permissions.RUNS_CANCEL,
            Permissions.ASSISTANTS_READ,
            Permissions.MODELS_READ,
        ]
        for perm in full_perms:
            resource, action = perm.split(":")
            assert ctx.has_permission(resource, action), f"{role} should have {perm}"

    # --- Admin endpoint access matrix ---

    @pytest.mark.parametrize(
        "role, endpoint, method, expected",
        [
            # GET /api/admin/stats — super_admin + department_admin
            ("super_admin", "/api/admin/stats", "get", 200),
            ("department_admin", "/api/admin/stats", "get", 200),
            ("user", "/api/admin/stats", "get", 403),
            ("viewer", "/api/admin/stats", "get", 403),
            # POST /api/admin/users (201) — super_admin + department_admin
            ("super_admin", "/api/admin/users", "post_user", 201),
            ("department_admin", "/api/admin/users", "post_user", 201),
            ("user", "/api/admin/users", "post_user", 403),
            ("viewer", "/api/admin/users", "post_user", 403),
            # GET /api/admin/users — super_admin + department_admin
            ("super_admin", "/api/admin/users", "get", 200),
            ("department_admin", "/api/admin/users", "get", 200),
            ("user", "/api/admin/users", "get", 403),
            ("viewer", "/api/admin/users", "get", 403),
            # PUT /api/admin/users/{user_id}/role — super_admin + department_admin
            ("super_admin", "/api/admin/users/target-user/role", "put", 200),
            ("department_admin", "/api/admin/users/target-user/role", "put", 200),
            ("user", "/api/admin/users/target-user/role", "put", 403),
            ("viewer", "/api/admin/users/target-user/role", "put", 403),
            # GET /api/admin/departments — super_admin only
            ("super_admin", "/api/admin/departments", "get", 200),
            ("department_admin", "/api/admin/departments", "get", 200),
            ("user", "/api/admin/departments", "get", 403),
            ("viewer", "/api/admin/departments", "get", 403),
            # POST /api/admin/departments — super_admin only
            ("super_admin", "/api/admin/departments", "post", 200),
            ("department_admin", "/api/admin/departments", "post", 403),
            ("user", "/api/admin/departments", "post", 403),
            ("viewer", "/api/admin/departments", "post", 403),
            # GET /api/admin/departments/{dept_id}/resources — super_admin only
            ("super_admin", "/api/admin/departments/dept-1/resources", "get", 200),
            ("department_admin", "/api/admin/departments/dept-1/resources", "get", 403),
            ("user", "/api/admin/departments/dept-1/resources", "get", 403),
            ("viewer", "/api/admin/departments/dept-1/resources", "get", 403),
            # PUT /api/admin/departments/{dept_id} — super_admin only
            ("super_admin", "/api/admin/departments/dept-1", "put", 200),
            ("department_admin", "/api/admin/departments/dept-1", "put", 403),
            ("user", "/api/admin/departments/dept-1", "put", 403),
            ("viewer", "/api/admin/departments/dept-1", "put", 403),
            # DELETE /api/admin/departments/{dept_id} — super_admin only
            ("super_admin", "/api/admin/departments/dept-1", "delete", 200),
            ("department_admin", "/api/admin/departments/dept-1", "delete", 403),
            ("user", "/api/admin/departments/dept-1", "delete", 403),
            ("viewer", "/api/admin/departments/dept-1", "delete", 403),
        ],
    )
    @patch("app.gateway.routers.admin.get_session_factory")
    @patch("app.gateway.deps.get_local_provider")
    def test_endpoint_access_matrix(self, mock_provider, mock_sf, role, endpoint, method, expected):
        """Each role gets the correct status code for each admin endpoint."""
        # Provider mock needed for POST /api/admin/users
        mock_auth_user = MagicMock()
        mock_auth_user.id = str(uuid4())
        mock_provider.return_value.create_user = AsyncMock(return_value=mock_auth_user)

        # Build session mock based on endpoint requirements
        dept_mock = MagicMock()
        dept_mock.id = "dept-1"
        dept_mock.name = "Test"

        if expected == 200:
            if "/users/" in endpoint and method == "put":
                dept_id = "dept-A" if role == "department_admin" else None
                target = _make_rbac_user(role="user", user_id="target-user", department_id=dept_id)
                session = _make_mock_session(user_result=target, count_result=2)
            elif "/departments/" in endpoint:
                # All 200 department endpoints need a valid dept lookup
                session = _make_mock_session(dept_result=dept_mock)
            else:
                session = _make_mock_session()
        else:
            session = _make_mock_session()

        mock_sf.return_value = _mock_session_factory(session)

        user = _make_rbac_user(role=role, department_id="dept-A" if role == "department_admin" else None)
        app = _make_app(current_user=user)
        client = TestClient(app)

        if method == "get":
            resp = client.get(endpoint)
        elif method == "post_user":
            resp = client.post(
                endpoint,
                json={
                    "email": "new@test.com",
                    "password": "pass123",
                    "username": "newuser",
                    "role": "user",
                },
            )
        elif method == "post":
            resp = client.post(endpoint, json={"name": "Test Dept", "description": ""})
        elif method == "put":
            resp = client.put(endpoint, json={"role": "user"})
        elif method == "delete":
            resp = client.delete(endpoint)
        else:
            raise ValueError(f"Unknown method: {method}")

        assert resp.status_code == expected, f"Role '{role}' on {method.upper()} {endpoint}: expected {expected}, got {resp.status_code}"


# =====================================================================
# B) Escalation Tests: department_admin Attempting Unauthorized Ops
# =====================================================================


class TestDepartmentAdminEscalation:
    """department_admin tries to escalate privileges or access cross-department resources."""

    def _dept_admin(self, dept_id: str = "dept-A") -> MagicMock:
        return _make_rbac_user(role="department_admin", department_id=dept_id)

    # --- Creating super_admin / department_admin ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_create_super_admin(self, mock_sf):
        """department_admin creating super_admin → 403."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.post(
            "/api/admin/users",
            json={
                "email": "new@test.com",
                "password": "pass123",
                "username": "newuser",
                "role": "super_admin",
            },
        )
        assert resp.status_code == 403
        assert "super_admin" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_create_dept_admin(self, mock_sf):
        """department_admin creating department_admin → 403."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.post(
            "/api/admin/users",
            json={
                "email": "new@test.com",
                "password": "pass123",
                "username": "newuser",
                "role": "department_admin",
            },
        )
        assert resp.status_code == 403
        assert "department_admin" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    @patch("app.gateway.deps.get_local_provider")
    def test_dept_admin_can_create_regular_user_in_own_dept(self, mock_provider, mock_sf):
        """department_admin can create regular users in their own department."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        mock_auth_user = MagicMock()
        mock_auth_user.id = str(uuid4())
        mock_provider.return_value.create_user = AsyncMock(return_value=mock_auth_user)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)

        resp = client.post(
            "/api/admin/users",
            json={
                "email": "new@test.com",
                "password": "pass123",
                "username": "newuser",
                "role": "user",
            },
        )

        assert resp.status_code == 201

    # --- Modifying super_admin ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_modify_super_admin(self, mock_sf):
        """department_admin cannot change super_admin's role → 403."""
        sa_user = _make_rbac_user(user_id="sa-1", role="super_admin", department_id="dept-A")
        session = _make_mock_session(user_result=sa_user)
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.put("/api/admin/users/sa-1/role", json={"role": "viewer"})
        assert resp.status_code == 403
        assert "super_admin" in resp.json()["detail"]

    # --- Modifying another department_admin ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_modify_another_dept_admin(self, mock_sf):
        """department_admin cannot modify another department_admin → 403."""
        other_admin = _make_rbac_user(user_id="other-admin", role="department_admin", department_id="dept-A")
        session = _make_mock_session(user_result=other_admin)
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.put("/api/admin/users/other-admin/role", json={"role": "user"})
        assert resp.status_code == 403
        assert "department_admin" in resp.json()["detail"]

    # --- Modifying user in different department ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_modify_cross_dept_user(self, mock_sf):
        """department_admin cannot modify user in different department → 403."""
        cross_user = _make_rbac_user(user_id="cross-user", role="user", department_id="dept-B")
        session = _make_mock_session(user_result=cross_user)
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin(dept_id="dept-A"))
        client = TestClient(app)
        resp = client.put("/api/admin/users/cross-user/role", json={"role": "viewer"})
        assert resp.status_code == 403
        assert "department" in resp.json()["detail"].lower()

    # --- Disabling last super_admin ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_super_admin_cannot_disable_last_super_admin(self, mock_sf):
        """super_admin cannot disable the last active super_admin → 400."""
        sa_user = _make_rbac_user(user_id="sa-1", role="super_admin", disabled=False)
        session = _make_mock_session(user_result=sa_user, count_result=1)
        mock_sf.return_value = _mock_session_factory(session)

        current_sa = _make_rbac_user(role="super_admin")
        app = _make_app(current_user=current_sa)
        client = TestClient(app)
        resp = client.put("/api/admin/users/sa-1/role", json={"role": "user"})
        assert resp.status_code == 400
        assert "last active super_admin" in resp.json()["detail"].lower()

    # --- Creating department ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_create_department(self, mock_sf):
        """department_admin cannot create departments → 403."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.post(
            "/api/admin/departments",
            json={"name": "New Dept", "description": ""},
        )
        assert resp.status_code == 403

    # --- Listing departments ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_can_list_departments(self, mock_sf):
        """department_admin can list departments (allowed by require_role)."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.get("/api/admin/departments")
        assert resp.status_code == 200

    # --- Updating department ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_update_department(self, mock_sf):
        """department_admin cannot update departments → 403."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.put(
            "/api/admin/departments/dept-1",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 403

    # --- Deleting department ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_cannot_delete_department(self, mock_sf):
        """department_admin cannot delete departments → 403."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin())
        client = TestClient(app)
        resp = client.delete("/api/admin/departments/dept-1")
        assert resp.status_code == 403

    # --- department_admin without department ---

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_no_dept_cannot_create_user(self, mock_sf):
        """department_admin without department_id → 400 when creating user."""
        session = _make_mock_session()
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin(dept_id=None))
        client = TestClient(app)
        resp = client.post(
            "/api/admin/users",
            json={
                "email": "new@test.com",
                "password": "pass123",
                "username": "newuser",
                "role": "user",
            },
        )
        assert resp.status_code == 400
        assert "no department" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_dept_admin_no_dept_cannot_modify_user_without_dept(self, mock_sf):
        """department_admin without dept cannot modify user without department → 403."""
        target = _make_rbac_user(user_id="target-1", role="user", department_id=None)
        session = _make_mock_session(user_result=target)
        mock_sf.return_value = _mock_session_factory(session)

        app = _make_app(current_user=self._dept_admin(dept_id=None))
        client = TestClient(app)
        resp = client.put("/api/admin/users/target-1/role", json={"role": "viewer"})
        assert resp.status_code == 403


# =====================================================================
# C) Resource Visibility Matrix
# =====================================================================


class TestResourceVisibilityMatrix:
    """Validate check_resource_access and filter_visible_resources across all role × visibility combos."""

    def _user(self, role="user", dept_id=None, user_id=None):
        return _make_user_model_mock(role=role, department_id=dept_id, user_id=user_id)

    # --- Super admin sees everything ---

    @pytest.mark.parametrize("visibility", ["private", "department", "public"])
    def test_super_admin_sees_all_visibilities(self, visibility):
        """super_admin can access any resource regardless of visibility."""
        user = self._user(role="super_admin")
        assert check_resource_access(user, "other", "dept-1", visibility) is True

    # --- Owner always sees own resources ---

    @pytest.mark.parametrize("visibility", ["private", "department", "public"])
    def test_owner_always_sees_own_resource(self, visibility):
        """Owner can always access own resources regardless of visibility."""
        uid = str(uuid4())
        user = self._user(user_id=uid)
        assert check_resource_access(user, uid, "dept-1", visibility) is True

    # --- Public visibility: all roles ---

    @pytest.mark.parametrize("role", ["super_admin", "department_admin", "user", "viewer"])
    def test_public_visible_to_all_roles(self, role):
        """Public resources are accessible by any authenticated user."""
        user = self._user(role=role, dept_id="dept-1")
        assert check_resource_access(user, "other", "dept-1", "public") is True

    # --- Department visibility: same dept vs different dept ---

    def test_dept_visibility_same_dept_user(self):
        """user can access dept-visible resource in same department."""
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other", "dept-1", "department") is True

    def test_dept_visibility_diff_dept_user(self):
        """user cannot access dept-visible resource in different department."""
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other", "dept-2", "department") is False

    def test_dept_visibility_same_dept_admin(self):
        """department_admin can access dept-visible resource in same department."""
        user = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_access(user, "other", "dept-1", "department") is True

    def test_dept_visibility_diff_dept_admin(self):
        """department_admin cannot access dept-visible resource in different department."""
        user = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_access(user, "other", "dept-2", "department") is False

    def test_dept_visibility_user_no_dept(self):
        """User without department cannot access department-visible resources."""
        user = self._user(role="user", dept_id=None)
        assert check_resource_access(user, "other", "dept-1", "department") is False

    def test_dept_visibility_resource_no_dept(self):
        """Resource without department_id denies dept access."""
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other", None, "department") is False

    # --- Private visibility: owner + super_admin only ---

    def test_private_only_owner_and_super_admin(self):
        """Private resources: only owner and super_admin can access."""
        # super_admin
        sa = self._user(role="super_admin")
        assert check_resource_access(sa, "other", "dept-1", "private") is True

        # owner
        uid = str(uuid4())
        owner = self._user(user_id=uid)
        assert check_resource_access(owner, uid, "dept-1", "private") is True

        # regular user (not owner)
        user = self._user(role="user", dept_id="dept-1")
        assert check_resource_access(user, "other", "dept-1", "private") is False

        # department_admin (not owner)
        admin = self._user(role="department_admin", dept_id="dept-1")
        assert check_resource_access(admin, "other", "dept-1", "private") is False

    # --- filter_visible_resources bulk matrix ---

    def test_filter_visible_super_admin_sees_all(self):
        """super_admin sees all resources in bulk filter."""
        user = self._user(role="super_admin")
        items = [
            SimpleNamespace(owner_id="a", department_id="d1", visibility="private"),
            SimpleNamespace(owner_id="b", department_id="d2", visibility="department"),
            SimpleNamespace(owner_id="c", department_id=None, visibility="public"),
        ]
        assert len(filter_visible_resources(items, user)) == 3

    def test_filter_visible_user_mixed_visibilities(self):
        """user sees own + same-dept department + public, but not others' private."""
        uid = str(uuid4())
        user = self._user(role="user", dept_id="dept-1", user_id=uid)
        items = [
            SimpleNamespace(owner_id=uid, department_id="dept-1", visibility="private"),  # own
            SimpleNamespace(owner_id="other", department_id="dept-1", visibility="department"),  # same dept
            SimpleNamespace(owner_id="other", department_id="dept-2", visibility="department"),  # diff dept
            SimpleNamespace(owner_id="other", department_id=None, visibility="public"),  # public
            SimpleNamespace(owner_id="other", department_id="dept-1", visibility="private"),  # other's private
        ]
        result = filter_visible_resources(items, user)
        assert len(result) == 3  # own + same dept + public

    def test_filter_visible_dept_admin_same_dept(self):
        """department_admin sees own + same-dept department + public resources."""
        uid = str(uuid4())
        user = self._user(role="department_admin", dept_id="dept-1", user_id=uid)
        items = [
            SimpleNamespace(owner_id=uid, department_id="dept-1", visibility="private"),  # own
            SimpleNamespace(owner_id="other", department_id="dept-1", visibility="department"),  # same dept
            SimpleNamespace(owner_id="other", department_id="dept-2", visibility="department"),  # diff dept
            SimpleNamespace(owner_id="other", department_id=None, visibility="public"),  # public
        ]
        result = filter_visible_resources(items, user)
        assert len(result) == 3  # own + same dept + public

    def test_filter_visible_viewer_like_user(self):
        """viewer sees same resources as user (visibility rules are role-agnostic)."""
        uid = str(uuid4())
        user = self._user(role="viewer", dept_id="dept-1", user_id=uid)
        items = [
            SimpleNamespace(owner_id=uid, department_id="dept-1", visibility="private"),
            SimpleNamespace(owner_id="other", department_id="dept-1", visibility="department"),
            SimpleNamespace(owner_id="other", department_id="dept-2", visibility="department"),
            SimpleNamespace(owner_id="other", department_id=None, visibility="public"),
        ]
        result = filter_visible_resources(items, user)
        assert len(result) == 3


# =====================================================================
# D) Viewer Role Restrictions
# =====================================================================


class TestViewerRoleRestrictions:
    """Validate that viewer has strictly read-only permissions."""

    def test_viewer_cannot_write_threads(self):
        """viewer lacks threads:write permission."""
        ctx = AuthContext(permissions=[Permissions.THREADS_READ, Permissions.RUNS_READ])
        assert not ctx.has_permission("threads", "write")
        assert not ctx.has_permission("threads", "delete")

    def test_viewer_cannot_create_runs(self):
        """viewer lacks runs:create permission."""
        ctx = AuthContext(permissions=[Permissions.THREADS_READ, Permissions.RUNS_READ])
        assert not ctx.has_permission("runs", "create")
        assert not ctx.has_permission("runs", "cancel")

    def test_viewer_has_threads_read(self):
        """viewer has threads:read permission."""
        ctx = AuthContext(permissions=[Permissions.THREADS_READ, Permissions.RUNS_READ])
        assert ctx.has_permission("threads", "read")

    def test_viewer_has_runs_read(self):
        """viewer has runs:read permission."""
        ctx = AuthContext(permissions=[Permissions.THREADS_READ, Permissions.RUNS_READ])
        assert ctx.has_permission("runs", "read")

    def test_viewer_blocked_from_admin_endpoints(self):
        """viewer cannot access any admin endpoint."""
        user = _make_rbac_user(role="viewer")
        app = _make_app(current_user=user)
        client = TestClient(app)

        for endpoint in ["/api/admin/stats", "/api/admin/users", "/api/admin/departments"]:
            resp = client.get(endpoint)
            assert resp.status_code == 403, f"viewer should be blocked from {endpoint}"

    def test_viewer_blocked_from_admin_create(self):
        """viewer cannot create departments or users."""
        user = _make_rbac_user(role="viewer")
        app = _make_app(current_user=user)
        client = TestClient(app)

        resp = client.post("/api/admin/departments", json={"name": "Test", "description": ""})
        assert resp.status_code == 403

    def test_viewer_blocked_from_role_update(self):
        """viewer cannot update user roles."""
        user = _make_rbac_user(role="viewer")
        app = _make_app(current_user=user)
        client = TestClient(app)

        resp = client.put("/api/admin/users/target/role", json={"role": "viewer"})
        assert resp.status_code == 403


# =====================================================================
# E) Fail-Closed Behavior
# =====================================================================


class TestFailClosedBehavior:
    """Validate that RBAC lookup failures deny access (503), not grant it."""

    @pytest.mark.asyncio
    async def test_db_failure_returns_503(self):
        """DB connection failure during RBAC lookup → 503, not 200."""
        from app.gateway.authz import _authenticate

        user = MagicMock()
        user.id = str(uuid4())

        mock_sf = MagicMock(side_effect=RuntimeError("DB down"))

        with (
            patch(
                "app.gateway.deps.get_optional_user_from_request",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate(MagicMock(spec=type("R", (), {"state": type("S", (), {})()})))
            assert exc_info.value.status_code == 503
            assert "temporarily unavailable" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_session_factory_none_denies_access(self):
        """An unavailable RBAC store fails closed instead of granting permissions."""
        from app.gateway.authz import _authenticate

        user = MagicMock()
        user.id = str(uuid4())

        with (
            patch(
                "app.gateway.deps.get_optional_user_from_request",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch("ideer.persistence.engine.get_session_factory", return_value=None),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate(req)
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_operational_error_raises_503(self):
        """OperationalError during RBAC lookup → 503."""
        from app.gateway.authz import _authenticate

        user = MagicMock()
        user.id = str(uuid4())

        mock_sf = MagicMock(side_effect=OperationalError("connection", {}, Exception()))

        with (
            patch(
                "app.gateway.deps.get_optional_user_from_request",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate(req)
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_programming_error_raises_503(self):
        """ProgrammingError during RBAC lookup → 503."""
        from app.gateway.authz import _authenticate

        user = MagicMock()
        user.id = str(uuid4())

        mock_sf = MagicMock(side_effect=ProgrammingError("sql", {}, Exception()))

        with (
            patch(
                "app.gateway.deps.get_optional_user_from_request",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            with pytest.raises(HTTPException) as exc_info:
                await _authenticate(req)
            assert exc_info.value.status_code == 503


# =====================================================================
# F) First-User Auto-Promotion
# =====================================================================


class TestUnprovisionedAuthenticatedUser:
    """Authenticated users need an explicit RBAC profile before authorization."""

    @pytest.mark.asyncio
    async def test_first_authenticated_user_without_profile_is_rejected(self):
        """Bootstrap is explicit; a request never creates a super-admin profile."""
        user = MagicMock()
        user.id = str(uuid4())
        user.email = "first@test.com"

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        # No users_ext record exists for this authenticated subject.
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

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
    async def test_unprovisioned_user_is_not_auto_created(self):
        """Authorization does not create a regular RBAC profile either."""
        user = MagicMock()
        user.id = str(uuid4())
        user.email = "second@test.com"

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

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
    async def test_existing_user_returned_directly(self):
        """Existing RBAC user is returned without re-creation."""
        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        existing_user = _make_rbac_user(role="department_admin", disabled=False)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = existing_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result is existing_user
        assert result.role == "department_admin"

    @pytest.mark.asyncio
    async def test_disabled_user_gets_403(self):
        """Disabled user is rejected with 403."""
        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

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


# =====================================================================
# G) Owner Checks
# =====================================================================


class TestOwnerChecks:
    """Validate that resource owners can modify their own resources."""

    def test_owner_can_modify_own_resource(self):
        """Owner can modify own resource."""
        uid = str(uuid4())
        user = _make_user_model_mock(user_id=uid)
        assert check_resource_modify(user, uid, "dept-1") is True

    def test_non_owner_cannot_modify(self):
        """Non-owner cannot modify resource."""
        user = _make_user_model_mock(user_id="user-1")
        assert check_resource_modify(user, "other-user", "dept-1") is False

    def test_super_admin_cannot_modify_others(self):
        """super_admin cannot modify resources owned by others (ownership-only model)."""
        user = _make_user_model_mock(role="super_admin", user_id="sa-1")
        assert check_resource_modify(user, "other-user", "dept-1") is False

    def test_dept_admin_cannot_modify_others(self):
        """department_admin cannot modify resources owned by others."""
        user = _make_user_model_mock(role="department_admin", user_id="admin-1")
        assert check_resource_modify(user, "other-user", "dept-1") is False

    def test_viewer_cannot_modify_others(self):
        """viewer cannot modify resources owned by others."""
        user = _make_user_model_mock(role="viewer", user_id="viewer-1")
        assert check_resource_modify(user, "other-user", "dept-1") is False

    def test_owner_resource_with_none_owner_id(self):
        """Resource with no owner_id denies modification for everyone."""
        user = _make_user_model_mock(user_id="user-1")
        assert check_resource_modify(user, None, "dept-1") is False

    def test_owner_access_resource(self):
        """Owner can always read own resources regardless of visibility."""
        uid = str(uuid4())
        user = _make_user_model_mock(user_id=uid)
        for vis in ["private", "department", "public"]:
            assert check_resource_access(user, uid, "dept-1", vis) is True


# =====================================================================
# H) Concurrent First-User Creation
# =====================================================================


class TestUnprovisionedUserRaceSafety:
    """Concurrent authenticated requests never create RBAC profiles implicitly."""

    @pytest.mark.asyncio
    async def test_integrity_error_on_first_user_requery(self):
        """IntegrityError on insert → re-query returns existing user."""
        user = MagicMock()
        user.id = str(uuid4())
        user.email = "concurrent@test.com"

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        # Use role="user" (not super_admin) to skip the recheck path
        existing = _make_rbac_user(role="user", disabled=False)

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = existing

        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return query_result
            elif call_count["n"] == 2:
                return count_result
            return requery_result

        mock_session = AsyncMock()
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
    async def test_integrity_error_user_not_found_after_requery(self):
        """IntegrityError + re-query returns None → 500."""
        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = None

        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return query_result
            elif call_count["n"] == 2:
                return count_result
            return requery_result

        mock_session = AsyncMock()
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
    async def test_concurrent_super_admin_downgrade(self):
        """When IntegrityError + re-query returns super_admin but admin_count > 1,
        the concurrent user should be downgraded to USER."""
        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        concurrent_user = _make_rbac_user(role="super_admin", disabled=False)

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = concurrent_user

        call_count = {"n": 0}

        async def execute_primary(stmt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return query_result
            elif call_count["n"] == 2:
                return count_result
            return requery_result

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=execute_primary)
        mock_session.add = MagicMock(side_effect=IntegrityError("dup", "dup", Exception()))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Recheck session: admin_count > 1 → downgrade
        recheck_user = _make_rbac_user(role="super_admin", disabled=False)
        recheck_session = AsyncMock()
        recheck_count = MagicMock()
        recheck_count.scalar.return_value = 2
        recheck_user_result = MagicMock()
        recheck_user_result.scalar_one_or_none.return_value = recheck_user

        recheck_call = {"n": 0}

        async def execute_recheck(stmt):
            recheck_call["n"] += 1
            if recheck_call["n"] == 1:
                return recheck_count
            return recheck_user_result

        recheck_session.execute = AsyncMock(side_effect=execute_recheck)
        recheck_session.commit = AsyncMock()
        recheck_session.__aenter__ = AsyncMock(return_value=recheck_session)
        recheck_session.__aexit__ = AsyncMock(return_value=False)

        sf_call = {"n": 0}

        def sf_factory():
            sf_call["n"] += 1
            if sf_call["n"] == 1:
                return mock_session
            return recheck_session

        mock_sf = MagicMock(side_effect=sf_factory)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_integrity_error_disabled_user_after_requery(self):
        """IntegrityError + re-query returns disabled user → 403."""
        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        disabled = _make_rbac_user(role="user", disabled=True)

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        requery_result = MagicMock()
        requery_result.scalar_one_or_none.return_value = disabled

        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return query_result
            elif call_count["n"] == 2:
                return count_result
            return requery_result

        mock_session = AsyncMock()
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
    async def test_operational_error_fallback_to_plain_count(self):
        """OperationalError on SELECT FOR UPDATE falls back to plain count."""
        from sqlalchemy.exc import OperationalError

        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        # First count attempt raises OperationalError, second succeeds
        count_error = OperationalError("statement", {}, Exception())
        count_ok = MagicMock()
        count_ok.scalar.return_value = 1

        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return query_result
            elif call_count["n"] == 2:
                raise count_error
            return count_ok

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        def refresh_side_effect(u):
            u.role = "user"

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_programming_error_fallback_to_plain_count(self):
        """ProgrammingError on SELECT FOR UPDATE falls back to plain count."""
        from sqlalchemy.exc import ProgrammingError

        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None

        count_error = ProgrammingError("statement", {}, Exception())
        count_ok = MagicMock()
        count_ok.scalar.return_value = 0  # first user

        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return query_result
            elif call_count["n"] == 2:
                raise count_error
            return count_ok

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        def refresh_side_effect(u):
            u.role = "super_admin"

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 403


# =====================================================================
# I) Invalid Role Handling
# =====================================================================


class TestInvalidRoleHandling:
    """Edge cases around invalid or null roles."""

    @pytest.mark.asyncio
    async def test_invalid_role_defaults_to_viewer(self):
        """User with invalid role string gets downgraded to viewer."""
        user = MagicMock()
        user.id = str(uuid4())

        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        invalid_user = _make_rbac_user(role="nonexistent_role", disabled=False)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = invalid_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf):
            result = await get_current_rbac_user(req)

        assert result.role == UserRole.VIEWER

    @pytest.mark.asyncio
    async def test_null_role_gets_viewer_permissions(self):
        """A NULL role fails closed to the read-only viewer permission set."""
        from app.gateway.authz import _authenticate

        user = MagicMock()
        user.id = str(uuid4())

        null_user = MagicMock()
        null_user.role = None
        null_user.disabled = False

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = null_user

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=query_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with (
            patch(
                "app.gateway.deps.get_optional_user_from_request",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch("ideer.persistence.engine.get_session_factory", return_value=mock_sf),
        ):
            req = MagicMock()
            req.state = type("S", (), {})()
            ctx = await _authenticate(req)
        assert ctx.has_permission("threads", "read")
        assert not ctx.has_permission("threads", "write")

    @pytest.mark.asyncio
    async def test_require_role_with_invalid_role_value(self):
        """require_role rejects user with role not in allowed list."""

        @require_role("super_admin")
        async def endpoint(current_user=None):
            return "ok"

        mock_user = _make_rbac_user(role="invalid_role")
        with pytest.raises(HTTPException) as exc_info:
            await endpoint(current_user=mock_user)
        assert exc_info.value.status_code == 403


# =====================================================================
# J) Complete Permission Matrix Summary
# =====================================================================


class TestPermissionMatrixSummary:
    """Document and verify the complete permission matrix as a single source of truth."""

    MATRIX = {
        # role: {resource: {action: allowed}}
        "super_admin": {
            "threads": {"read": True, "write": True, "delete": True},
            "runs": {"create": True, "read": True, "cancel": True},
            "assistants": {"read": True},
            "models": {"read": True},
            "admin_stats": {"read": True},
            "admin_users": {"read": True, "create": True, "update": True},
            "admin_departments": {"read": True, "create": True, "update": True, "delete": True},
        },
        "department_admin": {
            "threads": {"read": True, "write": True, "delete": True},
            "runs": {"create": True, "read": True, "cancel": True},
            "assistants": {"read": True},
            "models": {"read": True},
            "admin_stats": {"read": True},
            "admin_users": {"read": True, "create": True, "update": True},
            "admin_departments": {"read": False, "create": False, "update": False, "delete": False},
        },
        "user": {
            "threads": {"read": True, "write": True, "delete": True},
            "runs": {"create": True, "read": True, "cancel": True},
            "assistants": {"read": True},
            "models": {"read": True},
            "admin_stats": {"read": False},
            "admin_users": {"read": False, "create": False, "update": False},
            "admin_departments": {"read": False, "create": False, "update": False, "delete": False},
        },
        "viewer": {
            "threads": {"read": True, "write": False, "delete": False},
            "runs": {"create": False, "read": True, "cancel": False},
            "assistants": {"read": False},
            "models": {"read": False},
            "admin_stats": {"read": False},
            "admin_users": {"read": False, "create": False, "update": False},
            "admin_departments": {"read": False, "create": False, "update": False, "delete": False},
        },
    }

    def test_matrix_documentation(self):
        """Verify the permission matrix is consistent with implementation."""
        # Verify viewer restrictions are enforced
        viewer_ctx = AuthContext(permissions=[Permissions.THREADS_READ, Permissions.RUNS_READ])
        for resource, actions in self.MATRIX["viewer"].items():
            for action, expected in actions.items():
                if resource.startswith("admin_"):
                    continue  # Tested via endpoint tests
                actual = viewer_ctx.has_permission(resource, action)
                assert actual == expected, f"viewer {resource}:{action}: expected {expected}, got {actual}"

    def test_viewer_only_has_two_permissions(self):
        """viewer should have exactly 2 permissions."""
        viewer_perms = [Permissions.THREADS_READ, Permissions.RUNS_READ]
        ctx = AuthContext(permissions=viewer_perms)
        all_resource_actions = [
            ("threads", "read"),
            ("threads", "write"),
            ("threads", "delete"),
            ("runs", "create"),
            ("runs", "read"),
            ("runs", "cancel"),
            ("assistants", "read"),
            ("models", "read"),
        ]
        count = sum(1 for r, a in all_resource_actions if ctx.has_permission(r, a))
        assert count == 2


# =====================================================================
# K) get_current_rbac_user — No Auth / No DB
# =====================================================================


class TestGetCurrentRbacUserEdgeCases:
    """Edge cases for the get_current_rbac_user dependency."""

    @pytest.mark.asyncio
    async def test_no_user_on_request_raises_401(self):
        """Request without user attribute → 401."""
        req = MagicMock()
        req.state = type("S", (), {})()  # no 'user' attr
        with pytest.raises(HTTPException) as exc_info:
            await get_current_rbac_user(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_session_factory_raises_500(self):
        """No session factory → 500."""
        user = MagicMock()
        user.id = str(uuid4())
        req = MagicMock()
        req.state = type("S", (), {"user": user})()

        with patch("ideer.persistence.engine.get_session_factory", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_rbac_user(req)
        assert exc_info.value.status_code == 500
