"""Immutable Knowledge Revision candidates and publishing (M4 tickets 01-02).

A candidate freezes the logical documents whose ingestion is ``ready`` at
creation time: original files are copied into a revision-scoped store and a
deterministic manifest hash captures the document set and content versions.
Later draft edits or deletions cannot change an existing candidate.

Publishing builds a dedicated, immutable provider dataset from the frozen
content; the KB pointer moves only after the provider build is verified, so
failures never silently repoint a KnowledgeBase.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.eval_gate import eval_required, load_eval_evidence
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument, KnowledgeRevision
from app.agentplatform.knowledge.provider import KnowledgeProvider, KnowledgeProviderError, stable_provider_error
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceActor, ResourceConflict, ResourceNotFound, ResourceService
from deerflow.config.paths import get_paths

MAX_PUBLISH_ATTEMPTS = 3


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

    async def _owned_revision(self, resource_id: str, revision_id: str) -> KnowledgeRevision:
        revision = await self.session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        return revision

    def _verify_frozen_content(self, revision: KnowledgeRevision) -> None:
        """Integrity gate: frozen files must exist and re-hash to the manifest."""

        base_dir = get_paths().base_dir
        for entry in revision.manifest_json or []:
            key = revision_document_key(revision.id, str(entry["document_id"]), str(entry["filename"]))
            if not (base_dir / key).is_file():
                raise ResourceConflict(f"Frozen revision content is missing or corrupted: {entry['filename']}")
        if canonical_manifest_hash(list(revision.manifest_json or [])) != revision.manifest_hash:
            raise ResourceConflict("Frozen revision content no longer matches the manifest hash")

    async def publish_revision(
        self,
        resource_id: str,
        revision_id: str,
        *,
        provider: KnowledgeProvider | None = None,
    ) -> dict[str, object]:
        """Gate and transition a candidate into the ``indexing`` build state.

        Pointer switching happens in :func:`execute_publish` only after the
        provider dataset is built and verified; this phase never touches it.
        """

        await self._knowledge_base(resource_id, modify=True)
        revision = await self._owned_revision(resource_id, revision_id)
        if revision.status == "indexing":
            raise ResourceConflict("This revision is already publishing")
        if revision.status != "draft" and revision.status != "failed":
            raise ResourceConflict(f"Revision {revision_id} is not publishable (status={revision.status})")
        if revision.publish_attempt >= MAX_PUBLISH_ATTEMPTS:
            raise ResourceConflict("Publish attempts exhausted for this revision")
        self._verify_frozen_content(revision)
        if eval_required() and load_eval_evidence(resource_id, revision.manifest_hash) is None:
            raise ResourceConflict("Publishing requires evaluation evidence matching this revision")
        if provider is None:
            raise ResourceConflict("No knowledge provider is configured for publishing")

        revision.status = "indexing"
        revision.publish_attempt += 1
        revision.failure_code = None
        revision.failure_message = None
        try:
            await self.session.flush()
        except IntegrityError as exc:
            # The partial unique index admits at most one ``indexing`` revision
            # per KnowledgeBase, so a concurrent publish loses here.
            await self.session.rollback()
            raise ResourceConflict("Another revision of this KnowledgeBase is already publishing") from exc
        return _revision_payload(revision)


def _dataset_name(revision: KnowledgeRevision) -> str:
    return f"ideer-kb-{revision.knowledge_base_id[:8]}-rev{revision.revision_no}-{revision.id[:8]}"


async def _await_document_ready(
    provider: KnowledgeProvider,
    *,
    dataset_id: str,
    provider_document_id: str,
    poll_interval: float,
    deadline: float,
) -> None:
    while True:
        status = await provider.get_status(dataset_id=dataset_id, provider_document_id=provider_document_id)
        if status == "ready":
            return
        if status == "failed":
            raise KnowledgeProviderError("index_failed", provider_document_id=provider_document_id)
        if asyncio.get_running_loop().time() >= deadline:
            raise KnowledgeProviderError("index_timeout", provider_document_id=provider_document_id)
        await asyncio.sleep(poll_interval)


async def execute_publish(
    session_factory,
    *,
    resource_id: str,
    revision_id: str,
    actor_id: str,
    provider: KnowledgeProvider,
    poll_interval: float = 2.0,
    parse_timeout: float = 300.0,
) -> None:
    """Build the immutable provider dataset, verify it, then switch the pointer.

    Runs in its own session (background task). Every provider step is
    committed as it completes so a failed build stays resumable: the dataset
    ID and per-document uploads survive, and a retry only ingests what is
    missing. The KB pointer moves in a single final transaction.
    """

    from app.gateway.audit import record_audit

    async with session_factory() as session:
        revision = await session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id or revision.status != "indexing":
            return
        entries = list(revision.manifest_json or [])
        base_dir = get_paths().base_dir
        try:
            dataset_id = revision.provider_dataset_id
            if not dataset_id:
                dataset_id = await provider.create_dataset(name=_dataset_name(revision))
                revision.provider_dataset_id = dataset_id
                revision.provider_revision_hint = f"rev-{revision.revision_no}"
                await session.commit()

            document_map: dict[str, str] = dict(revision.provider_doc_map_json or {})
            for entry in entries:
                key = str(entry["document_id"])
                if key in document_map:
                    continue
                content = await asyncio.to_thread((base_dir / revision_document_key(revision.id, key, str(entry["filename"]))).read_bytes)
                result = await provider.ingest(
                    dataset_id=dataset_id,
                    filename=str(entry["filename"]),
                    mime_type=str(entry["mime_type"]),
                    content=content,
                    provider_document_id=document_map.get(key),
                )
                if not result.provider_document_id:
                    raise KnowledgeProviderError("invalid_response")
                document_map[key] = result.provider_document_id
                revision.provider_doc_map_json = dict(document_map)
                await session.commit()

            started = asyncio.get_running_loop().time()
            for entry in entries:
                key = str(entry["document_id"])
                provider_document_id = document_map[key]
                try:
                    await _await_document_ready(
                        provider,
                        dataset_id=dataset_id,
                        provider_document_id=provider_document_id,
                        poll_interval=poll_interval,
                        deadline=started + parse_timeout,
                    )
                except KnowledgeProviderError as exc:
                    if exc.code != "index_failed":
                        raise
                    # One bounded re-parse for a document the provider failed;
                    # a later publish retry can take over from here either way.
                    content = await asyncio.to_thread((base_dir / revision_document_key(revision.id, key, str(entry["filename"]))).read_bytes)
                    await provider.ingest(
                        dataset_id=dataset_id,
                        filename=str(entry["filename"]),
                        mime_type=str(entry["mime_type"]),
                        content=content,
                        provider_document_id=provider_document_id,
                        rebuild=True,
                    )
                    await _await_document_ready(
                        provider,
                        dataset_id=dataset_id,
                        provider_document_id=provider_document_id,
                        poll_interval=poll_interval,
                        deadline=started + parse_timeout,
                    )

            provider_documents = await provider.list_dataset_documents(dataset_id=dataset_id)
            listed_ids = {str(item.get("id")) for item in provider_documents if isinstance(item, dict)}
            if listed_ids != set(document_map.values()) or len(provider_documents) != len(document_map):
                raise KnowledgeProviderError("verification_failed")
            if canonical_manifest_hash(entries) != revision.manifest_hash:
                raise KnowledgeProviderError("verification_failed")

            prior = (
                (
                    await session.execute(
                        select(KnowledgeRevision).where(
                            KnowledgeRevision.knowledge_base_id == resource_id,
                            KnowledgeRevision.status == "published",
                            KnowledgeRevision.id != revision.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for old in prior:
                old.status = "superseded"
            revision.status = "published"
            revision.published_at = datetime.now(UTC)
            revision.failure_code = None
            revision.failure_message = None
            kb_row = await session.get(KnowledgeBase, resource_id)
            if kb_row is not None:
                kb_row.active_revision_id = revision.id
            await session.commit()
        except Exception as exc:  # provider/storage boundary: keep a recoverable record
            revision.status = "failed"
            revision.failure_code, revision.failure_message = stable_provider_error(exc)
            await session.commit()
            await record_audit(
                actor_id,
                "knowledge_revision_publish_failed",
                "knowledge_revision",
                revision_id,
                {"resource_id": resource_id, "failure_code": revision.failure_code, "attempt": revision.publish_attempt},
            )
            return
        await record_audit(
            actor_id,
            "knowledge_revision_published",
            "knowledge_revision",
            revision_id,
            {"resource_id": resource_id, "revision_no": revision.revision_no, "document_count": revision.document_count},
        )
