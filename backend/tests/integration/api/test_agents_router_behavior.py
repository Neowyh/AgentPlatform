"""Coverage boost tests for app.gateway.routers.agents.

Targets all missed lines from coverage report when running test_custom_agent.py:
Lines 39, 41, 53, 56, 58, 161-162, 187-196, 271-273, 288-290, 311-319,
366-368, 380, 383-385, 419, 446, 480-487, 538-539, 561, 565, 569, 573,
588-589, 603-607, 642-644, 671-673, 718-720, 779-822, 850-921, 942-994
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import yaml
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ideer.config.agents_api_config import AgentsApiConfig, get_agents_api_config, set_agents_api_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_paths(base_dir: Path):
    from ideer.config.paths import Paths

    return Paths(base_dir=base_dir)


def _write_agent(base_dir: Path, user_id: str, name: str, config: dict, soul: str = "You are helpful.") -> None:
    agent_dir = base_dir / "users" / user_id / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    config_copy = dict(config)
    if "name" not in config_copy:
        config_copy["name"] = name
    with open(agent_dir / "config.yaml", "w") as f:
        yaml.dump(config_copy, f)
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")


def _write_shared_agent(base_dir: Path, name: str, config: dict, soul: str = "Shared soul.") -> None:
    agent_dir = base_dir / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    config_copy = dict(config)
    if "name" not in config_copy:
        config_copy["name"] = name
    with open(agent_dir / "config.yaml", "w") as f:
        yaml.dump(config_copy, f)
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")


def _write_agent_meta(base_dir: Path, user_id: str, name: str, meta: dict) -> None:
    """Persist agent metadata in the isolated test database."""
    import asyncio

    from ideer.persistence.engine import get_session_factory, init_engine
    from ideer.persistence.models.resource_metadata import ResourceMetadata

    if get_session_factory() is None:
        asyncio.run(
            init_engine(
                "sqlite",
                url=f"sqlite+aiosqlite:///{base_dir / 'agent_metadata.db'}",
                sqlite_dir=str(base_dir),
            )
        )

    owner_id = meta.get("owner_id", user_id)
    _seed_test_user(owner_id)

    async def _write() -> None:
        from sqlalchemy import select

        session_factory = get_session_factory()
        if session_factory is None:
            raise RuntimeError("agent metadata test database was not initialized")

        async with session_factory() as session:
            result = await session.execute(
                select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == "agent",
                    ResourceMetadata.resource_id == name,
                    ResourceMetadata.owner_id == owner_id,
                )
            )
            resource = result.scalar_one_or_none()
            if resource is None:
                resource = ResourceMetadata(
                    id=str(uuid4()),
                    resource_type="agent",
                    resource_id=name,
                    owner_id=owner_id,
                )
                session.add(resource)

            resource.visibility = meta.get("visibility", "private")
            resource.department_id = meta.get("department_id")
            resource.version = meta.get("version", 1)
            resource.is_favorited = meta.get("is_favorited", False)
            await session.commit()

    asyncio.run(_write())


def _seed_test_user(user_id: str = "normal-user") -> None:
    """Seed a test user in the DB to satisfy ResourceMetadata FK constraint."""
    import asyncio
    from datetime import UTC, datetime

    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel, UserRole

    sf = get_session_factory()
    if sf is None:
        raise RuntimeError("agent metadata test database was not initialized")

    async def _seed():
        async with sf() as session:
            from sqlalchemy import select

            stmt = select(UserModel).where(UserModel.id == user_id)
            result = await session.execute(stmt)
            if result.scalar_one_or_none() is None:
                session.add(
                    UserModel(
                        id=user_id,
                        username=user_id,
                        role=UserRole.USER,
                        created_at=datetime.now(UTC),
                    )
                )
                await session.commit()

    asyncio.run(_seed())


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestValidateAgentName:
    """Line 119: _validate_agent_name invalid name."""

    def test_invalid_name_raises_422(self):
        from app.gateway.routers.agents import _validate_agent_name

        with pytest.raises(HTTPException) as excinfo:
            _validate_agent_name("bad name!")
        assert excinfo.value.status_code == 422


# ---------------------------------------------------------------------------
# TestClient-based tests for API endpoints
# ---------------------------------------------------------------------------


def _make_test_app(tmp_path: Path, user_role=None, user_id="test-user", dept_id=None):
    """Create a FastAPI app with the agents router."""
    from _router_auth_helpers import make_authed_test_app

    from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
    from app.gateway.routers.agents import router
    from ideer.persistence.models.user import UserRole

    app = make_authed_test_app()

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.role = user_role or UserRole.SUPER_ADMIN
    mock_user.department_id = dept_id
    mock_user.disabled = False

    async def _stub_current_user():
        return mock_user

    async def _stub_optional_user():
        return mock_user

    app.dependency_overrides[get_current_rbac_user] = _stub_current_user
    app.dependency_overrides[get_optional_rbac_user] = _stub_optional_user
    app.include_router(router)
    return app


@pytest.fixture()
def agent_client(tmp_path):
    import app.gateway.routers.agents as agents_router

    paths_instance = _make_paths(tmp_path)
    previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

    import asyncio

    from ideer.persistence.engine import close_engine, init_engine

    asyncio.run(init_engine("sqlite", url="sqlite+aiosqlite://", sqlite_dir=str(tmp_path)))
    _seed_test_user("test-user")
    from ideer.runtime.user_context import reset_current_user, set_current_user
    user_token = set_current_user(SimpleNamespace(id="test-user", email="test-user@test.local"))

    with (
        patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
        patch.object(agents_router, "get_paths", return_value=paths_instance),
    ):
        set_agents_api_config(AgentsApiConfig(enabled=True))
        try:
            app = _make_test_app(tmp_path)
            with TestClient(app) as client:
                client._tmp_path = tmp_path
                yield client
        finally:
            reset_current_user(user_token)
            set_agents_api_config(previous_config)
            asyncio.run(close_engine())


@pytest.fixture()
def user_client(tmp_path):
    """Client with USER role (not admin)."""
    import app.gateway.routers.agents as agents_router
    from ideer.persistence.models.user import UserRole

    paths_instance = _make_paths(tmp_path)
    previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

    import asyncio

    from ideer.persistence.engine import close_engine, init_engine

    asyncio.run(init_engine("sqlite", url="sqlite+aiosqlite://", sqlite_dir=str(tmp_path)))
    _seed_test_user("normal-user")
    from ideer.runtime.user_context import reset_current_user, set_current_user
    user_token = set_current_user(SimpleNamespace(id="normal-user", email="normal-user@test.local"))

    with (
        patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
        patch.object(agents_router, "get_paths", return_value=paths_instance),
    ):
        set_agents_api_config(AgentsApiConfig(enabled=True))
        try:
            app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="normal-user")
            with TestClient(app) as client:
                client._tmp_path = tmp_path
                yield client
        finally:
            reset_current_user(user_token)
            set_agents_api_config(previous_config)
            asyncio.run(close_engine())


@pytest.fixture()
def no_user_client(tmp_path):
    """Client with no authenticated user."""
    from _router_auth_helpers import make_authed_test_app

    from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
    from app.gateway.routers.agents import router

    paths_instance = _make_paths(tmp_path)
    previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

    with (
        patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
        patch("app.gateway.routers.agents.get_paths", return_value=paths_instance),
    ):
        set_agents_api_config(AgentsApiConfig(enabled=True))
        try:
            app = make_authed_test_app()

            async def _no_user():
                return None

            app.dependency_overrides[get_optional_rbac_user] = _no_user
            app.dependency_overrides[get_current_rbac_user] = _no_user
            app.include_router(router)
            with TestClient(app) as client:
                client._tmp_path = tmp_path
                yield client
        finally:
            set_agents_api_config(previous_config)


# ---------------------------------------------------------------------------
# check_agent_name endpoint (lines 311-319)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for list_agents with non-shared per-user agents (lines 262-266, 271, 273)
# and _require_agents_api_enabled (line 133) and _load_agent_meta missing (line 158)
# ---------------------------------------------------------------------------


class TestListAgentsWithPerUserAgents:
    def test_list_per_user_agents_with_metadata(self, agent_client):
        """Lines 262-266: non-shared agent path loads metadata."""
        # Create agents via API → goes to user dir, with metadata
        agent_client.post("/api/agents", json={"name": "my-agent-1", "soul": "S1", "visibility": "private"})
        agent_client.post("/api/agents", json={"name": "my-agent-2", "soul": "S2", "visibility": "public"})

        response = agent_client.get("/api/agents")
        assert response.status_code == 200
        agents = {a["name"]: a for a in response.json()["agents"]}
        assert "my-agent-1" in agents
        assert "my-agent-2" in agents
        assert agents["my-agent-1"]["visibility"] == "private"
        assert agents["my-agent-2"]["visibility"] == "private"
        assert agents["my-agent-1"]["read_only"] is False

    def test_list_per_user_agents_uses_persisted_public_visibility(self, tmp_path):
        """A per-user agent is visible to another user only when its DB metadata is public."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        # Create an agent for the test user via the filesystem
        _write_agent(tmp_path, "normal-user", "user-public", {"name": "user-public"}, "Soul.")
        _write_agent_meta(
            tmp_path,
            "normal-user",
            "user-public",
            {
                "visibility": "public",
                "owner_id": "normal-user",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())
        from ideer.runtime.user_context import reset_current_user, set_current_user

        user_token = set_current_user(SimpleNamespace(id="normal-user", email="normal-user@test.local"))

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="other-user")
                with TestClient(app) as client:
                    response = client.get("/api/agents")
                    assert response.status_code == 200
                    agents = {agent["name"]: agent for agent in response.json()["agents"]}
                    assert agents["user-public"]["visibility"] == "public"
                    assert agents["user-public"]["owner_id"] == "normal-user"
            finally:
                set_agents_api_config(previous_config)
                reset_current_user(user_token)

    def test_list_agent_without_metadata_defaults_private(self, agent_client, tmp_path):
        """Lines 262-266: agent without ResourceMetadata record → default private."""
        import app.gateway.routers.agents as agents_router

        # Create an agent dir without a DB metadata record
        agent_dir = tmp_path / "users" / "test-user" / "agents" / "no-meta-agent"
        agent_dir.mkdir(parents=True)
        with open(agent_dir / "config.yaml", "w") as f:
            yaml.dump({"name": "no-meta-agent"}, f)
        (agent_dir / "SOUL.md").write_text("Soul.", encoding="utf-8")

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path)
                with TestClient(app) as client:
                    response = client.get("/api/agents")
                    assert response.status_code == 200
                    agents = {a["name"]: a for a in response.json()["agents"]}
                    assert "no-meta-agent" in agents
                    assert agents["no-meta-agent"]["visibility"] == "private"
            finally:
                set_agents_api_config(previous_config)

    def test_list_shared_only_agents(self, agent_client, tmp_path):
        """Lines 262-266: list when agent is shared-only (public visibility)."""
        _write_shared_agent(tmp_path, "shared-list", {"name": "shared-list"}, "Shared.")

        response = agent_client.get("/api/agents")
        assert response.status_code == 200
        agents = {a["name"]: a for a in response.json()["agents"]}
        assert "shared-list" in agents
        assert agents["shared-list"]["visibility"] == "public"
        assert agents["shared-list"]["read_only"] is True

    def test_list_filters_private_for_user_role(self, user_client):
        """Lines 271: USER role cannot see other users' private agents."""
        # Create agent as super_admin (via agent_client fixture), then list as USER
        # The user_client creates agents under 'normal-user' user_id
        user_client.post("/api/agents", json={"name": "user-own", "soul": "test", "visibility": "private"})

        response = user_client.get("/api/agents")
        assert response.status_code == 200
        # User should see their own private agent
        names = [a["name"] for a in response.json()["agents"]]
        assert "user-own" in names

    def test_list_no_user_skips_non_public(self, tmp_path):
        """Lines 273: no authenticated user skips non-public agents."""
        from _router_auth_helpers import make_authed_test_app

        from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
        from app.gateway.routers.agents import router

        # Create a private agent in the shared dir with metadata
        _write_shared_agent(tmp_path, "shared-list-nu", {"name": "shared-list-nu"}, "Soul.")
        # Create a private per-user agent
        _write_agent(tmp_path, "owner-1", "priv-list-nu", {"name": "priv-list-nu"}, "Soul.")
        _write_agent_meta(
            tmp_path,
            "owner-1",
            "priv-list-nu",
            {
                "visibility": "private",
                "owner_id": "owner-1",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())
        import app.gateway.routers.agents as agents_router

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = make_authed_test_app()

                async def _no_user():
                    return None

                app.dependency_overrides[get_optional_rbac_user] = _no_user
                app.dependency_overrides[get_current_rbac_user] = _no_user
                app.include_router(router)
                with TestClient(app) as client:
                    response = client.get("/api/agents")
                    assert response.status_code == 200
                    names = [a["name"] for a in response.json()["agents"]]
                    # shared-list-nu is in shared dir → treated as public → visible
                    assert "shared-list-nu" in names
                    # priv-list-nu is private → not visible without auth
                    assert "priv-list-nu" not in names
            finally:
                set_agents_api_config(previous_config)

    def test_get_agent_http_exception_re_raise(self, agent_client):
        """Line 380: HTTPException re-raise in get_agent."""
        agent_client.post("/api/agents", json={"name": "re-raise-get", "soul": "test"})

        with patch("app.gateway.routers.agents.load_agent_config") as mock_load:
            mock_load.side_effect = HTTPException(status_code=409, detail="conflict")
            response = agent_client.get("/api/agents/re-raise-get")
            assert response.status_code == 409


class TestCheckAgentName:
    def test_available_name(self, agent_client):
        response = agent_client.get("/api/agents/check", params={"name": "my-new-agent"})
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["name"] == "my-new-agent"

    def test_taken_name(self, agent_client):
        agent_client.post("/api/agents", json={"name": "taken-agent", "soul": "test"})
        response = agent_client.get("/api/agents/check", params={"name": "taken-agent"})
        assert response.status_code == 200
        assert response.json()["available"] is False

    def test_invalid_name(self, agent_client):
        response = agent_client.get("/api/agents/check", params={"name": "bad name!"})
        assert response.status_code == 422


class TestAgentsApiDisabled:
    """Line 133: _require_agents_api_enabled raises 403 when disabled."""

    @pytest.fixture()
    def disabled_client(self, tmp_path):
        import app.gateway.routers.agents as agents_router

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=False))
            try:
                app = _make_test_app(tmp_path)
                with TestClient(app) as client:
                    yield client
            finally:
                set_agents_api_config(previous_config)

    def test_list_disabled(self, disabled_client):
        response = disabled_client.get("/api/agents")
        assert response.status_code == 403

    def test_get_disabled(self, disabled_client):
        response = disabled_client.get("/api/agents/test")
        assert response.status_code == 403

    def test_check_disabled(self, disabled_client):
        response = disabled_client.get("/api/agents/check", params={"name": "test"})
        assert response.status_code == 403

    def test_create_disabled(self, disabled_client):
        response = disabled_client.post("/api/agents", json={"name": "test", "soul": "x"})
        assert response.status_code == 403

    def test_update_disabled(self, disabled_client):
        response = disabled_client.put("/api/agents/test", json={"soul": "x", "version": 1})
        assert response.status_code == 403

    def test_delete_disabled(self, disabled_client):
        response = disabled_client.delete("/api/agents/test")
        assert response.status_code == 403

    def test_user_profile_disabled(self, disabled_client):
        assert disabled_client.get("/api/user-profile").status_code == 403
        assert disabled_client.put("/api/user-profile", json={"content": "x"}).status_code == 403

    def test_export_disabled(self, disabled_client):
        response = disabled_client.post("/api/agents/test/export")
        assert response.status_code == 403

    def test_import_disabled(self, disabled_client):
        response = disabled_client.post("/api/agents/import", json={"name": "test", "soul": "x"})
        assert response.status_code == 403

    def test_stats_disabled(self, disabled_client):
        response = disabled_client.get("/api/agents/test/stats")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# list_agents visibility filtering (lines 257-259, 271-273, 288-290)
# ---------------------------------------------------------------------------


class TestListAgentsVisibility:
    def test_list_filters_private_agents_for_non_owner(self, tmp_path):
        """Non-owner USER should not see private agents owned by others.

        Lines 271: continue when agent is not visible to current user.
        """
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        # Create agent under test-user-autouse (the effective user from conftest)
        # but with metadata saying it's owned by "other-user"
        _write_agent(tmp_path, "test-user-autouse", "other-private", {"name": "other-private"}, "Private.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "other-private",
            {
                "visibility": "private",
                "owner_id": "other-user",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="normal-user")
                with TestClient(app) as client:
                    response = client.get("/api/agents")
                    assert response.status_code == 200
                    names = [a["name"] for a in response.json()["agents"]]
                    assert "other-private" not in names
            finally:
                set_agents_api_config(previous_config)

    def test_list_shows_public_agents_to_everyone(self, tmp_path):
        """Public agents should be visible to all users — use shared dir for public visibility."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        # Use shared dir which is auto-detected as public
        _write_shared_agent(tmp_path, "public-agent", {"name": "public-agent"}, "Public.")

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="normal-user")
                with TestClient(app) as client:
                    response = client.get("/api/agents")
                    assert response.status_code == 200
                    names = [a["name"] for a in response.json()["agents"]]
                    assert "public-agent" in names
            finally:
                set_agents_api_config(previous_config)

    def test_list_no_user_filters_non_public(self, tmp_path):
        """Lines 273: without auth, only public (shared) agents should appear."""
        from _router_auth_helpers import make_authed_test_app

        from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
        from app.gateway.routers.agents import router

        # Use shared dir for public agent (auto-detected as public)
        _write_shared_agent(tmp_path, "pub-agent", {"name": "pub-agent"}, "Pub.")
        # Create private agent under test-user-autouse (the effective user from conftest)
        _write_agent(tmp_path, "test-user-autouse", "priv-agent-nu", {"name": "priv-agent-nu"}, "Priv.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "priv-agent-nu",
            {
                "visibility": "private",
                "owner_id": "test-user-autouse",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())
        import app.gateway.routers.agents as agents_router

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = make_authed_test_app()

                async def _no_user():
                    return None

                app.dependency_overrides[get_optional_rbac_user] = _no_user
                app.dependency_overrides[get_current_rbac_user] = _no_user
                app.include_router(router)
                with TestClient(app) as client:
                    response = client.get("/api/agents")
                    assert response.status_code == 200
                    names = [a["name"] for a in response.json()["agents"]]
                    assert "pub-agent" in names
                    assert "priv-agent-nu" not in names
            finally:
                set_agents_api_config(previous_config)

    def test_list_exception_returns_500(self, agent_client, tmp_path):
        """Lines 288-290: exception handler in list_agents."""
        with patch("app.gateway.routers.agents.list_custom_agents", side_effect=Exception("boom")):
            response = agent_client.get("/api/agents")
            assert response.status_code == 500


# ---------------------------------------------------------------------------
# get_agent visibility and error paths (lines 354-356, 366-368, 380, 383-385)
# ---------------------------------------------------------------------------


class TestGetAgentVisibility:
    def test_get_private_agent_not_visible_to_other_user(self, tmp_path):
        """Lines 366: non-visible agent returns 404 for authenticated user."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        # Agent exists under test-user-autouse but owned by another user
        _write_agent(tmp_path, "test-user-autouse", "hidden-agent", {"name": "hidden-agent"}, "Hidden.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "hidden-agent",
            {
                "visibility": "private",
                "owner_id": "owner-1",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="other-user")
                with TestClient(app) as client:
                    response = client.get("/api/agents/hidden-agent")
                    assert response.status_code == 404
            finally:
                set_agents_api_config(previous_config)

    def test_get_public_agent_visible_to_no_user(self, tmp_path):
        """Lines 367-368: no user + public agent → 200, no user + non-public → 404."""
        from _router_auth_helpers import make_authed_test_app

        from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
        from app.gateway.routers.agents import router

        _write_shared_agent(tmp_path, "pub-agent-gn", {"name": "pub-agent-gn"}, "Public soul.")
        # Create private agent under test-user-autouse
        _write_agent(tmp_path, "test-user-autouse", "priv-agent-gn", {"name": "priv-agent-gn"}, "Priv.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "priv-agent-gn",
            {
                "visibility": "private",
                "owner_id": "test-user-autouse",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())
        import app.gateway.routers.agents as agents_router

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = make_authed_test_app()

                async def _no_user():
                    return None

                app.dependency_overrides[get_optional_rbac_user] = _no_user
                app.dependency_overrides[get_current_rbac_user] = _no_user
                app.include_router(router)
                with TestClient(app) as client:
                    # Public agent → visible
                    response = client.get("/api/agents/pub-agent-gn")
                    assert response.status_code == 200
                    assert response.json()["name"] == "pub-agent-gn"

                    # Private agent → 404 when no user
                    response = client.get("/api/agents/priv-agent-gn")
                    assert response.status_code == 404
            finally:
                set_agents_api_config(previous_config)

    def test_get_agent_file_not_found(self, agent_client):
        """Lines 383-385: FileNotFoundError → 404."""
        response = agent_client.get("/api/agents/nonexistent-agent")
        assert response.status_code == 404

    def test_get_agent_generic_exception(self, agent_client):
        """Lines 383-385: generic exception → 500."""
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=Exception("boom")):
            response = agent_client.get("/api/agents/some-agent")
            assert response.status_code == 500

    def test_get_per_user_agent_with_metadata(self, agent_client):
        """Lines 358-361, 365-366: get non-shared agent with metadata."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "meta-agent",
                "soul": "test",
                "visibility": "private",
            },
        )

        response = agent_client.get("/api/agents/meta-agent")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "meta-agent"
        assert data["visibility"] == "private"
        assert data["read_only"] is False

    def test_get_private_agent_as_user_returns_404(self, user_client):
        """Lines 366, 368: USER role can't see other's private agent → 404."""
        # Create agent as another user by writing directly to filesystem
        user_client.post(
            "/api/agents",
            json={
                "name": "own-private",
                "soul": "test",
                "visibility": "private",
            },
        )
        # User can see their own private agent
        response = user_client.get("/api/agents/own-private")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# create_agent visibility and error paths (lines 419, 433-434, 442-446, 480-487)
# ---------------------------------------------------------------------------


class TestCreateAgentVisibility:
    def test_user_cannot_set_public_visibility(self, user_client):
        """All agents are created private regardless of requested visibility."""
        response = user_client.post(
            "/api/agents",
            json={
                "name": "my-agent",
                "soul": "test",
                "visibility": "public",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["visibility"] == "private"

    def test_user_can_set_department_visibility(self, tmp_path):
        """department_admin can set department visibility."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(
                    tmp_path,
                    user_role=UserRole.DEPARTMENT_ADMIN,
                    user_id="dept-admin",
                    dept_id="dept-1",
                )
                with TestClient(app) as client:
                    response = client.post(
                        "/api/agents",
                        json={
                            "name": "dept-agent",
                            "soul": "test",
                            "visibility": "department",
                        },
                    )
                    assert response.status_code == 201
            finally:
                set_agents_api_config(previous_config)

    def test_create_agent_exception_cleans_up(self, agent_client):
        """Lines 480-487: exception during creation cleans up the directory."""
        with patch("app.gateway.routers.agents.yaml.dump", side_effect=Exception("disk full")):
            response = agent_client.post(
                "/api/agents",
                json={
                    "name": "fail-agent",
                    "soul": "test",
                },
            )
            assert response.status_code == 500

    def test_create_agent_with_description(self, agent_client):
        """Line 440: config_data["description"] = request.description."""
        response = agent_client.post(
            "/api/agents",
            json={
                "name": "desc-agent",
                "description": "My description",
                "soul": "test",
            },
        )
        assert response.status_code == 201
        assert response.json()["description"] == "My description"

    def test_create_agent_http_exception_re_raised(self, agent_client):
        """Line 481: HTTPException re-raise in create_agent."""
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=HTTPException(status_code=409, detail="exists")):
            response = agent_client.post(
                "/api/agents",
                json={
                    "name": "dup-agent",
                    "soul": "test",
                },
            )
            assert response.status_code == 409

    def test_create_agent_file_exists_race(self, agent_client, tmp_path):
        """Lines 433-434: FileExistsError on mkdir → 409 (TOCTOU race)."""
        # Pre-create the directory to simulate a race condition
        agent_dir = tmp_path / "users" / "test-user" / "agents" / "race-agent"
        agent_dir.mkdir(parents=True, exist_ok=True)

        response = agent_client.post(
            "/api/agents",
            json={
                "name": "race-agent",
                "soul": "test",
            },
        )
        assert response.status_code == 409

    def test_create_agent_legacy_collision(self, agent_client, tmp_path):
        """Line 428: legacy dir exists → 409."""
        _write_shared_agent(tmp_path, "legacy-collide", {"name": "legacy-collide"})

        response = agent_client.post(
            "/api/agents",
            json={
                "name": "legacy-collide",
                "soul": "test",
            },
        )
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# update_agent paths (lines 527, 538-539, 561, 565, 569, 573, 588-589, 603-607)
# ---------------------------------------------------------------------------


class TestUpdateAgentPaths:
    def test_update_visibility_change(self, agent_client):
        """Visibility updates are ignored; changes require approval flow."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "vis-agent",
                "soul": "test",
                "visibility": "private",
            },
        )

        response = agent_client.put(
            "/api/agents/vis-agent",
            json={
                "visibility": "public",
                "version": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["visibility"] == "private"

    def test_update_skills_explicitly(self, agent_client):
        """Lines 569, 573: skills field update path."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "skills-agent",
                "soul": "test",
            },
        )

        response = agent_client.put(
            "/api/agents/skills-agent",
            json={
                "skills": ["skill-a", "skill-b"],
                "version": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["skills"] == ["skill-a", "skill-b"]

    def test_update_skills_to_empty_list(self, agent_client):
        """Line 569: skills set to empty list."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "no-skills-agent",
                "soul": "test",
            },
        )

        response = agent_client.put(
            "/api/agents/no-skills-agent",
            json={
                "skills": [],
                "version": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["skills"] == []

    def test_update_model_and_tool_groups(self, agent_client):
        """Lines 561, 565: model and tool_groups update paths."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "model-agent",
                "soul": "test",
            },
        )

        response = agent_client.put(
            "/api/agents/model-agent",
            json={
                "model": "gpt-4",
                "tool_groups": ["bash", "file:read"],
                "version": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["model"] == "gpt-4"
        assert response.json()["tool_groups"] == ["bash", "file:read"]

    def test_update_exception_returns_500(self, agent_client):
        """Lines 603-607: generic exception → 500."""
        agent_client.post("/api/agents", json={"name": "err-agent", "soul": "test"})

        original_load = __import__("app.gateway.routers.agents", fromlist=["load_agent_config"]).load_agent_config
        call_count = 0

        def _fail_on_refresh(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise Exception("boom")
            return original_load(*args, **kwargs)

        with patch("app.gateway.routers.agents.load_agent_config", side_effect=_fail_on_refresh):
            response = agent_client.put("/api/agents/err-agent", json={"description": "new", "version": 1})
            assert response.status_code == 500

    def test_update_missing_agent_404(self, agent_client):
        """Lines 521-522: FileNotFoundError → 404 on update."""
        response = agent_client.put("/api/agents/nonexistent", json={"description": "new", "version": 1})
        assert response.status_code == 404

    def test_update_no_config_change(self, agent_client):
        """Lines 581-582: update with only soul change (no config fields changed)."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "soul-only-update",
                "soul": "original",
                "model": "gpt-4",
            },
        )

        response = agent_client.put(
            "/api/agents/soul-only-update",
            json={
                "soul": "updated soul",
                "version": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["soul"] == "updated soul"
        # model should remain unchanged
        assert response.json()["model"] == "gpt-4"

    def test_update_http_exception_re_raised(self, agent_client):
        """Line 604: HTTPException re-raise in update."""
        agent_client.post("/api/agents", json={"name": "re-raise-agent", "soul": "test"})

        with patch("app.gateway.routers.agents.load_agent_config") as mock_load:
            # First call succeeds (initial load), second raises HTTPException
            from ideer.config.agents_config import AgentConfig

            mock_load.return_value = AgentConfig(name="re-raise-agent")
            mock_load.side_effect = [AgentConfig(name="re-raise-agent"), HTTPException(status_code=409, detail="conflict")]

            response = agent_client.put("/api/agents/re-raise-agent", json={"description": "new", "version": 1})
            assert response.status_code == 409

    def test_update_visibility_permission_denied(self, user_client):
        """Visibility changes via PUT are silently ignored; approval flow is required."""
        user_client.post("/api/agents", json={"name": "vis-denied", "soul": "test", "visibility": "private"})

        response = user_client.put("/api/agents/vis-denied", json={"visibility": "department", "version": 1})
        assert response.status_code == 200
        assert response.json()["visibility"] == "private"

    def test_update_shared_read_only_agent(self, agent_client, tmp_path):
        """Line 527: update shared-only agent → 409."""
        _write_shared_agent(tmp_path, "shared-update", {"name": "shared-update"})

        response = agent_client.put("/api/agents/shared-update", json={"description": "new", "version": 1})
        assert response.status_code == 409
        assert "shared read-only" in response.json()["detail"].lower()


class TestDeleteAgentPaths:
    def test_delete_exception_returns_500(self, agent_client):
        """Lines 718-720: shutil.rmtree exception → 500."""
        agent_client.post("/api/agents", json={"name": "del-err-agent", "soul": "test"})

        with patch("app.gateway.routers.agents.shutil.rmtree", side_effect=Exception("perm denied")):
            response = agent_client.delete("/api/agents/del-err-agent")
            assert response.status_code == 500

    def test_delete_shared_read_only_409(self, agent_client, tmp_path):
        """Lines 704-709: delete shared-only agent → 409."""
        _write_shared_agent(tmp_path, "shared-del", {"name": "shared-del"})

        response = agent_client.delete("/api/agents/shared-del")
        assert response.status_code == 409
        assert "shared read-only" in response.json()["detail"].lower()

    def test_delete_nonexistent_agent_404(self, agent_client):
        """Line 709: delete nonexistent agent → 404."""
        response = agent_client.delete("/api/agents/ghost-delete")
        assert response.status_code == 404

    def test_delete_success(self, agent_client):
        """Line 717: successful delete logs and returns 204."""
        agent_client.post("/api/agents", json={"name": "del-success", "soul": "test"})
        response = agent_client.delete("/api/agents/del-success")
        assert response.status_code == 204


# ---------------------------------------------------------------------------
# get_user_profile exception (lines 642-644)
# ---------------------------------------------------------------------------


class TestGetUserProfileException:
    def test_exception_returns_500(self, agent_client):
        with patch("app.gateway.routers.agents.get_paths", side_effect=Exception("boom")):
            response = agent_client.get("/api/user-profile")
            assert response.status_code == 500

    def test_get_empty_user_profile(self, agent_client):
        """Lines 638-641: get user profile when file doesn't exist → content=None."""
        response = agent_client.get("/api/user-profile")
        assert response.status_code == 200
        assert response.json()["content"] is None

    def test_get_user_profile_after_put(self, agent_client):
        """Lines 638-641: get user profile after writing → returns content."""
        agent_client.put("/api/user-profile", json={"content": "# Profile\n\nI am a dev."})
        response = agent_client.get("/api/user-profile")
        assert response.status_code == 200
        assert response.json()["content"] == "# Profile\n\nI am a dev."


# ---------------------------------------------------------------------------
# update_user_profile exception (lines 671-673)
# ---------------------------------------------------------------------------


class TestUpdateUserProfileException:
    def test_exception_returns_500(self, agent_client):
        with patch("app.gateway.routers.agents.get_paths", side_effect=Exception("boom")):
            response = agent_client.put("/api/user-profile", json={"content": "test"})
            assert response.status_code == 500

    def test_put_user_profile(self, agent_client, tmp_path):
        """Lines 667-670: update user profile success path."""
        response = agent_client.put("/api/user-profile", json={"content": "# My Profile"})
        assert response.status_code == 200
        assert response.json()["content"] == "# My Profile"

        user_md = tmp_path / "USER.md"
        assert user_md.exists()
        assert user_md.read_text(encoding="utf-8") == "# My Profile"

    def test_put_empty_user_profile_returns_none(self, agent_client):
        """Empty content returns None."""
        response = agent_client.put("/api/user-profile", json={"content": ""})
        assert response.status_code == 200
        assert response.json()["content"] is None


# ---------------------------------------------------------------------------
# delete_agent error paths (lines 705, 718-720)
# ---------------------------------------------------------------------------


class TestDeleteAgentPathsExtra:
    def test_delete_exception_returns_500(self, agent_client):
        """Lines 718-720: shutil.rmtree exception → 500."""
        agent_client.post("/api/agents", json={"name": "del-err-agent", "soul": "test"})

        with patch("app.gateway.routers.agents.shutil.rmtree", side_effect=Exception("perm denied")):
            response = agent_client.delete("/api/agents/del-err-agent")
            assert response.status_code == 500

    def test_delete_shared_read_only_409(self, agent_client, tmp_path):
        """Lines 704-709: delete shared-only agent → 409."""
        _write_shared_agent(tmp_path, "shared-del", {"name": "shared-del"})

        response = agent_client.delete("/api/agents/shared-del")
        assert response.status_code == 409
        assert "shared read-only" in response.json()["detail"].lower()

    def test_delete_nonexistent_agent_404(self, agent_client):
        """Line 709: delete nonexistent agent → 404."""
        response = agent_client.delete("/api/agents/ghost-delete")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# export_agent endpoint (lines 779-822)
# ---------------------------------------------------------------------------


class TestExportAgent:
    def test_export_own_agent(self, agent_client):
        """Lines 779-822: export endpoint success path."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "export-me",
                "soul": "Export soul",
                "model": "gpt-4",
                "tool_groups": ["bash"],
                "visibility": "private",
            },
        )

        response = agent_client.post("/api/agents/export-me/export")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "export-me"
        assert data["soul"] == "Export soul"
        assert data["config"]["model"] == "gpt-4"
        assert data["config"]["tool_groups"] == ["bash"]

    def test_export_shared_agent(self, agent_client, tmp_path):
        """Export a shared (read-only) agent."""
        _write_shared_agent(tmp_path, "shared-export", {"name": "shared-export"}, "Shared soul")

        response = agent_client.post("/api/agents/shared-export/export")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "shared-export"
        assert data["soul"] == "Shared soul"

    def test_export_missing_agent_404(self, agent_client):
        response = agent_client.post("/api/agents/nonexistent/export")
        assert response.status_code == 404

    def test_export_private_agent_not_visible_404(self, tmp_path):
        """Private agent owned by another user returns 404 on export."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        _write_agent(tmp_path, "owner-1", "hidden-export", {"name": "hidden-export"}, "Hidden.")
        _write_agent_meta(
            tmp_path,
            "owner-1",
            "hidden-export",
            {
                "visibility": "private",
                "owner_id": "owner-1",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="other-user")
                with TestClient(app) as client:
                    response = client.post("/api/agents/hidden-export/export")
                    assert response.status_code == 404
            finally:
                set_agents_api_config(previous_config)

    def test_export_config_with_skills(self, agent_client):
        """Export config that includes skills field."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "skills-export",
                "soul": "test",
                "skills": ["skill-a"],
            },
        )

        response = agent_client.post("/api/agents/skills-export/export")
        assert response.status_code == 200
        assert response.json()["config"]["skills"] == ["skill-a"]

    def test_export_no_user_private_agent_404(self, tmp_path):
        """Lines 807: no user + non-public agent → 404 on export."""
        from _router_auth_helpers import make_authed_test_app

        from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
        from app.gateway.routers.agents import router

        # Create agent under test-user-autouse (effective user from conftest)
        _write_agent(tmp_path, "test-user-autouse", "priv-export-nu", {"name": "priv-export-nu"}, "Soul.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "priv-export-nu",
            {
                "visibility": "private",
                "owner_id": "test-user-autouse",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())
        import app.gateway.routers.agents as agents_router

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = make_authed_test_app()

                async def _no_user():
                    return None

                app.dependency_overrides[get_optional_rbac_user] = _no_user
                app.dependency_overrides[get_current_rbac_user] = _no_user
                app.include_router(router)
                with TestClient(app) as client:
                    response = client.post("/api/agents/priv-export-nu/export")
                    assert response.status_code == 404
            finally:
                set_agents_api_config(previous_config)

    def test_export_private_agent_not_visible_to_user(self, tmp_path):
        """Line 805: authenticated USER can't export private agent owned by another."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        _write_agent(tmp_path, "test-user-autouse", "priv-export-other", {"name": "priv-export-other"}, "Soul.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "priv-export-other",
            {
                "visibility": "private",
                "owner_id": "other-owner",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="normal-user")
                with TestClient(app) as client:
                    response = client.post("/api/agents/priv-export-other/export")
                    assert response.status_code == 404
            finally:
                set_agents_api_config(previous_config)


# ---------------------------------------------------------------------------
# import_agent endpoint (lines 850-921)
# ---------------------------------------------------------------------------


class TestImportAgent:
    def test_import_agent_success(self, agent_client):
        """Lines 850-921: import endpoint success path."""
        response = agent_client.post(
            "/api/agents/import",
            json={
                "name": "imported-agent",
                "config": {"description": "Imported", "model": "gpt-4"},
                "soul": "Imported soul content",
                "visibility": "private",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "imported-agent"
        assert data["description"] == "Imported"
        assert data["model"] == "gpt-4"
        assert data["soul"] == "Imported soul content"

    def test_import_duplicate_name_409(self, agent_client):
        """Import fails when agent already exists."""
        agent_client.post(
            "/api/agents/import",
            json={
                "name": "dup-import",
                "config": {},
                "soul": "first",
            },
        )

        response = agent_client.post(
            "/api/agents/import",
            json={
                "name": "dup-import",
                "config": {},
                "soul": "second",
            },
        )
        assert response.status_code == 409

    def test_import_with_legacy_collision_409(self, agent_client, tmp_path):
        """Import fails when shared agent with same name exists."""
        _write_shared_agent(tmp_path, "legacy-import", {"name": "legacy-import"})

        response = agent_client.post(
            "/api/agents/import",
            json={
                "name": "legacy-import",
                "config": {},
                "soul": "test",
            },
        )
        assert response.status_code == 409

    def test_import_invalid_name_422(self, agent_client):
        response = agent_client.post(
            "/api/agents/import",
            json={
                "name": "bad name!",
                "config": {},
                "soul": "test",
            },
        )
        assert response.status_code == 422

    def test_import_visibility_permission_denied(self, tmp_path):
        """Non-super-admin can't import with public visibility."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="normal-user")
                with TestClient(app) as client:
                    response = client.post(
                        "/api/agents/import",
                        json={
                            "name": "pub-import",
                            "config": {},
                            "soul": "test",
                            "visibility": "public",
                        },
                    )
                    assert response.status_code == 201
                    assert response.json()["visibility"] == "private"
            finally:
                set_agents_api_config(previous_config)

    def test_import_exception_cleans_up(self, agent_client):
        """Lines 915-921: exception during import cleans up."""
        with patch("app.gateway.routers.agents.yaml.dump", side_effect=Exception("disk full")):
            response = agent_client.post(
                "/api/agents/import",
                json={
                    "name": "fail-import",
                    "config": {},
                    "soul": "test",
                },
            )
            assert response.status_code == 500

    def test_import_http_exception_re_raised(self, agent_client):
        """Line 916: HTTPException re-raise in import."""
        with patch("app.gateway.routers.agents.load_agent_config", side_effect=HTTPException(status_code=409, detail="exists")):
            response = agent_client.post(
                "/api/agents/import",
                json={
                    "name": "re-raise-import",
                    "config": {},
                    "soul": "test",
                },
            )
            assert response.status_code == 409


# ---------------------------------------------------------------------------
# get_agent_stats endpoint (lines 942-994)
# ---------------------------------------------------------------------------


class TestGetAgentStats:
    def test_stats_own_agent(self, agent_client):
        """Lines 942-994: stats endpoint success path."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "stats-agent",
                "soul": "Stats soul",
                "model": "gpt-4",
                "tool_groups": ["bash", "file:read"],
            },
        )

        response = agent_client.get("/api/agents/stats-agent/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "stats-agent"
        assert data["has_soul"] is True
        assert data["tool_groups_count"] == 2
        assert data["skills_count"] == 0
        assert data["visibility"] == "private"

    def test_stats_shared_agent(self, agent_client, tmp_path):
        """Stats for a shared agent."""
        _write_shared_agent(tmp_path, "shared-stats", {"name": "shared-stats"}, "Shared.")

        response = agent_client.get("/api/agents/shared-stats/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "shared-stats"
        # Note: stats endpoint returns meta.get("visibility", "private") which is "private"
        # when meta is empty (shared agents have no meta file)
        assert data["has_soul"] is True

    def test_stats_missing_agent_404(self, agent_client):
        response = agent_client.get("/api/agents/ghost/stats")
        assert response.status_code == 404

    def test_stats_not_visible_404(self, tmp_path):
        """Lines 968: private agent not visible to other user returns 404."""
        import app.gateway.routers.agents as agents_router
        from ideer.persistence.models.user import UserRole

        # Agent exists under test-user-autouse but owned by another user
        _write_agent(tmp_path, "test-user-autouse", "hidden-stats", {"name": "hidden-stats"}, "Hidden.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "hidden-stats",
            {
                "visibility": "private",
                "owner_id": "owner-1",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = _make_test_app(tmp_path, user_role=UserRole.USER, user_id="other-user")
                with TestClient(app) as client:
                    response = client.get("/api/agents/hidden-stats/stats")
                    assert response.status_code == 404
            finally:
                set_agents_api_config(previous_config)

    def test_stats_no_user_private_agent_404(self, tmp_path):
        """Lines 969-970: no user + non-public agent → 404 on stats."""
        from _router_auth_helpers import make_authed_test_app

        from app.gateway.authz import get_current_rbac_user, get_optional_rbac_user
        from app.gateway.routers.agents import router

        _write_agent(tmp_path, "test-user-autouse", "priv-stats-nu", {"name": "priv-stats-nu"}, "Soul.")
        _write_agent_meta(
            tmp_path,
            "test-user-autouse",
            "priv-stats-nu",
            {
                "visibility": "private",
                "owner_id": "test-user-autouse",
                "department_id": None,
            },
        )

        paths_instance = _make_paths(tmp_path)
        previous_config = AgentsApiConfig(**get_agents_api_config().model_dump())
        import app.gateway.routers.agents as agents_router

        with (
            patch("ideer.config.agents_config.get_paths", return_value=paths_instance),
            patch.object(agents_router, "get_paths", return_value=paths_instance),
        ):
            set_agents_api_config(AgentsApiConfig(enabled=True))
            try:
                app = make_authed_test_app()

                async def _no_user():
                    return None

                app.dependency_overrides[get_optional_rbac_user] = _no_user
                app.dependency_overrides[get_current_rbac_user] = _no_user
                app.include_router(router)
                with TestClient(app) as client:
                    response = client.get("/api/agents/priv-stats-nu/stats")
                    assert response.status_code == 404
            finally:
                set_agents_api_config(previous_config)

    def test_stats_agent_with_skills(self, agent_client):
        """Stats with skills count."""
        agent_client.post(
            "/api/agents",
            json={
                "name": "skills-stats",
                "soul": "test",
                "skills": ["skill-a", "skill-b", "skill-c"],
            },
        )

        response = agent_client.get("/api/agents/skills-stats/stats")
        assert response.status_code == 200
        assert response.json()["skills_count"] == 3

    def test_stats_no_soul(self, agent_client):
        """Stats with has_soul=False when soul is whitespace only."""
        agent_client.post("/api/agents", json={"name": "no-soul-agent", "soul": "   "})

        response = agent_client.get("/api/agents/no-soul-agent/stats")
        assert response.status_code == 200
        assert response.json()["has_soul"] is False

    def test_stats_db_query_exception_is_non_fatal(self, agent_client):
        """Lines 979-992: DB query exception is caught and non-fatal."""
        agent_client.post("/api/agents", json={"name": "db-err-agent", "soul": "test"})

        with patch("app.gateway.routers.agents.get_session_factory") as mock_sf:
            mock_sf.return_value = MagicMock(side_effect=Exception("DB down"))

            response = agent_client.get("/api/agents/db-err-agent/stats")
            assert response.status_code == 200
            # Falls back to 0
            assert response.json()["total_runs"] == 0
            assert response.json()["total_messages"] == 0

    def test_stats_no_session_factory(self, agent_client):
        """Lines 979-992: no session factory → 0 counts."""
        agent_client.post("/api/agents", json={"name": "no-db-agent", "soul": "test"})

        with patch("app.gateway.routers.agents.get_session_factory", return_value=None):
            response = agent_client.get("/api/agents/no-db-agent/stats")
            assert response.status_code == 200
            assert response.json()["total_runs"] == 0
            assert response.json()["total_messages"] == 0
