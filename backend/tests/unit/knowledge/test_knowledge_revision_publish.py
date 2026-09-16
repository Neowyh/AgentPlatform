"""Immutable Knowledge Revision publishing (M4 ticket 02)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.documents import KnowledgeDocumentService
from app.agentplatform.knowledge.integrity import INTEGRITY_DRIFTED
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument, KnowledgeRevision
from app.agentplatform.knowledge.provider import KnowledgeProviderError, ProviderIngestionResult
from app.agentplatform.knowledge.revisions import (
    KnowledgeRevisionService,
    execute_publish,
)
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceConflict, ResourceNotFound, ResourcePermissionDenied, ResourceService
from deerflow.persistence.base import Base

MAX_PUBLISH_ATTEMPTS = 3


class FakePublishProvider:
    """Controllable provider recording every call for assertions."""

    def __init__(
        self,
        *,
        fail_ingest_on_call: int | None = None,
        doc_status: str = "ready",
        extra_dataset_documents: int = 0,
        fail_create_dataset: bool = False,
        dataset_prefix: str = "published-dataset",
        omit_content_hash: bool = False,
    ) -> None:
        self.fail_ingest_on_call = fail_ingest_on_call
        self.doc_status = doc_status
        self.extra_dataset_documents = extra_dataset_documents
        self.fail_create_dataset = fail_create_dataset
        self.dataset_prefix = dataset_prefix
        self.omit_content_hash = omit_content_hash
        self.created_datasets: list[str] = []
        self.created_embedding_models: list[str | None] = []
        self.ingest_calls: list[dict] = []
        self.status_calls: list[dict] = []
        self.dataset_documents: dict[str, list[dict]] = {}

    async def create_dataset(self, *, name: str, embedding_model: str | None = None) -> str:
        if self.fail_create_dataset:
            raise KnowledgeProviderError("dataset_failed", "internal dataset detail")
        dataset_id = f"{self.dataset_prefix}-{len(self.created_datasets) + 1}"
        self.created_datasets.append(name)
        self.created_embedding_models.append(embedding_model)
        self.dataset_documents[dataset_id] = []
        return dataset_id

    async def ingest(
        self,
        *,
        dataset_id: str,
        filename: str,
        mime_type: str,
        content: bytes,
        provider_document_id: str | None = None,
        rebuild: bool = False,
    ) -> ProviderIngestionResult:
        self.ingest_calls.append(
            {
                "dataset_id": dataset_id,
                "filename": filename,
                "provider_document_id": provider_document_id,
                "rebuild": rebuild,
            }
        )
        if self.fail_ingest_on_call is not None and len(self.ingest_calls) >= self.fail_ingest_on_call:
            raise KnowledgeProviderError("parse_failed", "internal parse detail")
        document_id = provider_document_id or f"provider-doc-{sum(len(items) for items in self.dataset_documents.values()) + 1}"
        document = {"id": document_id, "name": filename}
        if not self.omit_content_hash:
            document["content_hash"] = hashlib.sha256(content).hexdigest()
        self.dataset_documents.setdefault(dataset_id, []).append(document)
        return ProviderIngestionResult(document_id, "processing")

    async def get_status(self, *, dataset_id: str, provider_document_id: str) -> str:
        self.status_calls.append({"dataset_id": dataset_id, "provider_document_id": provider_document_id})
        return self.doc_status

    async def delete_document(self, *, dataset_id: str, provider_document_id: str) -> None:
        self.delete_calls = getattr(self, "delete_calls", [])
        self.delete_calls.append({"dataset_id": dataset_id, "provider_document_id": provider_document_id})
        self.dataset_documents[dataset_id] = [item for item in self.dataset_documents.get(dataset_id, []) if item["id"] != provider_document_id]

    async def list_dataset_documents(self, *, dataset_id: str) -> list[dict]:
        documents = list(self.dataset_documents.get(dataset_id, []))
        for extra in range(self.extra_dataset_documents):
            documents.append({"id": f"stray-document-{extra}", "name": f"stray-{extra}.txt"})
        return documents


@pytest_asyncio.fixture
async def store(tmp_path) -> AsyncIterator[tuple[AsyncSession, async_sessionmaker]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'publish.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session, factory
    await engine.dispose()


def _actor(
    user_id: str = "owner",
    *,
    permissions: set[ResourceAction] | None = None,
) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id=None,
        role="user",
        permissions=frozenset(permissions or {ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


async def _seed_kb(session: AsyncSession, *, owner_id: str = "owner", slug: str = "publish") -> Resource:
    kb = await ResourceService(session, _actor(owner_id)).create_resource(
        resource_type="knowledge_base",
        slug=slug,
        display_name=slug,
        storage_kind="database",
    )
    await session.commit()
    return kb


def _seed_document(
    session: AsyncSession,
    tmp_path,
    kb: Resource,
    filename: str,
    content: bytes,
) -> KnowledgeDocument:
    document_id = str(uuid.uuid4())
    path = tmp_path / "knowledge-documents" / kb.id / f"{document_id}-{filename}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    row = KnowledgeDocument(
        id=document_id,
        resource_id=kb.id,
        original_filename=filename,
        size_bytes=len(content),
        mime_type="text/plain",
        content_hash=hashlib.sha256(content).hexdigest(),
        storage_key=path.relative_to(tmp_path).as_posix(),
        metadata_json={},
        provider_document_id=f"draft-{document_id[:8]}",
        status="ready",
        created_by=kb.owner_id,
    )
    session.add(row)
    return row


async def _seed_candidate(session: AsyncSession, tmp_path, kb: Resource, *, documents: int = 1) -> dict:
    for index in range(documents):
        _seed_document(session, tmp_path, kb, f"guide-{index}.txt", f"content {index}".encode())
    await session.commit()
    candidate = await KnowledgeRevisionService(session, _actor(kb.owner_id)).create_revision(kb.id)
    await session.commit()
    return candidate


async def _revision(factory: async_sessionmaker, revision_id: str) -> KnowledgeRevision:
    async with factory() as fresh:
        revision = await fresh.get(KnowledgeRevision, revision_id)
        assert revision is not None
        return revision


async def _kb_row(factory: async_sessionmaker, kb_id: str) -> KnowledgeBase:
    async with factory() as fresh:
        row = await fresh.get(KnowledgeBase, kb_id)
        assert row is not None
        return row


@pytest.mark.asyncio
async def test_publish_switches_pointer_only_after_dataset_verification(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb, documents=2)
    await session.commit()

    service = KnowledgeRevisionService(session, _actor())
    requested = await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()
    assert requested["status"] == "indexing"
    kb_row = await _kb_row(factory, kb.id)
    assert kb_row.active_revision_id is None

    provider = FakePublishProvider()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, poll_interval=0, parse_timeout=5)
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "published"
    assert revision.published_at is not None
    assert revision.provider_dataset_id == "published-dataset-1"
    assert len(revision.provider_doc_map_json) == 2
    kb_row = await _kb_row(factory, kb.id)
    assert kb_row.active_revision_id == revision.id
    assert provider.created_datasets == [f"ideer-kb-{kb.id[:8]}-rev1-{str(candidate['id'])[:8]}"]
    assert provider.created_embedding_models == [None]
    assert {call["dataset_id"] for call in provider.ingest_calls} == {"published-dataset-1"}
    assert {call["provider_document_id"] for call in provider.status_calls} == set(revision.provider_doc_map_json.values())


@pytest.mark.asyncio
async def test_prepare_builds_ready_candidate_without_switching_pointer(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    kb = await _seed_kb(session, slug="prepare")
    candidate = await _seed_candidate(session, tmp_path, kb, documents=1)
    provider = FakePublishProvider()
    service = KnowledgeRevisionService(session, _actor())
    requested = await service.prepare_revision(kb.id, str(candidate["id"]), provider=provider)
    await session.commit()

    await execute_publish(
        factory,
        resource_id=kb.id,
        revision_id=str(candidate["id"]),
        actor_id="owner",
        provider=provider,
        execution_token=requested["publish_execution_token"],
        poll_interval=0,
        parse_timeout=5,
        activate=False,
    )

    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "ready"
    assert (await _kb_row(factory, kb.id)).active_revision_id is None


@pytest.mark.asyncio
async def test_prepare_rejects_revision_known_to_be_drifted(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, _factory = store
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    kb = await _seed_kb(session, slug="drifted-prepare")
    candidate = await _seed_candidate(session, tmp_path, kb)
    revision = await session.get(KnowledgeRevision, str(candidate["id"]))
    assert revision is not None
    revision.status = "ready"
    revision.integrity_status = INTEGRITY_DRIFTED
    revision.provider_dataset_id = "drifted-dataset"
    await session.commit()

    with pytest.raises(ResourceConflict, match="not preparable"):
        await KnowledgeRevisionService(session, _actor()).prepare_revision(
            kb.id,
            str(candidate["id"]),
            provider=FakePublishProvider(),
        )


@pytest.mark.asyncio
async def test_prepare_failure_can_be_retried_without_duplicate_dataset(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    kb = await _seed_kb(session, slug="prepare-retry")
    candidate = await _seed_candidate(session, tmp_path, kb)
    revision_id = str(candidate["id"])

    failing = FakePublishProvider(fail_create_dataset=True)
    requested = await KnowledgeRevisionService(session, _actor()).prepare_revision(kb.id, revision_id, provider=failing)
    await session.commit()
    await execute_publish(factory, resource_id=kb.id, revision_id=revision_id, actor_id="owner", provider=failing, execution_token=requested["publish_execution_token"], poll_interval=0, parse_timeout=5, activate=False)
    failed = await _revision(factory, revision_id)
    assert failed.status == "failed"

    retry_provider = FakePublishProvider()
    retried = await KnowledgeRevisionService(session, _actor()).prepare_revision(kb.id, revision_id, provider=retry_provider)
    await session.commit()
    await execute_publish(factory, resource_id=kb.id, revision_id=revision_id, actor_id="owner", provider=retry_provider, execution_token=retried["publish_execution_token"], poll_interval=0, parse_timeout=5, activate=False)
    ready = await _revision(factory, revision_id)
    assert ready.status == "ready"
    assert len(retry_provider.created_datasets) == 1


@pytest.mark.asyncio
async def test_ready_candidate_publish_still_requires_eval_evidence(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    kb = await _seed_kb(session, slug="ready-eval")
    candidate = await _seed_candidate(session, tmp_path, kb)
    provider = FakePublishProvider()
    requested = await KnowledgeRevisionService(session, _actor()).prepare_revision(kb.id, str(candidate["id"]), provider=provider)
    await session.commit()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, execution_token=requested["publish_execution_token"], poll_interval=0, parse_timeout=5, activate=False)

    monkeypatch.setattr("app.agentplatform.knowledge.revisions.eval_required", lambda: True)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.load_eval_evidence", lambda kb_id, manifest: None)
    with pytest.raises(ResourceConflict, match="evaluation"):
        await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=provider)


@pytest.mark.asyncio
async def test_publish_accepts_provider_without_comparable_content_hash(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    provider = FakePublishProvider(omit_content_hash=True)
    await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=provider)
    await session.commit()

    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, poll_interval=0, parse_timeout=5)
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "published"
    assert revision.integrity_status == "unverified"


@pytest.mark.asyncio
async def test_publish_uses_frozen_embedding_profile_for_dataset_creation(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    kb_settings = await session.get(KnowledgeBase, kb.id)
    assert kb_settings is not None
    kb_settings.embedding_profile_json = {"model": "frozen-embed-v2"}
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    provider = FakePublishProvider()
    await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=provider)
    await session.commit()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, poll_interval=0, parse_timeout=5)
    assert provider.created_embedding_models == ["frozen-embed-v2"]


@pytest.mark.asyncio
async def test_superseded_pointer_replacement(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    actor = _actor()

    first = await _seed_candidate(session, tmp_path, kb)
    await KnowledgeRevisionService(session, actor).publish_revision(kb.id, str(first["id"]), provider=FakePublishProvider())
    await session.commit()
    first_provider = FakePublishProvider(dataset_prefix="ds-first")
    await execute_publish(factory, resource_id=kb.id, revision_id=str(first["id"]), actor_id="owner", provider=first_provider, poll_interval=0, parse_timeout=5)

    _seed_document(session, tmp_path, kb, "next.txt", b"next content")
    await session.commit()
    second = await KnowledgeRevisionService(session, actor).create_revision(kb.id)
    await KnowledgeRevisionService(session, actor).publish_revision(kb.id, str(second["id"]), provider=FakePublishProvider())
    await session.commit()
    second_provider = FakePublishProvider(dataset_prefix="ds-second")
    await execute_publish(factory, resource_id=kb.id, revision_id=str(second["id"]), actor_id="owner", provider=second_provider, poll_interval=0, parse_timeout=5)
    first_row = await _revision(factory, str(first["id"]))
    second_row = await _revision(factory, str(second["id"]))
    kb_row = await _kb_row(factory, kb.id)
    assert first_row.status == "superseded"
    assert second_row.status == "published"
    assert first_row.provider_dataset_id != second_row.provider_dataset_id
    assert kb_row.active_revision_id == second_row.id


@pytest.mark.asyncio
async def test_publish_failure_keeps_assets_and_resumes_on_retry(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb, documents=2)
    await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()

    failing = FakePublishProvider(fail_ingest_on_call=2)
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=failing, poll_interval=0, parse_timeout=5)
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "failed"
    assert revision.failure_code == "parse_failed"
    assert "internal" not in (revision.failure_message or "")
    assert revision.provider_dataset_id == "published-dataset-1"
    assert len(revision.provider_doc_map_json) == 1
    kb_row = await _kb_row(factory, kb.id)
    assert kb_row.active_revision_id is None

    resumed = FakePublishProvider()
    resumed.dataset_documents["published-dataset-1"] = list(failing.dataset_documents["published-dataset-1"])
    await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=resumed, poll_interval=0, parse_timeout=5)
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "published"
    assert len(revision.provider_doc_map_json) == 2
    assert resumed.created_datasets == []
    assert len(resumed.ingest_calls) == 1
    assert resumed.ingest_calls[0]["provider_document_id"] is None


@pytest.mark.asyncio
async def test_duplicate_and_concurrent_publish_are_rejected(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    service = KnowledgeRevisionService(session, _actor())
    await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()

    with pytest.raises(ResourceConflict, match="already publishing|publishing"):
        await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())

    _seed_document(session, tmp_path, kb, "more.txt", b"more")
    await session.commit()
    other = await service.create_revision(kb.id)
    with pytest.raises(ResourceConflict):
        await service.publish_revision(kb.id, str(other["id"]), provider=FakePublishProvider())


@pytest.mark.asyncio
async def test_execute_publish_rechecks_evaluation_before_switching_live_pointer(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    provider = FakePublishProvider()
    requested = await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=provider)
    await session.commit()

    checks = 0

    async def gate(*args, **kwargs) -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            raise ResourceConflict("evaluation policy changed during publish")

    monkeypatch.setattr("app.agentplatform.knowledge.revisions._require_eval_evidence", gate)
    await execute_publish(
        factory,
        resource_id=kb.id,
        revision_id=str(candidate["id"]),
        actor_id="owner",
        provider=provider,
        execution_token=requested["publish_execution_token"],
        poll_interval=0,
        parse_timeout=5,
    )

    revision = await _revision(factory, str(candidate["id"]))
    assert checks == 2
    assert revision.status == "failed"


@pytest.mark.asyncio
async def test_publish_gates_reject_before_side_effects(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    revision_id = str(candidate["id"])

    kb.visibility = "public"
    await session.commit()
    with pytest.raises(ResourcePermissionDenied):
        await KnowledgeRevisionService(session, _actor("intruder")).publish_revision(kb.id, revision_id, provider=FakePublishProvider())
    kb.visibility = "private"
    await session.commit()
    with pytest.raises(ResourceNotFound):
        await KnowledgeRevisionService(session, _actor("intruder")).publish_revision(uuid.uuid4().hex, revision_id, provider=FakePublishProvider())
    with pytest.raises(ResourceNotFound):
        await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(uuid.uuid4()), provider=FakePublishProvider())

    monkeypatch.setattr("app.agentplatform.knowledge.revisions.eval_required", lambda: True)
    with pytest.raises(ResourceConflict, match="evaluation"):
        await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, revision_id, provider=FakePublishProvider())
    revision = await _revision(factory, revision_id)
    assert revision.status == "draft"
    assert revision.publish_attempt == 0

    monkeypatch.setattr("app.agentplatform.knowledge.revisions.load_eval_evidence", lambda kb_id, manifest: {"evidence": True})
    requested = await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, revision_id, provider=FakePublishProvider())
    assert requested["status"] == "indexing"


@pytest.mark.asyncio
async def test_republish_rules_and_attempt_budget(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    service = KnowledgeRevisionService(session, _actor())

    await session.execute(update(KnowledgeRevision).where(KnowledgeRevision.id == str(candidate["id"])).values(publish_attempt=MAX_PUBLISH_ATTEMPTS))
    await session.commit()
    with pytest.raises(ResourceConflict, match="exhausted"):
        await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())

    await session.execute(update(KnowledgeRevision).where(KnowledgeRevision.id == str(candidate["id"])).values(publish_attempt=0, status="published"))
    await session.commit()
    with pytest.raises(ResourceConflict, match="not publishable"):
        await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())


@pytest.mark.asyncio
async def test_verification_failure_does_not_switch_pointer(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()

    provider = FakePublishProvider(extra_dataset_documents=1)
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, poll_interval=0, parse_timeout=5)
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "failed"
    assert revision.failure_code == "verification_failed"
    kb_row = await _kb_row(factory, kb.id)
    assert kb_row.active_revision_id is None


@pytest.mark.asyncio
async def test_provider_content_hash_mismatch_blocks_publish(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    await KnowledgeRevisionService(session, _actor()).publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()

    class TamperedProvider(FakePublishProvider):
        async def list_dataset_documents(self, *, dataset_id: str) -> list[dict]:
            documents = await super().list_dataset_documents(dataset_id=dataset_id)
            documents[0]["content_hash"] = "f" * 64
            return documents

    provider = TamperedProvider()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, poll_interval=0, parse_timeout=5)

    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "failed"
    assert revision.failure_code == "verification_failed"


@pytest.mark.asyncio
async def test_missing_frozen_content_fails_integrity_gate(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    service = KnowledgeRevisionService(session, _actor())
    revision = await _revision(factory, str(candidate["id"]))
    detail = await service.get_revision(kb.id, str(candidate["id"]))
    entry = detail["documents"][0]
    frozen = tmp_path / "knowledge-revisions" / str(candidate["id"]) / f"{entry['document_id']}-{entry['filename']}"
    frozen.unlink()

    with pytest.raises(ResourceConflict, match="missing|corrupt"):
        await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "draft"


@pytest.mark.asyncio
async def test_draft_changes_never_touch_published_datasets(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.documents.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    service = KnowledgeRevisionService(session, _actor())
    await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()
    publish_provider = FakePublishProvider()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=publish_provider, poll_interval=0, parse_timeout=5)
    revision = await _revision(factory, str(candidate["id"]))
    published_dataset = revision.provider_dataset_id

    draft_provider = FakePublishProvider()
    document_service = KnowledgeDocumentService(session, _actor(), draft_provider)
    await ResourceService(session, _actor()).bind_knowledge_dataset(kb.id, provider_dataset_id="draft-dataset")
    await session.commit()
    documents = await document_service.list_documents(kb.id)
    await document_service.delete(str(documents[0]["id"]), resource_id=kb.id)
    await session.commit()

    assert draft_provider.dataset_documents.get(published_dataset) is None
    deleted_from = {call["dataset_id"] for call in draft_provider.delete_calls} if hasattr(draft_provider, "delete_calls") else set()
    assert deleted_from == {"draft-dataset"}
    assert publish_provider.dataset_documents[published_dataset]
    listing = (await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.resource_id == kb.id))).scalars().all()
    assert any(item.status == "deleted" for item in listing)


@pytest.mark.asyncio
async def test_tampered_frozen_content_fails_integrity_gate(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    """Overwriting a frozen file's bytes (name intact) must block publishing."""
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    service = KnowledgeRevisionService(session, _actor())
    detail = await service.get_revision(kb.id, str(candidate["id"]))
    entry = detail["documents"][0]
    frozen = tmp_path / "knowledge-revisions" / str(candidate["id"]) / f"{entry['document_id']}-{entry['filename']}"
    frozen.write_bytes(b"tampered after the fact")

    with pytest.raises(ResourceConflict, match="corrupt"):
        await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "draft"


@pytest.mark.asyncio
async def test_stuck_indexing_revision_resumes_after_executor_loss(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    """A revision left in ``indexing`` by a crashed process is resumable."""
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb, documents=2)
    service = KnowledgeRevisionService(session, _actor())
    await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()

    from app.agentplatform.knowledge import revisions as revisions_module

    # Simulate the executor dying with the process: nothing in flight.
    revisions_module._ACTIVE_PUBLISHES.clear()
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "indexing"

    resumed = await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    assert resumed["status"] == "indexing"
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.publish_attempt == 1  # a resume is a continuation, not a new attempt

    provider = FakePublishProvider()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, poll_interval=0, parse_timeout=5)
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.status == "published"


@pytest.mark.asyncio
async def test_indexing_revision_conflicts_while_build_is_in_flight(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    """A duplicate publish while the build is genuinely running stays a 409."""
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    service = KnowledgeRevisionService(session, _actor())
    await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()

    with pytest.raises(ResourceConflict, match="already publishing"):
        await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    revision = await _revision(factory, str(candidate["id"]))
    assert revision.publish_attempt == 1


@pytest.mark.asyncio
async def test_foreign_publish_lease_blocks_until_expiry(
    store: tuple[AsyncSession, async_sessionmaker],
    tmp_path,
    monkeypatch,
) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    candidate = await _seed_candidate(session, tmp_path, kb)
    service = KnowledgeRevisionService(session, _actor())
    await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
    await session.commit()

    async with factory() as foreign:
        revision = await foreign.get(KnowledgeRevision, str(candidate["id"]))
        assert revision is not None
        revision.publish_lease_owner = "another-process"
        revision.publish_lease_until = datetime.now(UTC) + timedelta(minutes=5)
        await foreign.commit()

    from app.agentplatform.knowledge import revisions as revisions_module

    revisions_module._ACTIVE_PUBLISHES.clear()
    with pytest.raises(ResourceConflict, match="already publishing"):
        await service.publish_revision(kb.id, str(candidate["id"]), provider=FakePublishProvider())
