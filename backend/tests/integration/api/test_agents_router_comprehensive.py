"""Comprehensive mocked tests for the agents router.

Tests private helpers, RBAC logic, error paths, and edge cases that are hard
to exercise with the real filesystem.  The existing ``test_custom_agent.py``
covers the happy-path CRUD with real files; this file focuses on mocking
dependencies to validate guard clauses, visibility rules, and exception
handling.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user

# Import private helpers directly for unit testing.
from app.gateway.routers.agents import (
    AgentResponse,
    _agent_config_to_response,
    _is_shared_only,
    _load_agent_meta,
    _normalize_agent_name,
    _require_agents_api_enabled,
    _save_agent_meta,
    _validate_agent_name,
    router,
)
from ideer.config.agents_api_config import AgentsApiConfig
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "test-agent"
USER_ID = "user-1"
DEPT_ID = "dept-1"
OTHER_USER_ID = "other-user"
OTHER_DEPT_ID = "other-dept"


class _ScalarResult:
    def __init__(self, resource=None, resources=None):
        self._resource = resource
        self._resources = resources or ([] if resource is None else [resource])

    def scalar_one_or_none(self):
        return self._resource

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._resources))


class _AsyncSession:
    def __init__(self, *, resource=None, resources=None, execute_error: Exception | None = None):
        self.resource = resource
        self.resources = resources
        self.execute_error = execute_error
        self.added = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _stmt):
        if self.execute_error is not None:
            raise self.execute_error
        return _ScalarResult(self.resource, self.resources)

    def add(self, resource):
        self.added.append(resource)

    async def commit(self):
        self.committed = True


def _session_factory(session: _AsyncSession):
    return lambda: session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent_resp(**overrides) -> AgentResponse:
    """Create a valid AgentResponse instance for use in mock return values."""
    defaults = dict(
        name=AGENT_NAME,
        description="desc",
        model=None,
        tool_groups=None,
        skills=None,
        soul="",
        read_only=False,
        visibility="private",
        owner_id=USER_ID,
        department_id=DEPT_ID,
    )
    defaults.update(overrides)
    return AgentResponse(**defaults)


def _make_user(
    user_id: str = USER_ID,
    role: UserRole = UserRole.USER,
    department_id: str | None = DEPT_ID,
) -> MagicMock:
    """Create a mock UserModel with the given attributes."""
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = False
    return user


def _build_app(user: MagicMock | None = None) -> FastAPI:
    """Build a test FastAPI app with the agents router and auth overrides."""
    from _router_auth_helpers import make_authed_test_app

    app = make_authed_test_app()
    app.include_router(router)

    if user is not None:

        async def _current_user():
            return user

        async def _optional_user():
            return user

        app.dependency_overrides[get_current_rbac_user] = _current_user
        app.dependency_overrides[get_optional_rbac_user] = _optional_user

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_deps():
    """Yield common mocks for get_paths, get_effective_user_id, and API config."""
    mock_paths = MagicMock()
    mock_user_md = MagicMock()
    mock_paths.user_md_file = mock_user_md
    mock_paths.base_dir = MagicMock()

    with (
        patch("app.gateway.routers.agents.get_paths", return_value=mock_paths),
        patch("ideer.config.agents_config.get_paths", return_value=mock_paths),
        patch("app.gateway.routers.agents.get_effective_user_id", return_value=USER_ID),
        patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=True)),
        patch("app.gateway.routers.agents.check_resource_modify", return_value=True),
    ):
        yield mock_paths, mock_user_md


@pytest.fixture()
def viewer_client(mock_deps):
    """TestClient with a viewer-role user."""
    user = _make_user(role=UserRole.VIEWER)
    app = _build_app(user)
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def user_client(mock_deps):
    """TestClient with a regular user-role user."""
    user = _make_user(role=UserRole.USER)
    app = _build_app(user)
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def dept_admin_client(mock_deps):
    """TestClient with a department_admin-role user."""
    user = _make_user(role=UserRole.DEPARTMENT_ADMIN)
    app = _build_app(user)
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def super_admin_client(mock_deps):
    """TestClient with a super_admin-role user."""
    user = _make_user(role=UserRole.SUPER_ADMIN)
    app = _build_app(user)
    with TestClient(app) as client:
        yield client


# ===========================================================================
# _validate_agent_name
# ===========================================================================


class TestValidateAgentName:
    """Validate agent name against allowed pattern."""

    @pytest.mark.parametrize(
        "name",
        ["agent", "my-agent", "Agent123", "A", "a-b-c-d"],
    )
    def test_valid_names(self, name):
        _validate_agent_name(name)

    @pytest.mark.parametrize(
        "name",
        ["", "agent_name", "agent.name", "agent name", "agent!", "a@b", "a/b"],
    )
    def test_invalid_names_raise_422(self, name):
        with pytest.raises(HTTPException) as exc_info:
            _validate_agent_name(name)
        assert exc_info.value.status_code == 422

    def test_hyphen_only(self):
        _validate_agent_name("-")

    def test_digits_only(self):
        _validate_agent_name("12345")


# ===========================================================================
# _normalize_agent_name
# ===========================================================================


class TestNormalizeAgentName:
    def test_lowercases(self):
        assert _normalize_agent_name("MyAgent") == "myagent"

    def test_already_lowercase(self):
        assert _normalize_agent_name("agent") == "agent"

    def test_mixed_case(self):
        assert _normalize_agent_name("Code-Reviewer") == "code-reviewer"


# ===========================================================================
# _require_agents_api_enabled
# ===========================================================================


class TestRequireAgentsApiEnabled:
    def test_raises_when_disabled(self):
        with patch(
            "app.gateway.routers.agents.get_agents_api_config",
            return_value=AgentsApiConfig(enabled=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                _require_agents_api_enabled()
            assert exc_info.value.status_code == 403

    def test_passes_when_enabled(self):
        with patch(
            "app.gateway.routers.agents.get_agents_api_config",
            return_value=AgentsApiConfig(enabled=True),
        ):
            _require_agents_api_enabled()


class TestAgentMetadataDbHelpers:
    @pytest.mark.asyncio
    async def test_load_agent_meta_reads_resource_metadata(self):
        resource = SimpleNamespace(
            visibility="department",
            owner_id=USER_ID,
            department_id=DEPT_ID,
            version=7,
            is_favorited=True,
            created_at=None,
        )
        session = _AsyncSession(resource=resource)

        with patch("ideer.persistence.engine.get_session_factory", return_value=_session_factory(session)):
            meta = await _load_agent_meta(AGENT_NAME, USER_ID)

        assert meta == {
            "visibility": "department",
            "owner_id": USER_ID,
            "department_id": DEPT_ID,
            "version": 7,
            "is_favorited": True,
            "created_at": None,
        }

    @pytest.mark.asyncio
    async def test_load_agent_meta_falls_back_after_db_error(self):
        meta_file = MagicMock()
        meta_file.exists.return_value = False
        session = _AsyncSession(execute_error=RuntimeError("db down"))

        with (
            patch("ideer.persistence.engine.get_session_factory", return_value=_session_factory(session)),
            patch("app.gateway.routers.agents._agent_meta_path", return_value=meta_file),
        ):
            meta = await _load_agent_meta(AGENT_NAME, USER_ID)

        assert meta == {}

    @pytest.mark.asyncio
    async def test_save_agent_meta_updates_existing_resource(self):
        resource = SimpleNamespace(visibility="private", department_id=None, version=1)
        session = _AsyncSession(resource=resource)

        with patch("ideer.persistence.engine.get_session_factory", return_value=_session_factory(session)):
            await _save_agent_meta(
                AGENT_NAME,
                USER_ID,
                {"visibility": "public", "department_id": DEPT_ID, "owner_id": USER_ID},
            )

        assert resource.visibility == "public"
        assert resource.department_id == DEPT_ID
        assert session.added == []
        assert session.committed is True

    @pytest.mark.asyncio
    async def test_save_agent_meta_inserts_when_missing(self):
        session = _AsyncSession(resource=None)

        with patch("ideer.persistence.engine.get_session_factory", return_value=_session_factory(session)):
            await _save_agent_meta(
                AGENT_NAME,
                USER_ID,
                {"visibility": "department", "department_id": DEPT_ID, "owner_id": USER_ID},
            )

        assert len(session.added) == 1
        added = session.added[0]
        assert added.resource_type == "agent"
        assert added.resource_id == AGENT_NAME
        assert added.owner_id == USER_ID
        assert added.visibility == "department"
        assert session.committed is True


class TestToggleAgentFavoriteEndpoint:
    def test_toggles_existing_resource(self, user_client, mock_deps):
        resource = SimpleNamespace(is_favorited=False)
        session = _AsyncSession(resource=resource)

        with patch("app.gateway.routers.agents.get_session_factory", return_value=_session_factory(session)):
            resp = user_client.post(f"/api/agents/{AGENT_NAME}/favorite")

        assert resp.status_code == 200
        assert resp.json() == {"success": True, "is_favorited": True}
        assert resource.is_favorited is True
        assert session.committed is True

    def test_returns_404_for_missing_resource(self, user_client, mock_deps):
        session = _AsyncSession(resource=None)

        with patch("app.gateway.routers.agents.get_session_factory", return_value=_session_factory(session)):
            resp = user_client.post(f"/api/agents/{AGENT_NAME}/favorite")

        assert resp.status_code == 404

    def test_returns_500_when_database_unavailable(self, user_client, mock_deps):
        with patch("app.gateway.routers.agents.get_session_factory", return_value=None):
            resp = user_client.post(f"/api/agents/{AGENT_NAME}/favorite")

        assert resp.status_code == 500


# ===========================================================================
# _is_shared_only
# ===========================================================================


class TestIsSharedOnly:
    def test_shared_only_true(self):
        mock_paths = MagicMock()
        mock_paths.agent_dir.return_value.exists.return_value = True
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        with patch("app.gateway.routers.agents.get_paths", return_value=mock_paths):
            assert _is_shared_only("agent", "u1") is True

    def test_not_shared_when_user_copy_exists(self):
        mock_paths = MagicMock()
        mock_paths.agent_dir.return_value.exists.return_value = True
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        with patch("app.gateway.routers.agents.get_paths", return_value=mock_paths):
            assert _is_shared_only("agent", "u1") is False

    def test_not_shared_when_no_dir_at_all(self):
        mock_paths = MagicMock()
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        with patch("app.gateway.routers.agents.get_paths", return_value=mock_paths):
            assert _is_shared_only("agent", "u1") is False


# ===========================================================================
# _agent_config_to_response
# ===========================================================================


class TestAgentConfigToResponse:
    def _mock_config(self):
        cfg = MagicMock()
        cfg.name = "my-agent"
        cfg.description = "A test agent"
        cfg.model = "gpt-4"
        cfg.tool_groups = ["bash"]
        cfg.skills = ["search"]
        return cfg

    def test_without_soul(self):
        cfg = self._mock_config()
        resp = _agent_config_to_response(cfg, include_soul=False)
        assert resp.name == "my-agent"
        assert resp.description == "A test agent"
        assert resp.model == "gpt-4"
        assert resp.tool_groups == ["bash"]
        assert resp.skills == ["search"]
        assert resp.soul is None

    def test_with_soul(self):
        cfg = self._mock_config()
        with patch("app.gateway.routers.agents.load_agent_soul", return_value="soul content"):
            resp = _agent_config_to_response(
                cfg,
                include_soul=True,
                user_id=USER_ID,
                read_only=True,
                visibility="public",
                owner_id="o",
                department_id="d",
            )
        assert resp.soul == "soul content"
        assert resp.read_only is True
        assert resp.visibility == "public"
        assert resp.owner_id == "o"
        assert resp.department_id == "d"

    def test_soul_load_returns_none(self):
        cfg = self._mock_config()
        with patch("app.gateway.routers.agents.load_agent_soul", return_value=None):
            resp = _agent_config_to_response(cfg, include_soul=True, user_id=USER_ID)
        assert resp.soul == ""

    def test_optional_fields_none(self):
        cfg = MagicMock()
        cfg.name = "minimal"
        cfg.description = ""
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        resp = _agent_config_to_response(cfg, include_soul=False)
        assert resp.model is None
        assert resp.tool_groups is None
        assert resp.skills is None


# ===========================================================================
# GET /agents
# ===========================================================================


class TestListAgentsEndpoint:
    def test_success_empty(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        with patch("app.gateway.routers.agents.list_custom_agents", return_value=[]):
            resp = super_admin_client.get("/api/agents")
        assert resp.status_code == 200
        assert resp.json()["agents"] == []

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        mock_paths, _ = mock_deps
        with (
            patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)),
            patch("app.gateway.routers.agents.list_custom_agents", return_value=[]),
        ):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/agents")
        assert resp.status_code == 403

    def test_filters_private_agents_for_viewer(self, mock_deps):
        user = _make_user(user_id=OTHER_USER_ID, role=UserRole.VIEWER)
        mock_agent = MagicMock()
        mock_agent.name = AGENT_NAME
        mock_paths, _ = mock_deps
        with (
            patch("app.gateway.routers.agents.get_optional_rbac_user", return_value=user),
            patch("app.gateway.routers.agents.list_custom_agents", return_value=[mock_agent]),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=False),
        ):
            app = _build_app(user)
            with TestClient(app) as c:
                resp = c.get("/api/agents")
        assert resp.status_code == 200
        assert resp.json()["agents"] == []

    def test_includes_shared_agents_for_any_user(self, mock_deps):
        user = _make_user(user_id=OTHER_USER_ID, role=UserRole.USER)
        mock_agent = MagicMock()
        mock_agent.name = AGENT_NAME
        mock_agent.description = "desc"
        mock_agent.model = None
        mock_agent.tool_groups = None
        mock_agent.skills = None
        with (
            patch("app.gateway.routers.agents.get_optional_rbac_user", return_value=user),
            patch("app.gateway.routers.agents.list_custom_agents", return_value=[mock_agent]),
            patch("app.gateway.routers.agents._is_shared_only", return_value=True),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(
                read_only=True,
                visibility="public",
                owner_id=None,
                department_id=None,
                soul="soul",
            )
            app = _build_app(user)
            with TestClient(app) as c:
                resp = c.get("/api/agents")
        assert resp.status_code == 200
        assert len(resp.json()["agents"]) == 1

    def test_exception_returns_500(self, super_admin_client, mock_deps):
        with patch("app.gateway.routers.agents.list_custom_agents", side_effect=RuntimeError("boom")):
            resp = super_admin_client.get("/api/agents")
        assert resp.status_code == 500

    def test_no_user_filters_public_only(self, mock_deps):
        """When no auth user, only public agents are returned."""
        mock_agent = MagicMock()
        mock_agent.name = AGENT_NAME
        mock_paths, _ = mock_deps

        async def _anonymous_optional_user():
            return None

        with (
            patch("app.gateway.routers.agents.list_custom_agents", return_value=[mock_agent]),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID})),
        ):
            app = _build_app(None)
            app.dependency_overrides[get_optional_rbac_user] = _anonymous_optional_user
            with TestClient(app) as c:
                resp = c.get("/api/agents")
        assert resp.status_code == 200
        assert resp.json()["agents"] == []


# ===========================================================================
# GET /agents/check
# ===========================================================================


class TestCheckAgentNameEndpoint:
    def test_available(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        mock_paths.agent_dir.return_value.exists.return_value = False
        resp = super_admin_client.get("/api/agents/check", params={"name": "my-agent"})
        assert resp.status_code == 200
        assert resp.json()["available"] is True
        assert resp.json()["name"] == "my-agent"

    def test_taken_user_dir(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        mock_paths.agent_dir.return_value.exists.return_value = False
        resp = super_admin_client.get("/api/agents/check", params={"name": "taken"})
        assert resp.json()["available"] is False

    def test_taken_legacy_dir(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        mock_paths.agent_dir.return_value.exists.return_value = True
        resp = super_admin_client.get("/api/agents/check", params={"name": "legacy"})
        assert resp.json()["available"] is False

    def test_invalid_name_422(self, super_admin_client):
        resp = super_admin_client.get("/api/agents/check", params={"name": "bad name!"})
        assert resp.status_code == 422

    def test_normalizes_case(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        mock_paths.agent_dir.return_value.exists.return_value = False
        resp = super_admin_client.get("/api/agents/check", params={"name": "MyAgent"})
        assert resp.json()["name"] == "myagent"

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/agents/check", params={"name": "ok"})
        assert resp.status_code == 403


# ===========================================================================
# GET /agents/{name}
# ===========================================================================


class TestGetAgentEndpoint:
    def _mock_config(self):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.description = "desc"
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        return cfg

    def test_success(self, super_admin_client, mock_deps):
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=self._mock_config()),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(soul="soul")
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 200
        assert resp.json()["name"] == AGENT_NAME

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 403

    def test_not_found_404(self, super_admin_client, mock_deps):
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=FileNotFoundError()):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 404

    def test_invalid_name_422(self, super_admin_client):
        resp = super_admin_client.get("/api/agents/bad name!")
        assert resp.status_code == 422

    def test_shared_agent_public_visibility(self, super_admin_client, mock_deps):
        cfg = self._mock_config()
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=True),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(
                read_only=True,
                visibility="public",
                owner_id=None,
                department_id=None,
            )
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 200
        assert resp.json()["read_only"] is True
        mock_convert.assert_called_once()
        _, kwargs = mock_convert.call_args
        assert kwargs.get("visibility") == "public"

    def test_private_agent_invisible_returns_404(self, mock_deps):
        user = _make_user(user_id=OTHER_USER_ID, role=UserRole.USER)
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        with (
            patch("app.gateway.routers.agents.get_optional_rbac_user", return_value=user),
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=False),
        ):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 404

    def test_no_user_private_returns_404(self, mock_deps):
        cfg = MagicMock()
        cfg.name = AGENT_NAME

        async def _anonymous_optional_user():
            return None

        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID})),
        ):
            app = _build_app(None)
            app.dependency_overrides[get_optional_rbac_user] = _anonymous_optional_user
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 404

    def test_internal_error_500(self, super_admin_client, mock_deps):
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=RuntimeError("boom")):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 500


# ===========================================================================
# POST /agents (create)
# ===========================================================================


class TestCreateAgentEndpoint:
    PAYLOAD = {"name": AGENT_NAME, "soul": "test", "visibility": "private"}

    def test_success(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.description = ""
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._save_agent_meta", new=AsyncMock()),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
        ):
            mock_convert.return_value = _agent_resp(description="", soul="test")
            resp = super_admin_client.post("/api/agents", json=self.PAYLOAD)
        assert resp.status_code == 201
        assert resp.json()["name"] == AGENT_NAME

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post("/api/agents", json=self.PAYLOAD)
        assert resp.status_code == 403

    def test_invalid_name_422(self, super_admin_client, mock_deps):
        resp = super_admin_client.post("/api/agents", json={"name": "bad name!", "soul": "x"})
        assert resp.status_code == 422

    def test_legacy_collision_409(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = True
        resp = super_admin_client.post("/api/agents", json=self.PAYLOAD)
        assert resp.status_code == 409

    def test_file_exists_collision_409(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = FileExistsError
        resp = super_admin_client.post("/api/agents", json=self.PAYLOAD)
        assert resp.status_code == 409

    def test_visibility_dept_admin_can_set_department(self, dept_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.description = ""
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._save_agent_meta", new=AsyncMock()),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
        ):
            mock_convert.return_value = _agent_resp(
                description="",
                visibility="department",
                owner_id=USER_ID,
                department_id=DEPT_ID,
            )
            resp = dept_admin_client.post(
                "/api/agents",
                json={"name": AGENT_NAME, "soul": "", "visibility": "department"},
            )
        assert resp.status_code == 201

    def test_internal_error_cleanup(self, super_admin_client, mock_deps):
        """On failure the agent dir should be cleaned up."""
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        # Make agent_dir.exists() return True so cleanup code runs
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        mock_shutil = MagicMock()
        with (
            patch("builtins.open", side_effect=RuntimeError("disk full")),
            patch("app.gateway.routers.agents.shutil", mock_shutil),
        ):
            resp = super_admin_client.post("/api/agents", json=self.PAYLOAD)
        assert resp.status_code == 500
        mock_shutil.rmtree.assert_called_once()


# ===========================================================================
# PUT /agents/{name} (update)
# ===========================================================================


class TestUpdateAgentEndpoint:
    PAYLOAD = {"description": "updated", "version": 1}

    def _mock_cfg(self):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.description = "old"
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        return cfg

    def test_success(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=self._mock_cfg()),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.routers.agents._save_agent_meta", new=AsyncMock()),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(description="updated", soul="soul")
            resp = super_admin_client.put(f"/api/agents/{AGENT_NAME}", json=self.PAYLOAD)
        assert resp.status_code == 200

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.put(f"/api/agents/{AGENT_NAME}", json=self.PAYLOAD)
        assert resp.status_code == 403

    def test_not_found_404(self, super_admin_client, mock_deps):
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=FileNotFoundError()):
            resp = super_admin_client.put(f"/api/agents/{AGENT_NAME}", json=self.PAYLOAD)
        assert resp.status_code == 404

    def test_invalid_name_422(self, super_admin_client):
        resp = super_admin_client.put("/api/agents/bad name!", json=self.PAYLOAD)
        assert resp.status_code == 422

    def test_shared_read_only_409(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        mock_paths.agent_dir.return_value.exists.return_value = True
        with patch("app.gateway.routers.agents.load_agent_config", return_value=self._mock_cfg()):
            resp = super_admin_client.put(f"/api/agents/{AGENT_NAME}", json=self.PAYLOAD)
        assert resp.status_code == 409
        assert "shared read-only" in resp.json()["detail"]

    def test_viewer_cannot_update(self, viewer_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True

        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=self._mock_cfg()),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.routers.agents.check_resource_modify", return_value=False),
        ):
            resp = viewer_client.put(f"/api/agents/{AGENT_NAME}", json=self.PAYLOAD)
        assert resp.status_code == 403

    def test_internal_error_500(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=self._mock_cfg()),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("builtins.open", side_effect=RuntimeError("disk")),
        ):
            resp = super_admin_client.put(f"/api/agents/{AGENT_NAME}", json=self.PAYLOAD)
        assert resp.status_code == 500


# ===========================================================================
# DELETE /agents/{name}
# ===========================================================================


class TestDeleteAgentEndpoint:
    def test_success(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        with (
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.routers.agents.shutil"),
        ):
            resp = super_admin_client.delete(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 204

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.delete(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 403

    def test_shared_read_only_409(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        mock_paths.agent_dir.return_value.exists.return_value = True
        resp = super_admin_client.delete(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 409

    def test_not_found_404(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = False
        mock_paths.agent_dir.return_value.exists.return_value = False
        resp = super_admin_client.delete(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 404

    def test_invalid_name_422(self, super_admin_client):
        resp = super_admin_client.delete("/api/agents/bad name!")
        assert resp.status_code == 422

    def test_viewer_cannot_delete(self, viewer_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        with (
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.routers.agents.check_resource_modify", return_value=False),
        ):
            resp = viewer_client.delete(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 403

    def test_rmtree_error_500(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        with (
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.routers.agents.shutil.rmtree", side_effect=OSError("perm")),
        ):
            resp = super_admin_client.delete(f"/api/agents/{AGENT_NAME}")
        assert resp.status_code == 500


# ===========================================================================
# POST /agents/{name}/export
# ===========================================================================


class TestExportAgentEndpoint:
    def test_success(self, super_admin_client, mock_deps):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.description = "desc"
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value="soul"),
        ):
            resp = super_admin_client.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == AGENT_NAME
        assert data["soul"] == "soul"

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 403

    def test_not_found_404(self, super_admin_client, mock_deps):
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=FileNotFoundError()):
            resp = super_admin_client.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 404

    def test_invisible_agent_404(self, mock_deps):
        user = _make_user(user_id=OTHER_USER_ID, role=UserRole.USER)
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        with (
            patch("app.gateway.routers.agents.get_optional_rbac_user", return_value=user),
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=False),
        ):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 404

    def test_shared_agent_export(self, super_admin_client, mock_deps):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.description = "desc"
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=True),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value="shared soul"),
        ):
            resp = super_admin_client.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 200
        assert resp.json()["meta"] == {}


# ===========================================================================
# POST /agents/import
# ===========================================================================


class TestImportAgentEndpoint:
    PAYLOAD = {"name": AGENT_NAME, "soul": "imported", "visibility": "private"}

    def test_success(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.description = ""
        cfg.model = None
        cfg.tool_groups = None
        cfg.skills = None
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._save_agent_meta", new=AsyncMock()),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(description="", soul="imported")
            resp = super_admin_client.post("/api/agents/import", json=self.PAYLOAD)
        assert resp.status_code == 201
        assert resp.json()["name"] == AGENT_NAME

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post("/api/agents/import", json=self.PAYLOAD)
        assert resp.status_code == 403

    def test_invalid_name_422(self, super_admin_client, mock_deps):
        resp = super_admin_client.post("/api/agents/import", json={"name": "bad!", "soul": ""})
        assert resp.status_code == 422

    def test_legacy_collision_409(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = True
        resp = super_admin_client.post("/api/agents/import", json=self.PAYLOAD)
        assert resp.status_code == 409

    def test_file_exists_409(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = FileExistsError
        resp = super_admin_client.post("/api/agents/import", json=self.PAYLOAD)
        assert resp.status_code == 409

    def test_internal_error_cleanup(self, super_admin_client, mock_deps):
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        mock_shutil = MagicMock()
        with (
            patch("builtins.open", side_effect=RuntimeError("fail")),
            patch("app.gateway.routers.agents.shutil", mock_shutil),
        ):
            resp = super_admin_client.post("/api/agents/import", json=self.PAYLOAD)
        assert resp.status_code == 500
        mock_shutil.rmtree.assert_called_once()


# ===========================================================================
# GET /agents/{name}/stats
# ===========================================================================


class TestGetAgentStatsEndpoint:
    def test_success(self, super_admin_client, mock_deps):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.tool_groups = ["bash"]
        cfg.skills = ["search"]
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=5)))
        mock_sf = MagicMock(return_value=_AsyncCtxMgr(mock_session))
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID, "created_at": "2024-01-01"})),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value="soul"),
            patch("app.gateway.routers.agents.get_session_factory", return_value=mock_sf),
        ):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == AGENT_NAME
        assert data["visibility"] == "private"
        assert data["has_soul"] is True
        assert data["tool_groups_count"] == 1
        assert data["skills_count"] == 1

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 403

    def test_not_found_404(self, super_admin_client, mock_deps):
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=FileNotFoundError()):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 404

    def test_shared_agent_stats(self, super_admin_client, mock_deps):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.tool_groups = None
        cfg.skills = None
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=True),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value=""),
            patch("app.gateway.routers.agents.get_session_factory", return_value=None),
        ):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 200
        # Note: stats endpoint uses meta.get("visibility", "private") with empty meta
        # for shared agents (meta = {}), so the response visibility defaults to "private"
        # even though the local `visibility` variable is set to "public" for the
        # visibility check only.
        assert resp.json()["visibility"] == "private"
        assert resp.json()["has_soul"] is False
        assert resp.json()["tool_groups_count"] == 0

    def test_db_query_failure_graceful(self, super_admin_client, mock_deps):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.tool_groups = None
        cfg.skills = None
        mock_sf = MagicMock(side_effect=RuntimeError("db down"))
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value=None),
            patch("app.gateway.routers.agents.get_session_factory", return_value=mock_sf),
        ):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 200
        assert resp.json()["total_runs"] == 0
        assert resp.json()["total_messages"] == 0

    def test_session_factory_none(self, super_admin_client, mock_deps):
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        cfg.tool_groups = None
        cfg.skills = None
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value=None),
            patch("app.gateway.routers.agents.get_session_factory", return_value=None),
        ):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 200
        assert resp.json()["total_runs"] == 0

    def test_invisible_returns_404(self, mock_deps):
        user = _make_user(user_id=OTHER_USER_ID, role=UserRole.USER)
        cfg = MagicMock()
        cfg.name = AGENT_NAME
        with (
            patch("app.gateway.routers.agents.get_optional_rbac_user", return_value=user),
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", new=AsyncMock(return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID})),
            patch("app.gateway.authz.check_resource_access", return_value=False),
        ):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 404


# ===========================================================================
# GET /user-profile
# ===========================================================================


class TestGetUserProfileEndpoint:
    def test_success_with_content(self, super_admin_client, mock_deps):
        mock_paths, mock_user_md = mock_deps
        mock_user_md.exists.return_value = True
        mock_user_md.read_text.return_value = "# Profile"
        resp = super_admin_client.get("/api/user-profile")
        assert resp.status_code == 200
        assert resp.json()["content"] == "# Profile"

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/user-profile")
        assert resp.status_code == 403

    def test_file_not_found_returns_none(self, super_admin_client, mock_deps):
        mock_paths, mock_user_md = mock_deps
        mock_user_md.exists.return_value = False
        resp = super_admin_client.get("/api/user-profile")
        assert resp.status_code == 200
        assert resp.json()["content"] is None

    def test_empty_file_returns_none(self, super_admin_client, mock_deps):
        mock_paths, mock_user_md = mock_deps
        mock_user_md.exists.return_value = True
        mock_user_md.read_text.return_value = "   "
        resp = super_admin_client.get("/api/user-profile")
        assert resp.status_code == 200
        assert resp.json()["content"] is None

    def test_read_error_500(self, super_admin_client, mock_deps):
        mock_paths, mock_user_md = mock_deps
        mock_user_md.exists.return_value = True
        mock_user_md.read_text.side_effect = OSError("perm")
        resp = super_admin_client.get("/api/user-profile")
        assert resp.status_code == 500


# ===========================================================================
# PUT /user-profile
# ===========================================================================


class TestUpdateUserProfileEndpoint:
    def test_success(self, super_admin_client, mock_deps):
        resp = super_admin_client.put("/api/user-profile", json={"content": "# Profile"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "# Profile"

    def test_disabled_403(self, mock_deps):
        user = _make_user(role=UserRole.SUPER_ADMIN)
        with patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=False)):
            app = _build_app(user)
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.put("/api/user-profile", json={"content": "x"})
        assert resp.status_code == 403

    def test_empty_content_returns_none(self, super_admin_client, mock_deps):
        resp = super_admin_client.put("/api/user-profile", json={"content": ""})
        assert resp.status_code == 200
        assert resp.json()["content"] is None

    def test_write_error_500(self, super_admin_client, mock_deps):
        mock_paths, mock_user_md = mock_deps
        mock_user_md.write_text.side_effect = OSError("disk full")
        resp = super_admin_client.put("/api/user-profile", json={"content": "data"})
        assert resp.status_code == 500


# ===========================================================================
# RBAC: viewer blocked on write endpoints
# ===========================================================================


class TestViewerCannotWrite:
    """Verify the @require_role decorator blocks viewer on all write endpoints."""

    def test_create_forbidden(self, viewer_client, mock_deps):
        resp = viewer_client.post("/api/agents", json={"name": "agent", "soul": ""})
        assert resp.status_code == 403

    def test_update_forbidden(self, viewer_client, mock_deps):
        resp = viewer_client.put("/api/agents/agent", json={"description": "new", "version": 1})
        assert resp.status_code == 403

    def test_delete_forbidden(self, viewer_client, mock_deps):
        resp = viewer_client.delete("/api/agents/agent")
        assert resp.status_code == 403

    def test_import_forbidden(self, viewer_client, mock_deps):
        resp = viewer_client.post("/api/agents/import", json={"name": "agent", "soul": ""})
        assert resp.status_code == 403

    def test_update_profile_forbidden(self, viewer_client, mock_deps):
        resp = viewer_client.put("/api/user-profile", json={"content": "x"})
        assert resp.status_code == 403


# ===========================================================================
# Async context manager helper
# ===========================================================================


class _AsyncCtxMgr:
    """Minimal async context manager for mocking ``get_session_factory()``."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass
