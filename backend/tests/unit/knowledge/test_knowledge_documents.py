from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401
import app.agentplatform.rbac_models  # noqa: F401
import app.agentplatform.resource_models  # noqa: F401
import app.agentplatform.visibility_models  # noqa: F401
from app.agentplatform.knowledge.documents import DocumentValidationError, KnowledgeDocumentService
from app.agentplatform.knowledge.models import KnowledgeDocument
from app.agentplatform.knowledge.provider import KnowledgeProviderError, ProviderIngestionResult
from app.agentplatform.resources.service import ResourceAction, ResourceActor
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'documents.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def _actor(user_id: str = "owner", permissions: set[ResourceAction] | None = None) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id=None,
        role="user",
        permissions=frozenset(permissions or {ResourceAction.READ, ResourceAction.WRITE}),
    )


class FakeUpload:
    def __init__(self, filename: str, content: bytes, content_type: str = "text/plain") -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self.closed = False

    async def read(self, size: int) -> bytes:
        if not self._content:
            return b""
        chunk, self._content = self._content[:size], self._content[size:]
        return chunk

    async def close(self) -> None:
        self.closed = True


class FakeProvider:
    def __init__(self, *, fail: bool = False, status: str = "ready") -> None:
        self.fail = fail
        self.status = status
        self.calls = []

    async def ingest(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise KnowledgeProviderError("parse_failed", "internal provider detail")
        return ProviderIngestionResult("provider-doc-1", self.status)


@pytest.mark.asyncio
async def test_upload_persists_hash_metadata_and_isolated_original(session, tmp_path, monkeypatch) -> None:
    from app.agentplatform.knowledge.models import KnowledgeBase
    from app.agentplatform.resources.service import ResourceService

    service = ResourceService(session, _actor())
    kb = await service.create_resource(resource_type="knowledge_base", slug="docs", display_name="Docs", storage_kind="database")
    await session.commit()
    monkeypatch.setattr(
        "app.agentplatform.knowledge.documents.get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path),
    )

    upload = FakeUpload("guide.txt", b"hello knowledge")
    document = await KnowledgeDocumentService(session, _actor()).upload(kb.id, upload)
    await session.commit()

    assert document["name"] == "guide.txt"
    assert document["size"] == 15
    assert document["source"] == "upload"
    assert document["status"] == "uploaded"
    assert "provider_document_id" not in document
    row = await session.get(KnowledgeDocument, document["id"])
    assert row is not None
    storage_path = tmp_path / row.storage_key
    assert storage_path.read_bytes() == b"hello knowledge"
    assert upload.closed is True
    assert await session.get(KnowledgeBase, kb.id) is not None
    await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document["id"]))
    await session.rollback()
    assert storage_path.exists()


@pytest.mark.asyncio
async def test_upload_rejects_unsafe_name_and_type_before_storage(session, tmp_path, monkeypatch) -> None:
    from app.agentplatform.resources.service import ResourceService

    kb = await ResourceService(session, _actor()).create_resource(resource_type="knowledge_base", slug="docs", display_name="Docs", storage_kind="database")
    await session.commit()
    monkeypatch.setattr(
        "app.agentplatform.knowledge.documents.get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path),
    )

    with pytest.raises(DocumentValidationError):
        await KnowledgeDocumentService(session, _actor()).upload(kb.id, FakeUpload("../escape.exe", b"x"))
    assert not (tmp_path / "knowledge-documents").exists()


@pytest.mark.asyncio
async def test_non_owner_is_rejected_before_upload_side_effect(session, tmp_path, monkeypatch) -> None:
    from app.agentplatform.resources.service import ResourceNotFound, ResourceService

    kb = await ResourceService(session, _actor()).create_resource(resource_type="knowledge_base", slug="docs", display_name="Docs", storage_kind="database")
    await session.commit()
    monkeypatch.setattr(
        "app.agentplatform.knowledge.documents.get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path),
    )

    with pytest.raises(ResourceNotFound):
        await KnowledgeDocumentService(session, _actor("other")).upload(kb.id, FakeUpload("guide.txt", b"x"))
    assert not (tmp_path / "knowledge-documents").exists()


@pytest.mark.asyncio
async def test_upload_cleans_original_when_database_commit_fails(session, tmp_path, monkeypatch) -> None:
    from app.agentplatform.resources.service import ResourceService

    kb = await ResourceService(session, _actor()).create_resource(resource_type="knowledge_base", slug="docs", display_name="Docs", storage_kind="database")
    await session.commit()
    monkeypatch.setattr(
        "app.agentplatform.knowledge.documents.get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path),
    )

    document = await KnowledgeDocumentService(session, _actor()).upload(kb.id, FakeUpload("guide.txt", b"hello knowledge"))
    row = await session.get(KnowledgeDocument, document["id"])
    assert row is not None
    original = tmp_path / row.storage_key
    assert original.exists()

    session.add(
        KnowledgeDocument(
            id="conflicting-document",
            resource_id=kb.id,
            original_filename="other.txt",
            size_bytes=1,
            mime_type="text/plain",
            content_hash="different-hash",
            storage_key=row.storage_key,
            metadata_json={},
            created_by="owner",
        )
    )

    with pytest.raises(IntegrityError):
        await session.commit()

    assert not original.exists()


@pytest.mark.asyncio
async def test_processing_failure_is_sanitized_and_retry_reuses_logical_document(session, tmp_path, monkeypatch) -> None:
    from app.agentplatform.resources.service import ResourceService

    kb = await ResourceService(session, _actor()).create_resource(resource_type="knowledge_base", slug="docs", display_name="Docs", storage_kind="database")
    await ResourceService(session, _actor()).bind_knowledge_dataset(kb.id, provider_dataset_id="dataset-1")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.documents.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))

    document = await KnowledgeDocumentService(session, _actor()).upload(kb.id, FakeUpload("guide.txt", b"hello"))
    await session.commit()
    failed = await KnowledgeDocumentService(session, _actor(), FakeProvider(fail=True)).process(document["id"], resource_id=kb.id)
    assert failed["status"] == "failed"
    assert failed["failure_code"] == "parse_failed"
    assert failed["failure_message"] == "The provider could not parse this document."
    assert "internal" not in str(failed)

    provider = FakeProvider()
    recovered = await KnowledgeDocumentService(session, _actor(), provider).retry(document["id"], resource_id=kb.id)
    await session.commit()
    assert recovered["status"] == "ready"
    assert recovered["id"] == document["id"]
    assert provider.calls[0]["provider_document_id"] is None
    assert recovered["ingestion_attempt"] == 2


@pytest.mark.asyncio
async def test_cross_kb_document_action_is_rejected_before_provider_call(session, tmp_path, monkeypatch) -> None:
    from app.agentplatform.resources.service import ResourceService

    resources = ResourceService(session, _actor())
    first = await resources.create_resource(resource_type="knowledge_base", slug="first", display_name="First", storage_kind="database")
    second = await resources.create_resource(resource_type="knowledge_base", slug="second", display_name="Second", storage_kind="database")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.documents.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    document = await KnowledgeDocumentService(session, _actor()).upload(first.id, FakeUpload("guide.txt", b"hello"))
    await session.commit()
    provider = FakeProvider(status="processing")
    with pytest.raises(Exception, match="not found"):
        await KnowledgeDocumentService(session, _actor(), provider).retry(document["id"], resource_id=second.id)
    assert provider.calls == []


@pytest.mark.asyncio
async def test_reprocessing_a_processing_document_does_not_start_another_provider_task(session, tmp_path, monkeypatch) -> None:
    from app.agentplatform.resources.service import ResourceService

    resources = ResourceService(session, _actor())
    kb = await resources.create_resource(resource_type="knowledge_base", slug="docs", display_name="Docs", storage_kind="database")
    await resources.bind_knowledge_dataset(kb.id, provider_dataset_id="dataset-1")
    await session.commit()
    monkeypatch.setattr("app.agentplatform.knowledge.documents.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    document = await KnowledgeDocumentService(session, _actor()).upload(kb.id, FakeUpload("guide.txt", b"hello"))
    await session.commit()

    provider = FakeProvider(status="processing")
    first = await KnowledgeDocumentService(session, _actor(), provider).process(document["id"], resource_id=kb.id)
    second = await KnowledgeDocumentService(session, _actor(), provider).process(document["id"], resource_id=kb.id)

    assert first["status"] == "processing"
    assert second["status"] == "processing"
    assert len(provider.calls) == 1
