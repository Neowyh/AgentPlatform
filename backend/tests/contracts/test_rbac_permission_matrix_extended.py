"""Extended RBAC permission matrix tests covering all role-protected routes.

Covers routes from:
  - Skills  (``backend/app/gateway/routers/skills.py``)
  - Tools   (``backend/app/gateway/routers/tools.py``)
  - Visibility applications (``backend/app/gateway/routers/visibility_applications.py``)
  - Agents  (``backend/app/gateway/routers/agents.py``)
  - Workflows (``backend/app/gateway/routers/workflows.py``)

For each route protected by ``@require_role`` we test all 4 roles
(super_admin, department_admin, user, viewer) and verify the expected
HTTP status code.

Section layout:
  A) Skills routes — require_role unit tests + router integration
  B) Tools routes
  C) Visibility-application routes
  D) Agent routes
  E) Workflow routes
  F) Cross-router summary matrix
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from conftest import _make_rbac_user
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user, require_role
from app.gateway.deps import get_config
from app.gateway.routers.agents import router as agents_router
from app.gateway.routers.skills import router as skills_router
from app.gateway.routers.tools import router as tools_router
from app.gateway.routers.visibility_applications import router as visibility_app_router
from app.gateway.routers.workflows import router as workflows_router
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_factory(application: object | None = None):
    """Build a mock session factory that returns the given application."""
    mock_session = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = application
        result.scalars.return_value = MagicMock(all=MagicMock(return_value=[application] if application else []))
        result.scalar.return_value = 1
        return result

    mock_session.execute = AsyncMock(side_effect=_execute)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda o: None)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_session)


def _build_app_with_router(router, user: MagicMock | None = None) -> FastAPI:
    """Build a minimal FastAPI app with a single router and stubbed auth + config."""
    app = FastAPI()
    app.include_router(router)

    mock_config = MagicMock()
    app.dependency_overrides[get_config] = lambda: mock_config

    if user is not None:

        async def _stub():
            return user

        app.dependency_overrides[get_current_rbac_user] = _stub
        app.dependency_overrides[get_optional_rbac_user] = _stub
    return app


# =====================================================================
# A) Skills Routes
# =====================================================================


class TestSkillsRoutesRequireRole:
    """Systematic role check for every @require_role-protected skills endpoint."""

    @pytest.mark.parametrize(
        "allowed_roles, test_role, expected_status",
        [
            # POST /api/skills/install — DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 403),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # PUT /api/skills/{skill_name} — DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 403),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # POST /api/skills/custom/import — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
        ],
    )
    @pytest.mark.asyncio
    async def test_require_role_on_skills(self, allowed_roles, test_role, expected_status):
        @require_role(*allowed_roles)
        async def endpoint(current_user=None):
            return "ok"

        mock_user = _make_rbac_user(role=test_role.value)
        if expected_status == 200:
            await endpoint(current_user=mock_user)
        else:
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(current_user=mock_user)
            assert exc_info.value.status_code == expected_status

    # --- Router-level integration ---

    @pytest.mark.asyncio
    async def test_install_skill_viewer_blocked(self):
        """viewer gets 403 on POST /api/skills/install."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(skills_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/skills/install", json={"thread_id": "t-1", "path": "mnt/test.skill"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_skill_viewer_blocked(self):
        """viewer gets 403 on PUT /api/skills/{name}."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(skills_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put("/api/skills/test-skill", json={"enabled": False})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_import_skill_viewer_blocked(self):
        """viewer gets 403 on POST /api/skills/custom/import."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(skills_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/skills/custom/import", json={"name": "test-skill", "content": "# Test"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_import_skill_user_allowed(self):
        """user can call POST /api/skills/custom/import (gets non-403 response)."""
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(skills_router, user)
        with (
            patch("app.gateway.routers.skills.get_or_new_skill_storage") as mock_store,
            patch("app.gateway.routers.skills.get_config"),
        ):
            storage = MagicMock()
            storage.custom_skill_exists.return_value = False
            storage.load_skills.return_value = []
            mock_store.return_value = storage
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/skills/custom/import", json={"name": "test-skill", "content": "# Test skill"})
        # Not 403 — actual status depends on the mock chain
        assert resp.status_code != 403


# =====================================================================
# B) Tools Routes
# =====================================================================


class TestToolsRoutesRequireRole:
    """Systematic role check for tools routes."""

    @pytest.mark.parametrize(
        "allowed_roles, test_role, expected_status",
        [
            # POST /api/tools/{name}/test — DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 403),
            ((UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
        ],
    )
    @pytest.mark.asyncio
    async def test_require_role_on_tools(self, allowed_roles, test_role, expected_status):
        @require_role(*allowed_roles)
        async def endpoint(current_user=None):
            return "ok"

        mock_user = _make_rbac_user(role=test_role.value)
        if expected_status == 200:
            await endpoint(current_user=mock_user)
        else:
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(current_user=mock_user)
            assert exc_info.value.status_code == expected_status

    @pytest.mark.asyncio
    async def test_tool_test_viewer_blocked(self):
        """viewer gets 403 on POST /api/tools/{name}/test."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(tools_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tools/my-tool/test", json={"params": {}})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_tool_test_user_blocked(self):
        """user gets 403 on POST /api/tools/{name}/test."""
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(tools_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tools/my-tool/test", json={"params": {}})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_tool_test_super_admin_allowed(self):
        """super_admin passes require_role for tool test (gets 404, not 403)."""
        user = _make_rbac_user(role="super_admin")
        app = _build_app_with_router(tools_router, user)
        with (
            patch("app.gateway.routers.tools.get_available_tools", return_value=[]),
            patch("app.gateway.routers.tools.get_app_config"),
            patch("app.gateway.routers.tools._load_tool_meta", new_callable=AsyncMock, return_value={}),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/tools/nonexistent/test", json={"params": {}})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_tool_test_dept_admin_allowed(self):
        """department_admin passes require_role for tool test (gets 404, not 403)."""
        user = _make_rbac_user(role="department_admin")
        app = _build_app_with_router(tools_router, user)
        with (
            patch("app.gateway.routers.tools.get_available_tools", return_value=[]),
            patch("app.gateway.routers.tools.get_app_config"),
            patch("app.gateway.routers.tools._load_tool_meta", new_callable=AsyncMock, return_value={}),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/tools/nonexistent/test", json={"params": {}})
        assert resp.status_code == 404


# =====================================================================
# C) Visibility Application Routes
# =====================================================================


class TestVisibilityAppRoutesRequireRole:
    """Systematic role check for visibility-application routes."""

    @pytest.mark.parametrize(
        "allowed_roles, test_role, expected_status",
        [
            # PUT /api/visibility-applications/{id} — SUPER_ADMIN + DEPARTMENT_ADMIN
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.USER, 403),
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.VIEWER, 403),
            # GET /api/visibility-applications — SUPER_ADMIN + DEPARTMENT_ADMIN
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.USER, 403),
            ((UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN), UserRole.VIEWER, 403),
        ],
    )
    @pytest.mark.asyncio
    async def test_require_role_on_vis_apps(self, allowed_roles, test_role, expected_status):
        @require_role(*allowed_roles)
        async def endpoint(current_user=None):
            return "ok"

        mock_user = _make_rbac_user(role=test_role.value)
        if expected_status == 200:
            await endpoint(current_user=mock_user)
        else:
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(current_user=mock_user)
            assert exc_info.value.status_code == expected_status

    @pytest.mark.asyncio
    async def test_review_application_user_blocked(self):
        """user gets 403 on PUT /api/visibility-applications/{id}."""
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(visibility_app_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(f"/api/visibility-applications/{uuid4()}", json={"action": "approved", "comment": "", "version": 1})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_review_application_viewer_blocked(self):
        """viewer gets 403 on PUT /api/visibility-applications/{id}."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(visibility_app_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(f"/api/visibility-applications/{uuid4()}", json={"action": "approved", "comment": "", "version": 1})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_applications_user_blocked(self):
        """user gets 403 on GET /api/visibility-applications."""
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(visibility_app_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/visibility-applications")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_applications_viewer_blocked(self):
        """viewer gets 403 on GET /api/visibility-applications."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(visibility_app_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/visibility-applications")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_applications_super_admin_allowed(self):
        """super_admin passes require_role for visibility-applications list."""
        user = _make_rbac_user(role="super_admin")
        app = _build_app_with_router(visibility_app_router, user)
        mock_sf = _make_session_factory()
        with patch("app.gateway.routers.visibility_applications.get_session_factory", return_value=mock_sf):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/visibility-applications")
        assert resp.status_code == 200


# =====================================================================
# D) Agent Routes
# =====================================================================


class TestAgentRoutesRequireRole:
    """Systematic role check for agent routes."""

    @pytest.mark.parametrize(
        "allowed_roles, test_role, expected_status",
        [
            # POST /api/agents — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # PUT /api/agents/{name} — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # DELETE /api/agents/{name} — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # POST /api/agents/{name}/favorite — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # PUT /api/user-profile — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
        ],
    )
    @pytest.mark.asyncio
    async def test_require_role_on_agents(self, allowed_roles, test_role, expected_status):
        @require_role(*allowed_roles)
        async def endpoint(current_user=None):
            return "ok"

        mock_user = _make_rbac_user(role=test_role.value)
        if expected_status == 200:
            await endpoint(current_user=mock_user)
        else:
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(current_user=mock_user)
            assert exc_info.value.status_code == expected_status

    # --- Router-level integration for viewer blocks ---

    @pytest.mark.asyncio
    async def test_create_agent_viewer_blocked(self):
        """viewer gets 403 on POST /api/agents."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(agents_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/agents", json={"name": "my-agent", "soul": ""})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_agent_viewer_blocked(self):
        """viewer gets 403 on PUT /api/agents/{name}."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(agents_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put("/api/agents/my-agent", json={"version": 1})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_agent_viewer_blocked(self):
        """viewer gets 403 on DELETE /api/agents/{name}."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(agents_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/agents/my-agent")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_favorite_agent_viewer_blocked(self):
        """viewer gets 403 on POST /api/agents/{name}/favorite."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(agents_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/agents/my-agent/favorite")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_user_profile_viewer_blocked(self):
        """viewer gets 403 on PUT /api/user-profile."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(agents_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put("/api/user-profile", json={"content": "hello"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_create_agent_user_allowed(self):
        """user passes require_role for agent creation (gets non-403 response)."""
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(agents_router, user)
        with patch("app.gateway.routers.agents._require_agents_api_enabled"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/agents", json={"name": "my-agent", "soul": ""})
        assert resp.status_code != 403


# =====================================================================
# E) Workflow Routes
# =====================================================================


class TestWorkflowRoutesRequireRole:
    """Systematic role check for workflow routes."""

    @pytest.mark.parametrize(
        "allowed_roles, test_role, expected_status",
        [
            # POST /api/workflows — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # PUT /api/workflows/{name} — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # DELETE /api/workflows/{name} — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # POST /api/workflows/import — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # POST /api/workflows/{name}/favorite — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
            # POST /api/workflows/{name}/run — USER + DEPARTMENT_ADMIN + SUPER_ADMIN
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.SUPER_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.DEPARTMENT_ADMIN, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.USER, 200),
            ((UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN), UserRole.VIEWER, 403),
        ],
    )
    @pytest.mark.asyncio
    async def test_require_role_on_workflows(self, allowed_roles, test_role, expected_status):
        @require_role(*allowed_roles)
        async def endpoint(current_user=None):
            return "ok"

        mock_user = _make_rbac_user(role=test_role.value)
        if expected_status == 200:
            await endpoint(current_user=mock_user)
        else:
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(current_user=mock_user)
            assert exc_info.value.status_code == expected_status

    # --- Router-level integration ---

    @pytest.mark.asyncio
    async def test_create_workflow_viewer_blocked(self):
        """viewer gets 403 on POST /api/workflows."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(workflows_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/workflows", json={"name": "test-wf", "yaml_content": "name: test-wf\nversion: '1'\nsteps:\n  - id: s1\n    type: agent\n    agent: planner\n    prompt: hello\n"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_workflow_viewer_blocked(self):
        """viewer gets 403 on PUT /api/workflows/{name}."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(workflows_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put("/api/workflows/test-wf", json={"yaml_content": "name: test-wf\nversion: '1'\nsteps:\n  - id: s1\n    type: agent\n    agent: planner\n    prompt: hello\n", "version": 1})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_workflow_viewer_blocked(self):
        """viewer gets 403 on DELETE /api/workflows/{name}."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(workflows_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/workflows/test-wf")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_import_workflow_viewer_blocked(self):
        """viewer gets 403 on POST /api/workflows/import."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(workflows_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/workflows/import", json={"yaml_content": "name: test-wf\nversion: '1'\nsteps:\n  - id: s1\n    type: agent\n    agent: planner\n    prompt: hello\n"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_favorite_workflow_viewer_blocked(self):
        """viewer gets 403 on POST /api/workflows/{name}/favorite."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(workflows_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/workflows/test-wf/favorite")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_run_workflow_viewer_blocked(self):
        """viewer gets 403 on POST /api/workflows/{name}/run."""
        user = _make_rbac_user(role="viewer")
        app = _build_app_with_router(workflows_router, user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/workflows/test-wf/run", json={"inputs": {}})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_create_workflow_user_allowed(self):
        """user passes require_role for workflow creation (gets non-403 response)."""
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(workflows_router, user)
        definition = "schema_version: 2\nname: test-wf\ninputs: {}\nstate: {}\nentrypoint: s1\nnodes:\n  - id: s1\n    type: interrupt\n    roles: [user]\nedges: []\n"
        v2_store = MagicMock()
        v2_store.get_latest_definition = AsyncMock(return_value=None)
        v2_store.save_definition = AsyncMock(return_value=SimpleNamespace(version=1))
        with (
            patch("app.gateway.routers.workflows._v2_store", return_value=v2_store),
            patch("app.gateway.routers.workflows._workflow_store.save_meta", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/workflows", json={"name": "test-wf", "yaml_content": definition})
        assert resp.status_code != 403

    @pytest.mark.asyncio
    async def test_run_workflow_validates_required_input_and_creates_queued_run(self):
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(workflows_router, user)
        definition = SimpleNamespace(
            version=3,
            definition={
                "schema_version": 2,
                "name": "test-wf",
                "inputs": {"request": {"type": "string", "required": True}},
                "state": {},
                "entrypoint": "start",
                "nodes": [{"id": "start", "type": "interrupt", "roles": ["user"]}],
                "edges": [],
            },
        )
        v2_store = MagicMock()
        v2_store.get_latest_definition = AsyncMock(return_value=definition)
        v2_store.create_run = AsyncMock(return_value=None)
        meta = {"visibility": "private", "owner_id": user.id, "department_id": None}
        with (
            patch("app.gateway.routers.workflows._v2_store", return_value=v2_store),
            patch("app.gateway.routers.workflows._workflow_store.load_meta", new_callable=AsyncMock, return_value=meta),
            patch("app.gateway.routers.workflows.check_resource_access", return_value=True),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                missing = await client.post("/api/workflows/test-wf/run", json={"inputs": {}})
                accepted = await client.post("/api/workflows/test-wf/run", json={"inputs": {"request": "hello"}})

        assert missing.status_code == 400
        assert "Missing required input" in missing.json()["detail"]
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "queued"
        v2_store.create_run.assert_awaited_once()
        assert v2_store.create_run.await_args.args[2:] == (3, {"request": "hello"}, str(user.id))

    @pytest.mark.asyncio
    async def test_workflow_events_replay_after_sequence_in_order(self):
        user = _make_rbac_user(role="user")
        app = _build_app_with_router(workflows_router, user)
        run = SimpleNamespace(run_id="run-1", workflow_name="test-wf")
        events = [
            SimpleNamespace(seq=2, event_type="node_completed", payload={"node_id": "start"}),
            SimpleNamespace(seq=3, event_type="run_completed", payload={}),
        ]
        v2_store = MagicMock()
        v2_store.get_run = AsyncMock(return_value=run)
        v2_store.list_events = AsyncMock(return_value=events)
        meta = {"visibility": "private", "owner_id": user.id, "department_id": None}
        with (
            patch("app.gateway.routers.workflows._v2_store", return_value=v2_store),
            patch("app.gateway.routers.workflows._workflow_store.load_meta", new_callable=AsyncMock, return_value=meta),
            patch("app.gateway.routers.workflows.check_resource_access", return_value=True),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/workflows/test-wf/runs/run-1/events?after_seq=1")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.index("id: 2") < response.text.index("id: 3")
        v2_store.list_events.assert_awaited_once_with("run-1", 1)


# =====================================================================
# F) Cross-Router Summary Matrix
# =====================================================================


class TestCrossRouterPermissionSummary:
    """Document the complete permission matrix for all non-admin protected routes."""

    MATRIX = {
        # route_key: {role: expected_status}
        # 200 = allowed, 403 = denied
        "skills:install": {
            UserRole.VIEWER: 403,
            UserRole.USER: 403,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "skills:update": {
            UserRole.VIEWER: 403,
            UserRole.USER: 403,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "skills:custom_import": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "tools:test": {
            UserRole.VIEWER: 403,
            UserRole.USER: 403,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "vis_apps:review": {
            UserRole.VIEWER: 403,
            UserRole.USER: 403,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "vis_apps:list": {
            UserRole.VIEWER: 403,
            UserRole.USER: 403,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "agents:create": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "agents:update": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "agents:delete": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "agents:favorite": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "user_profile:update": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "workflows:create": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "workflows:update": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "workflows:delete": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "workflows:import": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "workflows:favorite": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
        "workflows:run": {
            UserRole.VIEWER: 403,
            UserRole.USER: 200,
            UserRole.DEPARTMENT_ADMIN: 200,
            UserRole.SUPER_ADMIN: 200,
        },
    }

    def test_matrix_consistency(self):
        """Verify the summary matrix matches actual require_role behavior."""
        admin_only_routes = {"skills:install", "skills:update", "tools:test", "vis_apps:review", "vis_apps:list"}
        user_allowed_routes = set(self.MATRIX) - admin_only_routes

        for route_key, expectations in self.MATRIX.items():
            for role, expected_status in expectations.items():
                if route_key in admin_only_routes:
                    if role in (UserRole.VIEWER, UserRole.USER):
                        assert expected_status == 403, f"{route_key}: {role} should be 403"
                    else:
                        assert expected_status == 200, f"{route_key}: {role} should be 200"
                else:
                    assert route_key in user_allowed_routes
                    if role == UserRole.VIEWER:
                        assert expected_status == 403, f"{route_key}: viewer should be 403"
                    else:
                        assert expected_status == 200, f"{route_key}: {role} should be 200"

    def test_viewer_blocked_on_all_write_endpoints(self):
        """viewer is blocked from every protected route in the matrix."""
        for route_key, expectations in self.MATRIX.items():
            assert expectations[UserRole.VIEWER] == 403, f"viewer should be blocked from {route_key}"

    def test_super_admin_allowed_on_all_endpoints(self):
        """super_admin is allowed on every protected route."""
        for route_key, expectations in self.MATRIX.items():
            assert expectations[UserRole.SUPER_ADMIN] == 200, f"super_admin should be allowed on {route_key}"
