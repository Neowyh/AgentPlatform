"""Retrieval tests against published Knowledge Revisions (M6 ticket 01).

A retrieval test reuses the official knowledge_search version mapping
(published revision -> per-revision provider dataset + frozen document
allowlist), applies the official tool retrieval parameters, projects bounded
caller-safe hits, and archives every execution for permission-checked
replay. Tests never fabricate Runs, Tool Calls, or chat citations.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
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
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument, KnowledgeRetrievalTest, KnowledgeRevision
from app.agentplatform.knowledge.provider import ProviderIngestionResult
from app.agentplatform.knowledge.retrieval_test import (
    MAX_TEST_QUERY_CHARS,
    MAX_TEST_TOP_K,
    KnowledgeRetrievalTestService,
    RetrievalTestUnavailable,
)
from app.agentplatform.knowledge.revisions import KnowledgeRevisionService, execute_publish
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceConflict, ResourceNotFound, ResourceService
from deerflow.community.ragflow.client import RAGFlowAPIError, RAGFlowConnectionError
from deerflow.persistence.base import Base

TEST_QUERY = "What is the retry policy?"


class FakePublishProvider:
    """Publish-capable provider whose dataset listing verifies manifests."""

    def __init__(self, dataset_prefix: str = "published-dataset") -> None:
        self.dataset_prefix = dataset_prefix
        self.created: list[str] = []
        self.docs: dict[str, list[dict]] = {}

    async def create_dataset(self, *, name: str, embedding_model: str | None = None) -> str:
        dataset_id = f"{self.dataset_prefix}-{len(self.created) + 1}"
        self.created.append(dataset_id)
        self.docs[dataset_id] = []
        return dataset_id

    async def ingest(self, *, dataset_id: str, filename: str, mime_type: str, content: bytes, provider_document_id: str | None = None, rebuild: bool = False) -> ProviderIngestionResult:
        document_id = provider_document_id or f"provider-doc-{len(self.docs[dataset_id]) + 1}"
        self.docs[dataset_id].append({"id": document_id, "name": filename, "content_hash": hashlib.sha256(content).hexdigest()})
        return ProviderIngestionResult(document_id, "processing")

    async def get_status(self, *, dataset_id: str, provider_document_id: str) -> str:
        return "ready"

    async def delete_document(self, *, dataset_id: str, provider_document_id: str) -> None:
        self.docs[dataset_id] = [item for item in self.docs.get(dataset_id, []) if item["id"] != provider_document_id]

    async def list_dataset_documents(self, *, dataset_id: str) -> list[dict]:
        return list(self.docs.get(dataset_id, []))


@pytest.fixture(autouse=True)
def _frozen_paths(tmp_path: object, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agentplatform.knowledge.revisions.get_paths", lambda: SimpleNamespace(base_dir=tmp_path))


@pytest_asyncio.fixture
async def store(tmp_path) -> AsyncIterator[tuple[AsyncSession, async_sessionmaker]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retrieval-tests.db'}")
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


def _settings(**overrides):
    values = {"page_size": 8, "similarity_threshold": 0.2, "vector_similarity_weight": 0.3, "top_k": 256, "timeout": 30.0}
    values.update(overrides)
    return SimpleNamespace(**values)


async def _seed_kb(session: AsyncSession, *, owner_id: str = "owner", slug: str = "retrieval-test") -> Resource:
    kb = await ResourceService(session, _actor(owner_id)).create_resource(
        resource_type="knowledge_base",
        slug=slug,
        display_name=slug,
        storage_kind="database",
    )
    await session.commit()
    return kb


def _seed_document(session: AsyncSession, tmp_path, kb: Resource, filename: str, content: bytes) -> KnowledgeDocument:
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


async def _publish_revision(
    session: AsyncSession,
    factory: async_sessionmaker,
    tmp_path,
    kb: Resource,
    *,
    documents: int = 2,
) -> KnowledgeRevision:
    for index in range(documents):
        _seed_document(session, tmp_path, kb, f"guide-{index}.txt", f"content {index}".encode())
    await session.commit()
    service = KnowledgeRevisionService(session, _actor(kb.owner_id))
    candidate = await service.create_revision(kb.id)
    provider = FakePublishProvider()
    await service.publish_revision(kb.id, str(candidate["id"]), provider=provider)
    await session.commit()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id=kb.owner_id, provider=provider, poll_interval=0, parse_timeout=5)
    revision = await session.get(KnowledgeRevision, str(candidate["id"]))
    assert revision is not None
    await session.refresh(revision)
    assert revision.status == "published"
    return revision


def _fake_search(result: dict | Exception):
    calls: list[dict] = []

    async def search(query: str, *, settings, dataset_id: str, document_ids: list[str], applied: dict) -> dict:
        calls.append({"query": query, "settings": settings, "dataset_id": dataset_id, "document_ids": list(document_ids), "applied": dict(applied)})
        if isinstance(result, Exception):
            raise result
        return result

    search.calls = calls
    return search


def _chunk_result(chunks: list[dict]) -> dict:
    return {"chunks": chunks, "total": len(chunks)}


async def _execute(
    service: KnowledgeRetrievalTestService,
    revision: KnowledgeRevision,
    *,
    query: str = TEST_QUERY,
    top_k: int | None = None,
    profile_id: str = "frozen",
) -> dict:
    return await service.execute(revision.knowledge_base_id, revision.id, query=query, top_k=top_k, profile_id=profile_id)


@pytest.mark.asyncio
async def test_execute_maps_published_revision_to_dataset_and_documents(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb)
    provider_document_ids = sorted(revision.provider_doc_map_json.values())
    search = _fake_search(
        _chunk_result(
            [
                {"document_id": provider_document_ids[1], "document_keyword": "guide-1.txt", "content": "Retry with backoff.", "similarity": 0.91, "chunk_id": "c-2", "page": 3},
                {"document_id": provider_document_ids[0], "document_keyword": "guide-0.txt", "content": "No retry here.", "similarity": 0.42},
            ]
        )
    )
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    payload = await _execute(service, revision, top_k=5)

    assert len(search.calls) == 1
    call = search.calls[0]
    assert call["query"] == TEST_QUERY
    assert call["dataset_id"] == revision.provider_dataset_id
    assert call["document_ids"] == provider_document_ids
    assert call["applied"] == {"page_size": 5, "similarity_threshold": 0.2, "vector_similarity_weight": 0.3, "top_k": 256, "timeout": 30.0}

    assert payload["result_status"] == "success"
    assert payload["returned_count"] == 2
    assert payload["truncated"] is False
    assert payload["revision_id"] == revision.id
    assert payload["revision_no"] == revision.revision_no
    assert payload["manifest_hash"] == revision.manifest_hash
    assert payload["query"] == TEST_QUERY
    assert payload["requested_top_k"] == 5
    assert payload["created_by"] == "owner"
    assert [item["rank"] for item in payload["items"]] == [1, 2]
    first, second = payload["items"]
    assert first["document_id"] in revision.provider_doc_map_json
    assert first["display_name"] == "guide-1.txt"
    assert first["content_hash"] is not None
    assert first["chunk_ref"] is not None
    assert first["score"] == 0.91
    assert first["position"] == {"page": 3}
    assert second["position"] == {}
    assert second["score"] == 0.42
    assert first["rerank_score"] is None

    serialized = json.dumps(payload)
    assert revision.provider_dataset_id not in serialized
    for provider_document_id in provider_document_ids:
        assert provider_document_id not in serialized


@pytest.mark.asyncio
async def test_execute_applies_frozen_retrieval_profile(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    entries = [dict(entry) for entry in revision.manifest_json or []]
    entries[0]["knowledge_profiles"] = {
        "retrieval": {
            "top_k": 42,
            "similarity_threshold": 0.35,
            "vector_similarity_weight": 0.7,
        }
    }
    revision.manifest_json = entries
    await session.commit()

    search = _fake_search(_chunk_result([]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    await _execute(service, revision, top_k=5)

    assert search.calls[0]["applied"] == {
        "page_size": 5,
        "similarity_threshold": 0.35,
        "vector_similarity_weight": 0.7,
        "top_k": 42,
        "timeout": 30.0,
    }


@pytest.mark.asyncio
async def test_execute_persists_archive_record(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb)
    provider_document_ids = sorted(revision.provider_doc_map_json.values())
    search = _fake_search(_chunk_result([{"document_id": provider_document_ids[0], "document_keyword": "guide-0.txt", "content": "Retry.", "similarity": 0.8}]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    payload = await _execute(service, revision)
    await session.commit()

    rows = await KnowledgeRetrievalTestService(session, _actor()).list_tests(kb.id)
    assert rows["total"] == 1
    summary = rows["items"][0]
    assert summary["id"] == payload["id"]
    assert summary["revision_no"] == revision.revision_no
    assert summary["result_status"] == "success"
    assert summary["created_by"] == "owner"
    assert "items" not in summary

    detail = await KnowledgeRetrievalTestService(session, _actor()).get_test(kb.id, payload["id"])
    assert detail["items"][0]["content"] == "Retry."
    assert detail["revision_id"] == revision.id

    record = await session.get(KnowledgeRetrievalTest, payload["id"])
    assert record is not None
    assert record.retrieval_profile_json == {}
    assert record.applied_parameters_json["page_size"] == 8
    assert record.result_status == "success"
    assert record.returned_count == 1


@pytest.mark.asyncio
async def test_execute_records_frozen_retrieval_profile(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    entries = [dict(entry) for entry in revision.manifest_json or []]
    entries[0]["knowledge_profiles"] = {"retrieval": {"top_k": 42, "similarity_threshold": 0.35}}
    revision.manifest_json = entries
    await session.commit()

    search = _fake_search(_chunk_result([]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())
    payload = await _execute(service, revision)

    assert payload["retrieval_profile"] == {"top_k": 42, "similarity_threshold": 0.35}
    assert payload["result_status"] == "empty_hit"
    assert payload["returned_count"] == 0


@pytest.mark.asyncio
async def test_revision_payload_exposes_frozen_profiles(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    entries = [dict(entry) for entry in revision.manifest_json or []]
    entries[0]["knowledge_profiles"] = {"retrieval": {"top_k": 42}, "embedding": {"model": "embed-v2"}}
    revision.manifest_json = entries
    await session.commit()

    detail = await KnowledgeRevisionService(session, _actor()).get_revision(kb.id, revision.id)
    assert detail["knowledge_profiles"] == {"retrieval": {"top_k": 42}, "embedding": {"model": "embed-v2"}}
    listed = await KnowledgeRevisionService(session, _actor()).list_revisions(kb.id)
    assert listed[0]["knowledge_profiles"]["retrieval"] == {"top_k": 42}


@pytest.mark.asyncio
async def test_execute_falls_back_to_kb_profile_for_legacy_revision(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.retrieval_profile_json = {"top_k": 64}
    await session.commit()
    # A pre-freeze revision carries no knowledge_profiles in its manifest.
    revision.manifest_json = [{key: value for key, value in entry.items() if key != "knowledge_profiles"} for entry in revision.manifest_json or []]
    await session.commit()

    search = _fake_search(_chunk_result([]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())
    payload = await _execute(service, revision)

    assert payload["retrieval_profile"] == {"top_k": 64}


@pytest.mark.asyncio
async def test_execute_can_select_current_configured_profile_without_mutating_revision(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    entries = [dict(entry) for entry in revision.manifest_json or []]
    entries[0]["knowledge_profiles"] = {"retrieval": {"top_k": 42}}
    revision.manifest_json = entries
    kb_row = await session.get(KnowledgeBase, kb.id)
    assert kb_row is not None
    kb_row.retrieval_profile_json = {"top_k": 64}
    await session.commit()

    search = _fake_search(_chunk_result([]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    payload = await _execute(service, revision, profile_id="configured")

    assert payload["retrieval_profile"] == {"top_k": 64}
    assert search.calls[0]["applied"]["top_k"] == 64
    await session.refresh(revision)
    assert revision.manifest_json[0]["knowledge_profiles"]["retrieval"] == {"top_k": 42}


@pytest.mark.asyncio
async def test_execute_archives_timeout_state_when_provider_exceeds_budget(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)

    async def slow_search(query, **kwargs):
        await asyncio.sleep(0.02)
        return _chunk_result([])

    service = KnowledgeRetrievalTestService(session, _actor(), search=slow_search, settings_factory=lambda: _settings(timeout=0.001))

    payload = await _execute(service, revision)

    assert payload["result_status"] == "provider_error"
    assert payload["error_code"] == "timeout"
    record = await session.get(KnowledgeRetrievalTest, payload["id"])
    assert record is not None
    assert record.applied_parameters_json["timeout"] == 0.001


@pytest.mark.asyncio
async def test_execute_caps_results_at_requested_k_and_marks_truncated(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    provider_document_id = next(iter(revision.provider_doc_map_json.values()))
    chunks = [{"document_id": provider_document_id, "document_keyword": "guide-0.txt", "content": f"chunk {index}", "similarity": 0.5} for index in range(9)]
    service = KnowledgeRetrievalTestService(session, _actor(), search=_fake_search(_chunk_result(chunks)), settings_factory=lambda: _settings())

    payload = await _execute(service, revision, top_k=4)

    assert payload["returned_count"] == 4
    assert payload["truncated"] is True
    assert [item["rank"] for item in payload["items"]] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_execute_bounds_snippet_length(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    provider_document_id = next(iter(revision.provider_doc_map_json.values()))
    huge = "x" * 9000
    search = _fake_search(_chunk_result([{"document_id": provider_document_id, "document_keyword": "guide-0.txt", "content": huge, "similarity": 0.5}]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    payload = await _execute(service, revision)

    content = payload["items"][0]["content"]
    assert len(content) < 9000
    assert content.startswith("xxxx")


@pytest.mark.asyncio
async def test_execute_provider_failure_is_a_distinct_recorded_state(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    search = _fake_search(RAGFlowConnectionError("internal host detail"))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    payload = await _execute(service, revision)
    await session.commit()

    assert payload["result_status"] == "provider_error"
    assert payload["error_code"] == "connection_error"
    assert payload["items"] == []
    assert payload["returned_count"] == 0
    assert "internal host detail" not in json.dumps(payload)

    detail = await KnowledgeRetrievalTestService(session, _actor()).get_test(kb.id, payload["id"])
    assert detail["result_status"] == "provider_error"


@pytest.mark.asyncio
async def test_execute_provider_api_failure_uses_low_cardinality_code(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    search = _fake_search(RAGFlowAPIError("boom", code=403))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    payload = await _execute(service, revision)
    assert payload["result_status"] == "provider_error"
    assert payload["error_code"] == "provider_api_error"


@pytest.mark.asyncio
async def test_execute_surfaces_rerank_score_only_when_provider_provides_one(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    provider_document_id = next(iter(revision.provider_doc_map_json.values()))
    chunks = [
        {"document_id": provider_document_id, "document_keyword": "guide-0.txt", "content": "with rerank", "similarity": 0.9, "rerank_similarity": 0.81},
        {"document_id": provider_document_id, "document_keyword": "guide-0.txt", "content": "without rerank", "similarity": 0.5, "rerank_similarity": True},
    ]
    service = KnowledgeRetrievalTestService(session, _actor(), search=_fake_search(_chunk_result(chunks)), settings_factory=lambda: _settings())

    payload = await _execute(service, revision)

    assert [item["rerank_score"] for item in payload["items"]] == [0.81, None]


@pytest.mark.asyncio
async def test_execute_maps_missing_tooling_module_to_unavailable(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)

    def _no_tooling():
        raise ImportError("deerflow.community.ragflow is not installed")

    service = KnowledgeRetrievalTestService(session, _actor(), search=_fake_search(_chunk_result([])), settings_factory=_no_tooling)

    with pytest.raises(RetrievalTestUnavailable):
        await _execute(service, revision)


@pytest.mark.asyncio
async def test_execute_without_tool_settings_is_unavailable(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    service = KnowledgeRetrievalTestService(session, _actor(), search=_fake_search(_chunk_result([])), settings_factory=lambda: None)

    with pytest.raises(RetrievalTestUnavailable):
        await _execute(service, revision)


@pytest.mark.asyncio
async def test_execute_validates_query_and_top_k_bounds(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    service = KnowledgeRetrievalTestService(session, _actor(), search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())

    for bad_query in ["", "   ", "x" * (MAX_TEST_QUERY_CHARS + 1)]:
        with pytest.raises(ValueError):
            await service.execute(kb.id, revision.id, query=bad_query)
    for bad_top_k in [0, MAX_TEST_TOP_K + 1, -3]:
        with pytest.raises(ValueError):
            await service.execute(kb.id, revision.id, query=TEST_QUERY, top_k=bad_top_k)


@pytest.mark.asyncio
async def test_execute_requires_visible_knowledge_base(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session, owner_id="owner", slug="private-kb")
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    service = KnowledgeRetrievalTestService(session, _actor("intruder"), search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())

    with pytest.raises(ResourceNotFound):
        await service.execute(kb.id, revision.id, query=TEST_QUERY)
    with pytest.raises(ResourceNotFound):
        await service.list_tests(kb.id)


@pytest.mark.asyncio
async def test_execute_rejects_non_published_or_unusable_revisions(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    _seed_document(session, tmp_path, kb, "guide.txt", b"content")
    await session.commit()
    service = KnowledgeRevisionService(session, _actor(kb.owner_id))
    candidate = await service.create_revision(kb.id)
    await session.commit()
    draft_id = str(candidate["id"])
    retrieval_service = KnowledgeRetrievalTestService(session, _actor(), search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())

    with pytest.raises(ResourceConflict):
        await retrieval_service.execute(kb.id, draft_id, query=TEST_QUERY)

    revision = await session.get(KnowledgeRevision, draft_id)
    assert revision is not None
    revision.integrity_status = "drifted"
    revision.status = "published"
    await session.commit()
    with pytest.raises(ResourceConflict):
        await retrieval_service.execute(kb.id, draft_id, query=TEST_QUERY)


@pytest.mark.asyncio
async def test_candidate_retrieval_is_owner_only_and_not_listed_to_strangers(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session, slug="candidate-owner-only")
    kb.visibility = "public"
    _seed_document(session, tmp_path, kb, "guide.txt", b"content")
    await session.commit()
    candidate = await KnowledgeRevisionService(session, _actor()).create_revision(kb.id)
    provider = FakePublishProvider()
    requested = await KnowledgeRevisionService(session, _actor()).prepare_revision(kb.id, str(candidate["id"]), provider=provider)
    await session.commit()
    await execute_publish(factory, resource_id=kb.id, revision_id=str(candidate["id"]), actor_id="owner", provider=provider, execution_token=requested["publish_execution_token"], poll_interval=0, parse_timeout=5, activate=False)

    owner = KnowledgeRetrievalTestService(session, _actor(), search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())
    ready = await session.get(KnowledgeRevision, str(candidate["id"]))
    assert ready is not None
    await _execute(owner, ready)
    stranger = KnowledgeRetrievalTestService(session, _actor("stranger"), search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())
    assert (await stranger.list_tests(kb.id))["total"] == 0
    with pytest.raises(ResourceNotFound):
        await stranger.execute(kb.id, str(candidate["id"]), query=TEST_QUERY)


@pytest.mark.asyncio
async def test_guessed_revision_or_test_ids_reveal_nothing(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    search = _fake_search(_chunk_result([]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())
    payload = await _execute(service, revision)
    await session.commit()

    stranger = KnowledgeRetrievalTestService(session, _actor("intruder"), search=search, settings_factory=lambda: _settings())
    with pytest.raises(ResourceNotFound):
        await stranger.get_test(kb.id, payload["id"])
    with pytest.raises(ResourceNotFound):
        await KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings()).get_test(kb.id, str(uuid.uuid4()))
    with pytest.raises(ResourceNotFound):
        await KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings()).execute(kb.id, str(uuid.uuid4()), query=TEST_QUERY)


@pytest.mark.asyncio
async def test_historical_read_rechecks_current_permission(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session, owner_id="owner", slug="shared-kb")
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    service = KnowledgeRetrievalTestService(session, _actor("owner"), search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())
    payload = await _execute(service, revision)
    await session.commit()

    resource = await session.get(Resource, kb.id)
    assert resource is not None
    resource.visibility = "private"
    await session.commit()

    member = ResourceActor(user_id="colleague", department_id=None, role="user", permissions=frozenset({ResourceAction.READ, ResourceAction.USE}))
    with pytest.raises(ResourceNotFound):
        await KnowledgeRetrievalTestService(session, member).get_test(kb.id, payload["id"])
    with pytest.raises(ResourceNotFound):
        await KnowledgeRetrievalTestService(session, member).list_tests(kb.id)


@pytest.mark.asyncio
async def test_service_requires_read_permission(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    viewer_only = _actor("viewer", permissions={ResourceAction.USE})
    service = KnowledgeRetrievalTestService(session, viewer_only, search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())

    from app.agentplatform.resources.service import ResourcePermissionDenied

    with pytest.raises(ResourcePermissionDenied):
        await service.execute(kb.id, revision.id, query=TEST_QUERY)


@pytest.mark.asyncio
async def test_service_requires_use_permission_to_execute(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    revision = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    read_only = _actor("owner", permissions={ResourceAction.READ})
    service = KnowledgeRetrievalTestService(session, read_only, search=_fake_search(_chunk_result([])), settings_factory=lambda: _settings())

    from app.agentplatform.resources.service import ResourcePermissionDenied

    with pytest.raises(ResourcePermissionDenied):
        await service.execute(kb.id, revision.id, query=TEST_QUERY)


@pytest.mark.asyncio
async def test_superseded_revision_remains_testable(store, tmp_path) -> None:
    session, factory = store
    kb = await _seed_kb(session)
    first = await _publish_revision(session, factory, tmp_path, kb, documents=1)
    await _publish_revision(session, factory, tmp_path, kb, documents=1)
    assert first.status == "published"  # stale identity-map value before refresh
    await session.refresh(first)
    assert first.status == "superseded"
    search = _fake_search(_chunk_result([]))
    service = KnowledgeRetrievalTestService(session, _actor(), search=search, settings_factory=lambda: _settings())

    payload = await service.execute(kb.id, first.id, query=TEST_QUERY)
    assert payload["revision_id"] == first.id
    assert payload["result_status"] == "empty_hit"
