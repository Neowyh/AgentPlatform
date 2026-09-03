"""T3: canonical run preparation resolves and loads in a single pass.

Regression: with a preferred Skill, the dependency closure was resolved twice
(once for the Skill check, once inside the snapshot freeze) and the Agent
definition was loaded twice (once directly, once inside skill loading).
Both must happen exactly once per preparation.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from app.gateway.canonical_agent_run_preparation import prepare_canonical_agent_run
from ideer.persistence.base import Base
from ideer.persistence.models.user import UserModel
from ideer.resources.publisher import ResourcePublisher
from ideer.resources.runtime import CanonicalResourceLoader
from ideer.resources.service import ResourceAction, ResourceActor, ResourceService
from ideer.resources.storage import ResourceStorage


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'single-pass.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _actor(user_id: str) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id="dept-a",
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


@pytest.mark.asyncio
async def test_prepare_resolves_closure_and_loads_agent_once(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_source = tmp_path / "agent-source"
    agent_source.mkdir()
    (agent_source / "config.yaml").write_text("name: single-pass-agent\n")
    (agent_source / "SOUL.md").write_text("frozen soul\n")
    skill_source = tmp_path / "skill-source"
    skill_source.mkdir()
    (skill_source / "SKILL.md").write_text("---\nname: single-pass-skill\ndescription: Single pass skill\n---\n\n# Skill\n")
    async with session_factory() as session:
        session.add_all(
            [
                UserModel(id="owner", username="owner@test.com", role="user", department_id=None, disabled=False),
                UserModel(id="runner", username="runner@test.com", role="user", department_id=None, disabled=False),
            ]
        )
        await session.commit()
        service = ResourceService(session, _actor("owner"))
        agent = await service.create_resource(
            resource_type="agent",
            slug="single-pass-agent",
            display_name="Single Pass Agent",
            storage_kind="filesystem",
        )
        await session.commit()
        skill = await service.create_resource(
            resource_type="skill",
            slug="single-pass-skill",
            display_name="Single Pass Skill",
            storage_kind="filesystem",
        )
        await session.commit()
        publisher = ResourcePublisher(service, ResourceStorage(tmp_path))
        draft = await publisher.save_filesystem_draft(agent.id, source_dir=agent_source, expected_revision=0)
        await publisher.publish_filesystem(agent.id, expected_draft_revision=draft.revision, scan_result={})
        draft = await publisher.save_filesystem_draft(skill.id, source_dir=skill_source, expected_revision=0)
        await publisher.publish_filesystem(skill.id, expected_draft_revision=draft.revision, scan_result={})
        await service.replace_dependencies(agent.id, [skill.id])
        agent.visibility = "public"
        skill.visibility = "public"
        await session.commit()
        agent_id, skill_id = agent.id, skill.id

    monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.gateway.audit.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("ideer.config.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    closure_calls: list[str] = []
    original_resolve = ResourceService.resolve_dependency_closure

    async def counting_resolve(self, root_resource_id: str):
        closure_calls.append(root_resource_id)
        return await original_resolve(self, root_resource_id)

    agent_loads: list[str] = []
    original_load_agent = CanonicalResourceLoader.load_agent

    async def counting_load_agent(self, run_id: str, resource_id: str):
        agent_loads.append(resource_id)
        return await original_load_agent(self, run_id, resource_id)

    monkeypatch.setattr(ResourceService, "resolve_dependency_closure", counting_resolve)
    monkeypatch.setattr(CanonicalResourceLoader, "load_agent", counting_load_agent)

    request = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id="runner")))
    factory = await prepare_canonical_agent_run(agent_id, request, str(uuid.uuid4()), preferred_skill=skill_id)

    assert callable(factory)
    assert closure_calls == [agent_id]
    assert agent_loads == [agent_id]
