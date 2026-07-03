"""Tests for visibility_applications API router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.visibility_applications import router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: str = "user", dept_id: str | None = None) -> MagicMock:
    u = MagicMock()
    u.id = uuid4()
    u.role = role
    u.department_id = dept_id
    return u


def _make_app(
    *,
    id: str | None = None,
    resource_type: str = "tool",
    resource_id: str = "res-1",
    applicant_id: str | None = None,
    current_visibility: str = "private",
    target_visibility: str = "department",
    department_id: str | None = None,
    reason: str = "",
    status: str = "pending",
    submitted_at: str = "2025-01-01T00:00:00",
    reviewed_by: str | None = None,
    reviewed_at: str | None = None,
    review_comment: str = "",
    version: int = 1,
) -> MagicMock:
    app = MagicMock()
    app.id = id or str(uuid4())
    app.resource_type = resource_type
    app.resource_id = resource_id
    app.applicant_id = applicant_id or str(uuid4())
    app.current_visibility = current_visibility
    app.target_visibility = target_visibility
    app.department_id = department_id
    app.reason = reason
    app.status = status
    app.submitted_at = submitted_at
    app.reviewed_by = reviewed_by
    app.reviewed_at = reviewed_at
    app.review_comment = review_comment
    app.version = version
    return app


def _make_session_factory(scalar_result=None, scalars_result=None):
    """Create a mock session factory that works with `async with sf() as session:`."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    if scalars_result is not None:
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = scalars_result
        mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda o: None)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    # MagicMock(return_value=...) makes sf() return mock_session synchronously
    mock_sf = MagicMock(return_value=mock_session)
    return mock_sf


def _build_app(user: MagicMock | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    _user = user or _make_user()

    async def _stub_rbac_user():
        return _user

    app.dependency_overrides[get_current_rbac_user] = _stub_rbac_user
    return app


# ---------------------------------------------------------------------------
# POST /api/visibility-applications
# ---------------------------------------------------------------------------


class TestCreateApplication:
    @pytest.mark.asyncio
    async def test_creates_application(self):
        user = _make_user()
        app_obj = _build_app(user)

        mock_sf = _make_session_factory(scalar_result=None)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "tool",
                        "resource_id": "my-tool",
                        "target_visibility": "public",
                        "reason": "Need public access",
                    },
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_type"] == "tool"
        assert data["resource_id"] == "my-tool"
        assert data["target_visibility"] == "public"
        assert data["reason"] == "Need public access"
        assert data["status"] == "pending"
        assert data["version"] == 1
        assert data["applicant_id"] == str(user.id)

    @pytest.mark.asyncio
    async def test_rejects_duplicate_pending(self):
        user = _make_user()
        app_obj = _build_app(user)

        existing = _make_app()
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.post(
                    "/api/visibility-applications",
                    json={
                        "resource_type": "tool",
                        "resource_id": "my-tool",
                        "target_visibility": "public",
                        "reason": "",
                    },
                )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_resource_type(self):
        user = _make_user()
        app_obj = _build_app(user)

        async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
            resp = await client.post(
                "/api/visibility-applications",
                json={
                    "resource_type": "invalid",
                    "resource_id": "my-tool",
                    "target_visibility": "public",
                },
            )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/visibility-applications/{id}/withdraw
# ---------------------------------------------------------------------------


class TestWithdrawApplication:
    @pytest.mark.asyncio
    async def test_withdraws_own_application(self):
        user = _make_user()
        app_obj = _build_app(user)

        existing = _make_app(applicant_id=str(user.id), status="pending")
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(f"/api/visibility-applications/{existing.id}/withdraw")

        assert resp.status_code == 200
        assert resp.json()["status"] == "withdrawn"

    @pytest.mark.asyncio
    async def test_rejects_withdraw_of_others_application(self):
        user = _make_user()
        app_obj = _build_app(user)

        other_user_id = str(uuid4())
        existing = _make_app(applicant_id=other_user_id, status="pending")
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(f"/api/visibility-applications/{existing.id}/withdraw")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_withdraw_of_non_pending(self):
        user = _make_user()
        app_obj = _build_app(user)

        existing = _make_app(applicant_id=str(user.id), status="approved")
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(f"/api/visibility-applications/{existing.id}/withdraw")

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_not_found(self):
        user = _make_user()
        app_obj = _build_app(user)

        mock_sf = _make_session_factory(scalar_result=None)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(f"/api/visibility-applications/{uuid4()}/withdraw")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/visibility-applications/{id} — review
# ---------------------------------------------------------------------------


class TestReviewApplication:
    @pytest.mark.asyncio
    async def test_approves_application(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        existing = _make_app(status="pending", version=1)
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/visibility-applications/{existing.id}",
                    json={"action": "approved", "comment": "Looks good", "version": 1},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["review_comment"] == "Looks good"
        assert data["version"] == 2

    @pytest.mark.asyncio
    async def test_rejects_application(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        existing = _make_app(status="pending", version=1)
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/visibility-applications/{existing.id}",
                    json={"action": "rejected", "comment": "No", "version": 1},
                )

        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_rejects_review_with_wrong_version(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        existing = _make_app(status="pending", version=2)
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/visibility-applications/{existing.id}",
                    json={"action": "approved", "comment": "", "version": 1},
                )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_rejects_review_by_user_role(self):
        user = _make_user(role="user")
        app_obj = _build_app(user)

        async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
            resp = await client.put(
                f"/api/visibility-applications/{uuid4()}",
                json={"action": "approved", "comment": "", "version": 1},
            )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_review_not_found(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        mock_sf = _make_session_factory(scalar_result=None)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/visibility-applications/{uuid4()}",
                    json={"action": "approved", "comment": "", "version": 1},
                )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_review_already_reviewed(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        existing = _make_app(status="approved", version=2)
        mock_sf = _make_session_factory(scalar_result=existing)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.put(
                    f"/api/visibility-applications/{existing.id}",
                    json={"action": "rejected", "comment": "", "version": 2},
                )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/visibility-applications
# ---------------------------------------------------------------------------


class TestListApplications:
    @pytest.mark.asyncio
    async def test_lists_pending_for_admin(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        apps = [_make_app(), _make_app()]
        mock_sf = _make_session_factory(scalars_result=apps)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.get("/api/visibility-applications")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["applications"]) == 2

    @pytest.mark.asyncio
    async def test_rejects_list_by_user_role(self):
        user = _make_user(role="user")
        app_obj = _build_app(user)

        async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
            resp = await client.get("/api/visibility-applications")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_lists_by_resource_type(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        apps = [_make_app(resource_type="skill")]
        mock_sf = _make_session_factory(scalars_result=apps)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.get("/api/visibility-applications?resource_type=skill")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["applications"]) == 1
        assert data["applications"][0]["resource_type"] == "skill"

    @pytest.mark.asyncio
    async def test_lists_by_status(self):
        user = _make_user(role="super_admin")
        app_obj = _build_app(user)

        apps = [_make_app(status="approved")]
        mock_sf = _make_session_factory(scalars_result=apps)

        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
                resp = await client.get("/api/visibility-applications?status=approved")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["applications"]) == 1
        assert data["applications"][0]["status"] == "approved"
