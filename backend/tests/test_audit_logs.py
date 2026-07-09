"""Tests for admin audit-log read permissions."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user
from app.gateway.routers.audit_logs import router as audit_logs_router

pytestmark = pytest.mark.no_auto_user


def _make_user(role: str = "department_admin") -> MagicMock:
    user = MagicMock()
    user.id = "admin-1"
    user.role = role
    user.department_id = "dept-1"
    user.disabled = False
    return user


def _make_app(role: str = "department_admin"):
    user = _make_user(role)
    app = make_authed_test_app()
    app.include_router(audit_logs_router)

    async def _stub_rbac():
        return user

    app.dependency_overrides[get_current_rbac_user] = _stub_rbac
    return app


def _make_session_factory(session: AsyncMock) -> MagicMock:
    sf_mock = MagicMock()
    sf_mock.return_value.__aenter__ = AsyncMock(return_value=session)
    sf_mock.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf_mock


def _make_audit_log() -> MagicMock:
    row = MagicMock()
    row.id = "log-1"
    row.actor_id = "user-1"
    row.action = "resource.update"
    row.resource_type = "tool"
    row.resource_id = "tool-a"
    row.detail = "changed visibility"
    row.ip_address = "127.0.0.1"
    row.created_at = datetime(2024, 1, 1)
    return row


@patch("app.gateway.routers.audit_logs.get_session_factory")
def test_department_admin_can_list_audit_logs(mock_sf):
    session = AsyncMock()
    row = _make_audit_log()
    call_count = {"n": 0}

    async def _execute(stmt):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.scalar = MagicMock(return_value=1)
        else:
            result.scalars.return_value.all.return_value = [row]
        return result

    session.execute = AsyncMock(side_effect=_execute)
    mock_sf.return_value = _make_session_factory(session)

    with TestClient(_make_app("department_admin")) as client:
        resp = client.get("/api/admin/audit-logs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "log-1"


@patch("app.gateway.routers.audit_logs.get_session_factory")
def test_department_admin_can_view_audit_log_detail(mock_sf):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _make_audit_log()
    session.execute = AsyncMock(return_value=result)
    mock_sf.return_value = _make_session_factory(session)

    with TestClient(_make_app("department_admin")) as client:
        resp = client.get("/api/admin/audit-logs/log-1")

    assert resp.status_code == 200
    assert resp.json()["id"] == "log-1"
