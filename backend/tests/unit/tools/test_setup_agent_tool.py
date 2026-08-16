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
from ideer.runtime.user_context import reset_current_user, set_current_user
from ideer.tools.builtins.setup_agent_tool import (
    _upsert_agent_metadata,
    _upsert_skill_metadata_if_missing,
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


# --- Data loss prevention tests ---


class TestSetupAgentNoDataLoss:
    """Ensure shutil.rmtree only removes directories created during the current call."""

    def test_existing_agent_dir_preserved_on_failure(self, tmp_path: Path):
        """If the agent directory already exists and setup fails,
        the directory and its contents must NOT be deleted."""
        agent_dir = tmp_path / "users" / "test-user-autouse" / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        old_soul = agent_dir / "SOUL.md"
        old_soul.write_text("original soul content", encoding="utf-8")

        with patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)):
            # Force soul_file.write_text to raise after directory already exists
            with patch.object(Path, "write_text", side_effect=OSError("disk full")):
                setup_agent.func(
                    soul="new soul",
                    description="desc",
                    runtime=_make_runtime(),
                )

        # Directory must still exist
        assert agent_dir.exists(), "Pre-existing agent directory was deleted on failure"
        # Original SOUL.md should still be on disk (not deleted by rmtree)
        assert old_soul.exists(), "Pre-existing SOUL.md was deleted on failure"

    def test_new_agent_dir_cleaned_up_on_failure(self, tmp_path: Path):
        """If the agent directory is newly created and setup fails,
        the directory should be cleaned up."""
        agent_dir = tmp_path / "users" / "test-user-autouse" / "agents" / "test-agent"
        assert not agent_dir.exists()

        with patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)):
            with patch("yaml.dump", side_effect=OSError("write error")):
                setup_agent.func(
                    soul="new soul",
                    description="desc",
                    runtime=_make_runtime(),
                )

        # Newly created directory should be cleaned up
        assert not agent_dir.exists(), "Newly created agent directory was not cleaned up on failure"

    def test_successful_setup_creates_files(self, tmp_path: Path):
        """Happy path: setup_agent creates config.yaml and SOUL.md."""
        _call_setup_agent(tmp_path, soul="# My Agent", description="A test agent")

        agent_dir = tmp_path / "users" / "test-user-autouse" / "agents" / "test-agent"
        assert agent_dir.exists()
        assert (agent_dir / "SOUL.md").read_text() == "# My Agent"
        assert (agent_dir / "config.yaml").exists()

    @pytest.mark.no_auto_user
    def test_runtime_user_id_used_when_contextvar_missing(self, tmp_path: Path):
        """setup_agent should not fall back to default when runtime carries user_id."""
        runtime = _DummyRuntime(
            context={"agent_name": "test-agent", "user_id": "auth-user-42"},
            tool_call_id="tool-3",
        )

        with patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)):
            setup_agent.func(
                soul="# My Agent",
                description="A test agent",
                runtime=runtime,
            )

        expected_dir = tmp_path / "users" / "auth-user-42" / "agents" / "test-agent"
        default_dir = tmp_path / "users" / "default" / "agents" / "test-agent"
        assert (expected_dir / "SOUL.md").read_text() == "# My Agent"
        assert not default_dir.exists()

    @pytest.mark.no_auto_user
    def test_contextvar_user_id_is_used_when_runtime_context_has_no_user_id(self, tmp_path: Path):
        token = set_current_user(SimpleNamespace(id="context-user"))
        try:
            _call_setup_agent(tmp_path, soul="# Context Agent", description="context")
        finally:
            reset_current_user(token)

        assert (tmp_path / "users" / "context-user" / "agents" / "test-agent" / "SOUL.md").exists()
        assert not (tmp_path / "users" / "default" / "agents" / "test-agent").exists()

    @pytest.mark.no_auto_user
    def test_missing_agent_name_writes_the_shared_default_soul_file(self, tmp_path: Path):
        runtime = _DummyRuntime(context={}, tool_call_id="tool-default")

        with patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)):
            result = setup_agent.func(soul="# Shared", description="ignored", runtime=runtime)

        assert result.update["created_agent_name"] is None
        assert (tmp_path / "SOUL.md").read_text(encoding="utf-8") == "# Shared"
        assert not (tmp_path / "config.yaml").exists()

    def test_empty_description_and_explicit_empty_skills_are_persisted_as_no_description_and_no_skills(self, tmp_path: Path):
        runtime = _make_runtime("minimal-agent")

        with patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)):
            setup_agent.func(soul="# Minimal", description="", runtime=runtime, skills=[])

        config = (tmp_path / "users" / "test-user-autouse" / "agents" / "minimal-agent" / "config.yaml").read_text(encoding="utf-8")
        assert "name: minimal-agent" in config
        assert "description:" not in config
        assert "skills: []" in config


def test_upsert_agent_metadata_logs_database_failure(caplog):
    class FailingSession:
        async def __aenter__(self):
            raise RuntimeError("database offline")

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    with patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=lambda: FailingSession()):
        _upsert_agent_metadata("agent-a", "user-a")

    assert "Failed to write agent metadata" in caplog.text


def test_upsert_skill_metadata_skips_when_database_is_unavailable():
    storage = MagicMock()

    with patch("ideer.skills.storage.get_or_new_skill_storage", return_value=storage), patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=None):
        _upsert_skill_metadata_if_missing(["custom-skill"], "user-a")

    storage.custom_skill_exists.assert_not_called()


def test_upsert_skill_metadata_persists_only_existing_custom_skills():
    storage = MagicMock()
    storage.custom_skill_exists.side_effect = lambda name: name == "installed-skill"
    session = _MetadataSession()

    with patch("ideer.skills.storage.get_or_new_skill_storage", return_value=storage), patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=lambda: session):
        _upsert_skill_metadata_if_missing(["missing-skill", "installed-skill"], "user-a")

    assert storage.custom_skill_exists.call_args_list[0].args == ("missing-skill",)
    assert storage.custom_skill_exists.call_args_list[1].args == ("installed-skill",)
    assert len(session.added) == 1
    assert session.added[0].resource_id == "installed-skill"
    assert session.added[0].owner_id == "user-a"
    assert session.commits == 1


def test_upsert_skill_metadata_does_not_overwrite_existing_metadata():
    storage = MagicMock()
    storage.custom_skill_exists.return_value = True
    session = _MetadataSession(existing=object())

    with patch("ideer.skills.storage.get_or_new_skill_storage", return_value=storage), patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=lambda: session):
        _upsert_skill_metadata_if_missing(["existing-skill"], "user-a")

    assert session.added == []
    assert session.commits == 0


def test_upsert_skill_metadata_continues_after_one_skill_fails(caplog):
    storage = MagicMock()
    storage.custom_skill_exists.side_effect = [RuntimeError("storage failure"), True]
    session = _MetadataSession()

    with patch("ideer.skills.storage.get_or_new_skill_storage", return_value=storage), patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=lambda: session):
        _upsert_skill_metadata_if_missing(["broken-skill", "working-skill"], "user-a")

    assert "Failed to upsert metadata for skill 'broken-skill'" in caplog.text
    assert [resource.resource_id for resource in session.added] == ["working-skill"]
    assert session.commits == 1

    class FailingSkillNames(list):
        def __iter__(self):
            raise RuntimeError("skill list unavailable")

    with patch("ideer.skills.storage.get_or_new_skill_storage", return_value=storage), patch("ideer.tools.builtins.setup_agent_tool.get_session_factory", return_value=lambda: session):
        _upsert_skill_metadata_if_missing(FailingSkillNames(["unused"]), "user-a")

    assert "Failed to cascade skill metadata registration" in caplog.text


def test_setup_agent_cascades_nonempty_skill_metadata_registration(tmp_path: Path):
    runtime = _make_runtime("skill-agent")

    with (
        patch("ideer.tools.builtins.setup_agent_tool.get_paths", return_value=_make_paths_mock(tmp_path)),
        patch("ideer.tools.builtins.setup_agent_tool._upsert_agent_metadata") as upsert_agent,
        patch("ideer.tools.builtins.setup_agent_tool._upsert_skill_metadata_if_missing") as upsert_skills,
    ):
        result = setup_agent.func(
            soul="# Skill Agent",
            description="Uses selected skills",
            runtime=runtime,
            skills=["custom-skill"],
        )

    assert result.update["created_agent_name"] == "skill-agent"
    upsert_agent.assert_called_once_with("skill-agent", "test-user-autouse")
    upsert_skills.assert_called_once_with(["custom-skill"], "test-user-autouse")


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
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
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
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
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
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")
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
        monkeypatch.setenv("IDEER_RESOURCE_CATALOG_MODE", "canonical")

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
