"""LIVE knowledge dependencies freeze at Run start (M4 ticket 03)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeRevision
from app.agentplatform.resource_models import Resource, ResourceDependency, ResourceVersion
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceConflict, ResourceService
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def store(tmp_path) -> AsyncIterator[tuple[AsyncSession, async_sessionmaker]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'freeze.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session, factory
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
) -> Resource:
    resource = await ResourceService(session, _actor()).create_resource(
        resource_type=resource_type,
        slug=slug,
        display_name=slug,
        storage_kind="database" if resource_type == "knowledge_base" else "filesystem",
    )
    resource.latest_version = 1
    resource.draft_revision = 1
    session.add(
        ResourceVersion(
            id=str(uuid.uuid4()),
            resource_id=resource.id,
            version=1,
            content_hash=hashlib.sha256(slug.encode()).hexdigest(),
            storage_key=f"{resource_type}s/{resource.id}",
            scan_result={},
            content={"description": slug},
            created_by=resource.owner_id,
        )
    )
    return resource


def _revision(
    session: AsyncSession,
    kb: Resource,
    *,
    revision_no: int,
    status: str = "published",
    content: bytes = b"frozen",
) -> KnowledgeRevision:
    entry = {
        "document_id": f"doc-{revision_no}",
        "content_hash": hashlib.sha256(content).hexdigest(),
        "filename": f"guide-{revision_no}.txt",
        "size_bytes": len(content),
        "mime_type": "text/plain",
        "metadata": {},
    }
    row = KnowledgeRevision(
        id=str(uuid.uuid4()),
        knowledge_base_id=kb.id,
        revision_no=revision_no,
        status=status,
        manifest_hash=hashlib.sha256(str(entry).encode()).hexdigest(),
        manifest_json=[entry],
        provider_doc_map_json={f"doc-{revision_no}": f"provider-doc-{revision_no}"},
        document_count=1,
        provider_dataset_id=f"published-dataset-{revision_no}",
        provider_revision_hint=f"rev-{revision_no}",
        publish_attempt=1,
        created_by=kb.owner_id,
        published_at=datetime.now(UTC) if status == "published" else None,
    )
    session.add(row)
    return row


async def _seed_kb_dependency(session: AsyncSession, agent: Resource, kb: Resource) -> None:
    session.add(ResourceDependency(id=str(uuid.uuid4()), source_resource_id=agent.id, target_resource_id=kb.id, dependency_mode="live"))


async def _seed_agent_with_kb(session: AsyncSession, slug: str = "kb-live") -> tuple[Resource, Resource]:
    agent = await _seed_resource(session, resource_type="agent", slug="helper")
    kb = await _seed_resource(session, resource_type="knowledge_base", slug=slug)
    await _seed_kb_dependency(session, agent, kb)
    await session.commit()
    return agent, kb


@pytest.mark.asyncio
async def test_live_dependency_freezes_published_revision_into_run_snapshot(store) -> None:
    session, _factory = store
    agent, kb = await _seed_agent_with_kb(session)
    revision = _revision(session, kb, revision_no=1)
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.retrieval_profile_json = {"top_k": 6}
    kb_row.embedding_profile_json = {"model": "bge-m3"}
    kb_row.active_revision_id = revision.id
    await session.commit()

    service = ResourceService(session, _actor())
    closure = await service.resolve_dependency_closure(agent.id)
    kb_items = [item for item in closure if item.resource.type == "knowledge_base"]
    assert len(kb_items) == 1
    assert kb_items[0].knowledge_revision is not None
    assert kb_items[0].knowledge_revision.id == revision.id

    snapshots = await service.create_run_snapshot("run-a", agent.id, closure=closure)
    await session.commit()
    kb_snapshot = next(snapshot for snapshot in snapshots if snapshot.resource_id == kb.id)
    assert kb_snapshot.knowledge_revision_id == revision.id
    assert kb_snapshot.knowledge_revision_no == 1
    assert kb_snapshot.manifest_hash == revision.manifest_hash
    assert kb_snapshot.provider_dataset_id == "published-dataset-1"
    assert kb_snapshot.provider_type == "ragflow"
    assert len(kb_snapshot.retrieval_profile_hash) == 64
    assert len(kb_snapshot.embedding_profile_hash) == 64
    agent_snapshot = next(snapshot for snapshot in snapshots if snapshot.resource_id == agent.id)
    assert agent_snapshot.knowledge_revision_id is None


@pytest.mark.asyncio
async def test_profile_change_after_freeze_does_not_move_run_a(store) -> None:
    session, _factory = store
    agent, kb = await _seed_agent_with_kb(session)
    revision = _revision(session, kb, revision_no=1)
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.active_revision_id = revision.id
    await session.commit()

    service = ResourceService(session, _actor())
    closure = await service.resolve_dependency_closure(agent.id)
    snapshots = await service.create_run_snapshot("run-a", agent.id, closure=closure)
    await session.commit()
    kb_snapshot = next(snapshot for snapshot in snapshots if snapshot.resource_id == kb.id)
    original_profile_hash = kb_snapshot.retrieval_profile_hash

    kb_row.retrieval_profile_json = {"top_k": 99}
    await session.commit()

    new_closure = await service.resolve_dependency_closure(agent.id)
    kb_item = next(item for item in new_closure if item.resource.type == "knowledge_base")
    assert kb_item.knowledge_revision is not None and kb_item.knowledge_revision.id == revision.id
    new_snapshots = await service.create_run_snapshot("run-b", agent.id, closure=new_closure)
    new_kb_snapshot = next(snapshot for snapshot in new_snapshots if snapshot.resource_id == kb.id)
    assert new_kb_snapshot.retrieval_profile_hash != original_profile_hash
    assert kb_snapshot.retrieval_profile_hash == original_profile_hash


@pytest.mark.asyncio
async def test_publishing_rev2_moves_new_runs_not_run_a(store) -> None:
    session, _factory = store
    agent, kb = await _seed_agent_with_kb(session)
    revision_one = _revision(session, kb, revision_no=1)
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.active_revision_id = revision_one.id
    await session.commit()

    service = ResourceService(session, _actor())
    closure_a = await service.resolve_dependency_closure(agent.id)
    await service.create_run_snapshot("run-a", agent.id, closure=closure_a)
    await session.commit()

    revision_two = _revision(session, kb, revision_no=2)
    kb_row.active_revision_id = revision_two.id
    await session.commit()

    closure_b = await service.resolve_dependency_closure(agent.id)
    kb_item_b = next(item for item in closure_b if item.resource.type == "knowledge_base")
    assert kb_item_b.knowledge_revision is not None and kb_item_b.knowledge_revision.id == revision_two.id
    await service.create_run_snapshot("run-b", agent.id, closure=closure_b)
    await session.commit()

    from sqlalchemy import select

    from app.agentplatform.resource_models import RunResourceSnapshot

    run_a_kb = (await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == "run-a", RunResourceSnapshot.resource_id == kb.id))).scalar_one()
    run_b_kb = (await session.execute(select(RunResourceSnapshot).where(RunResourceSnapshot.run_id == "run-b", RunResourceSnapshot.resource_id == kb.id))).scalar_one()
    assert run_a_kb.knowledge_revision_id == revision_one.id
    assert run_a_kb.provider_dataset_id == "published-dataset-1"
    assert run_b_kb.knowledge_revision_id == revision_two.id
    assert run_b_kb.provider_dataset_id == "published-dataset-2"


@pytest.mark.asyncio
async def test_missing_published_revision_rejects_the_run(store) -> None:
    session, _factory = store
    agent, kb = await _seed_agent_with_kb(session)
    _revision(session, kb, revision_no=1, status="draft")
    await session.commit()

    service = ResourceService(session, _actor())
    with pytest.raises(ResourceConflict, match="published revision"):
        await service.resolve_dependency_closure(agent.id)


@pytest.mark.asyncio
async def test_draft_active_revision_is_not_resolvable(store) -> None:
    session, _factory = store
    agent, kb = await _seed_agent_with_kb(session)
    revision = _revision(session, kb, revision_no=1, status="draft")
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.active_revision_id = revision.id
    await session.commit()

    service = ResourceService(session, _actor())
    with pytest.raises(ResourceConflict, match="published revision"):
        await service.resolve_dependency_closure(agent.id)
