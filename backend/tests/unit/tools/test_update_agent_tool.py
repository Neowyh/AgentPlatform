"""Tests for update_agent tool — partial updates, atomic writes, and validation.

Resolves issue #2616: a custom agent must be able to persist updates to its
own SOUL.md / config.yaml from inside a normal chat (not only from bootstrap).

The tool writes per-user (``{base_dir}/users/{user_id}/agents/{name}/``) so
that one user's update cannot mutate another user's agent.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceVersion
from ideer.persistence.models.user import UserModel
from ideer.tools.builtins.setup_agent_tool import setup_agent
from ideer.tools.builtins.update_agent_tool import update_agent

DEFAULT_USER = "test-user-autouse"  # matches the autouse fixture in tests/conftest.py


class _DummyRuntime(SimpleNamespace):
    context: dict
    tool_call_id: str


def _runtime(agent_name: str | None = "test-agent", tool_call_id: str = "call_1") -> _DummyRuntime:
    return _DummyRuntime(context={"agent_name": agent_name} if agent_name is not None else {}, tool_call_id=tool_call_id)


def _make_paths_mock(tmp_path: Path) -> MagicMock:
    paths = MagicMock()
    paths.base_dir = tmp_path
    paths.agent_dir = lambda name: tmp_path / "agents" / name
    paths.agents_dir = tmp_path / "agents"
    paths.user_agent_dir = lambda user_id, name: tmp_path / "users" / user_id / "agents" / name
    paths.user_agents_dir = lambda user_id: tmp_path / "users" / user_id / "agents"
    return paths


def _user_agent_dir(tmp_path: Path, name: str = "test-agent", user_id: str = DEFAULT_USER) -> Path:
    return tmp_path / "users" / user_id / "agents" / name


def _seed_agent(
    tmp_path: Path,
    name: str = "test-agent",
    *,
    description: str = "old desc",
    soul: str = "old soul",
    skills: list[str] | None = None,
    user_id: str = DEFAULT_USER,
) -> Path:
    """Create a baseline agent dir with config.yaml and SOUL.md for tests to mutate."""
    agent_dir = _user_agent_dir(tmp_path, name, user_id=user_id)
    agent_dir.mkdir(parents=True, exist_ok=True)
    cfg: dict = {"name": name, "description": description}
    if skills is not None:
        cfg["skills"] = skills
    (agent_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")
    return agent_dir


@pytest.fixture()
def patched_paths(tmp_path: Path):
    paths_mock = _make_paths_mock(tmp_path)
    with patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=paths_mock):
        # load_agent_config also calls get_paths(); patch the same target it uses.
        with patch("ideer.config.agents_config.get_paths", return_value=paths_mock):
            yield paths_mock


@pytest.fixture()
def stub_app_config():
    """Stub get_app_config so model validation accepts only known names."""
    fake = MagicMock()
    fake.get_model_config.side_effect = lambda name: object() if name in {"gpt-known", "m1"} else None
    with patch("ideer.tools.builtins.update_agent_tool.get_app_config", return_value=fake):
        yield fake


# --- Canonical catalog mode tests ---


@pytest_asyncio.fixture
async def catalog_db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _seed_user(catalog_db: async_sessionmaker[AsyncSession]) -> None:
    async def _seed() -> None:
        async with catalog_db() as session:
            session.add(UserModel(id=DEFAULT_USER, username=f"{DEFAULT_USER}@test.com", role="user", disabled=False))
            await session.commit()

    asyncio.run(_seed())


def _seed_skill_resource(catalog_db: async_sessionmaker[AsyncSession], resource_id: str, slug: str) -> None:
    async def _seed() -> None:
        async with catalog_db() as session:
            session.add(
                Resource(
                    id=resource_id,
                    type="skill",
                    slug=slug,
                    display_name=slug,
                    owner_id=DEFAULT_USER,
                    visibility="private",
                    lifecycle_status="active",
                    storage_kind="filesystem",
                    storage_key=f"skills/{resource_id}",
                )
            )
            await session.commit()

    asyncio.run(_seed())


def _create_canonical_agent(tmp_path: Path, catalog_db: async_sessionmaker[AsyncSession], name: str, *, soul: str, description: str) -> str:
    """Create a published canonical agent via setup_agent, returning its resource id."""
    with (
        patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=catalog_db),
        patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
    ):
        result = setup_agent.func(soul=soul, description=description, runtime=_runtime(agent_name=name))
    return result.update["created_agent_resource_id"]


def _published_dir(tmp_path: Path, resource_id: str, version: int) -> Path:
    return tmp_path / "resources" / "agents" / resource_id / "versions" / str(version)


def _assert_version(catalog_db: async_sessionmaker[AsyncSession], resource_id: str, version: int) -> None:
    async def _assert() -> None:
        async with catalog_db() as session:
            resource = (await session.execute(select(Resource).where(Resource.id == resource_id))).scalar_one()
            assert resource.latest_version == version
            versions = (await session.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource_id))).scalars().all()
            assert [item.version for item in versions] == list(range(1, version + 1))

    asyncio.run(_assert())


class TestUpdateAgentCanonical:
    def test_canonical_mode_updates_fields_via_draft_and_publish(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)
        resource_id = _create_canonical_agent(tmp_path, catalog_db, "canonical-agent", soul="# First Soul", description="First description")

        with (
            patch("ideer.tools.builtins.update_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            result = update_agent.func(runtime=_runtime("canonical-agent"), soul="# Second Soul", description="Second description")

        assert "soul" in result.update["messages"][0].content
        assert "description" in result.update["messages"][0].content
        _assert_version(catalog_db, resource_id, version=2)
        published = _published_dir(tmp_path, resource_id, 2)
        assert (published / "SOUL.md").read_text(encoding="utf-8") == "# Second Soul"
        cfg = yaml.safe_load((published / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["description"] == "Second description"
        assert not (tmp_path / "users" / DEFAULT_USER / "agents" / "canonical-agent").exists()

    def test_canonical_mode_omitted_fields_are_preserved(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)
        resource_id = _create_canonical_agent(tmp_path, catalog_db, "canonical-agent", soul="# Keep Soul", description="Keep description")

        with (
            patch("ideer.tools.builtins.update_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            result = update_agent.func(runtime=_runtime("canonical-agent"), description="Changed description")

        assert "description" in result.update["messages"][0].content
        assert "soul" not in result.update["messages"][0].content
        published = _published_dir(tmp_path, resource_id, 2)
        assert (published / "SOUL.md").read_text(encoding="utf-8") == "# Keep Soul"
        cfg = yaml.safe_load((published / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["description"] == "Changed description"

    def test_canonical_mode_resolves_skill_dependencies(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)
        _seed_skill_resource(catalog_db, "77777777-7777-7777-7777-777777777777", "research")
        resource_id = _create_canonical_agent(tmp_path, catalog_db, "canonical-agent", soul="# Skillful", description="desc")

        with (
            patch("ideer.tools.builtins.update_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            result = update_agent.func(runtime=_runtime("canonical-agent"), skills=["research"])

        assert "skills" in result.update["messages"][0].content
        cfg = yaml.safe_load((_published_dir(tmp_path, resource_id, 2) / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["skills"] == ["77777777-7777-7777-7777-777777777777"]

        async def _read_dependencies() -> list[str]:
            async with catalog_db() as session:
                dependencies = (await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == resource_id))).scalars().all()
                return [dependency.target_resource_id for dependency in dependencies]

        assert asyncio.run(_read_dependencies()) == ["77777777-7777-7777-7777-777777777777"]

    def test_canonical_mode_skills_omitted_keeps_existing_dependencies(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)
        _seed_skill_resource(catalog_db, "77777777-7777-7777-7777-777777777777", "research")
        resource_id = _create_canonical_agent(tmp_path, catalog_db, "canonical-agent", soul="# Skillful", description="desc")

        with (
            patch("ideer.tools.builtins.update_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            update_agent.func(runtime=_runtime("canonical-agent"), skills=["research"])
            update_agent.func(runtime=_runtime("canonical-agent"), description="bumped")

        cfg = yaml.safe_load((_published_dir(tmp_path, resource_id, 3) / "config.yaml").read_text(encoding="utf-8"))
        assert cfg["skills"] == ["77777777-7777-7777-7777-777777777777"], "omitting skills must preserve the existing dependency list"

    def test_canonical_mode_no_op_when_values_match(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)
        resource_id = _create_canonical_agent(tmp_path, catalog_db, "canonical-agent", soul="# Soul", description="Same description")

        with (
            patch("ideer.tools.builtins.update_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            result = update_agent.func(runtime=_runtime("canonical-agent"), description="Same description")

        assert "No changes applied" in result.update["messages"][0].content
        _assert_version(catalog_db, resource_id, version=1)

    def test_canonical_mode_unknown_agent_returns_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)

        with (
            patch("ideer.tools.builtins.update_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.update_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            result = update_agent.func(runtime=_runtime("ghost-agent"), description="x")

        assert "Error" in result.update["messages"][0].content
        assert "ghost-agent" in result.update["messages"][0].content

    def test_canonical_mode_without_database_returns_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        with patch("ideer.tools.builtins.update_agent_tool.get_session_factory", return_value=None):
            result = update_agent.func(runtime=_runtime("canonical-agent"), description="x")

        assert "Error" in result.update["messages"][0].content
