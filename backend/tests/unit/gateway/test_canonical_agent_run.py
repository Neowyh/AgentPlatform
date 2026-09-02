"""Direct LangGraph Run preparation for UUID-addressed canonical Agents."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import ideer.persistence.models  # noqa: F401
from app.gateway.canonical_agent_run_preparation import prepare_canonical_agent_run
from app.gateway.routers.assistants_compat import _list_canonical_assistants
from ideer.persistence.base import Base
from ideer.persistence.models.audit_log import AuditLog
from ideer.persistence.models.resource_catalog import Resource, RunResourceSnapshot
from ideer.persistence.models.user import UserModel
from ideer.resources.publisher import ResourcePublisher
from ideer.resources.runtime import CanonicalResourceLoader, ResourceRuntimeError
from ideer.resources.service import ResourceAction, ResourceActor, ResourceService
from ideer.resources.storage import ResourceStorage


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'canonical-run.db'}")
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
async def test_prepare_canonical_agent_run_freezes_visible_version_and_hides_private_resource(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visible_run_id = str(uuid.uuid4())
    hidden_run_id = str(uuid.uuid4())
    source = tmp_path / "agent-source"
    source.mkdir()
    (source / "config.yaml").write_text("name: canonical-agent\n")
    (source / "SOUL.md").write_text("frozen soul\n")
    async with session_factory() as session:
        session.add_all(
            [
                UserModel(id="owner", username="owner@test.com", role="user", department_id=None, disabled=False),
                UserModel(id="runner", username="runner@test.com", role="user", department_id=None, disabled=False),
            ]
        )
        await session.commit()
        service = ResourceService(session, _actor("owner"))
        resource = await service.create_resource(
            resource_type="agent",
            slug="canonical-agent",
            display_name="Canonical Agent",
            storage_kind="filesystem",
        )
        await session.commit()
        publisher = ResourcePublisher(service, ResourceStorage(tmp_path))
        draft = await publisher.save_filesystem_draft(resource.id, source_dir=source, expected_revision=0)
        await publisher.publish_filesystem(resource.id, expected_draft_revision=draft.revision, scan_result={})
        resource.visibility = "public"
        await session.commit()
        resource_id = resource.id

    monkeypatch.setattr("ideer.persistence.engine.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.gateway.audit.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("ideer.config.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    request = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id="runner")))

    factory = await prepare_canonical_agent_run(resource_id, request, visible_run_id)

    assert callable(factory)
    assistants = await _list_canonical_assistants(request)
    assert [(item.assistant_id, item.name) for item in assistants] == [(resource_id, "Canonical Agent")]
    async with session_factory() as session:
        snapshots = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == visible_run_id))).scalars())
        assert [(item.resource_id, item.version) for item in snapshots] == [(resource_id, 1)]

    rejected_run_id = str(uuid.uuid4())
    with pytest.raises(HTTPException) as rejected_info:
        await prepare_canonical_agent_run(
            resource_id,
            request,
            rejected_run_id,
            preferred_skill="academic-paper-review",
            diagnostic_context={
                "task_id": "academic-paper-review",
                "context_source": "scenario_binding",
            },
            thread_id="thread-123",
        )
    assert rejected_info.value.status_code == 409
    assert rejected_info.value.detail == {
        "code": "skill_outside_agent_closure",
        "message": "The selected Skill is not available to the current Expert.",
        "agent": {"resource_id": resource_id, "slug": "canonical-agent"},
        "requested_skill": "academic-paper-review",
        "available_skills": [],
        "context_source": "scenario_binding",
    }
    async with session_factory() as session:
        audit = (await session.execute(select(AuditLog).where(AuditLog.action == "run_preparation_rejected"))).scalar_one()
        assert audit.detail is not None
        assert '"thread_id": "thread-123"' in audit.detail
        assert '"run_attempt_id": "' in audit.detail
        assert '"task_id": "academic-paper-review"' in audit.detail
        assert "message" not in audit.detail

    original_skill_loader = CanonicalResourceLoader.load_agent_skill_definitions

    async def fail_skill_loading(*_args: object, **_kwargs: object) -> list[object]:
        raise ResourceRuntimeError("skill view preparation failed")

    monkeypatch.setattr(CanonicalResourceLoader, "load_agent_skill_definitions", fail_skill_loading)
    with pytest.raises(HTTPException) as failed_info:
        await prepare_canonical_agent_run(resource_id, request, hidden_run_id)
    assert failed_info.value.status_code == 409
    async with session_factory() as session:
        failed = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == hidden_run_id))).scalars())
        assert failed == []
    monkeypatch.setattr(
        CanonicalResourceLoader,
        "load_agent_skill_definitions",
        original_skill_loader,
    )

    async with session_factory() as session:
        resource = await session.get(Resource, resource_id)
        assert resource is not None
        resource.visibility = "private"
        await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await prepare_canonical_agent_run(resource_id, request, hidden_run_id)
    assert exc_info.value.status_code == 404
    async with session_factory() as session:
        hidden = list((await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == hidden_run_id))).scalars())
        assert hidden == []
