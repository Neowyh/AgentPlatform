"""Tests for setup_agent tool — validates agent name security and data loss prevention."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from ideer.persistence.base import Base
from ideer.persistence.models.resource_catalog import Resource, ResourceDependency, ResourceVersion
from ideer.persistence.models.user import UserModel
from ideer.tools.builtins.setup_agent_tool import (
    setup_agent,
)

# --- Helpers ---


class _DummyRuntime(SimpleNamespace):
    context: dict
    tool_call_id: str


def _make_runtime(agent_name: str | None = "test-agent") -> MagicMock:
    runtime = MagicMock()
    runtime.context = {"agent_name": agent_name}
    runtime.tool_call_id = "call_1"
    return runtime


def _make_paths_mock(tmp_path: Path):
    paths = MagicMock()
    paths.base_dir = tmp_path
    paths.agent_dir = lambda name: tmp_path / "agents" / name
    paths.user_agent_dir = lambda user_id, name: tmp_path / "users" / user_id / "agents" / name
    return paths


def _call_setup_agent(tmp_path: Path, soul: str, description: str, agent_name: str = "test-agent"):
    """Call the underlying setup_agent function directly, bypassing langchain tool wrapper."""
    with patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)):
        return setup_agent.func(
            soul=soul,
            description=description,
            runtime=_make_runtime(agent_name),
        )


class _MetadataSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, statement):
        del statement
        return SimpleNamespace(scalar_one_or_none=lambda: self.existing)

    def add(self, resource):
        self.added.append(resource)

    async def commit(self):
        self.commits += 1


# --- Agent name validation tests ---


def test_setup_agent_rejects_invalid_agent_name_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("IDEER_HOME", str(tmp_path))
    outside_dir = tmp_path.parent / "outside-target"
    traversal_agent = f"../../../{outside_dir.name}/evil"
    runtime = _DummyRuntime(context={"agent_name": traversal_agent}, tool_call_id="tool-1")

    result = setup_agent.func(soul="test soul", description="desc", runtime=runtime)

    messages = result.update["messages"]
    assert len(messages) == 1
    assert "Invalid agent name" in messages[0].content
    assert not (tmp_path / "users" / "test-user-autouse" / "agents").exists()
    assert not (outside_dir / "evil" / "SOUL.md").exists()


def test_setup_agent_rejects_absolute_agent_name_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("IDEER_HOME", str(tmp_path))
    absolute_agent = str(tmp_path / "outside-agent")
    runtime = _DummyRuntime(context={"agent_name": absolute_agent}, tool_call_id="tool-2")

    result = setup_agent.func(soul="test soul", description="desc", runtime=runtime)

    messages = result.update["messages"]
    assert len(messages) == 1
    assert "Invalid agent name" in messages[0].content
    assert not (tmp_path / "users" / "test-user-autouse" / "agents").exists()
    assert not (Path(absolute_agent) / "SOUL.md").exists()


# --- Canonical catalog mode tests ---


@pytest_asyncio.fixture
async def catalog_db(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _user_model(user_id: str = "test-user-autouse") -> UserModel:
    return UserModel(id=user_id, username=f"{user_id}@test.com", role="user", disabled=False)


def _skill_resource(resource_id: str, slug: str, owner_id: str) -> Resource:
    return Resource(
        id=resource_id,
        type="skill",
        slug=slug,
        display_name=slug,
        owner_id=owner_id,
        visibility="private",
        lifecycle_status="active",
        storage_kind="filesystem",
        storage_key=f"skills/{resource_id}",
    )


class TestSetupAgentCanonical:
    def test_canonical_mode_creates_published_agent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)

        with (
            patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            result = setup_agent.func(
                soul="# Canonical Agent",
                description="A canonical agent",
                runtime=_make_runtime("canonical-agent"),
            )

        assert result.update["created_agent_name"] == "canonical-agent"
        resource_id = result.update["created_agent_resource_id"]
        assert resource_id

        _assert_published_agent(catalog_db, resource_id, "canonical-agent", version=1)
        assert not (tmp_path / "users" / "test-user-autouse" / "agents" / "canonical-agent").exists()
        assert (tmp_path / "resources" / "agents" / resource_id / "versions" / "1" / "config.yaml").exists()
        published = tmp_path / "resources" / "agents" / resource_id / "versions" / "1"
        assert (published / "SOUL.md").read_text(encoding="utf-8") == "# Canonical Agent"

    def test_canonical_mode_updates_existing_agent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)

        with (
            patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            first = setup_agent.func(
                soul="# First Soul",
                description="First description",
                runtime=_make_runtime("canonical-agent"),
            )
            second = setup_agent.func(
                soul="# Second Soul",
                description="Second description",
                runtime=_make_runtime("canonical-agent"),
            )

        resource_id = first.update["created_agent_resource_id"]
        assert second.update["created_agent_resource_id"] == resource_id
        _assert_published_agent(catalog_db, resource_id, "canonical-agent", version=2)
        published = tmp_path / "resources" / "agents" / resource_id / "versions" / "2"
        assert (published / "SOUL.md").read_text(encoding="utf-8") == "# Second Soul"

    def test_canonical_mode_resolves_skill_dependencies(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        catalog_db: async_sessionmaker[AsyncSession],
    ) -> None:
        _seed_user(catalog_db)

        async def _seed_skill() -> None:
            async with catalog_db() as session:
                session.add(_skill_resource("77777777-7777-7777-7777-777777777777", "research", "test-user-autouse"))
                await session.commit()

        asyncio.run(_seed_skill())

        with (
            patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=catalog_db),
            patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        ):
            result = setup_agent.func(
                soul="# Skillful Agent",
                description="Uses skills",
                runtime=_make_runtime("skillful-agent"),
                skills=["research", "ghost-skill"],
            )

        resource_id = result.update["created_agent_resource_id"]
        _assert_published_agent(catalog_db, resource_id, "skillful-agent", version=1)

        async def _read_dependencies() -> list[str]:
            async with catalog_db() as session:
                dependencies = (await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == resource_id))).scalars().all()
                return [dependency.target_resource_id for dependency in dependencies]

        assert asyncio.run(_read_dependencies()) == ["77777777-7777-7777-7777-777777777777"]

    def test_canonical_mode_without_database_returns_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        with patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=None):
            result = setup_agent.func(
                soul="# No DB",
                description="desc",
                runtime=_make_runtime("no-db-agent"),
            )

        messages = result.update["messages"]
        assert len(messages) == 1
        assert "Error" in messages[0].content
        assert "created_agent_resource_id" not in result.update


def _seed_user(catalog_db: async_sessionmaker[AsyncSession]) -> None:
    async def _seed() -> None:
        async with catalog_db() as session:
            session.add(_user_model())
            await session.commit()

    asyncio.run(_seed())


def _assert_published_agent(
    catalog_db: async_sessionmaker[AsyncSession],
    resource_id: str,
    slug: str,
    *,
    version: int,
) -> None:
    async def _assert() -> None:
        async with catalog_db() as session:
            resource = (await session.execute(select(Resource).where(Resource.id == resource_id))).scalar_one()
            assert resource.type == "agent"
            assert resource.slug == slug
            assert resource.owner_id == "test-user-autouse"
            assert resource.latest_version == version
            versions = (await session.execute(select(ResourceVersion).where(ResourceVersion.resource_id == resource_id))).scalars().all()
            assert [item.version for item in versions] == list(range(1, version + 1))

    asyncio.run(_assert())
