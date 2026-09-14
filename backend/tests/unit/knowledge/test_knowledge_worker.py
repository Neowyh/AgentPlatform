from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401
import app.agentplatform.rbac_models  # noqa: F401
import app.agentplatform.resource_models  # noqa: F401
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument
from app.agentplatform.knowledge.worker import KnowledgeWorker
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceService
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _actor() -> ResourceActor:
    return ResourceActor(
        user_id="owner",
        department_id=None,
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.WRITE}),
    )


class WorkerProvider:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.ingested: list[dict] = []

    async def create_dataset(self, *, name: str, embedding_model: str | None = None) -> str:
        self.created.append(name)
        return "dataset-worker"

    async def ingest(self, **kwargs):
        self.ingested.append(kwargs)
        from app.agentplatform.knowledge.provider import ProviderIngestionResult

        return ProviderIngestionResult("provider-document", "ready")

    async def get_status(self, **kwargs):
        return "ready"

    async def delete_document(self, **kwargs):
        return None


@pytest.mark.asyncio
async def test_worker_initializes_and_ingests_durable_intents(session_factory, tmp_path, monkeypatch) -> None:
    provider = WorkerProvider()
    async with session_factory() as session:
        resource = await ResourceService(session, _actor()).create_resource(
            resource_type="knowledge_base",
            slug="worker-kb",
            display_name="Worker KB",
            storage_kind="database",
        )
        await session.commit()

        root = tmp_path / "knowledge-documents" / resource.id
        root.mkdir(parents=True)
        path = root / "doc.txt"
        path.write_text("worker content", encoding="utf-8")
        document = KnowledgeDocument(
            id="worker-document",
            resource_id=resource.id,
            original_filename="doc.txt",
            size_bytes=14,
            mime_type="text/plain",
            content_hash="a" * 64,
            storage_key=path.relative_to(tmp_path).as_posix(),
            metadata_json={},
            created_by="owner",
        )
        session.add(document)
        await session.commit()

    monkeypatch.setattr(
        "app.agentplatform.knowledge.worker.get_session_factory",
        lambda: session_factory,
    )
    monkeypatch.setattr(
        "app.agentplatform.knowledge.worker.configured_ragflow_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "app.agentplatform.knowledge.documents.get_paths",
        lambda: SimpleNamespace(base_dir=tmp_path),
    )

    await KnowledgeWorker()._tick()

    async with session_factory() as session:
        binding = await session.get(KnowledgeBase, resource.id)
        row = await session.get(KnowledgeDocument, "worker-document")
    assert binding is not None
    assert binding.initialization_status == "ready"
    assert binding.provider_dataset_id == "dataset-worker"
    assert row is not None
    assert row.status == "ready"
    assert row.lease_owner is None
    assert provider.created == [f"deerflow-{resource.id}"]
    assert provider.ingested[0]["dataset_id"] == "dataset-worker"


@pytest.mark.asyncio
async def test_worker_releases_lease_when_service_boundary_raises(session_factory, tmp_path, monkeypatch) -> None:
    async with session_factory() as session:
        resource = await ResourceService(session, _actor()).create_resource(
            resource_type="knowledge_base",
            slug="worker-error-kb",
            display_name="Worker Error KB",
            storage_kind="database",
        )
        await session.commit()
        path = tmp_path / "document.txt"
        path.write_text("content", encoding="utf-8")
        session.add(
            KnowledgeDocument(
                id="worker-error-document",
                resource_id=resource.id,
                original_filename="document.txt",
                size_bytes=7,
                mime_type="text/plain",
                content_hash="b" * 64,
                storage_key=path.name,
                metadata_json={},
                created_by="owner",
            )
        )
        await session.commit()

    class ExplodingService:
        def __init__(self, *args, **kwargs):
            pass

        async def process(self, *args, **kwargs):
            raise RuntimeError("unexpected worker failure")

    monkeypatch.setattr("app.agentplatform.knowledge.worker.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.agentplatform.knowledge.worker.configured_ragflow_provider", lambda: WorkerProvider())
    monkeypatch.setattr("app.agentplatform.knowledge.worker.KnowledgeDocumentService", ExplodingService)

    await KnowledgeWorker()._tick()

    async with session_factory() as session:
        row = await session.get(KnowledgeDocument, "worker-error-document")
    assert row is not None
    assert row.status == "failed"
    assert row.failure_code == "worker_error"
    assert row.lease_owner is None
    assert row.lease_until is None
