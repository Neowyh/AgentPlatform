"""Retrieval test endpoints follow Resource Governance and the canonical API (M6 ticket 01)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.models import KnowledgeDocument, KnowledgeRevision
from app.agentplatform.knowledge.provider import ProviderIngestionResult
from app.agentplatform.knowledge.revisions import KnowledgeRevisionService, execute_publish
from app.agentplatform.rbac_models import UserModel, UserRole
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor
from app.gateway.routers import knowledge_tests, resources
from deerflow.community.ragflow.client import RAGFlowConnectionError
from deerflow.persistence.base import Base

_SETTINGS = SimpleNamespace(page_size=8, similarity_threshold=0.2, vector_similarity_weight=0.3, top_k=256, timeout=30.0)
_REAL_SERVICE = knowledge_tests.KnowledgeRetrievalTestService


class _FakePublishProvider:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.docs: dict[str, list[dict]] = {}

    async def create_dataset(self, *, name: str, embedding_model: str | None = None) -> str:
        dataset_id = f"published-dataset-{len(self.created) + 1}"
        self.created.append(dataset_id)
        self.docs[dataset_id] = []
        return dataset_id

    async def ingest(self, *, dataset_id: str, filename: str, mime_type: str, content: bytes, provider_document_id: str | None = None, rebuild: bool = False) -> ProviderIngestionResult:
        document_id = f"provider-doc-{len(self.docs[dataset_id]) + 1}"
        self.docs[dataset_id].append({"id": document_id, "name": filename})
        return ProviderIngestionResult(document_id, "processing")

    async def get_status(self, *, dataset_id: str, provider_document_id: str) -> str:
        return "ready"

    async def delete_document(self, *, dataset_id: str, provider_document_id: str) -> None:
        return None

    async def list_dataset_documents(self, *, dataset_id: str) -> list[dict]:
        return list(self.docs.get(dataset_id, []))


async def _make_env(tmp_path, monkeypatch: pytest.MonkeyPatch, role: UserRole = UserRole.USER, user_id: str = "owner") -> tuple:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retrieval-tests-api.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    current_user = UserModel(
        id=user_id,
        username=f"{user_id}@test.com",
        role=role,
        department_id="dept-a",
        disabled=False,
    )
    async with factory() as session:
        session.add(current_user)
        await session.commit()
    monkeypatch.setattr(resources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(resources, "get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))
    return engine, factory, current_user


async def _seed_kb(factory, user, slug: str = "retrieval-api") -> Resource:
    created = await resources.create_resource(
        resources.ResourceCreateRequest(type="knowledge_base", slug=slug, display_name=slug, storage_kind="database"),
        user,
    )
    async with factory() as session:
        kb = await session.get(Resource, created["id"])
        assert kb is not None
        return kb


def _actor(user_id: str, *, permissions=None) -> ResourceActor:
    return ResourceActor(
        user_id=user_id,
        department_id=None,
        role="user",
        permissions=frozenset(permissions or {ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}),
    )


async def _seed_document(factory, tmp_path, kb_id: str, owner_id: str, filename: str) -> None:
    import hashlib

    async with factory() as session:
        document_id = str(uuid.uuid4())
        path = tmp_path / "knowledge-documents" / kb_id / f"{document_id}-{filename}"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"content of {filename}".encode()
        path.write_bytes(content)
        session.add(
            KnowledgeDocument(
                id=document_id,
                resource_id=kb_id,
                original_filename=filename,
                size_bytes=len(content),
                mime_type="text/plain",
                content_hash=hashlib.sha256(content).hexdigest(),
                storage_key=path.relative_to(tmp_path).as_posix(),
                metadata_json={},
                status="ready",
                created_by=owner_id,
            )
        )
        await session.commit()


async def _publish_revision(factory: async_sessionmaker, tmp_path, kb: Resource, owner_id: str, *, documents: int = 1) -> KnowledgeRevision:
    for index in range(documents):
        await _seed_document(factory, tmp_path, kb.id, owner_id, f"guide-{index}.txt")
    async with factory() as session:
        service = KnowledgeRevisionService(session, _actor(owner_id))
        candidate = await service.create_revision(kb.id)
        provider = _FakePublishProvider()
        await service.publish_revision(kb.id, str(candidate["id"]), provider=provider)
        await session.commit()
        revision_id = str(candidate["id"])
    await execute_publish(factory, resource_id=kb.id, revision_id=revision_id, actor_id=owner_id, provider=provider, poll_interval=0, parse_timeout=5)
    async with factory() as session:
        revision = await session.get(KnowledgeRevision, revision_id)
        assert revision is not None and revision.status == "published", (revision.status if revision else None, revision.failure_code if revision else None, revision.failure_message if revision else None)
        return revision


def _chunk_result(chunks: list[dict]) -> dict:
    return {"chunks": chunks, "total": len(chunks)}


def _install_search(monkeypatch: pytest.MonkeyPatch, result, settings=_SETTINGS) -> list[dict]:
    calls: list[dict] = []

    async def search(query: str, *, settings, dataset_id: str, document_ids: list[str], applied: dict) -> dict:
        calls.append({"query": query, "dataset_id": dataset_id, "document_ids": list(document_ids), "applied": dict(applied)})
        if isinstance(result, Exception):
            raise result
        return result

    def service_factory(session, actor):
        return _REAL_SERVICE(session, actor, search=search, settings_factory=lambda: settings)

    monkeypatch.setattr(knowledge_tests, "KnowledgeRetrievalTestService", service_factory)
    return calls


def _install_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        knowledge_tests,
        "KnowledgeRetrievalTestService",
        lambda session, actor: _REAL_SERVICE(session, actor, search=_passthrough_search(), settings_factory=lambda: None),
    )


class _FailingStorageService:
    def __init__(self, session, actor) -> None:
        pass

    async def execute(self, *args, **kwargs) -> dict:
        raise OperationalError("INSERT failed", {}, Exception("disk full"))


def _passthrough_search():
    async def search(query: str, *, settings, dataset_id: str, document_ids: list[str], applied: dict) -> dict:
        return _chunk_result([])

    return search


async def _noop_audit(*args, **kwargs) -> None:
    return None


@pytest.mark.asyncio
async def test_retrieval_test_execute_lists_and_replays_archives(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    kb = await _seed_kb(factory, current_user)
    revision = await _publish_revision(factory, tmp_path, kb, current_user.id)
    provider_document_id = next(iter(revision.provider_doc_map_json.values()))
    calls = _install_search(
        monkeypatch,
        _chunk_result([{"document_id": provider_document_id, "document_keyword": "guide-0.txt", "content": "Retry with backoff.", "similarity": 0.9, "page": 2}]),
    )
    audits: list[tuple] = []

    async def _audit(actor_id, action, resource_type=None, resource_id=None, detail=None, ip_address=None) -> None:
        audits.append((actor_id, action, detail))

    monkeypatch.setattr(knowledge_tests, "record_audit", _audit)

    created = await knowledge_tests.create_retrieval_test(
        kb.id,
        knowledge_tests.RetrievalTestCreateRequest(revision_id=revision.id, query="What is the retry policy?", top_k=5),
        current_user,
    )
    assert created["result_status"] == "success"
    assert created["requested_top_k"] == 5
    assert created["revision_no"] == revision.revision_no
    assert created["manifest_hash"] == revision.manifest_hash
    assert created["retrieval_profile"] == {}
    assert created["applied_parameters"]["page_size"] == 5
    assert created["items"][0]["rank"] == 1
    assert calls[0]["dataset_id"] == revision.provider_dataset_id
    assert calls[0]["document_ids"] == sorted(revision.provider_doc_map_json.values())
    # Audit trail carries identity only, never the question text.
    assert audits[-1][1] == "knowledge_retrieval_test_executed"
    assert "query" not in (audits[-1][2] or {})

    listed = await knowledge_tests.list_retrieval_tests(kb.id, 0, 20, current_user)
    assert listed["total"] == 1
    summary = listed["items"][0]
    assert summary["id"] == created["id"]
    assert "items" not in summary and "applied_parameters" not in summary

    replayed = await knowledge_tests.get_retrieval_test(kb.id, str(created["id"]), current_user)
    assert replayed["items"][0]["content"] == "Retry with backoff."
    assert replayed["items"][0]["position"] == {"page": 2}
    assert len(calls) == 1  # replay reads the archive, no re-retrieval
    await engine.dispose()


@pytest.mark.asyncio
async def test_retrieval_test_request_rejects_unsupported_parameters() -> None:
    with pytest.raises(ValidationError):
        knowledge_tests.RetrievalTestCreateRequest(revision_id="r1", query="q", similarity_threshold=0.5)
    with pytest.raises(ValidationError):
        knowledge_tests.RetrievalTestCreateRequest(revision_id="r1", query="q", top_k=99)
    with pytest.raises(ValidationError):
        knowledge_tests.RetrievalTestCreateRequest(revision_id="r1", query="")


@pytest.mark.asyncio
async def test_retrieval_test_endpoint_distinct_safe_states(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    kb = await _seed_kb(factory, current_user)
    revision = await _publish_revision(factory, tmp_path, kb, current_user.id)
    monkeypatch.setattr(knowledge_tests, "record_audit", _noop_audit)

    # Provider outage: the execution still archives as an explicit failure state.
    _install_search(monkeypatch, RAGFlowConnectionError("internal detail"))
    failed = await knowledge_tests.create_retrieval_test(
        kb.id,
        knowledge_tests.RetrievalTestCreateRequest(revision_id=revision.id, query="anything"),
        current_user,
    )
    assert failed["result_status"] == "provider_error"
    assert failed["error_code"] == "connection_error"
    assert "internal detail" not in str(failed)

    # Retrieval tooling unconfigured: 503 with a distinct code.
    _install_unconfigured(monkeypatch)
    with pytest.raises(HTTPException) as unavailable:
        await knowledge_tests.create_retrieval_test(
            kb.id,
            knowledge_tests.RetrievalTestCreateRequest(revision_id=revision.id, query="anything"),
            current_user,
        )
    assert unavailable.value.status_code == 503
    assert unavailable.value.detail["code"] == "retrieval_test_unavailable"

    # Storage failure while archiving: 503 with a distinct storage code.
    monkeypatch.setattr(knowledge_tests, "KnowledgeRetrievalTestService", _FailingStorageService)
    with pytest.raises(HTTPException) as storage:
        await knowledge_tests.create_retrieval_test(
            kb.id,
            knowledge_tests.RetrievalTestCreateRequest(revision_id=revision.id, query="anything"),
            current_user,
        )
    assert storage.value.status_code == 503
    assert storage.value.detail["code"] == "retrieval_test_storage_unavailable"

    # A draft revision is not retrievable: 409, distinct from unknown (404).
    _install_search(monkeypatch, _chunk_result([]))
    await _seed_document(factory, tmp_path, kb.id, current_user.id, "draft-doc.txt")
    async with factory() as session:
        revision_service = KnowledgeRevisionService(session, _actor(current_user.id))
        candidate = await revision_service.create_revision(kb.id)
        await session.commit()
        draft_id = str(candidate["id"])
    with pytest.raises(HTTPException) as conflict:
        await knowledge_tests.create_retrieval_test(
            kb.id,
            knowledge_tests.RetrievalTestCreateRequest(revision_id=draft_id, query="anything"),
            current_user,
        )
    assert conflict.value.status_code == 409

    # Unknown or invisible identifiers are uniformly 404.
    intruder = UserModel(id="intruder", username="intruder@test.com", role=UserRole.USER, department_id="dept-b", disabled=False)
    with pytest.raises(HTTPException) as hidden_list:
        await knowledge_tests.list_retrieval_tests(kb.id, 0, 20, intruder)
    assert hidden_list.value.status_code == 404
    with pytest.raises(HTTPException) as guessed_test:
        await knowledge_tests.get_retrieval_test(kb.id, str(uuid.uuid4()), current_user)
    assert guessed_test.value.status_code == 404
    with pytest.raises(HTTPException) as guessed_revision:
        await knowledge_tests.create_retrieval_test(
            kb.id,
            knowledge_tests.RetrievalTestCreateRequest(revision_id=str(uuid.uuid4()), query="anything"),
            current_user,
        )
    assert guessed_revision.value.status_code == 404
    await engine.dispose()
