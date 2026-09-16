"""Knowledge revision candidate endpoints follow Resource Governance (M4 ticket 01)."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import deerflow.persistence.models  # noqa: F401  -- registers DeerFlow ORM tables
import deerflow.persistence.models.workflow_v2  # noqa: F401
from app.agentplatform.knowledge.models import KnowledgeDocument
from app.agentplatform.rbac_models import UserModel, UserRole
from app.agentplatform.resource_models import Resource
from app.gateway.routers import resources
from deerflow.persistence.base import Base


async def _make_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: UserRole = UserRole.USER,
    user_id: str = "owner",
) -> tuple:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'revisions-api.db'}")
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


def _seed_ready_document(session, tmp_path: Path, kb, filename: str, content: bytes) -> KnowledgeDocument:
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
        provider_document_id="provider-doc-1",
        status="ready",
        created_by=kb.owner_id,
    )
    session.add(row)
    return row


@pytest.mark.asyncio
async def test_revision_create_list_detail_and_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    calls: list[tuple] = []

    async def _audit(actor_id, action, resource_type=None, resource_id=None, detail=None, ip_address=None) -> None:
        calls.append((actor_id, action, resource_type, resource_id, detail))

    monkeypatch.setattr(resources, "record_audit", _audit)

    created = await resources.create_resource(
        resources.ResourceCreateRequest(type="knowledge_base", slug="revisions", display_name="Revisions", storage_kind="database"),
        current_user,
    )
    kb_id = created["id"]
    async with factory() as session:
        kb = await session.get(Resource, kb_id)
        _seed_ready_document(session, tmp_path, kb, "guide.txt", b"knowledge bytes")
        await session.commit()

    revision = await resources.create_knowledge_revision(kb_id, current_user)
    assert revision["status"] == "draft"
    assert revision["document_count"] == 1
    assert revision["resource_id"] == kb_id
    assert "provider_dataset_id" not in revision
    assert "provider_type" not in revision
    assert calls[-1][1] == "knowledge_revision_created"
    assert calls[-1][3] == revision["id"]

    listed = await resources.list_knowledge_revisions(kb_id, current_user)
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == revision["id"]

    detail = await resources.get_knowledge_revision(kb_id, str(revision["id"]), current_user)
    assert detail["documents"][0]["filename"] == "guide.txt"
    assert detail["documents"][0]["content_hash"] == hashlib.sha256(b"knowledge bytes").hexdigest()
    await engine.dispose()


@pytest.mark.asyncio
async def test_revision_endpoints_enforce_governance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)

    created = await resources.create_resource(
        resources.ResourceCreateRequest(type="knowledge_base", slug="private", display_name="Private", storage_kind="database"),
        current_user,
    )
    kb_id = created["id"]
    async with factory() as session:
        kb = await session.get(Resource, kb_id)
        _seed_ready_document(session, tmp_path, kb, "guide.txt", b"bytes")
        await session.commit()
    revision = await resources.create_knowledge_revision(kb_id, current_user)

    intruder = UserModel(id="intruder", username="intruder@test.com", role=UserRole.USER, department_id="dept-b", disabled=False)

    with pytest.raises(HTTPException) as hidden:
        await resources.list_knowledge_revisions(kb_id, intruder)
    assert hidden.value.status_code == 404

    with pytest.raises(HTTPException) as forbidden:
        await resources.create_knowledge_revision(kb_id, intruder)
    assert forbidden.value.status_code in {403, 404}

    with pytest.raises(HTTPException) as scoped:
        await resources.get_knowledge_revision(str(uuid.uuid4()), str(revision["id"]), current_user)
    assert scoped.value.status_code == 404
    await engine.dispose()


@pytest.mark.asyncio
async def test_publish_endpoint_transitions_and_schedules_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import BackgroundTasks

    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    calls: list[tuple] = []

    async def _audit(actor_id, action, resource_type=None, resource_id=None, detail=None, ip_address=None) -> None:
        calls.append((actor_id, action, resource_id))

    monkeypatch.setattr(resources, "record_audit", _audit)
    monkeypatch.setattr(resources, "configured_ragflow_provider", lambda: object())

    created = await resources.create_resource(
        resources.ResourceCreateRequest(type="knowledge_base", slug="publish", display_name="Publish", storage_kind="database"),
        current_user,
    )
    kb_id = created["id"]
    async with factory() as session:
        kb = await session.get(Resource, kb_id)
        _seed_ready_document(session, tmp_path, kb, "guide.txt", b"bytes")
        await session.commit()
    revision = await resources.create_knowledge_revision(kb_id, current_user)

    background = BackgroundTasks()
    payload = await resources.publish_knowledge_revision(kb_id, str(revision["id"]), background, current_user)
    assert payload["status"] == "indexing"
    assert len(background.tasks) == 1
    assert calls[-1][1] == "knowledge_revision_publish_requested"

    with pytest.raises(HTTPException) as duplicate:
        await resources.publish_knowledge_revision(kb_id, str(revision["id"]), BackgroundTasks(), current_user)
    assert duplicate.value.status_code == 409
    await engine.dispose()


@pytest.mark.asyncio
async def test_prepare_endpoint_is_separate_from_publish_and_does_not_require_eval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import BackgroundTasks

    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    monkeypatch.setenv("IDEER_KNOWLEDGE_EVAL_REQUIRED", "1")
    monkeypatch.setattr(resources, "configured_ragflow_provider", lambda: object())

    created = await resources.create_resource(
        resources.ResourceCreateRequest(type="knowledge_base", slug="prepare", display_name="Prepare", storage_kind="database"),
        current_user,
    )
    kb_id = created["id"]
    async with factory() as session:
        kb = await session.get(Resource, kb_id)
        _seed_ready_document(session, tmp_path, kb, "guide.txt", b"bytes")
        await session.commit()
    revision = await resources.create_knowledge_revision(kb_id, current_user)

    background = BackgroundTasks()
    payload = await resources.prepare_knowledge_revision(kb_id, str(revision["id"]), background, current_user)

    assert payload["status"] == "indexing"
    assert len(background.tasks) == 1
    assert payload["resource_id"] == kb_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_publish_endpoint_reports_unavailable_without_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No configured knowledge provider is a 503, not a client conflict."""
    engine, factory, current_user = await _make_env(tmp_path, monkeypatch)
    monkeypatch.setattr(resources, "configured_ragflow_provider", lambda: None)

    created = await resources.create_resource(
        resources.ResourceCreateRequest(type="knowledge_base", slug="noprov", display_name="NoProv", storage_kind="database"),
        current_user,
    )
    kb_id = created["id"]
    async with factory() as session:
        kb = await session.get(Resource, kb_id)
        _seed_ready_document(session, tmp_path, kb, "guide.txt", b"bytes")
        await session.commit()
    revision = await resources.create_knowledge_revision(kb_id, current_user)

    from fastapi import BackgroundTasks

    with pytest.raises(HTTPException) as unavailable:
        await resources.publish_knowledge_revision(kb_id, str(revision["id"]), BackgroundTasks(), current_user)
    assert unavailable.value.status_code == 503
    await engine.dispose()
