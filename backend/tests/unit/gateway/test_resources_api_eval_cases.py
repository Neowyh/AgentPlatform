"""Eval case endpoints follow Resource Governance and the canonical API (M6 ticket 03)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import deerflow.persistence.models  # noqa: F401  -- registers DeerFlow ORM tables
import deerflow.persistence.models.workflow_v2  # noqa: F401
from app.agentplatform.knowledge.models import KnowledgeDocument
from app.agentplatform.rbac_models import UserModel, UserRole
from app.gateway.routers import resources
from deerflow.persistence.base import Base


async def _make_env(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    role: UserRole = UserRole.USER,
    user_id: str = "owner",
) -> tuple:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'eval-cases-api.db'}")
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
    return engine, factory, current_user


async def _seed_kb(factory, user, slug: str = "eval-api") -> str:
    created = await resources.create_resource(
        resources.ResourceCreateRequest(type="knowledge_base", slug=slug, display_name=slug, storage_kind="database"),
        user,
    )
    return created["id"]


async def _seed_document(factory, kb_id: str, owner_id: str, filename: str = "guide.txt") -> KnowledgeDocument:
    async with factory() as session:
        row = KnowledgeDocument(
            id=str(uuid.uuid4()),
            resource_id=kb_id,
            original_filename=filename,
            size_bytes=8,
            mime_type="text/plain",
            content_hash="0" * 64,
            storage_key=f"knowledge-documents/{kb_id}/{uuid.uuid4()}-{filename}",
            metadata_json={},
            status="ready",
            created_by=owner_id,
        )
        session.add(row)
        await session.commit()
        return row


def _create_request(question: str = "What is the retry policy?", document_ids: list[str] | None = None, tags: list[str] | None = None) -> resources.EvalCaseCreateRequest:
    return resources.EvalCaseCreateRequest(
        question=question,
        expected_document_ids=document_ids or [],
        tags=tags or [],
    )


@pytest.mark.asyncio
async def test_eval_case_crud_endpoints_with_audit(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    calls: list[tuple] = []

    async def _audit(actor_id, action, resource_type=None, resource_id=None, detail=None, ip_address=None) -> None:
        calls.append((actor_id, action, resource_type, resource_id, detail))

    monkeypatch.setattr(resources, "record_audit", _audit)

    kb_id = await _seed_kb(factory, current_user)
    document = await _seed_document(factory, kb_id, current_user.id)

    created = await resources.create_eval_case(kb_id, _create_request(document_ids=[document.id], tags=["regression"]), current_user)
    assert created["resource_id"] == kb_id
    assert created["expected_document_ids"] == [document.id]
    assert created["version_no"] == 1
    assert calls[-1][1] == "eval_case_created"
    assert calls[-1][3] == created["id"]
    # Case content stays in controlled storage; the audit trail records
    # identity and hash only, never the question text.
    assert "question" not in (calls[-1][4] or {})

    listed = await resources.list_eval_cases(kb_id, current_user)
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == created["id"]

    detail = await resources.get_eval_case(kb_id, str(created["id"]), current_user)
    assert detail["versions"][0]["change_type"] == "created"

    updated = await resources.update_eval_case(
        kb_id,
        str(created["id"]),
        resources.EvalCaseUpdateRequest(tags=["regression", "smoke"]),
        current_user,
    )
    assert updated["version_no"] == 2
    assert updated["tags"] == ["regression", "smoke"]
    assert calls[-1][1] == "eval_case_updated"

    await resources.delete_eval_case(kb_id, str(created["id"]), current_user)
    assert calls[-1][1] == "eval_case_deleted"
    listed = await resources.list_eval_cases(kb_id, current_user)
    assert listed["total"] == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_eval_case_endpoint_reports_revision_applicability(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(resources, "record_audit", _noop_audit)
    from app.agentplatform.knowledge.models import KnowledgeRevision

    kb_id = await _seed_kb(factory, current_user)
    document = await _seed_document(factory, kb_id, current_user.id)
    async with factory() as session:
        revision_id = str(uuid.uuid4())
        session.add(
            KnowledgeRevision(
                id=revision_id,
                knowledge_base_id=kb_id,
                revision_no=1,
                status="published",
                manifest_hash="a" * 64,
                manifest_json=[{"document_id": document.id}],
                provider_doc_map_json={},
                document_count=1,
                created_by=current_user.id,
            )
        )
        await session.commit()

    created = await resources.create_eval_case(kb_id, _create_request(document_ids=[document.id]), current_user)
    report = await resources.get_eval_case_revision_applicability(kb_id, revision_id, current_user)
    assert report["revision_id"] == revision_id
    assert report["items"][0]["case_id"] == created["id"]
    assert report["items"][0]["applicable"] is True

    with pytest.raises(HTTPException) as missing_revision:
        await resources.get_eval_case_revision_applicability(kb_id, str(uuid.uuid4()), current_user)
    assert missing_revision.value.status_code == 404
    await engine.dispose()


async def _noop_audit(*args, **kwargs) -> None:
    return None


@pytest.mark.asyncio
async def test_eval_case_endpoints_enforce_governance_and_validation(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(resources, "record_audit", _noop_audit)

    kb_id = await _seed_kb(factory, current_user)
    document = await _seed_document(factory, kb_id, current_user.id)
    created = await resources.create_eval_case(kb_id, _create_request(document_ids=[document.id]), current_user)

    with pytest.raises(HTTPException) as empty_question:
        await resources.create_eval_case(kb_id, _create_request(question="   ", document_ids=[document.id]), current_user)
    assert empty_question.value.status_code == 400

    with pytest.raises(HTTPException) as empty_expected:
        await resources.create_eval_case(kb_id, _create_request(), current_user)
    assert empty_expected.value.status_code == 400

    with pytest.raises(HTTPException) as unknown_document:
        await resources.create_eval_case(kb_id, _create_request(document_ids=[str(uuid.uuid4())]), current_user)
    assert unknown_document.value.status_code == 400

    intruder = UserModel(id="intruder", username="intruder@test.com", role=UserRole.USER, department_id="dept-b", disabled=False)
    with pytest.raises(HTTPException) as hidden:
        await resources.list_eval_cases(kb_id, intruder)
    assert hidden.value.status_code == 404

    with pytest.raises(HTTPException) as forbidden:
        await resources.create_eval_case(kb_id, _create_request(document_ids=[document.id]), intruder)
    assert forbidden.value.status_code in {403, 404}

    with pytest.raises(HTTPException) as guessed:
        await resources.get_eval_case(kb_id, str(created["id"]), UserModel(id="reader", username="reader@test.com", role=UserRole.VIEWER, department_id="dept-b", disabled=False))
    assert guessed.value.status_code == 404

    with pytest.raises(HTTPException) as scoped:
        await resources.get_eval_case(str(uuid.uuid4()), str(created["id"]), current_user)
    assert scoped.value.status_code == 404
    await engine.dispose()
