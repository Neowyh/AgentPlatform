"""Eval cases: canonical CRUD, versioning, governance, revision applicability (M6 ticket 03)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.agentplatform.audit_model  # noqa: F401 - register audit_logs
import app.agentplatform.rbac_models  # noqa: F401 - register users_ext
import app.agentplatform.resource_models  # noqa: F401 - register resource tables
import app.agentplatform.visibility_models  # noqa: F401 - register visibility tables
from app.agentplatform.knowledge.eval_cases import (
    MAX_EXPECTED_DOCUMENTS,
    MAX_QUESTION_LENGTH,
    KnowledgeEvalCaseService,
    KnowledgeEvalCaseValidationError,
    eval_case_content_hash,
)
from app.agentplatform.knowledge.models import KnowledgeDocument, KnowledgeRevision
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceNotFound, ResourcePermissionDenied, ResourceService
from deerflow.persistence.base import Base


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'eval-cases.db'}")
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


async def _seed_kb(session: AsyncSession, slug: str = "eval-kb", *, owner_id: str = "owner") -> Resource:
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
    kb: Resource,
    *,
    filename: str = "guide.txt",
) -> KnowledgeDocument:
    row = KnowledgeDocument(
        id=str(uuid.uuid4()),
        resource_id=kb.id,
        original_filename=filename,
        size_bytes=8,
        mime_type="text/plain",
        content_hash="0" * 64,
        storage_key=f"knowledge-documents/{kb.id}/{uuid.uuid4()}-{filename}",
        metadata_json={},
        status="ready",
        created_by=kb.owner_id,
    )
    session.add(row)
    return row


async def _create_case(
    session: AsyncSession,
    kb: Resource,
    *,
    question: str = "What does the spec say about retries?",
    expected: list[str] | None = None,
    tags: list[str] | None = None,
    actor: ResourceActor | None = None,
) -> dict:
    documents = expected or []
    return await KnowledgeEvalCaseService(session, actor or _actor()).create_case(
        kb.id,
        question=question,
        expected_document_ids=documents,
        tags=tags or [],
    )


@pytest.mark.asyncio
async def test_eval_case_content_hash_is_deterministic_and_content_sensitive() -> None:
    assert eval_case_content_hash("q", ["a", "b"], ["x"]) == eval_case_content_hash("q", ["b", "a"], ["x"])
    assert eval_case_content_hash("q", ["a"], []) != eval_case_content_hash("q ", ["a"], [])
    assert eval_case_content_hash("q", ["a"], []) != eval_case_content_hash("q", ["a"], ["t"])


@pytest.mark.asyncio
async def test_eval_case_create_list_detail_roundtrip(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    document = _seed_document(session, kb)
    await session.commit()

    created = await _create_case(session, kb, expected=[document.id], tags=["regression", "api"])
    assert created["resource_id"] == kb.id
    assert created["question"] == "What does the spec say about retries?"
    assert created["expected_document_ids"] == [document.id]
    assert created["tags"] == ["regression", "api"]
    assert created["version_no"] == 1
    assert created["content_hash"] == eval_case_content_hash(created["question"], [document.id], ["regression", "api"])
    assert created["created_by"] == "owner"

    listed = await KnowledgeEvalCaseService(session, _actor()).list_cases(kb.id)
    assert [case["id"] for case in listed] == [created["id"]]

    detail = await KnowledgeEvalCaseService(session, _actor()).get_case(kb.id, created["id"])
    assert detail["id"] == created["id"]
    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["version_no"] == 1
    assert detail["versions"][0]["change_type"] == "created"
    assert detail["versions"][0]["question"] == created["question"]


@pytest.mark.asyncio
async def test_eval_case_update_appends_version_and_recomputes_hash(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    first = _seed_document(session, kb)
    second = _seed_document(session, kb, filename="other.txt")
    await session.commit()
    created = await _create_case(session, kb, expected=[first.id], tags=["v1"])

    updated = await KnowledgeEvalCaseService(session, _actor()).update_case(
        kb.id,
        created["id"],
        expected_document_ids=[first.id, second.id],
        tags=["v2"],
    )
    assert updated["version_no"] == 2
    assert updated["expected_document_ids"] == [first.id, second.id]
    assert updated["tags"] == ["v2"]
    assert updated["content_hash"] != created["content_hash"]

    detail = await KnowledgeEvalCaseService(session, _actor()).get_case(kb.id, created["id"])
    assert [version["version_no"] for version in detail["versions"]] == [1, 2]
    assert [version["change_type"] for version in detail["versions"]] == ["created", "updated"]
    assert detail["versions"][0]["tags"] == ["v1"]
    assert detail["versions"][1]["tags"] == ["v2"]


@pytest.mark.asyncio
async def test_eval_case_update_with_unchanged_content_does_not_append_version(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    document = _seed_document(session, kb)
    await session.commit()
    created = await _create_case(session, kb, expected=[document.id], tags=["same"])

    unchanged = await KnowledgeEvalCaseService(session, _actor()).update_case(
        kb.id,
        created["id"],
        question=f"  {created['question']}  ",
    )
    assert unchanged["version_no"] == 1
    assert unchanged["id"] == created["id"]


@pytest.mark.asyncio
async def test_eval_case_delete_removes_case_and_history(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    document = _seed_document(session, kb)
    await session.commit()
    created = await _create_case(session, kb, expected=[document.id])
    service = KnowledgeEvalCaseService(session, _actor())

    await service.delete_case(kb.id, created["id"])
    with pytest.raises(ResourceNotFound):
        await service.get_case(kb.id, created["id"])
    listed = await service.list_cases(kb.id)
    assert listed == []


@pytest.mark.asyncio
async def test_eval_case_validation_rejects_empty_duplicate_unknown_and_bounds(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    document = _seed_document(session, kb)
    other_kb = await _seed_kb(session, slug="other-kb")
    foreign_document = _seed_document(session, other_kb)
    await session.commit()
    service = KnowledgeEvalCaseService(session, _actor())

    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="   ", expected_document_ids=[document.id])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[document.id, document.id])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[str(uuid.uuid4())])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[foreign_document.id])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="x" * (MAX_QUESTION_LENGTH + 1), expected_document_ids=[document.id])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[document.id] * (MAX_EXPECTED_DOCUMENTS + 1))
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[document.id], tags=["x" * 65])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[document.id], tags=[f"t{i}" for i in range(21)])
    with pytest.raises(KnowledgeEvalCaseValidationError):
        await service.create_case(kb.id, question="q", expected_document_ids=[document.id], tags=["dup", "dup"])


@pytest.mark.asyncio
async def test_eval_case_governance_requires_read_and_modify(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    document = _seed_document(session, kb)
    await session.commit()
    created = await _create_case(session, kb, expected=[document.id])

    kb.visibility = "public"
    await session.commit()
    viewer = KnowledgeEvalCaseService(session, _actor("viewer", permissions={ResourceAction.READ}))
    with pytest.raises(ResourcePermissionDenied):
        await viewer.create_case(kb.id, question="q", expected_document_ids=[document.id])
    with pytest.raises(ResourcePermissionDenied):
        await viewer.update_case(kb.id, created["id"], question="q2")
    with pytest.raises(ResourcePermissionDenied):
        await viewer.delete_case(kb.id, created["id"])
    assert (await viewer.list_cases(kb.id))[0]["id"] == created["id"]

    kb.visibility = "private"
    await session.commit()
    outsider = KnowledgeEvalCaseService(session, _actor("outsider"))
    with pytest.raises(ResourceNotFound):
        await outsider.list_cases(kb.id)
    with pytest.raises(ResourceNotFound):
        await outsider.get_case(kb.id, created["id"])
    with pytest.raises(ResourceNotFound):
        await outsider.get_case(kb.id, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_eval_case_revision_applicability_reports_missing_expected_documents(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    included = _seed_document(session, kb)
    await session.commit()

    revision_id = str(uuid.uuid4())
    session.add(
        KnowledgeRevision(
            id=revision_id,
            knowledge_base_id=kb.id,
            revision_no=1,
            status="published",
            manifest_hash="a" * 64,
            manifest_json=[{"document_id": included.id, "content_hash": "0" * 64, "filename": included.original_filename}],
            provider_doc_map_json={},
            document_count=1,
            created_by=kb.owner_id,
        )
    )
    await session.commit()

    missing = _seed_document(session, kb, filename="added-later.txt")
    await session.commit()
    service = KnowledgeEvalCaseService(session, _actor())
    applicable = await _create_case(session, kb, question="covered", expected=[included.id])
    stale = await _create_case(session, kb, question="stale", expected=[included.id, missing.id])

    report = await service.revision_applicability(kb.id, revision_id)
    assert report["revision_id"] == revision_id
    assert report["manifest_hash"] == "a" * 64
    by_case = {item["case_id"]: item for item in report["items"]}
    assert by_case[applicable["id"]]["applicable"] is True
    assert by_case[applicable["id"]]["missing_document_ids"] == []
    assert by_case[stale["id"]]["applicable"] is False
    assert by_case[stale["id"]]["missing_document_ids"] == [missing.id]

    detail = await service.get_case(kb.id, stale["id"])
    assert detail["expected_document_ids"] == [included.id, missing.id]


@pytest.mark.asyncio
async def test_eval_case_revision_applicability_scopes_revision_to_kb(session: AsyncSession) -> None:
    kb = await _seed_kb(session)
    other_kb = await _seed_kb(session, slug="other-kb")
    await session.commit()
    foreign_revision_id = str(uuid.uuid4())
    session.add(
        KnowledgeRevision(
            id=foreign_revision_id,
            knowledge_base_id=other_kb.id,
            revision_no=1,
            status="published",
            manifest_hash="b" * 64,
            manifest_json=[],
            provider_doc_map_json={},
            document_count=0,
            created_by=other_kb.owner_id,
        )
    )
    await session.commit()

    with pytest.raises(ResourceNotFound):
        await KnowledgeEvalCaseService(session, _actor()).revision_applicability(kb.id, foreign_revision_id)
