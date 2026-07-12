"""Comprehensive tests for the admin management router.

Covers ALL functions and code paths in backend/app/gateway/routers/admin.py
including edge cases, error handling, and boundary conditions.

Target: 98%+ line/branch coverage.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.admin import router as admin_router
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str = "admin-1",
    role: str = UserRole.SUPER_ADMIN,
    department_id: str | None = None,
    disabled: bool = False,
    username: str = "admin-user",
) -> MagicMock:
    """Create a mock RBAC user with all expected attributes."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = disabled
    user.created_at = None
    user.last_login = None
    user.username = username
    # department relationship for list_departments
    user.department = None
    return user


def _make_rbac_user_with_department(
    user_id: str = "u1",
    role: str = UserRole.USER,
    department_id: str = "dept-1",
    dept_name: str = "Engineering",
) -> MagicMock:
    """Create a mock RBAC user that has a department relationship loaded."""
    user = _make_rbac_user(user_id=user_id, role=role, department_id=department_id)
    dept = MagicMock()
    dept.name = dept_name
    user.department = dept
    return user


def _make_dept(
    dept_id: str = "dept-1",
    name: str = "Engineering",
    description: str = "Engineering team",
    created_at: datetime | None = None,
) -> MagicMock:
    """Create a mock department model."""
    dept = MagicMock()
    dept.id = dept_id
    dept.name = name
    dept.description = description
    dept.created_at = created_at
    return dept


def _make_app(current_user: MagicMock | None = None) -> FastAPI:
    """Create a test FastAPI app with admin router and stubbed auth."""
    app = FastAPI()
    app.include_router(admin_router)
    user = current_user or _make_rbac_user()

    async def _stub_current_user():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current_user
    return app


def _make_session_factory(session: AsyncMock) -> MagicMock:
    """Wrap a mock session into a session factory with async context manager."""
    sf_mock = MagicMock()
    sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
    sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf_mock


def _make_session_with_execute(execute_fn) -> AsyncMock:
    """Create a mock session whose execute uses the given side_effect function."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_fn)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# GET /api/admin/stats
# ---------------------------------------------------------------------------


class TestGetAdminStats:
    """Tests for GET /api/admin/stats endpoint."""

    @patch("app.gateway.routers.admin._collect_admin_resource_inventory", new_callable=AsyncMock)
    @patch("app.gateway.routers.admin.get_session_factory")
    def test_stats_returns_user_and_dept_counts(self, mock_sf, mock_inventory):
        """Happy path: returns counts for users, departments, and resources."""
        session = AsyncMock()
        mock_inventory.return_value = [
            {"resource_type": "agent"},
            {"resource_type": "agent"},
            *({"resource_type": "tool"} for _ in range(5)),
            *({"resource_type": "skill"} for _ in range(8)),
        ]

        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] <= 2:
                # First call: user count, second call: dept count
                result.scalar = MagicMock(return_value=10 if call_count["n"] == 1 else 3)
            else:
                result.scalar = MagicMock(return_value=0)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] == 10
        assert data["total_departments"] == 3
        assert data["total_agents"] == 2
        assert data["total_tools"] == 5
        assert data["total_skills"] == 8
        assert data["total_resources"] == 15

    @patch("app.gateway.routers.admin.get_workflow_store", create=True)
    @patch("app.gateway.routers.admin.get_or_new_skill_storage")
    @patch("app.gateway.routers.admin.get_available_tools")
    @patch("app.gateway.routers.admin.get_paths", create=True)
    @patch("app.gateway.routers.admin.get_session_factory")
    def test_stats_uses_canonical_inventory_when_metadata_undercounts(
        self,
        mock_sf,
        mock_get_paths,
        mock_get_tools,
        mock_get_skill_storage,
        mock_get_workflow_store,
        tmp_path,
    ):
        """Stats count live inventory, not only resource_metadata rows."""
        shared_agents = tmp_path / "agents"
        shared_agents.mkdir()
        (shared_agents / "shared-a").mkdir()
        (shared_agents / "shared-a" / "config.yaml").write_text("name: shared-a\n")
        (shared_agents / "broken").mkdir()

        user_agents = tmp_path / "users" / "u1" / "agents"
        user_agents.mkdir(parents=True)
        (user_agents / "custom-a").mkdir()
        (user_agents / "custom-a" / "config.yaml").write_text("name: custom-a\n")

        mock_get_paths.return_value = SimpleNamespace(base_dir=tmp_path, agents_dir=shared_agents)
        mock_get_tools.return_value = [SimpleNamespace(name="tool-a"), SimpleNamespace(name="tool-b")]
        mock_get_skill_storage.return_value.load_skills.return_value = [SimpleNamespace(name="skill-a")]
        mock_get_workflow_store.return_value.list_workflows = AsyncMock(return_value=([{"name": "wf-a"}, {"name": "wf-b"}], 2))

        session = AsyncMock()
        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar = MagicMock(return_value=10)
            elif call_count["n"] == 2:
                result.scalar = MagicMock(return_value=3)
            elif call_count["n"] == 3:
                result.scalars.return_value.all.return_value = []
            else:
                result.scalar = MagicMock(return_value=0)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agents"] == 2
        assert data["total_tools"] == 2
        assert data["total_skills"] == 1
        assert data["total_workflows"] == 2
        assert data["total_resources"] == 7

    @patch("app.gateway.routers.admin._collect_admin_resource_inventory", new_callable=AsyncMock)
    @patch("app.gateway.routers.admin.get_session_factory")
    def test_stats_returns_zeros_when_counts_are_none(self, mock_sf, mock_inventory):
        """When scalar() returns None, defaults to 0."""
        session = AsyncMock()
        mock_inventory.return_value = []

        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            result.scalar = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] == 0
        assert data["total_departments"] == 0
        assert data["total_agents"] == 0
        assert data["total_tools"] == 0
        assert data["total_skills"] == 0
        assert data["total_resources"] == 0

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_stats_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        resp = TestClient(app).get("/api/admin/stats")

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/admin/resources
# ---------------------------------------------------------------------------


class TestListResources:
    """Tests for GET /api/admin/resources endpoint."""

    @patch("app.gateway.routers.admin.get_workflow_store", create=True)
    @patch("app.gateway.routers.admin.get_or_new_skill_storage")
    @patch("app.gateway.routers.admin.get_available_tools")
    @patch("app.gateway.routers.admin.get_paths", create=True)
    @patch("app.gateway.routers.admin.get_session_factory")
    def test_resources_returns_canonical_inventory_with_metadata_defaults(
        self,
        mock_sf,
        mock_get_paths,
        mock_get_tools,
        mock_get_skill_storage,
        mock_get_workflow_store,
        tmp_path,
    ):
        shared_agents = tmp_path / "agents"
        shared_agents.mkdir()
        (shared_agents / "shared-a").mkdir()
        (shared_agents / "shared-a" / "config.yaml").write_text("name: shared-a\n")
        user_agents = tmp_path / "users" / "u1" / "agents"
        user_agents.mkdir(parents=True)
        (user_agents / "custom-a").mkdir()
        (user_agents / "custom-a" / "config.yaml").write_text("name: custom-a\n")

        mock_get_paths.return_value = SimpleNamespace(base_dir=tmp_path, agents_dir=shared_agents)
        mock_get_tools.return_value = [SimpleNamespace(name="tool-a")]
        mock_get_skill_storage.return_value.load_skills.return_value = [
            SimpleNamespace(name="public-skill", category="public"),
            SimpleNamespace(name="custom-skill", category="custom"),
        ]
        mock_get_workflow_store.return_value.list_workflows = AsyncMock(return_value=([{"name": "wf-a"}], 1))

        meta = MagicMock()
        meta.id = "meta-tool-a"
        meta.resource_type = "tool"
        meta.resource_id = "tool-a"
        meta.visibility = "department"
        meta.owner_id = "owner-1"
        meta.department_id = "dept-1"
        meta.created_at = datetime(2024, 1, 1)

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = [meta]
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/resources?limit=20&offset=0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        by_id = {item["resource_id"]: item for item in data["resources"]}
        assert by_id["shared-a"]["visibility"] == "public"
        assert by_id["tool-a"]["visibility"] == "department"
        assert by_id["custom-a"]["visibility"] == "private"
        assert by_id["public-skill"]["visibility"] == "public"
        assert by_id["custom-skill"]["visibility"] == "private"
        assert by_id["wf-a"]["visibility"] == "private"

    @patch("app.gateway.routers.admin.get_workflow_store", create=True)
    @patch("app.gateway.routers.admin.get_or_new_skill_storage")
    @patch("app.gateway.routers.admin.get_available_tools")
    @patch("app.gateway.routers.admin.get_paths", create=True)
    @patch("app.gateway.routers.admin.get_session_factory")
    def test_resources_applies_type_filter_before_total_and_pagination(
        self,
        mock_sf,
        mock_get_paths,
        mock_get_tools,
        mock_get_skill_storage,
        mock_get_workflow_store,
        tmp_path,
    ):
        shared_agents = tmp_path / "agents"
        shared_agents.mkdir()
        for name in ("agent-a", "agent-b"):
            (shared_agents / name).mkdir()
            (shared_agents / name / "config.yaml").write_text(f"name: {name}\n")

        mock_get_paths.return_value = SimpleNamespace(base_dir=tmp_path, agents_dir=shared_agents)
        mock_get_tools.return_value = [SimpleNamespace(name="tool-a")]
        mock_get_skill_storage.return_value.load_skills.return_value = []
        mock_get_workflow_store.return_value.list_workflows = AsyncMock(return_value=([], 0))

        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/resources?resource_type=agent&limit=1&offset=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["resources"]) == 1
        assert data["resources"][0]["resource_type"] == "agent"


# ---------------------------------------------------------------------------
# GET /api/admin/users
# ---------------------------------------------------------------------------


class TestListUsers:
    """Tests for GET /api/admin/users endpoint."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_returns_paginated_results(self, mock_sf):
        """Happy path: returns paginated user list with metadata."""
        u1 = _make_rbac_user(user_id="u1", username="alice")
        u1.created_at = datetime(2024, 1, 1)
        u1.last_login = datetime(2024, 6, 1)
        dept = MagicMock()
        dept.name = "Engineering"
        u1.department = dept

        u2 = _make_rbac_user(user_id="u2", username="bob")
        u2.created_at = None
        u2.last_login = None
        u2.department = None

        session = AsyncMock()

        async def _execute(stmt):
            stmt_str = str(stmt)
            result = MagicMock()
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=2)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[u1, u2])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["users"]) == 2
        # First user has department and timestamps
        assert data["users"][0]["department_name"] == "Engineering"
        assert data["users"][0]["created_at"] is not None
        assert data["users"][0]["last_login"] is not None
        # Second user has no department and no timestamps
        assert data["users"][1]["department_name"] is None
        assert data["users"][1]["created_at"] is None
        assert data["users"][1]["last_login"] is None

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users")

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_invalid_role_filter(self, mock_sf):
        """Returns 400 for an invalid role filter value."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users?role=bogus_role")

        assert resp.status_code == 400
        assert "Invalid role filter" in resp.json()["detail"]
        # Response should include valid roles
        detail = resp.json()["detail"]
        assert "super_admin" in detail

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_valid_role_filter(self, mock_sf):
        """Valid role filter passes validation and is applied."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users?role=super_admin")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["users"]) == 0

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_with_department_id_filter(self, mock_sf):
        """department_id filter is applied to the query."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users?department_id=dept-1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["users"]) == 0

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_limit_clamped_to_200(self, mock_sf):
        """Limit > 200 returns 422 (FastAPI Query validation)."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users?limit=9999")

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_limit_clamped_to_minimum_1(self, mock_sf):
        """Limit < 1 returns 422 (FastAPI Query validation)."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users?limit=-5")

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_negative_offset_clamped_to_zero(self, mock_sf):
        """Negative offset returns 422 (FastAPI Query validation)."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users?offset=-10")

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_with_both_filters(self, mock_sf):
        """Both department_id and role filters applied together."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/users?department_id=dept-1&role=user&limit=10&offset=5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 5

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_users_all_role_filter_values(self, mock_sf):
        """Each valid UserRole value is accepted as a filter."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        for role_val in UserRole:
            resp = TestClient(app).get(f"/api/admin/users?role={role_val.value}")
            assert resp.status_code == 200, f"Role {role_val.value} should be valid"
            data = resp.json()
            assert data["total"] == 0
            assert len(data["users"]) == 0


# ---------------------------------------------------------------------------
# PUT /api/admin/users/{user_id}/role
# ---------------------------------------------------------------------------


class TestUpdateUserRole:
    """Tests for PUT /api/admin/users/{user_id}/role endpoint."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_success(self, mock_sf):
        """Happy path: update a user's role without changing status."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.USER
        target.disabled = False

        session = AsyncMock()
        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/users/target-1/role",
            json={"role": "department_admin"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["user_id"] == "target-1"
        assert data["new_role"] == UserRole.DEPARTMENT_ADMIN
        assert data["role"] == UserRole.DEPARTMENT_ADMIN
        assert data["disabled"] is False
        assert target.role == UserRole.DEPARTMENT_ADMIN
        session.commit.assert_awaited()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_invalid_role_value(self, mock_sf):
        """Returns 400 for an invalid role value."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/users/target-1/role",
            json={"role": "nobody"},
        )

        assert resp.status_code == 400
        assert "Invalid role" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_user_not_found(self, mock_sf):
        """Returns 404 when target user does not exist."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/users/nonexistent/role",
            json={"role": "user"},
        )

        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_prevent_demoting_last_super_admin(self, mock_sf):
        """Cannot demote the last active super_admin."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.SUPER_ADMIN
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put("/api/admin/users/target-1/role", json={"role": "user"})

        assert resp.status_code == 400
        assert "last active super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_demote_super_admin_when_others_exist(self, mock_sf):
        """Can demote a super_admin when another active one exists."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.SUPER_ADMIN
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                # More than 1 active super_admin
                result.scalar = MagicMock(return_value=3)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/users/target-1/role",
            json={"role": "user"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["new_role"] == UserRole.USER
        assert resp.json()["disabled"] is False
        assert target.role == UserRole.USER

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_sqlite_for_update_fallback(self, mock_sf):
        """with_for_update exception is caught (SQLite fallback)."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.USER

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        # Patch with_for_update to simulate SQLite raising an exception
        from sqlalchemy.sql.selectable import Select

        original = Select.with_for_update

        def _raise_on_for_update(self, *args, **kwargs):
            raise NotImplementedError("SQLite doesn't support FOR UPDATE")

        Select.with_for_update = _raise_on_for_update
        try:
            app = _make_app()
            resp = TestClient(app).put(
                "/api/admin/users/target-1/role",
                json={"role": "department_admin"},
            )
            assert resp.status_code == 200
        finally:
            Select.with_for_update = original

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_demote_super_admin_sqlite_fallback(self, mock_sf):
        """SQLite fallback also covers the count_stmt.with_for_update path."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.SUPER_ADMIN

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=3)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        from sqlalchemy.sql.selectable import Select

        original = Select.with_for_update

        def _raise_on_for_update(self, *args, **kwargs):
            raise NotImplementedError("SQLite doesn't support FOR UPDATE")

        Select.with_for_update = _raise_on_for_update
        try:
            app = _make_app()
            resp = TestClient(app).put(
                "/api/admin/users/target-1/role",
                json={"role": "user"},
            )
            assert resp.status_code == 200
        finally:
            Select.with_for_update = original

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_to_every_valid_role(self, mock_sf):
        """Each valid UserRole value can be sent."""
        for role_val in UserRole:
            target = MagicMock()
            target.id = "target-1"
            target.role = UserRole.USER
            target.disabled = False

            session = AsyncMock()

            async def _execute(stmt, _target=target):
                result = MagicMock()
                stmt_str = str(stmt)
                if "count" in stmt_str.lower():
                    result.scalar = MagicMock(return_value=5)
                else:
                    result.scalar_one_or_none = MagicMock(return_value=_target)
                return result

            session.execute = AsyncMock(side_effect=_execute)
            session.commit = AsyncMock()
            mock_sf.return_value = _make_session_factory(session)

            app = _make_app()
            resp = TestClient(app).put(
                "/api/admin/users/target-1/role",
                json={"role": role_val.value},
            )

            assert resp.status_code == 200, f"Setting role to {role_val.value} should succeed"
            assert resp.json()["new_role"] == role_val
            assert resp.json()["disabled"] is False

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_promote_to_super_admin(self, mock_sf):
        """Promoting a regular user to super_admin preserves status."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.USER
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/users/target-1/role",
            json={"role": "super_admin"},
        )

        assert resp.status_code == 200
        assert resp.json()["new_role"] == UserRole.SUPER_ADMIN
        assert resp.json()["disabled"] is False


# ---------------------------------------------------------------------------
# Toggle user status (PATCH /api/admin/users/{user_id}/status)
# ---------------------------------------------------------------------------


class TestToggleUserStatus:
    """Tests for PATCH /api/admin/users/{user_id}/status endpoint."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_success(self, mock_sf):
        """Happy path: toggle disabled on a non-admin user."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.USER
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).patch("/api/admin/users/target-1/status")

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert target.disabled is True
        session.commit.assert_awaited()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_cannot_disable_self(self, mock_sf):
        """Toggling yourself succeeds (no self-check in endpoint)."""
        admin = _make_rbac_user(user_id="admin-1")
        admin.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=3)
            else:
                result.scalar_one_or_none = MagicMock(return_value=admin)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app(current_user=admin)
        resp = TestClient(app).patch("/api/admin/users/admin-1/status")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        admin = _make_rbac_user(user_id="admin-1")
        mock_sf.return_value = None

        app = _make_app(current_user=admin)
        resp = TestClient(app).patch("/api/admin/users/target-1/status")

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_not_found(self, mock_sf):
        """Returns 404 when target user does not exist."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).patch("/api/admin/users/nonexistent/status")

        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_last_super_admin_blocked(self, mock_sf):
        """Cannot disable the last active super_admin."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.SUPER_ADMIN
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).patch("/api/admin/users/target-1/status")

        assert resp.status_code == 400
        assert "last active super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_super_admin_when_others_exist(self, mock_sf):
        """Can disable a super_admin when multiple exist."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.SUPER_ADMIN
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=3)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).patch("/api/admin/users/target-1/status")

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert target.disabled is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_count_returns_none_defaults_to_zero(self, mock_sf):
        """When super_admin count returns None, it defaults to 0."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.SUPER_ADMIN
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=None)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).patch("/api/admin/users/target-1/status")

        # 0 <= 1, so it blocks
        assert resp.status_code == 400
        assert "last active super_admin" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_non_admin_skips_super_admin_check(self, mock_sf):
        """Disabling a non-super_admin user skips the super_admin count check."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.USER
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).patch("/api/admin/users/target-1/status")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_user_sqlite_for_update_fallback(self, mock_sf):
        """SQLite fallback for with_for_update in toggle disabled."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.USER
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        from sqlalchemy.sql.selectable import Select

        original = Select.with_for_update

        def _raise_on_for_update(self, *args, **kwargs):
            raise NotImplementedError("SQLite doesn't support FOR UPDATE")

        Select.with_for_update = _raise_on_for_update
        try:
            app = _make_app()
            resp = TestClient(app).patch("/api/admin/users/target-1/status")
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            Select.with_for_update = original

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_disable_super_admin_sqlite_for_update_fallback(self, mock_sf):
        """SQLite fallback for count_stmt.with_for_update in toggle disabled."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.SUPER_ADMIN
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=3)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        from sqlalchemy.sql.selectable import Select

        original = Select.with_for_update

        def _raise_on_for_update(self, *args, **kwargs):
            raise NotImplementedError("SQLite doesn't support FOR UPDATE")

        Select.with_for_update = _raise_on_for_update
        try:
            app = _make_app()
            resp = TestClient(app).patch("/api/admin/users/target-1/status")
            assert resp.status_code == 200
            assert resp.json()["success"] is True
        finally:
            Select.with_for_update = original

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_toggle_status_via_patch(self, mock_sf):
        """PATCH /status toggles disabled flag."""
        target = MagicMock()
        target.id = "target-1"
        target.role = UserRole.USER
        target.disabled = False

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=0)
            else:
                result.scalar_one_or_none = MagicMock(return_value=target)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).patch("/api/admin/users/target-1/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["disabled"] is True
        assert data["user_id"] == "target-1"
        assert target.disabled is True


# ---------------------------------------------------------------------------
# GET /api/admin/departments
# ---------------------------------------------------------------------------


class TestListDepartments:
    """Tests for GET /api/admin/departments endpoint."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_as_super_admin_shows_member_count(self, mock_sf):
        """Super admin sees actual member_count values."""
        dept = _make_dept(created_at=datetime(2024, 1, 1))

        session = AsyncMock()
        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            stmt_str = str(stmt).lower()
            result = MagicMock()
            if "group by" in stmt_str:
                # Member count query returns (dept_id, count) tuples
                result.all = MagicMock(return_value=[("dept-1", 5)])
            elif "count" in stmt_str:
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[dept])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        admin = _make_rbac_user(role=UserRole.SUPER_ADMIN)
        app = _make_app(current_user=admin)
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["departments"]) == 1
        assert data["departments"][0]["member_count"] == 5
        assert data["departments"][0]["agent_count"] == 0
        assert data["departments"][0]["skill_count"] == 0

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_as_department_admin_shows_member_count(self, mock_sf):
        """Department admin can list departments and sees member_count."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            stmt_str = str(stmt).lower()
            result = MagicMock()
            if "group by" in stmt_str:
                result.all = MagicMock(return_value=[("dept-1", 3)])
            elif "count" in stmt_str:
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[dept])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        admin = _make_rbac_user(role=UserRole.DEPARTMENT_ADMIN)
        app = _make_app(current_user=admin)
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["departments"]) == 1
        assert data["departments"][0]["member_count"] == 3
        assert data["departments"][0]["agent_count"] == 0
        assert data["departments"][0]["skill_count"] == 0

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_as_regular_user_redacts_member_count(self, mock_sf):
        """Regular user gets 403 — only super_admin can list departments."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            stmt_str = str(stmt).lower()
            result = MagicMock()
            if "group by" in stmt_str:
                result.all = MagicMock(return_value=[("dept-1", 5)])
            elif "count" in stmt_str:
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[dept])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        user = _make_rbac_user(role=UserRole.USER)
        app = _make_app(current_user=user)
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 403

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_as_viewer_redacts_member_count(self, mock_sf):
        """Viewer gets 403 — only super_admin can list departments."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            stmt_str = str(stmt).lower()
            result = MagicMock()
            if "group by" in stmt_str:
                result.all = MagicMock(return_value=[])
            elif "count" in stmt_str:
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[dept])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        viewer = _make_rbac_user(role=UserRole.VIEWER)
        app = _make_app(current_user=viewer)
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 403

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 500

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_limit_clamped(self, mock_sf):
        """Out-of-range limit returns 422 (FastAPI Query validation)."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/departments?limit=9999")
        assert resp.status_code == 422

        resp = TestClient(app).get("/api/admin/departments?limit=-5")
        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_negative_offset_clamped(self, mock_sf):
        """Negative offset returns 422 (FastAPI Query validation)."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/departments?offset=-10")
        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_empty_result(self, mock_sf):
        """Empty department list returns valid response."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 200
        assert resp.json()["departments"] == []
        assert resp.json()["total"] == 0

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_with_created_at(self, mock_sf):
        """Department with created_at returns it as string."""
        dept = _make_dept(created_at=datetime(2024, 3, 15, 10, 30, 0))

        session = AsyncMock()

        async def _execute(stmt):
            stmt_str = str(stmt).lower()
            result = MagicMock()
            if "group by" in stmt_str:
                result.all = MagicMock(return_value=[])
            elif "count" in stmt_str:
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[dept])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 200
        assert resp.json()["departments"][0]["created_at"] is not None

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_without_created_at(self, mock_sf):
        """Department without created_at returns None."""
        dept = _make_dept(created_at=None)

        session = AsyncMock()

        async def _execute(stmt):
            stmt_str = str(stmt).lower()
            result = MagicMock()
            if "group by" in stmt_str:
                result.all = MagicMock(return_value=[])
            elif "count" in stmt_str:
                result.scalar = MagicMock(return_value=1)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[dept])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 200
        assert resp.json()["departments"][0]["created_at"] is None

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_dept_with_no_members_in_count_map(self, mock_sf):
        """Department not in member_counts map gets default 0."""
        dept1 = _make_dept(dept_id="dept-1")
        dept2 = _make_dept(dept_id="dept-2", name="Sales")

        session = AsyncMock()

        async def _execute(stmt):
            stmt_str = str(stmt).lower()
            result = MagicMock()
            if "group by" in stmt_str:
                # Only dept-1 has members in the count result
                result.all = MagicMock(return_value=[("dept-1", 3)])
            elif "count" in stmt_str:
                result.scalar = MagicMock(return_value=2)
            else:
                result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[dept1, dept2])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        admin = _make_rbac_user(role=UserRole.SUPER_ADMIN)
        app = _make_app(current_user=admin)
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 200
        depts = resp.json()["departments"]
        assert depts[0]["member_count"] == 3  # dept-1
        assert depts[1]["member_count"] == 0  # dept-2 not in map

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_list_departments_count_returns_none(self, mock_sf):
        """When total count is None, defaults to 0."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar = MagicMock(return_value=None)
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).get("/api/admin/departments")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# POST /api/admin/departments
# ---------------------------------------------------------------------------


class TestCreateDepartment:
    """Tests for POST /api/admin/departments endpoint."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_success(self, mock_sf):
        """Happy path: create a department with valid name."""
        session = AsyncMock()

        async def _execute(stmt):
            # Duplicate check: no existing dept
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        session.add = MagicMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "Engineering", "description": "Eng team"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Engineering"
        assert data["description"] == "Eng team"
        assert "id" in data
        session.add.assert_called_once()
        session.commit.assert_awaited()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_strips_whitespace(self, mock_sf):
        """Leading/trailing whitespace is stripped from name."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        session.add = MagicMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "  Engineering  ", "description": "test"},
        )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Engineering"

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_empty_name_rejected(self, mock_sf):
        """Whitespace-only name is rejected."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "   ", "description": "test"},
        )

        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_empty_string_name_rejected(self, mock_sf):
        """Empty string name is rejected (after strip)."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock())
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "", "description": "test"},
        )

        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "Engineering"},
        )

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_duplicate_name_detected(self, mock_sf):
        """Returns 409 when department name already exists."""
        existing = _make_dept(name="Engineering")

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=existing)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "Engineering"},
        )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_integrity_error_on_commit(self, mock_sf):
        """Returns 409 when IntegrityError occurs during commit."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock(side_effect=IntegrityError("dup", "", Exception()))
        session.rollback = AsyncMock()
        session.add = MagicMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "Engineering"},
        )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]
        session.rollback.assert_awaited()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_default_description(self, mock_sf):
        """Description defaults to empty string when not provided."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        session.add = MagicMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "TestDept"},
        )

        assert resp.status_code == 200
        assert resp.json()["description"] == ""


# ---------------------------------------------------------------------------
# PUT /api/admin/departments/{dept_id}
# ---------------------------------------------------------------------------


class TestUpdateDepartment:
    """Tests for PUT /api/admin/departments/{dept_id} endpoint."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_name_only(self, mock_sf):
        """Update only the name."""
        dept = _make_dept()
        call_count = {"n": 0}

        session = AsyncMock()

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # First call: find dept
                result.scalar_one_or_none = MagicMock(return_value=dept)
            else:
                # Second call: duplicate check
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "New Name"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_description_only(self, mock_sf):
        """Update only the description."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"description": "Updated description"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert dept.description == "Updated description"

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_name_and_description(self, mock_sf):
        """Update both name and description."""
        dept = _make_dept()
        call_count = {"n": 0}

        session = AsyncMock()

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none = MagicMock(return_value=dept)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "New Name", "description": "New desc"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_no_fields_changes_nothing(self, mock_sf):
        """Sending neither name nor description still succeeds (no-op)."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_not_found(self, mock_sf):
        """Returns 404 when department does not exist."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/nonexistent",
            json={"name": "New Name"},
        )

        assert resp.status_code == 404
        assert "Department not found" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "New Name"},
        )

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_empty_name_rejected(self, mock_sf):
        """Returns 400 when new name is whitespace only."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "   "},
        )

        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_empty_string_name_rejected(self, mock_sf):
        """Returns 400 when new name is empty string."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": ""},
        )

        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_duplicate_name_rejected(self, mock_sf):
        """Returns 409 when new name conflicts with existing department."""
        dept = _make_dept()
        existing = _make_dept(dept_id="dept-2", name="Taken Name")
        call_count = {"n": 0}

        session = AsyncMock()

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # First call: find dept by id
                result.scalar_one_or_none = MagicMock(return_value=dept)
            else:
                # Second call: duplicate name check -- found duplicate
                result.scalar_one_or_none = MagicMock(return_value=existing)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "Taken Name"},
        )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_integrity_error_on_commit(self, mock_sf):
        """Returns 409 when IntegrityError occurs during commit."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            # First call returns dept, second returns no duplicate
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        # Override the first execute to return the dept
        call_count = {"n": 0}

        async def _execute_with_dept(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none = MagicMock(return_value=dept)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute_with_dept)
        session.commit = AsyncMock(side_effect=IntegrityError("dup", "", Exception()))
        session.rollback = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "New Name"},
        )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]
        session.rollback.assert_awaited()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_strips_whitespace_from_name(self, mock_sf):
        """Whitespace is stripped from the new name before checking duplicates."""
        dept = _make_dept()
        call_count = {"n": 0}

        session = AsyncMock()

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # First call: find dept by id
                result.scalar_one_or_none = MagicMock(return_value=dept)
            else:
                # Second call: duplicate name check -- no duplicate
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "  New Name  "},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_name_none_skips_name_update(self, mock_sf):
        """When name is explicitly null in JSON, name is not updated."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"description": "Only desc"},
        )

        assert resp.status_code == 200
        # Name should not have changed
        assert dept.name == "Engineering"


# ---------------------------------------------------------------------------
# DELETE /api/admin/departments/{dept_id}
# ---------------------------------------------------------------------------


class TestDeleteDepartment:
    """Tests for DELETE /api/admin/departments/{dept_id} endpoint."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_success(self, mock_sf):
        """Happy path: delete department with no active members."""
        dept = _make_dept()

        session = AsyncMock()
        call_count = {"n": 0}

        async def _execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            stmt_str = str(stmt)
            if call_count["n"] == 1:
                # First call: find dept
                result.scalar_one_or_none = MagicMock(return_value=dept)
            elif "count" in stmt_str.lower():
                # Member count: 0 active members
                result.scalar = MagicMock(return_value=0)
            else:
                # update statement (clearing department_id on disabled users)
                result.rowcount = MagicMock(return_value=0)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).delete("/api/admin/departments/dept-1")

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        session.delete.assert_awaited_once_with(dept)
        session.commit.assert_awaited()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_not_found(self, mock_sf):
        """Returns 404 when department does not exist."""
        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).delete("/api/admin/departments/nonexistent")

        assert resp.status_code == 404
        assert "Department not found" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_database_not_initialized(self, mock_sf):
        """Returns 500 when session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        resp = TestClient(app).delete("/api/admin/departments/dept-1")

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_with_active_members_blocked(self, mock_sf):
        """Cannot delete department that has active (non-disabled) members."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=5)
            else:
                result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).delete("/api/admin/departments/dept-1")

        assert resp.status_code == 400
        assert "members" in resp.json()["detail"].lower()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_count_returns_none_treated_as_zero(self, mock_sf):
        """When member count is None, treated as 0 (allows deletion)."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=None)
            else:
                result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).delete("/api/admin/departments/dept-1")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_integrity_error_on_commit(self, mock_sf):
        """Returns 409 when IntegrityError occurs during delete/commit."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=0)
            else:
                result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.delete = AsyncMock()
        session.commit = AsyncMock(side_effect=IntegrityError("fk", "", Exception()))
        session.rollback = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).delete("/api/admin/departments/dept-1")

        assert resp.status_code == 409
        assert "remaining database references" in resp.json()["detail"]
        session.rollback.assert_awaited()

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_delete_department_clears_disabled_user_references(self, mock_sf):
        """Disabled users' department_id is cleared before deletion."""
        dept = _make_dept()

        session = AsyncMock()
        execute_calls = []

        async def _execute(stmt):
            execute_calls.append(str(stmt))
            result = MagicMock()
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                result.scalar = MagicMock(return_value=0)
            elif "UPDATE" in stmt_str or "update" in stmt_str:
                # The sql_update for clearing department_id
                result.rowcount = MagicMock(return_value=2)
            else:
                result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).delete("/api/admin/departments/dept-1")

        assert resp.status_code == 200
        # Verify that the update statement was executed (clearing department_id)
        update_calls = [c for c in execute_calls if "update" in c.lower()]
        assert len(update_calls) > 0


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestRequestModels:
    """Tests for Pydantic request model validation."""

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_role_request_requires_role_field(self, mock_sf):
        """UpdateRoleRequest requires 'role' field."""
        mock_sf.return_value = _make_session_factory(AsyncMock())

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/users/target-1/role",
            json={},
        )

        # FastAPI returns 422 for validation errors
        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_request_requires_name_field(self, mock_sf):
        """CreateDepartmentRequest requires 'name' field."""
        mock_sf.return_value = _make_session_factory(AsyncMock())

        app = _make_app()
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"description": "no name"},
        )

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_name_max_length(self, mock_sf):
        """CreateDepartmentRequest enforces max_length on name."""
        mock_sf.return_value = _make_session_factory(AsyncMock())

        app = _make_app()
        # Name > 100 chars
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "A" * 101},
        )

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_create_department_description_max_length(self, mock_sf):
        """CreateDepartmentRequest enforces max_length on description."""
        mock_sf.return_value = _make_session_factory(AsyncMock())

        app = _make_app()
        # Description > 500 chars
        resp = TestClient(app).post(
            "/api/admin/departments",
            json={"name": "Test", "description": "X" * 501},
        )

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_name_max_length(self, mock_sf):
        """UpdateDepartmentRequest enforces max_length on name."""
        mock_sf.return_value = _make_session_factory(AsyncMock())

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": "A" * 101},
        )

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_description_max_length(self, mock_sf):
        """UpdateDepartmentRequest enforces max_length on description."""
        mock_sf.return_value = _make_session_factory(AsyncMock())

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"description": "X" * 501},
        )

        assert resp.status_code == 422

    @patch("app.gateway.routers.admin.get_session_factory")
    def test_update_department_accepts_null_name(self, mock_sf):
        """UpdateDepartmentRequest accepts null for optional name field."""
        dept = _make_dept()

        session = AsyncMock()

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=dept)
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        mock_sf.return_value = _make_session_factory(session)

        app = _make_app()
        resp = TestClient(app).put(
            "/api/admin/departments/dept-1",
            json={"name": None, "description": "updated"},
        )

        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# Router configuration
# ---------------------------------------------------------------------------


class TestRouterConfiguration:
    """Tests verifying router prefix and tags are correctly set."""

    def test_router_prefix(self):
        """Router has the correct prefix."""
        assert admin_router.prefix == "/api/admin"

    def test_router_tags(self):
        """Router has the 'admin' tag."""
        assert "admin" in admin_router.tags

    def test_router_has_all_expected_routes(self):
        """Router exposes all expected endpoints."""
        routes = {r.path: r.methods for r in admin_router.routes if hasattr(r, "methods")}
        assert "/api/admin/stats" in routes
        assert "/api/admin/users" in routes
        assert "/api/admin/users/{user_id}/role" in routes
        assert "/api/admin/departments" in routes
        assert "/api/admin/departments/{dept_id}" in routes
        assert "/api/admin/departments/{dept_id}/resources" in routes
