"""Tests for the audit log query router (backend/app/gateway/routers/audit_logs.py).

Covers:
- GET /api/admin/audit-logs — list audit logs with filtering & pagination
- GET /api/admin/audit-logs/{log_id} — get single audit log detail
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.audit_logs import router as audit_router
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rbac_user(
    user_id: str = "admin-1",
    role: str = "super_admin",
) -> MagicMock:
    """Create a mock RBAC user."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.disabled = False
    return user


def _make_audit_log(
    log_id: str = "log-1",
    actor_id: str | None = "user-1",
    action: str = "user.login",
    resource_type: str | None = "user",
    resource_id: str | None = "res-1",
    detail: str | None = "Logged in",
    ip_address: str | None = "127.0.0.1",
    created_at: datetime | None = datetime(2025, 1, 15, 10, 30, 0),
) -> MagicMock:
    """Create a mock AuditLog ORM object."""
    log = MagicMock()
    log.id = log_id
    log.actor_id = actor_id
    log.action = action
    log.resource_type = resource_type
    log.resource_id = resource_id
    log.detail = detail
    log.ip_address = ip_address
    log.created_at = created_at
    return log


def _make_app(current_user: MagicMock | None = None) -> FastAPI:
    """Create a test FastAPI app with audit_logs router and stubbed auth."""
    app = FastAPI()
    app.include_router(audit_router)

    user = current_user or _make_rbac_user()

    async def _stub_current_user():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_current_user
    return app


def _mock_session_factory(session: AsyncMock) -> MagicMock:
    """Create a mock session factory that yields the given session."""
    sf = MagicMock()
    sf.return_value.__aenter__ = AsyncMock(return_value=session)
    sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf


def _make_session(list_results: list | None = None, total: int = 0):
    """Build a mock async session that handles count + list queries.

    Returns (session, sf_mock) — sf_mock is the session factory.
    """
    list_results = list_results or []

    async def _execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt)
        if "count" in stmt_str.lower() and "select" not in stmt_str.split("count")[0][-10:]:
            # Count query
            result.scalar = MagicMock(return_value=total)
        else:
            # List query
            result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=list_results)))
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=_execute)
    sf = _mock_session_factory(session)
    return session, sf


# ---------------------------------------------------------------------------
# GET /api/admin/audit-logs — list endpoint
# ---------------------------------------------------------------------------


class TestListAuditLogs:
    """Tests for the list audit logs endpoint."""

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_returns_empty_when_no_logs(self, mock_sf):
        """Empty database returns empty list with total=0."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_returns_paginated_results(self, mock_sf):
        """Returns audit logs with correct pagination metadata."""
        logs = [_make_audit_log(log_id=f"log-{i}") for i in range(3)]
        session, sf = _make_session(list_results=logs, total=3)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 20

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_response_fields(self, mock_sf):
        """Each item contains all expected fields."""
        log = _make_audit_log()
        session, sf = _make_session(list_results=[log], total=1)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["id"] == "log-1"
        assert item["actor_id"] == "user-1"
        assert item["action"] == "user.login"
        assert item["resource_type"] == "user"
        assert item["resource_id"] == "res-1"
        assert item["detail"] == "Logged in"
        assert item["ip_address"] == "127.0.0.1"
        assert "created_at" in item

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_filter_by_actor_id(self, mock_sf):
        """Passing actor_id filter triggers correct DB query."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?actor_id=user-42")

        assert resp.status_code == 200
        # Verify session.execute was called (the query ran)
        session.execute.assert_awaited()

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_filter_by_action(self, mock_sf):
        """Passing action filter triggers correct DB query."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?action=user.login")

        assert resp.status_code == 200

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_filter_by_resource_type(self, mock_sf):
        """Passing resource_type filter triggers correct DB query."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?resource_type=thread")

        assert resp.status_code == 200

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_filter_by_date_range(self, mock_sf):
        """Passing start_date and end_date triggers correct DB query."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59")

        assert resp.status_code == 200

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_combined_filters(self, mock_sf):
        """Multiple filters can be combined in a single request."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?actor_id=user-1&action=user.login&resource_type=thread&start_date=2025-01-01T00:00:00&end_date=2025-12-31T23:59:59")

        assert resp.status_code == 200

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_pagination_page_and_size(self, mock_sf):
        """Page and page_size parameters are respected."""
        session, sf = _make_session(list_results=[], total=50)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?page=2&page_size=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["page_size"] == 10

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_pagination_boundary(self, mock_sf):
        """Requesting a page beyond total results returns empty items."""
        session, sf = _make_session(list_results=[], total=5)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?page=100&page_size=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 5

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_no_database_returns_500(self, mock_sf):
        """Returns 500 when database session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_db_error_returns_500(self, mock_sf):
        """Database errors are caught and returned as 500."""
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db exploded"))
        sf = _mock_session_factory(session)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 500
        assert "Internal server error" in resp.json()["detail"]

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_ordinal_null_fields(self, mock_sf):
        """Audit logs with null fields are serialized correctly."""
        log = _make_audit_log(
            actor_id=None,
            resource_type=None,
            resource_id=None,
            detail=None,
            ip_address=None,
        )
        session, sf = _make_session(list_results=[log], total=1)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["actor_id"] is None
        assert item["resource_type"] is None
        assert item["resource_id"] is None
        assert item["detail"] is None
        assert item["ip_address"] is None

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_created_at_none_serializes_to_empty_string(self, mock_sf):
        """When created_at is None, the response field becomes empty string."""
        log = _make_audit_log(created_at=None)
        session, sf = _make_session(list_results=[log], total=1)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["created_at"] == ""

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_invalid_start_date_returns_500(self, mock_sf):
        """Invalid ISO datetime in start_date triggers server error."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?start_date=not-a-date")

        assert resp.status_code == 500

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_invalid_end_date_returns_500(self, mock_sf):
        """Invalid ISO datetime in end_date triggers server error."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?end_date=2025-13-45T99:99:99")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/admin/audit-logs/{log_id} — detail endpoint
# ---------------------------------------------------------------------------


class TestGetAuditLogDetail:
    """Tests for the get audit log detail endpoint."""

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_get_detail_returns_log(self, mock_sf):
        """Returns the audit log entry when found."""
        log = _make_audit_log(log_id="log-42")

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=log)
            return result

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf = _mock_session_factory(session)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs/log-42")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "log-42"
        assert data["action"] == "user.login"

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_get_detail_not_found(self, mock_sf):
        """Returns 404 when the log_id does not exist."""

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf = _mock_session_factory(session)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs/nonexistent-id")

        assert resp.status_code == 404
        assert "Audit log not found" in resp.json()["detail"]

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_get_detail_no_database_returns_500(self, mock_sf):
        """Returns 500 when database session factory is None."""
        mock_sf.return_value = None

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs/log-1")

        assert resp.status_code == 500
        assert "Database not initialized" in resp.json()["detail"]

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_get_detail_db_error_returns_500(self, mock_sf):
        """Database errors are caught and returned as 500."""
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db failed"))
        sf = _mock_session_factory(session)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs/log-1")

        assert resp.status_code == 500
        assert "Internal server error" in resp.json()["detail"]

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_get_detail_created_at_none_returns_empty_string(self, mock_sf):
        """When created_at is None, the response field becomes empty string."""
        log = _make_audit_log(log_id="log-null", created_at=None)

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=log)
            return result

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf = _mock_session_factory(session)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs/log-null")

        assert resp.status_code == 200
        data = resp.json()
        assert data["created_at"] == ""


# ---------------------------------------------------------------------------
# Permission tests — require_role(SUPER_ADMIN)
# ---------------------------------------------------------------------------


class TestAuditLogsPermissions:
    """Tests for role-based access control on audit log endpoints."""

    def _user_with_role(self, role: str) -> MagicMock:
        return _make_rbac_user(role=role)

    def test_non_super_admin_denied_on_list(self):
        """User with 'user' role is denied access to list endpoint."""
        app = _make_app(current_user=self._user_with_role(UserRole.USER))
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 403
        assert "Requires role" in resp.json()["detail"]

    def test_viewer_denied_on_list(self):
        """Viewer role is denied access to list endpoint."""
        app = _make_app(current_user=self._user_with_role(UserRole.VIEWER))
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 403

    def test_department_admin_allowed_on_list(self):
        """Department admin has global read access to audit logs."""
        session, sf = _make_session(list_results=[], total=0)
        with patch("app.gateway.routers.audit_logs.get_session_factory", return_value=sf):
            app = _make_app(current_user=self._user_with_role(UserRole.DEPARTMENT_ADMIN))
            client = TestClient(app)
            resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_department_admin_allowed_on_detail(self):
        """Department admin has global read access to audit log details."""
        log = _make_audit_log(log_id="log-1")

        async def _execute(_stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = log
            return result

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=_execute)
        with patch("app.gateway.routers.audit_logs.get_session_factory", return_value=_mock_session_factory(session)):
            app = _make_app(current_user=self._user_with_role(UserRole.DEPARTMENT_ADMIN))
            client = TestClient(app)
            resp = client.get("/api/admin/audit-logs/log-1")

        assert resp.status_code == 200
        assert resp.json()["id"] == "log-1"

    def test_viewer_denied_on_detail(self):
        """Viewer role is denied access to detail endpoint."""
        app = _make_app(current_user=self._user_with_role(UserRole.VIEWER))
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs/log-1")

        assert resp.status_code == 403

    def test_super_admin_allowed_on_list(self):
        """Super admin can access list endpoint."""
        session, sf = _make_session(list_results=[], total=0)
        with patch("app.gateway.routers.audit_logs.get_session_factory", return_value=sf):
            app = _make_app(current_user=self._user_with_role(UserRole.SUPER_ADMIN))
            client = TestClient(app)
            resp = client.get("/api/admin/audit-logs")

            assert resp.status_code == 200

    def test_non_super_admin_denied_on_detail(self):
        """User with 'user' role is denied access to detail endpoint."""
        app = _make_app(current_user=self._user_with_role(UserRole.USER))
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs/log-1")

        assert resp.status_code == 403

    def test_super_admin_allowed_on_detail(self):
        """Super admin can access detail endpoint."""
        log = _make_audit_log(log_id="log-1")

        async def _execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=log)
            return result

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=_execute)
        sf = _mock_session_factory(session)

        with patch("app.gateway.routers.audit_logs.get_session_factory", return_value=sf):
            app = _make_app(current_user=self._user_with_role(UserRole.SUPER_ADMIN))
            client = TestClient(app)
            resp = client.get("/api/admin/audit-logs/log-1")

            assert resp.status_code == 200

    def test_none_user_denied(self):
        """Unauthenticated (no current_user) returns 401."""
        app = _make_app()

        async def _no_user():
            return None

        app.dependency_overrides[get_current_rbac_user] = _no_user
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestAuditLogsEdgeCases:
    """Edge cases for audit log endpoints."""

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_default_pagination_values(self, mock_sf):
        """Default page=1 and page_size=20 when no params given."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 20

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_start_date_only(self, mock_sf):
        """start_date without end_date works."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?start_date=2025-06-01T00:00:00")

        assert resp.status_code == 200

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_end_date_only(self, mock_sf):
        """end_date without start_date works."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?end_date=2025-12-31T23:59:59")

        assert resp.status_code == 200

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_no_filters_returns_all(self, mock_sf):
        """No filters means no WHERE clauses — all logs returned."""
        logs = [_make_audit_log(log_id=f"log-{i}") for i in range(5)]
        session, sf = _make_session(list_results=logs, total=5)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs")

        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_page_size_zero_rejected(self, mock_sf):
        """page_size=0 violates ge=1 constraint → 422."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?page_size=0")

        assert resp.status_code == 422

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_page_size_over_max_rejected(self, mock_sf):
        """page_size=101 violates le=100 constraint → 422."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?page_size=101")

        assert resp.status_code == 422

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_page_zero_rejected(self, mock_sf):
        """page=0 violates ge=1 constraint → 422."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?page=0")

        assert resp.status_code == 422

    @patch("app.gateway.routers.audit_logs.get_session_factory")
    def test_list_page_size_max_boundary(self, mock_sf):
        """page_size=100 is the maximum allowed value."""
        session, sf = _make_session(list_results=[], total=0)
        mock_sf.return_value = sf

        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/admin/audit-logs?page_size=100")

        assert resp.status_code == 200
        assert resp.json()["page_size"] == 100
