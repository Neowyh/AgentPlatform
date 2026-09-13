"""Immutable Knowledge Revision candidates for a KnowledgeBase (M4 ticket 01).

A candidate freezes the logical documents whose ingestion is ``ready`` at
creation time: original files are copied into a revision-scoped store and a
deterministic manifest hash captures the document set and content versions.
Later draft edits or deletions cannot change an existing candidate.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.models import KnowledgeDocument, KnowledgeRevision
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceActor, ResourceNotFound, ResourceService
from deerflow.config.paths import get_paths


class KnowledgeRevisionValidationError(ValueError):
    """Raised when a revision candidate cannot be created from current content."""


def canonical_manifest_hash(entries: list[dict]) -> str:
    """Deterministically hash the manifest entries (order-independent)."""

    ordered = sorted(entries, key=lambda entry: str(entry.get("document_id")))
    payload = json.dumps(ordered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def revision_document_key(revision_id: str, document_id: str, filename: str) -> str:
    return f"knowledge-revisions/{revision_id}/{document_id}-{filename}"


def _manifest_entry(document: KnowledgeDocument) -> dict[str, object]:
    return {
        "document_id": document.id,
        "content_hash": document.content_hash,
        "filename": document.original_filename,
        "size_bytes": document.size_bytes,
        "mime_type": document.mime_type,
        "metadata": document.metadata_json or {},
    }


def _revision_payload(revision: KnowledgeRevision, *, documents: list[dict] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": revision.id,
        "resource_id": revision.knowledge_base_id,
        "revision_no": revision.revision_no,
        "status": revision.status,
        "manifest_hash": revision.manifest_hash,
        "document_count": revision.document_count,
        "failure_code": revision.failure_code,
        "failure_message": revision.failure_message,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
        "published_at": revision.published_at.isoformat() if revision.published_at else None,
    }
    if documents is not None:
        payload["documents"] = documents
    return payload


def _copy_atomic(source, destination) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".copy-{uuid.uuid4().hex}.part"
    try:
        with temporary.open("wb") as target, source.open("rb") as origin:
            while chunk := origin.read(1024 * 1024):
                target.write(chunk)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class KnowledgeRevisionService:
    def __init__(self, session: AsyncSession, actor: ResourceActor) -> None:
        self.session = session
        self.resource_service = ResourceService(session, actor)

    async def _knowledge_base(self, resource_id: str, *, modify: bool = False) -> Resource:
        resource = await self.resource_service.get_visible(resource_id)
        if resource.type != "knowledge_base":
            raise ResourceNotFound(f"KnowledgeBase {resource_id} not found")
        if modify:
            self.resource_service.assert_modify(resource)
        return resource

    async def create_revision(self, resource_id: str) -> dict[str, object]:
        await self._knowledge_base(resource_id, modify=True)
        rows = await self.session.execute(select(KnowledgeDocument).where(KnowledgeDocument.resource_id == resource_id, KnowledgeDocument.status == "ready").order_by(KnowledgeDocument.created_at, KnowledgeDocument.id))
        ready_documents = list(rows.scalars())
        if not ready_documents:
            raise KnowledgeRevisionValidationError("A revision candidate requires at least one ready document")

        base_dir = get_paths().base_dir
        missing = [doc.storage_key for doc in ready_documents if not (base_dir / doc.storage_key).is_file()]
        if missing:
            raise KnowledgeRevisionValidationError("Ready document content is missing and cannot be frozen")

        revision_id = str(uuid.uuid4())
        entries: list[dict[str, object]] = []
        created_paths = []
        try:
            for document in ready_documents:
                key = revision_document_key(revision_id, document.id, document.original_filename)
                destination = base_dir / key
                await asyncio.to_thread(_copy_atomic, base_dir / document.storage_key, destination)
                created_paths.append(destination)
                entries.append(_manifest_entry(document))
        except BaseException:
            for path in created_paths:
                path.unlink(missing_ok=True)
            raise
        entries.sort(key=lambda entry: str(entry["document_id"]))
        highest = await self.session.scalar(select(func.max(KnowledgeRevision.revision_no)).where(KnowledgeRevision.knowledge_base_id == resource_id))
        revision = KnowledgeRevision(
            id=revision_id,
            knowledge_base_id=resource_id,
            revision_no=int(highest or 0) + 1,
            status="draft",
            manifest_hash=canonical_manifest_hash(entries),
            manifest_json=entries,
            provider_doc_map_json={},
            document_count=len(entries),
            created_by=self.resource_service.actor.user_id,
        )
        self.session.add(revision)
        await self.session.flush()
        return _revision_payload(revision)

    async def list_revisions(self, resource_id: str) -> list[dict[str, object]]:
        await self._knowledge_base(resource_id)
        rows = await self.session.execute(select(KnowledgeRevision).where(KnowledgeRevision.knowledge_base_id == resource_id).order_by(KnowledgeRevision.revision_no))
        return [_revision_payload(revision) for revision in rows.scalars()]

    async def get_revision(self, resource_id: str, revision_id: str) -> dict[str, object]:
        await self._knowledge_base(resource_id)
        revision = await self.session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        return _revision_payload(revision, documents=list(revision.manifest_json or []))
