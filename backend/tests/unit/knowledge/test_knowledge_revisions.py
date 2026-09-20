"""Knowledge Revision candidates: deterministic manifest, immutability, governance (M4 ticket 01)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument, KnowledgeRevision
from app.agentplatform.knowledge.revisions import (
    KnowledgeRevisionService,
    KnowledgeRevisionValidationError,
    canonical_manifest_hash,
)
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceNotFound, ResourcePermissionDenied, ResourceService
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'revisions.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
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


async def _seed_kb(session: AsyncSession, slug: str = "revisions", *, owner_id: str = "owner") -> Resource:
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
    *,
    status: str = "ready",
) -> KnowledgeDocument:
    document_id = str(uuid.uuid4())
    root = tmp_path / "knowledge-documents" / kb.id
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{document_id}-{filename}"
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
        provider_document_id="provider-doc-1" if status == "ready" else None,
        status=status,
        created_by=kb.owner_id,
    )
    session.add(row)
    return row


@pytest.mark.asyncio
async def test_candidate_freezes_only_ready_documents_with_deterministic_manifest(
    session: AsyncSession,
    tmp_path,
    monkeypatch,
) -> None:
    kb = await _seed_kb(session)
    _seed_document(session, tmp_path, kb, "b-guide.txt", b"beta content")
    _seed_document(session, tmp_path, kb, "a-intro.txt", b"alpha content")
    _seed_document(session, tmp_path, kb, "broken.txt", b"not indexed", status="failed")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    payload = await KnowledgeRevisionService(session, _actor()).create_revision(kb.id)
    await session.commit()

    assert payload["status"] == "draft"
    assert payload["revision_no"] == 1
    assert payload["document_count"] == 2
    assert len(payload["manifest_hash"]) == 64
    detail = await KnowledgeRevisionService(session, _actor()).get_revision(kb.id, str(payload["id"]))
    document_ids = {entry["document_id"] for entry in detail["documents"]}
    assert len(document_ids) == 2
    assert "content_hash" not in document_ids
    hashes = {entry["filename"]: entry["content_hash"] for entry in detail["documents"]}
    assert hashes["a-intro.txt"] == hashlib.sha256(b"alpha content").hexdigest()
    assert hashes["b-guide.txt"] == hashlib.sha256(b"beta content").hexdigest()
    failed_hashes = {entry["filename"] for entry in detail["documents"]}
    assert "broken.txt" not in failed_hashes
    for entry in detail["documents"]:
        frozen = tmp_path / "knowledge-revisions" / str(payload["id"]) / f"{entry['document_id']}-{entry['filename']}"
        assert frozen.is_file()

    # Determinism: recomputing from the manifest entries matches the stored
    # hash, and an unchanged document set yields the same hash again.
    assert canonical_manifest_hash(detail["documents"]) == payload["manifest_hash"]
    repeat = await KnowledgeRevisionService(session, _actor()).create_revision(kb.id)
    assert repeat["manifest_hash"] == payload["manifest_hash"]
    assert repeat["revision_no"] == 2


@pytest.mark.asyncio
async def test_candidate_manifest_freezes_knowledge_profiles(
    session: AsyncSession,
    tmp_path,
    monkeypatch,
) -> None:
    kb = await _seed_kb(session)
    _seed_document(session, tmp_path, kb, "guide.txt", b"profile content")
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.retrieval_profile_json = {"top_k": 5}
    kb_row.embedding_profile_json = {"model": "bge-m3"}
    kb_row.ingestion_profile_json = {"chunk_size": 512}
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    payload = await KnowledgeRevisionService(session, _actor()).create_revision(kb.id)
    detail = await KnowledgeRevisionService(session, _actor()).get_revision(kb.id, str(payload["id"]))

    assert detail["documents"][0]["knowledge_profiles"] == {
        "retrieval": {"top_k": 5},
        "embedding": {"model": "bge-m3"},
        "ingestion": {"chunk_size": 512},
    }


@pytest.mark.asyncio
async def test_canonical_manifest_hash_ignores_entry_order(session: AsyncSession) -> None:
    first = canonical_manifest_hash([{"document_id": "a", "content_hash": "h1"}, {"document_id": "b", "content_hash": "h2"}])
    second = canonical_manifest_hash([{"document_id": "b", "content_hash": "h2"}, {"document_id": "a", "content_hash": "h1"}])
    assert first == second
    assert first != canonical_manifest_hash([{"document_id": "a", "content_hash": "h2"}])


@pytest.mark.asyncio
async def test_candidate_survives_draft_delete_and_new_uploads(
    session: AsyncSession,
    tmp_path,
    monkeypatch,
) -> None:
    from app.agentplatform.knowledge.documents import KnowledgeDocumentService

    kb = await _seed_kb(session)
    document = _seed_document(session, tmp_path, kb, "guide.txt", b"frozen bytes", status="ready")
    document.provider_document_id = None
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.documents.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    service = KnowledgeRevisionService(session, _actor())
    candidate = await service.create_revision(kb.id)
    await session.commit()

    await KnowledgeDocumentService(session, _actor()).delete(str(document.id), resource_id=kb.id)
    _seed_document(session, tmp_path, kb, "next.txt", b"new draft bytes")
    await session.commit()

    detail = await service.get_revision(kb.id, str(candidate["id"]))
    assert detail["document_count"] == 1
    assert detail["manifest_hash"] == candidate["manifest_hash"]
    assert detail["documents"][0]["filename"] == "guide.txt"
    frozen = tmp_path / "knowledge-revisions" / str(candidate["id"]) / f"{detail['documents'][0]['document_id']}-guide.txt"
    assert frozen.read_bytes() == b"frozen bytes"


@pytest.mark.asyncio
async def test_create_requires_ready_documents(session: AsyncSession, tmp_path, monkeypatch) -> None:
    kb = await _seed_kb(session)
    _seed_document(session, tmp_path, kb, "draft.txt", b"bytes", status="uploaded")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    with pytest.raises(KnowledgeRevisionValidationError):
        await KnowledgeRevisionService(session, _actor()).create_revision(kb.id)


@pytest.mark.asyncio
async def test_create_follows_owner_governance_without_side_effects(
    session: AsyncSession,
    tmp_path,
    monkeypatch,
) -> None:
    kb = await _seed_kb(session)
    _seed_document(session, tmp_path, kb, "guide.txt", b"bytes")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    intruder = KnowledgeRevisionService(session, _actor("intruder", permissions={ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}))
    kb.visibility = "public"
    await session.commit()
    with pytest.raises(ResourcePermissionDenied):
        await intruder.create_revision(kb.id)

    kb.visibility = "private"
    kb.owner_id = "someone-else"
    await session.commit()
    with pytest.raises(ResourceNotFound):
        await KnowledgeRevisionService(session, _actor("intruder")).create_revision(kb.id)

    assert (tmp_path / "knowledge-revisions").exists() is False


@pytest.mark.asyncio
async def test_list_and_detail_follow_visibility_and_stay_kb_scoped(
    session: AsyncSession,
    tmp_path,
    monkeypatch,
) -> None:
    kb = await _seed_kb(session)
    _seed_document(session, tmp_path, kb, "guide.txt", b"bytes")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    owner_service = KnowledgeRevisionService(session, _actor())
    candidate = await owner_service.create_revision(kb.id)
    candidate_row = await session.get(KnowledgeRevision, candidate["id"])
    assert candidate_row is not None
    candidate_row.status = "published"
    kb.active_revision_id = candidate_row.id
    await session.commit()

    viewer = KnowledgeRevisionService(session, _actor("viewer", permissions={ResourceAction.READ}))
    kb.visibility = "public"
    await session.commit()
    items = await viewer.list_revisions(kb.id)
    assert [item["id"] for item in items] == [candidate["id"]]
    detail = await viewer.get_revision(kb.id, str(candidate["id"]))
    assert detail["documents"][0]["filename"] == "guide.txt"

    kb.visibility = "private"
    kb.owner_id = "someone-else"
    await session.commit()
    with pytest.raises(ResourceNotFound):
        await viewer.list_revisions(kb.id)
    kb.owner_id = "owner"
    kb.visibility = "public"
    await session.commit()

    other = await _seed_kb(session, slug="other")
    with pytest.raises(ResourceNotFound):
        await owner_service.get_revision(other.id, str(candidate["id"]))
    with pytest.raises(ResourceNotFound):
        await owner_service.get_revision(kb.id, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_revision_numbers_increment_per_knowledge_base(
    session: AsyncSession,
    tmp_path,
    monkeypatch,
) -> None:
    kb = await _seed_kb(session)
    other = await _seed_kb(session, slug="other")
    _seed_document(session, tmp_path, kb, "guide.txt", b"bytes")
    _seed_document(session, tmp_path, other, "guide.txt", b"bytes")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    service = KnowledgeRevisionService(session, _actor())

    first = await service.create_revision(kb.id)
    second = await service.create_revision(kb.id)
    other_first = await service.create_revision(other.id)

    assert (first["revision_no"], second["revision_no"], other_first["revision_no"]) == (1, 2, 1)
    items = await service.list_revisions(kb.id)
    assert [item["revision_no"] for item in items] == [1, 2]
    assert items[0]["created_at"] is not None
    assert items[0]["published_at"] is None
