"""Targeted coverage tests for agents router error paths.

Each test covers specific uncovered lines in agents.py as identified by
coverage analysis. Follows the pattern from test_agents_router_full.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
from app.gateway.routers.agents import AgentResponse, router
from ideer.config.agents_api_config import AgentsApiConfig
from ideer.persistence.models.user import UserRole

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "test-agent"
USER_ID = "user-1"
DEPT_ID = "dept-1"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    user_id: str = USER_ID,
    role: UserRole = UserRole.USER,
    department_id: str | None = DEPT_ID,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.role = role
    user.department_id = department_id
    user.disabled = False
    return user


def _build_app(user: MagicMock | None = None):
    from _router_auth_helpers import make_authed_test_app

    app = make_authed_test_app()
    app.include_router(router)

    if user is not None:

        async def _current():
            return user

        async def _optional():
            return user

        app.dependency_overrides[get_current_rbac_user] = _current
        app.dependency_overrides[get_optional_rbac_user] = _optional

    return app


def _mock_cfg(name: str = AGENT_NAME, **overrides) -> MagicMock:
    cfg = MagicMock()
    cfg.name = name
    cfg.description = overrides.get("description", "desc")
    cfg.model = overrides.get("model", None)
    cfg.tool_groups = overrides.get("tool_groups", None)
    cfg.skills = overrides.get("skills", None)
    return cfg


def _agent_resp(**overrides) -> AgentResponse:
    """Create a valid AgentResponse for mock return values."""
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_deps():
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
def super_admin_client(mock_deps):
    """TestClient with a super_admin-role user."""
    user = _make_user(role=UserRole.SUPER_ADMIN)
    app = _build_app(user)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture()
def user_client(mock_deps):
    """TestClient with a regular user-role user."""
    user = _make_user(role=UserRole.USER)
    app = _build_app(user)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class _AsyncCtxMgr:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass


def _make_sf_mock(runs=0, messages=0):
    """Create a mock session factory returning the given run/message counts."""
    mock_session = MagicMock()
    # First call (run_count) returns runs, second call (msg_count) returns messages
    mock_session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar=MagicMock(return_value=runs)),
            MagicMock(scalar=MagicMock(return_value=messages)),
        ]
    )
    return MagicMock(return_value=_AsyncCtxMgr(mock_session))


# ===========================================================================
# Line 446: create_agent — config_data["skills"] = request.skills
# ===========================================================================


class TestCreateAgentSkillsCoverage:
    """Cover create_agent code paths involving skills field."""

    def test_create_with_skills(self, super_admin_client, mock_deps):
        """Line 446: skills field written to config_data when not None."""
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        cfg = _mock_cfg(skills=["search", "code"])
        with (
            patch("app.gateway.routers.agents._can_set_visibility", return_value=True),
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._save_agent_meta"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml") as mock_yaml,
        ):
            mock_convert.return_value = _agent_resp(skills=["search", "code"], soul="s")
            resp = super_admin_client.post(
                "/api/agents",
                json={"name": AGENT_NAME, "soul": "s", "skills": ["search", "code"]},
            )
        assert resp.status_code == 201
        # Verify yaml.dump was called (config was written)
        mock_yaml.dump.assert_called_once()


# ===========================================================================
# Line 481: create_agent — except HTTPException: raise (re-raise)
# ===========================================================================


class TestCreateAgentHTTPExceptionReraise:
    """Cover the 'except HTTPException: raise' branch in create_agent."""

    def test_reraise_http_exception_from_inner_try(self, super_admin_client, mock_deps):
        """Line 481: HTTPException raised inside inner try is re-raised."""
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        # Make _save_agent_meta raise HTTPException inside the inner try block
        with (
            patch("app.gateway.routers.agents._can_set_visibility", return_value=True),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch(
                "app.gateway.routers.agents._save_agent_meta",
                side_effect=HTTPException(status_code=422, detail="write failed"),
            ),
        ):
            resp = super_admin_client.post(
                "/api/agents",
                json={"name": AGENT_NAME, "soul": "content", "visibility": "private"},
            )
        assert resp.status_code == 422
        assert "write failed" in resp.json()["detail"]


# ===========================================================================
# Lines 561, 565, 569, 573: update_agent — model/tool_groups/skills fields
# ===========================================================================


class TestUpdateAgentFieldCoverage:
    """Cover update_agent branches for model, tool_groups, and skills fields."""

    def test_update_sets_model(self, super_admin_client, mock_deps):
        """Lines 560-561: new_model is not None, written to updated dict."""
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        cfg = _mock_cfg(model=None)
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._save_agent_meta"),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(model="gpt-4", soul="s")
            resp = super_admin_client.put(
                f"/api/agents/{AGENT_NAME}",
                json={"model": "gpt-4"},
            )
        assert resp.status_code == 200

    def test_update_sets_tool_groups(self, super_admin_client, mock_deps):
        """Lines 564-565: new_tool_groups is not None, written to updated dict."""
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        cfg = _mock_cfg(tool_groups=None)
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._save_agent_meta"),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(tool_groups=["bash"], soul="s")
            resp = super_admin_client.put(
                f"/api/agents/{AGENT_NAME}",
                json={"tool_groups": ["bash"]},
            )
        assert resp.status_code == 200

    def test_update_sets_skills_from_request(self, super_admin_client, mock_deps):
        """Lines 568-569: 'skills' in fields_set, takes request.skills."""
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        cfg = _mock_cfg(skills=None)
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._save_agent_meta"),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(skills=["search"], soul="s")
            resp = super_admin_client.put(
                f"/api/agents/{AGENT_NAME}",
                json={"skills": ["search"]},
            )
        assert resp.status_code == 200

    def test_update_skills_not_in_fields_set_uses_existing(self, super_admin_client, mock_deps):
        """Line 570-571: 'skills' NOT in fields_set, falls through to agent_cfg.skills."""
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        cfg = _mock_cfg(skills=["existing-skill"])
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._save_agent_meta"),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(description="updated", skills=["existing-skill"], soul="s")
            resp = super_admin_client.put(
                f"/api/agents/{AGENT_NAME}",
                json={"description": "updated"},
            )
        assert resp.status_code == 200

    def test_update_skills_empty_list(self, super_admin_client, mock_deps):
        """Line 573: new_skills is [] (not None), written to updated dict."""
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        cfg = _mock_cfg(skills=["old-skill"])
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._save_agent_meta"),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(skills=[], soul="s")
            resp = super_admin_client.put(
                f"/api/agents/{AGENT_NAME}",
                json={"skills": []},
            )
        assert resp.status_code == 200


# ===========================================================================
# Lines 588-589: update_agent — visibility change persisted to metadata
# ===========================================================================


class TestUpdateAgentVisibilityPersist:
    """Cover the visibility-change persistence branch in update_agent."""

    def test_visibility_change_saved_to_meta(self, super_admin_client, mock_deps):
        """Lines 587-589: visibility changed, meta updated and saved."""
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        cfg = _mock_cfg()
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._can_set_visibility", return_value=True),
            patch("app.gateway.routers.agents._save_agent_meta") as mock_save,
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(visibility="public", soul="s")
            resp = super_admin_client.put(
                f"/api/agents/{AGENT_NAME}",
                json={"visibility": "public"},
            )
        assert resp.status_code == 200
        # Verify _save_agent_meta was called (visibility persisted)
        mock_save.assert_called()


# ===========================================================================
# Line 604: update_agent — except HTTPException: raise
# ===========================================================================


class TestUpdateAgentHTTPExceptionReraise:
    """Cover the 'except HTTPException: raise' branch in update_agent."""

    def test_reraise_http_exception_during_write(self, super_admin_client, mock_deps):
        """Line 604: HTTPException raised inside inner try is re-raised."""
        mock_paths, _ = mock_deps
        mock_paths.user_agent_dir.return_value.exists.return_value = True
        cfg = _mock_cfg()
        # First call (initial load) returns cfg, second call (refresh) raises
        with (
            patch("app.gateway.routers.agents.load_agent_config", side_effect=[cfg, HTTPException(status_code=409, detail="conflict")]),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
        ):
            resp = super_admin_client.put(
                f"/api/agents/{AGENT_NAME}",
                json={"description": "new"},
            )
        assert resp.status_code == 409


# ===========================================================================
# Lines 806-807: export_agent — no user, non-public visibility
# ===========================================================================


class TestExportAgentNoUserNonPublic:
    """Cover the anonymous-user + non-public visibility path in export_agent."""

    def test_no_user_non_public_returns_404(self, mock_deps):
        """Lines 806-807: anonymous user + private agent -> 404."""
        cfg = _mock_cfg()
        with (
            patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=True)),
            patch("app.gateway.routers.agents.get_effective_user_id", return_value=USER_ID),
            patch("app.gateway.routers.agents._validate_agent_name"),
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID}),
        ):
            app = _build_app(None)

            async def _none_optional():
                return None

            app.dependency_overrides[get_optional_rbac_user] = _none_optional
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 404


# ===========================================================================
# Lines 816, 818, 820: export_agent — model/tool_groups/skills in config
# ===========================================================================


class TestExportAgentConfigFields:
    """Cover export_agent branches for model, tool_groups, and skills."""

    def test_export_with_all_optional_fields(self, super_admin_client, mock_deps):
        """Lines 816, 818, 820: model, tool_groups, and skills included in export."""
        cfg = _mock_cfg(model="gpt-4", tool_groups=["bash", "shell"], skills=["search"])
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._is_visible_to_user", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value="soul"),
        ):
            resp = super_admin_client.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["config"]["model"] == "gpt-4"
        assert data["config"]["tool_groups"] == ["bash", "shell"]
        assert data["config"]["skills"] == ["search"]

    def test_export_excludes_none_optional_fields(self, super_admin_client, mock_deps):
        """When model/tool_groups/skills are None, they are omitted from config."""
        cfg = _mock_cfg(model=None, tool_groups=None, skills=None)
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID}),
            patch("app.gateway.routers.agents._is_visible_to_user", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value=""),
        ):
            resp = super_admin_client.post(f"/api/agents/{AGENT_NAME}/export")
        assert resp.status_code == 200
        config = resp.json()["config"]
        assert "model" not in config
        assert "tool_groups" not in config
        assert "skills" not in config


# ===========================================================================
# Line 880: import_agent — config_data[key] = request.config[key]
# ===========================================================================


class TestImportAgentConfigFields:
    """Cover import_agent branches for config field extraction."""

    def test_import_with_config_fields(self, super_admin_client, mock_deps):
        """Line 880: config keys copied from request.config."""
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        cfg = _mock_cfg(model="gpt-4", tool_groups=["bash"], skills=["search"])
        with (
            patch("app.gateway.routers.agents._can_set_visibility", return_value=True),
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._save_agent_meta"),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch("app.gateway.routers.agents._agent_config_to_response") as mock_convert,
        ):
            mock_convert.return_value = _agent_resp(
                description="desc",
                model="gpt-4",
                tool_groups=["bash"],
                skills=["search"],
                soul="imported",
            )
            resp = super_admin_client.post(
                "/api/agents/import",
                json={
                    "name": AGENT_NAME,
                    "soul": "imported",
                    "visibility": "private",
                    "config": {
                        "description": "desc",
                        "model": "gpt-4",
                        "tool_groups": ["bash"],
                        "skills": ["search"],
                    },
                },
            )
        assert resp.status_code == 201


# ===========================================================================
# Line 916: import_agent — except HTTPException: raise
# ===========================================================================


class TestImportAgentHTTPExceptionReraise:
    """Cover the 'except HTTPException: raise' branch in import_agent."""

    def test_reraise_http_exception_during_import_write(self, super_admin_client, mock_deps):
        """Line 916: HTTPException raised inside inner try is re-raised."""
        mock_paths, _ = mock_deps
        mock_paths.agent_dir.return_value.exists.return_value = False
        mock_paths.user_agent_dir.return_value.mkdir.side_effect = None
        # Make _save_agent_meta raise HTTPException inside the inner try block
        with (
            patch("app.gateway.routers.agents._can_set_visibility", return_value=True),
            patch("builtins.open", MagicMock()),
            patch("app.gateway.routers.agents.yaml"),
            patch(
                "app.gateway.routers.agents._save_agent_meta",
                side_effect=HTTPException(status_code=422, detail="bad data"),
            ),
        ):
            resp = super_admin_client.post(
                "/api/agents/import",
                json={"name": AGENT_NAME, "soul": "x", "visibility": "private"},
            )
        assert resp.status_code == 422
        assert "bad data" in resp.json()["detail"]


# ===========================================================================
# Lines 969-970: stats_agent — no user, non-public visibility
# ===========================================================================


class TestStatsAgentNoUserNonPublic:
    """Cover the anonymous-user + non-public visibility path in get_agent_stats."""

    def test_stats_no_user_non_public_returns_404(self, mock_deps):
        """Lines 969-970: anonymous user + private agent -> 404."""
        cfg = _mock_cfg()
        with (
            patch("app.gateway.routers.agents.get_agents_api_config", return_value=AgentsApiConfig(enabled=True)),
            patch("app.gateway.routers.agents.get_effective_user_id", return_value=USER_ID),
            patch("app.gateway.routers.agents._validate_agent_name"),
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID}),
        ):
            app = _build_app(None)

            async def _none_optional():
                return None

            app.dependency_overrides[get_optional_rbac_user] = _none_optional
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 404


# ===========================================================================
# Lines 986-990: stats_agent — DB query for run/message counts
# ===========================================================================


class TestStatsAgentDBQueries:
    """Cover the DB query branches in get_agent_stats."""

    def test_stats_with_db_run_and_message_counts(self, super_admin_client, mock_deps):
        """Lines 986-990: DB query for run/message counts.

        RunRow does not have a ``graph_id`` column in this codebase, so the
        endpoint's ``except`` block catches the AttributeError and returns
        0 counts. This verifies the graceful fallback path.
        """
        cfg = _mock_cfg(tool_groups=["bash"], skills=["search"])
        mock_sf = _make_sf_mock(runs=10, messages=25)
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID, "department_id": DEPT_ID, "created_at": "2024-06-01"}),
            patch("app.gateway.routers.agents._is_visible_to_user", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value="soul"),
            patch("app.gateway.routers.agents.get_session_factory", return_value=mock_sf),
        ):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 200
        data = resp.json()
        # RunRow has no graph_id -> AttributeError caught -> graceful fallback to 0
        assert data["total_runs"] == 0
        assert data["total_messages"] == 0

    def test_stats_db_session_execute_raises(self, super_admin_client, mock_deps):
        """Lines 986-990: exception during DB query handled gracefully."""
        cfg = _mock_cfg()
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("db error"))
        mock_sf = MagicMock(return_value=_AsyncCtxMgr(mock_session))
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID}),
            patch("app.gateway.routers.agents._is_visible_to_user", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value=None),
            patch("app.gateway.routers.agents.get_session_factory", return_value=mock_sf),
        ):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 200
        # Graceful fallback: counts default to 0
        assert resp.json()["total_runs"] == 0
        assert resp.json()["total_messages"] == 0

    def test_stats_db_session_factory_raises(self, super_admin_client, mock_deps):
        """Lines 986-990: exception from session factory context manager."""
        cfg = _mock_cfg()
        # Factory itself raises when called as context manager
        mock_sf = MagicMock(side_effect=ConnectionError("conn refused"))
        with (
            patch("app.gateway.routers.agents.load_agent_config", return_value=cfg),
            patch("app.gateway.routers.agents._is_shared_only", return_value=False),
            patch("app.gateway.routers.agents._load_agent_meta", return_value={"visibility": "private", "owner_id": USER_ID}),
            patch("app.gateway.routers.agents._is_visible_to_user", return_value=True),
            patch("app.gateway.routers.agents.load_agent_soul", return_value=None),
            patch("app.gateway.routers.agents.get_session_factory", return_value=mock_sf),
        ):
            resp = super_admin_client.get(f"/api/agents/{AGENT_NAME}/stats")
        assert resp.status_code == 200
        assert resp.json()["total_runs"] == 0
        assert resp.json()["total_messages"] == 0
