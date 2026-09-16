from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agentplatform.knowledge.eval_cases import eval_case_content_hash
from app.agentplatform.knowledge.evaluation import (
    KnowledgeEvaluationService,
    calculate_retrieval_metrics,
    require_evaluation_execution_access,
)
from app.agentplatform.knowledge.models import KnowledgeEvalCase, KnowledgeEvalRun, KnowledgeRevision
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourcePermissionDenied
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def evaluation_session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'evaluation.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _owner() -> ResourceActor:
    return ResourceActor("owner", None, "user", frozenset({ResourceAction.READ, ResourceAction.USE, ResourceAction.WRITE}))


async def _evaluation_fixture(session: AsyncSession) -> tuple[Resource, KnowledgeEvalCase]:
    from app.agentplatform.resources.service import ResourceService

    kb = await ResourceService(session, _owner()).create_resource(resource_type="knowledge_base", slug="evaluation", display_name="Evaluation", storage_kind="database")
    document_id = str(uuid.uuid4())
    revision = KnowledgeRevision(
        id=str(uuid.uuid4()),
        knowledge_base_id=kb.id,
        revision_no=1,
        status="published",
        manifest_hash="a" * 64,
        manifest_json=[{"document_id": document_id, "filename": "guide.txt", "content_hash": "b" * 64}],
        provider_doc_map_json={document_id: "provider-doc"},
        document_count=1,
        provider_dataset_id="dataset",
        created_by="owner",
    )
    case = KnowledgeEvalCase(
        id=str(uuid.uuid4()),
        knowledge_base_id=kb.id,
        question="Where is the guide?",
        expected_document_ids_json=[document_id],
        tags_json=["smoke"],
        content_hash=eval_case_content_hash("Where is the guide?", [document_id], ["smoke"]),
        version_no=1,
        created_by="owner",
    )
    session.add_all([revision, case])
    await session.commit()
    return kb, case


def test_metrics_deduplicate_chunks_before_ranking_and_count_multiple_expected_documents() -> None:
    metrics = calculate_retrieval_metrics(["doc-a", "doc-a", "doc-b", "doc-c"], ["doc-a", "doc-c"])

    assert metrics == {"expected_hit": True, "recall_at_k": 1.0, "mrr_at_k": 1.0}


def test_metrics_are_zero_for_a_successful_zero_hit_and_support_fewer_than_k() -> None:
    assert calculate_retrieval_metrics(["doc-z"], ["doc-a"]) == {
        "expected_hit": False,
        "recall_at_k": 0.0,
        "mrr_at_k": 0.0,
    }
    assert calculate_retrieval_metrics([], ["doc-a", "doc-b"]) == {
        "expected_hit": False,
        "recall_at_k": 0.0,
        "mrr_at_k": 0.0,
    }


def test_execution_requires_current_use_and_write_permissions() -> None:
    require_evaluation_execution_access(ResourceActor("worker", None, "user", frozenset({ResourceAction.USE, ResourceAction.WRITE})))
    with pytest.raises(ResourcePermissionDenied):
        require_evaluation_execution_access(ResourceActor("viewer", None, "user", frozenset({ResourceAction.READ})))


@pytest.mark.asyncio
async def test_start_freezes_selected_case_and_profile_for_historical_reads(evaluation_session: AsyncSession) -> None:
    kb, case = await _evaluation_fixture(evaluation_session)
    service = KnowledgeEvaluationService(evaluation_session, _owner())

    revision = (await evaluation_session.execute(select(KnowledgeRevision))).scalar_one()
    payload = await service.start(kb.id, revision.id, profile_id="configured", top_k=3, case_ids=[case.id])
    run = await evaluation_session.get(KnowledgeEvalRun, payload["id"])

    assert run is not None
    assert run.profile_id == "configured"
    assert run.top_k == 3
    assert run.case_snapshot_json[0]["content_hash"] == case.content_hash
    assert run.case_snapshot_json[0]["expected_document_ids"] == case.expected_document_ids_json
    case.question = "Changed after start"
    await evaluation_session.commit()
    historical = await service.get_run(kb.id, run.id)
    assert historical["results"] == []
    assert historical["revision_id"] == payload["revision_id"]


@pytest.mark.asyncio
async def test_retry_creates_a_traceable_attempt(evaluation_session: AsyncSession) -> None:
    kb, case = await _evaluation_fixture(evaluation_session)
    revision = (await evaluation_session.execute(select(KnowledgeRevision))).scalar_one()
    original = await KnowledgeEvaluationService(evaluation_session, _owner()).start(kb.id, revision.id, case_ids=[case.id])
    row = await evaluation_session.get(KnowledgeEvalRun, original["id"])
    assert row is not None
    row.status = "failed"
    await evaluation_session.commit()

    retried = await KnowledgeEvaluationService(evaluation_session, _owner()).retry(kb.id, row.id)

    assert retried["retry_of_run_id"] == row.id
    assert retried["id"] != row.id
