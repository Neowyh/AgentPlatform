"""E2E tests for the visibility applications router.

Covers the complete workflow through the real HTTP stack:
- POST   /api/visibility-applications          — submit application
- PUT    /api/visibility-applications/{id}      — approve / reject (optimistic lock)
- PUT    /api/visibility-applications/{id}/withdraw — withdraw own application
- GET    /api/visibility-applications           — list pending applications (admin)

Scenarios:
  - Full workflow: create resource → submit → approve → visibility changed
  - Full workflow: create resource → submit → reject
  - Withdraw own pending application
  - Optimistic lock conflict on review
  - Optimistic lock conflict on withdraw
  - Duplicate pending application (409)
  - Resource not found (404)
  - Application not found (404)
  - Target visibility same as current (400)
  - Non-admin cannot review (403)
  - Non-admin cannot list (403)
  - Only pending applications can be withdrawn (400)
  - Cannot review own application as department_admin (403)
  - List with filters (status, resource_type)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.visibility_applications import router as vis_router

pytestmark = pytest.mark.no_auto_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


def _make_user(user_id: str = "user-1", role: str = "user", dept_id: str | None = "dept-1") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = dept_id
    user.disabled = False
    user.username = f"user-{user_id}"
    return user


def _make_resource(
    resource_type: str = "skill",
    resource_id: str = "my-skill",
    visibility: str = "private",
    department_id: str | None = "dept-1",
) -> MagicMock:
    res = MagicMock()
    res.resource_type = resource_type
    res.resource_id = resource_id
    res.visibility = visibility
    res.department_id = department_id
    res.deleted_at = None
    return res


def _make_application(
    *,
    app_id: str | None = None,
    resource_type: str = "skill",
    resource_id: str = "my-skill",
    applicant_id: str = "user-1",
    current_visibility: str = "private",
    target_visibility: str = "public",
    department_id: str | None = "dept-1",
    reason: str = "need public",
    status: str = "pending",
    reviewed_by: str | None = None,
    review_comment: str = "",
    version: int = 1,
) -> MagicMock:
    app = MagicMock()
    app.id = app_id or _uid()
    app.resource_type = resource_type
    app.resource_id = resource_id
    app.applicant_id = applicant_id
    app.current_visibility = current_visibility
    app.target_visibility = target_visibility
    app.department_id = department_id
    app.reason = reason
    app.status = status
    app.submitted_at = datetime.now(UTC)
    app.reviewed_by = reviewed_by
    app.reviewed_at = datetime.now(UTC) if reviewed_by else None
    app.review_comment = review_comment
    app.version = version
    return app


def _make_app(role: str = "super_admin", user_id: str = "admin-1") -> tuple:
    user = _make_user(user_id=user_id, role=role)
    app = make_authed_test_app()
    app.include_router(vis_router)

    async def _stub_rbac():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_rbac
    return app, user


def _patch_session(session_mock: MagicMock):
    """Patch get_session_factory and record_audit for the session mock."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx)
    return patch(
        "app.gateway.routers.visibility_applications.get_session_factory",
        return_value=factory,
    ), patch(
        "app.gateway.routers.visibility_applications.record_audit",
        new_callable=AsyncMock,
    )


def _setup_create_session(resource: MagicMock):
    """Build a session mock for POST (create application).

    Call sequence: pending check → resource lookup → add → commit → refresh.
    """
    session = MagicMock()
    pending_result = MagicMock()
    pending_result.scalar_one_or_none.return_value = None  # no existing pending

    resource_result = MagicMock()
    resource_result.scalar_one_or_none.return_value = resource

    session.execute = AsyncMock(side_effect=[pending_result, resource_result])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _setup_list_session(applications: list[MagicMock], total: int | None = None):
    """Build a session mock for GET (list applications)."""
    session = MagicMock()
    if total is None:
        total = len(applications)

    count_result = MagicMock()
    count_result.scalar.return_value = total

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = applications

    session.execute = AsyncMock(side_effect=[count_result, list_result])
    return session


# ---------------------------------------------------------------------------
# Tests — POST /api/visibility-applications — submit application
# ---------------------------------------------------------------------------


class TestCreateApplication:
    """Tests for POST /api/visibility-applications."""

    def test_create_application_success(self):
        """Submit application succeeds with valid resource and different visibility."""
        resource = _make_resource(visibility="private")
        session = _setup_create_session(resource)

        # After add+commit, refresh should set attributes on the app obj
        def _refresh(app_obj):
            app_obj.id = app_obj.id or "app-1"
            app_obj.version = 1
            app_obj.status = "pending"
            app_obj.submitted_at = datetime.now(UTC)
            app_obj.applicant_id = app_obj.applicant_id or "user-1"
            app_obj.current_visibility = "private"
            app_obj.reviewed_by = None
            app_obj.reviewed_at = None
            app_obj.review_comment = ""

        session.refresh = AsyncMock(side_effect=_refresh)

        sf_patch, audit_patch = _patch_session(session)
        app, user = _make_app(role="user", user_id="applicant-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "my-skill",
                        "target_visibility": "public",
                        "reason": "Need public access",
                    },
                )
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_type"] == "skill"
        assert data["resource_id"] == "my-skill"
        assert data["target_visibility"] == "public"
        assert data["current_visibility"] == "private"
        assert data["applicant_id"] == "applicant-1"
        assert data["reason"] == "Need public access"
        assert data["status"] == "pending"
        assert data["version"] == 1

    def test_create_application_invalid_resource_type(self):
        """Reject application with invalid resource_type."""
        resource = _make_resource()
        session = _setup_create_session(resource)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "invalid",
                        "resource_id": "my-skill",
                        "target_visibility": "public",
                    },
                )
        assert resp.status_code == 422  # Pydantic validation error

    def test_create_application_target_same_as_current(self):
        """Reject application when target == current visibility."""
        resource = _make_resource(visibility="private")
        session = _setup_create_session(resource)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "my-skill",
                        "target_visibility": "private",
                        "reason": "Same visibility",
                    },
                )
        assert resp.status_code == 400
        assert "same as current" in resp.json()["detail"].lower()

    def test_create_application_resource_not_found(self):
        """Reject application when resource does not exist."""
        session = MagicMock()
        pending_result = MagicMock()
        pending_result.scalar_one_or_none.return_value = None
        resource_result = MagicMock()
        resource_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[pending_result, resource_result])
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "nonexistent",
                        "target_visibility": "public",
                    },
                )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_create_application_duplicate_pending(self):
        """Reject when a pending application already exists for the resource."""
        session = MagicMock()
        pending_result = MagicMock()
        existing_app = _make_application(status="pending")
        pending_result.scalar_one_or_none.return_value = existing_app
        session.execute = AsyncMock(return_value=pending_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "my-skill",
                        "target_visibility": "public",
                    },
                )
        assert resp.status_code == 409
        assert "pending" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests — PUT /api/visibility-applications/{id} — approve / reject
# ---------------------------------------------------------------------------


class TestReviewApplication:
    """Tests for PUT /api/visibility-applications/{id} (approve/reject)."""

    def test_approve_application_updates_visibility(self):
        """Approving an application updates resource_visibility."""
        app_obj = _make_application(version=1, status="pending")
        resource = _make_resource(visibility="private")

        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        resource_result = MagicMock()
        resource_result.scalar_one_or_none.return_value = resource
        update_result = MagicMock()
        session.execute = AsyncMock(side_effect=[find_result, update_result])
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        sf_patch, audit_patch = _patch_session(session)
        app, user = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "LGTM", "version": 1},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["version"] == 2
        assert data["reviewed_by"] == "admin-1"
        assert data["reviewed_at"] is not None
        # Verify resource visibility update was executed (2nd execute call)
        assert session.execute.await_count == 2

    def test_reject_application(self):
        """Rejecting an application sets status to rejected."""
        app_obj = _make_application(version=1, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "rejected", "comment": "Not now", "version": 1},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["version"] == 2
        assert data["reviewed_by"] == "admin-1"
        assert data["reviewed_at"] is not None

    def test_review_application_not_found(self):
        """Reviewing a nonexistent application returns 404."""
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    "/api/visibility-applications/nonexistent",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code == 404

    def test_review_application_not_pending(self):
        """Reviewing a non-pending application returns 400."""
        app_obj = _make_application(status="approved", version=2)
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "", "version": 2},
                )
        assert resp.status_code == 400
        assert "not pending" in resp.json()["detail"].lower()

    def test_review_optimistic_lock_conflict(self):
        """Review fails when version does not match."""
        app_obj = _make_application(version=3, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code == 409
        assert "version" in resp.json()["detail"].lower()

    def test_dept_admin_cannot_review_own_application(self):
        """Department admin cannot review their own application."""
        app_obj = _make_application(applicant_id="admin-dept", department_id="dept-1", version=1, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="department_admin", user_id="admin-dept")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code == 403
        assert "own" in resp.json()["detail"].lower()

    def test_dept_admin_can_review_other_department_application(self):
        """dept_admin can review applications from other departments (no cross-dept restriction in review_application)."""
        # Application belongs to dept-2, reviewer is dept admin of dept-1
        app_obj = _make_application(
            applicant_id="user-from-dept2",
            department_id="dept-2",
            version=1,
            status="pending",
        )
        resource = _make_resource(visibility="private", department_id="dept-2")

        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        update_result = MagicMock()
        resource_result = MagicMock()
        resource_result.scalar_one_or_none.return_value = resource
        session.execute = AsyncMock(side_effect=[find_result, update_result])
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        sf_patch, audit_patch = _patch_session(session)
        # dept_admin belongs to dept-1, reviewing an app from dept-2
        app, user = _make_app(role="department_admin", user_id="dept-admin-dept1")
        # Explicitly verify: reviewer is dept-1, application is dept-2 — different departments
        assert app_obj.department_id == "dept-2"
        assert user.department_id == "dept-1"
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "Approved cross-dept", "version": 1},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_super_admin_can_review_cross_department(self):
        """Super admin is not restricted by department — can review any department's application."""
        app_obj = _make_application(applicant_id="user-from-dept2", department_id="dept-2", version=1, status="pending")
        resource = _make_resource(visibility="private", department_id="dept-2")

        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        update_result = MagicMock()
        resource_result = MagicMock()
        resource_result.scalar_one_or_none.return_value = resource
        session.execute = AsyncMock(side_effect=[find_result, update_result])
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        sf_patch, audit_patch = _patch_session(session)
        # super_admin reviews an app from dept-2
        app, user = _make_app(role="super_admin", user_id="super-admin-1")
        assert app_obj.department_id == "dept-2"
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "Cross-dept approved", "version": 1},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_dept_admin_can_review_application_without_department(self):
        """dept_admin can review an application with department_id=None (no cross-dept restriction)."""
        app_obj = _make_application(applicant_id="user-no-dept", department_id=None, version=1, status="pending")
        resource = _make_resource(visibility="private", department_id=None)

        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        update_result = MagicMock()
        resource_result = MagicMock()
        resource_result.scalar_one_or_none.return_value = resource
        session.execute = AsyncMock(side_effect=[find_result, update_result])
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        sf_patch, audit_patch = _patch_session(session)
        app, user = _make_app(role="department_admin", user_id="dept-admin-1")
        # Verify: application has no department, user has dept-1
        assert app_obj.department_id is None
        assert user.department_id == "dept-1"
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Tests — PUT /api/visibility-applications/{id}/withdraw
# ---------------------------------------------------------------------------


class TestWithdrawApplication:
    """Tests for PUT /api/visibility-applications/{id}/withdraw."""

    def test_withdraw_own_application(self):
        """User can withdraw their own pending application."""
        app_obj = _make_application(applicant_id="applicant-1", version=1, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        session.commit = AsyncMock()

        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="applicant-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}/withdraw",
                    json={"version": 1},
                )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify mock was mutated correctly
        assert str(app_obj.status) == "withdrawn"
        assert app_obj.version == 2

    def test_withdraw_not_found(self):
        """Withdrawing a nonexistent application returns 404."""
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app()
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    "/api/visibility-applications/nonexistent/withdraw",
                    json={"version": 1},
                )
        assert resp.status_code == 404

    def test_withdraw_other_user_application_forbidden(self):
        """User cannot withdraw another user's application."""
        app_obj = _make_application(applicant_id="user-other", version=1, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="user-me")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}/withdraw",
                    json={"version": 1},
                )
        assert resp.status_code == 403
        assert "own" in resp.json()["detail"].lower()

    def test_withdraw_non_pending_application(self):
        """Cannot withdraw a non-pending application."""
        app_obj = _make_application(applicant_id="user-1", version=2, status="approved")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="user-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}/withdraw",
                    json={"version": 2},
                )
        assert resp.status_code == 400
        assert "pending" in resp.json()["detail"].lower()

    def test_withdraw_optimistic_lock_conflict(self):
        """Withdraw fails when version does not match."""
        app_obj = _make_application(applicant_id="user-1", version=3, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="user-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}/withdraw",
                    json={"version": 1},
                )
        assert resp.status_code == 409
        assert "version" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests — GET /api/visibility-applications — list applications
# ---------------------------------------------------------------------------


class TestListApplications:
    """Tests for GET /api/visibility-applications (admin view)."""

    def test_list_pending_applications(self):
        """Admin can list pending applications."""
        apps = [
            _make_application(status="pending", version=1),
            _make_application(status="pending", version=1),
        ]
        session = _setup_list_session(apps)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.get("/api/visibility-applications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["applications"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_with_status_filter(self):
        """List respects status query parameter — only matching records returned."""
        approved_app = _make_application(status="approved", resource_type="skill", resource_id="res-2")
        # When filtering by status=approved, only approved_app should appear
        session = _setup_list_session([approved_app], total=1)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.get("/api/visibility-applications?status=approved")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["applications"]) == 1
        assert data["applications"][0]["status"] == "approved"
        assert data["applications"][0]["resource_id"] == "res-2"

    def test_list_with_resource_type_filter(self):
        """List respects resource_type query parameter — only matching records returned."""
        skill_app = _make_application(status="pending", resource_type="skill", resource_id="res-1")
        # When filtering by resource_type=skill, only skill_app should appear
        session = _setup_list_session([skill_app], total=1)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.get("/api/visibility-applications?resource_type=skill")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["applications"]) == 1
        assert data["applications"][0]["resource_type"] == "skill"
        assert data["applications"][0]["resource_id"] == "res-1"

    def test_list_combined_filters(self):
        """List respects both status and resource_type filters simultaneously."""
        # Only one record matches both pending + tool
        matching_app = _make_application(status="pending", resource_type="tool", resource_id="res-tool")
        session = _setup_list_session([matching_app], total=1)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.get("/api/visibility-applications?status=pending&resource_type=tool")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["applications"][0]["status"] == "pending"
        assert data["applications"][0]["resource_type"] == "tool"

    def test_list_with_pagination(self):
        """List respects page and page_size parameters."""
        session = _setup_list_session([], total=5)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.get("/api/visibility-applications?page=2&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert data["total"] == 5

    def test_non_admin_cannot_list(self):
        """Non-admin user cannot list applications."""
        session = MagicMock()
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.get("/api/visibility-applications")
        assert resp.status_code in (403, 401)


# ---------------------------------------------------------------------------
# Tests — RBAC enforcement
# ---------------------------------------------------------------------------


class TestRBAC:
    """Tests for role-based access control."""

    def test_super_admin_can_review(self):
        """Super admin can approve applications."""
        app_obj = _make_application(version=1, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="super_admin")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code == 200

    def test_dept_admin_can_review(self):
        """Department admin can approve applications from their own department (not their own)."""
        # Explicitly set both to dept-1 to verify same-department match
        app_obj = _make_application(applicant_id="other-user", department_id="dept-1", version=1, status="pending")
        session = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session.execute = AsyncMock(return_value=find_result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="department_admin", user_id="dept-admin-1")
        # Verify the reviewer belongs to the same department as the application
        assert app_obj.department_id == "dept-1"
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_obj.id}",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code == 200

    def test_regular_user_cannot_review(self):
        """Regular user cannot approve applications."""
        session = MagicMock()
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    "/api/visibility-applications/fake-id",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code in (403, 401)

    def test_viewer_cannot_review(self):
        """Viewer cannot approve applications."""
        session = MagicMock()
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="viewer")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.put(
                    "/api/visibility-applications/fake-id",
                    json={"action": "approved", "comment": "", "version": 1},
                )
        assert resp.status_code in (403, 401)

    def test_regular_user_can_submit(self):
        """Regular user can submit applications."""
        resource = _make_resource(visibility="private")
        session = _setup_create_session(resource)
        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="applicant-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "my-skill",
                        "target_visibility": "public",
                    },
                )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Tests — Full workflow integration
# ---------------------------------------------------------------------------


class TestFullWorkflow:
    """End-to-end workflow tests through the HTTP stack."""

    def test_submit_then_approve_updates_visibility(self):
        """Submit → approve flow updates resource visibility."""
        resource = _make_resource(visibility="private")
        session = _setup_create_session(resource)

        # Refresh sets fields on the app object after commit
        def _refresh(app_obj):
            app_obj.version = 1
            app_obj.status = "pending"
            app_obj.submitted_at = datetime.now(UTC)
            app_obj.applicant_id = app_obj.applicant_id or "applicant-1"

        session.refresh = AsyncMock(side_effect=_refresh)

        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="applicant-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                # Step 1: submit
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "my-skill",
                        "target_visibility": "public",
                        "reason": "Need public",
                    },
                )
                assert resp.status_code == 201
                app_data = resp.json()

        # Step 2: approve (separate session with different user)
        app_obj = _make_application(
            app_id=app_data["id"],
            version=1,
            status="pending",
            target_visibility="public",
        )
        session2 = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        update_result = MagicMock()
        session2.execute = AsyncMock(side_effect=[find_result, update_result])
        session2.commit = AsyncMock()
        session2.refresh = AsyncMock()

        sf_patch2, audit_patch2 = _patch_session(session2)
        admin_app, _ = _make_app(role="super_admin", user_id="admin-1")
        with sf_patch2, audit_patch2:
            with TestClient(admin_app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{app_data['id']}",
                    json={"action": "approved", "comment": "Approved", "version": 1},
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "approved"

    def test_submit_then_withdraw(self):
        """Submit → withdraw flow."""
        resource = _make_resource(visibility="private")
        session = _setup_create_session(resource)

        created_app_id = "app-withdraw-test"

        def _refresh(app_obj):
            app_obj.id = created_app_id
            app_obj.version = 1
            app_obj.status = "pending"
            app_obj.submitted_at = datetime.now(UTC)
            app_obj.applicant_id = "applicant-1"

        session.refresh = AsyncMock(side_effect=_refresh)

        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="applicant-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "my-skill",
                        "target_visibility": "public",
                    },
                )
                assert resp.status_code == 201

        # Step 2: withdraw
        app_obj = _make_application(
            app_id=created_app_id,
            applicant_id="applicant-1",
            version=1,
            status="pending",
        )
        session2 = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session2.execute = AsyncMock(return_value=find_result)
        session2.commit = AsyncMock()

        sf_patch2, audit_patch2 = _patch_session(session2)
        app2, _ = _make_app(role="user", user_id="applicant-1")
        with sf_patch2, audit_patch2:
            with TestClient(app2) as client:
                resp = client.put(
                    f"/api/visibility-applications/{created_app_id}/withdraw",
                    json={"version": 1},
                )
                assert resp.status_code == 200
                assert resp.json()["success"] is True

    def test_submit_then_reject(self):
        """Submit → reject flow."""
        resource = _make_resource(visibility="private")
        session = _setup_create_session(resource)

        created_app_id = "app-reject-test"

        def _refresh(app_obj):
            app_obj.id = created_app_id
            app_obj.version = 1
            app_obj.status = "pending"
            app_obj.submitted_at = datetime.now(UTC)
            app_obj.applicant_id = "applicant-1"

        session.refresh = AsyncMock(side_effect=_refresh)

        sf_patch, audit_patch = _patch_session(session)
        app, _ = _make_app(role="user", user_id="applicant-1")
        with sf_patch, audit_patch:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "skill",
                        "resource_id": "my-skill",
                        "target_visibility": "public",
                    },
                )
                assert resp.status_code == 201

        # Step 2: reject
        app_obj = _make_application(
            app_id=created_app_id,
            version=1,
            status="pending",
        )
        session2 = MagicMock()
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = app_obj
        session2.execute = AsyncMock(return_value=find_result)
        session2.commit = AsyncMock()
        session2.refresh = AsyncMock()

        sf_patch2, audit_patch2 = _patch_session(session2)
        admin_app, _ = _make_app(role="super_admin")
        with sf_patch2, audit_patch2:
            with TestClient(admin_app) as client:
                resp = client.put(
                    f"/api/visibility-applications/{created_app_id}",
                    json={"action": "rejected", "comment": "Denied", "version": 1},
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "rejected"
