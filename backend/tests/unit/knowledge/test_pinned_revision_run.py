"""PINNED knowledge dependencies run fixed published revisions (M4 ticket 04)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeRevision
from app.agentplatform.resource_models import Resource, ResourceDependency, ResourceVersion
from app.agentplatform.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceConflict,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceService,
)
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pinned.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def _actor(user_id: str = "owner") -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id=None,
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


async def _seed_resource(
    session: AsyncSession,
    *,
    resource_type: str,
    slug: str,
    owner_id: str = "owner",
    latest_version: int = 1,
) -> Resource:
    resource = await ResourceService(session, _actor(owner_id)).create_resource(
        resource_type=resource_type,
        slug=slug,
        display_name=slug,
        storage_kind="database" if resource_type == "knowledge_base" else "filesystem",
    )
    resource.latest_version = latest_version
    resource.draft_revision = latest_version
    for version in range(1, latest_version + 1):
        session.add(
            ResourceVersion(
                id=str(uuid.uuid4()),
                resource_id=resource.id,
                version=version,
                content_hash=hashlib.sha256(f"{slug}-{version}".encode()).hexdigest(),
                storage_key=f"{resource_type}s/{resource.id}",
                scan_result={},
                content={"version": version},
                created_by=owner_id,
            )
        )
    return resource


def _published_revision(session: AsyncSession, kb: Resource, *, revision_no: int) -> KnowledgeRevision:
    row = KnowledgeRevision(
        id=f"kb-{kb.slug}-rev-{revision_no}",
        knowledge_base_id=kb.id,
        revision_no=revision_no,
        status="published",
        manifest_hash=str(revision_no) * 64,
        manifest_json=[],
        provider_doc_map_json={"doc": f"provider-doc-{revision_no}"},
        document_count=1,
        provider_dataset_id=f"{kb.slug}-dataset-{revision_no}",
        publish_attempt=1,
        created_by=kb.owner_id,
        published_at=datetime.now(UTC),
    )
    session.add(row)
    return row


@pytest.mark.asyncio
async def test_pinned_declaration_validates_revision_existence_and_ownership(session: AsyncSession) -> None:
    agent = await _seed_resource(session, resource_type="agent", slug="pinned-agent")
    kb = await _seed_resource(session, resource_type="knowledge_base", slug="pinned-kb")
    other_kb = await _seed_resource(session, resource_type="knowledge_base", slug="other-kb")
    draft_revision = _published_revision(session, kb, revision_no=0)
    draft_revision.status = "draft"
    draft_revision.published_at = None
    revision = _published_revision(session, kb, revision_no=1)
    foreign_revision = _published_revision(session, other_kb, revision_no=1)
    await session.commit()
    service = ResourceService(session, _actor())

    with pytest.raises(ResourceConflict, match="does not belong"):
        await service.replace_dependencies(agent.id, [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": str(uuid.uuid4())}])
    with pytest.raises(ResourceConflict, match="does not belong"):
        await service.replace_dependencies(agent.id, [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": foreign_revision.id}])
    with pytest.raises(ResourceConflict, match="published Knowledge Revision"):
        await service.replace_dependencies(agent.id, [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": draft_revision.id}])
    with pytest.raises(ResourceConflict, match="must be empty for live"):
        await service.replace_dependencies(agent.id, [{"resource_id": kb.id, "dependency_mode": "live", "revision_id": revision.id}])

    remaining = (await session.execute(select(ResourceDependency).where(ResourceDependency.source_resource_id == agent.id))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_pinned_declaration_requires_visible_knowledge_base(session: AsyncSession) -> None:
    agent = await _seed_resource(session, resource_type="agent", slug="pinned-agent")
    kb = await _seed_resource(session, resource_type="knowledge_base", slug="hidden-kb", owner_id="someone-else")
    revision = _published_revision(session, kb, revision_no=1)
    await session.commit()

    intruder = ResourceService(session, _actor("intruder"))
    with pytest.raises(ResourceNotFound):
        await intruder.replace_dependencies(agent.id, [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": revision.id}])
    await session.rollback()


@pytest.mark.asyncio
async def test_only_the_owner_can_redeclare_dependencies(session: AsyncSession) -> None:
    agent = await _seed_resource(session, resource_type="agent", slug="shared-agent")
    kb = await _seed_resource(session, resource_type="knowledge_base", slug="shared-kb")
    revision = _published_revision(session, kb, revision_no=1)
    await session.commit()
    await ResourceService(session, _actor()).replace_dependencies(
        agent.id,
        [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": revision.id}],
    )
    await session.commit()

    agent.visibility = "public"
    await session.commit()
    with pytest.raises(ResourcePermissionDenied):
        await ResourceService(
            session,
            _actor(
                "caller",
            ),
        ).replace_dependencies(
            agent.id,
            [{"resource_id": kb.id, "dependency_mode": "live"}],
        )


@pytest.mark.asyncio
async def test_pinned_revision_stays_fixed_when_a_newer_revision_publishes(session: AsyncSession) -> None:
    agent = await _seed_resource(session, resource_type="agent", slug="fixed-agent")
    kb = await _seed_resource(session, resource_type="knowledge_base", slug="fixed-kb")
    revision_one = _published_revision(session, kb, revision_no=1)
    revision_two = _published_revision(session, kb, revision_no=2)
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.active_revision_id = revision_two.id
    await session.commit()
    await ResourceService(session, _actor()).replace_dependencies(
        agent.id,
        [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": revision_one.id}],
    )
    await session.commit()

    service = ResourceService(session, _actor())
    closure = await service.resolve_dependency_closure(agent.id)
    kb_item = next(item for item in closure if item.resource.id == kb.id)
    assert kb_item.knowledge_revision is not None
    assert kb_item.knowledge_revision.id == revision_one.id
    assert kb_item.knowledge_revision.provider_dataset_id == "fixed-kb-dataset-1"

    snapshots = await service.create_run_snapshot("pinned-run", agent.id, closure=closure)
    await session.commit()
    kb_snapshot = next(snapshot for snapshot in snapshots if snapshot.resource_id == kb.id)
    assert kb_snapshot.knowledge_revision_id == revision_one.id
    assert kb_snapshot.provider_dataset_id == "fixed-kb-dataset-1"


@pytest.mark.asyncio
async def test_redeclaring_dependencies_after_run_start_does_not_move_its_snapshot(session: AsyncSession) -> None:
    agent = await _seed_resource(session, resource_type="agent", slug="midrun-agent")
    kb = await _seed_resource(session, resource_type="knowledge_base", slug="midrun-kb")
    revision_one = _published_revision(session, kb, revision_no=1)
    revision_two = _published_revision(session, kb, revision_no=2)
    await session.commit()
    service = ResourceService(session, _actor())
    await service.replace_dependencies(
        agent.id,
        [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": revision_one.id}],
    )
    await session.commit()
    closure = await service.resolve_dependency_closure(agent.id)
    await service.create_run_snapshot("running-run", agent.id, closure=closure)
    await session.commit()

    await service.replace_dependencies(
        agent.id,
        [{"resource_id": kb.id, "dependency_mode": "pinned", "revision_id": revision_two.id}],
    )
    await session.commit()

    from app.agentplatform.resource_models import RunResourceSnapshot

    frozen = (await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == "running-run"))).scalars().all()
    kb_snapshot = next(snapshot for snapshot in frozen if snapshot.resource_id == kb.id)
    assert kb_snapshot.knowledge_revision_id == revision_one.id
