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
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.eval_gate import eval_required, load_eval_evidence
from app.agentplatform.knowledge.integrity import INTEGRITY_UNVERIFIED, UNUSABLE_INTEGRITY
from app.agentplatform.knowledge.models import KnowledgeBase, KnowledgeDocument, KnowledgeRevision
from app.agentplatform.knowledge.provider import KnowledgeProvider, KnowledgeProviderError, stable_provider_error
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceAction, ResourceActor, ResourceConflict, ResourceNotFound, ResourceService
from deerflow.config.paths import get_paths

MAX_PUBLISH_ATTEMPTS = 3
PUBLISH_LEASE_SECONDS = 300

# Provider datasets the platform creates follow this prefix; reconciliation
# uses it to recognise platform-created orphan datasets (shared constant so
# a rename cannot silently break orphan detection).
PUBLISHED_DATASET_NAME_PREFIX = "ideer-kb-"

# Revision ids whose background build this process may still be running.
# Guards the in-process duplicate-publish race; a process restart empties
# the set, which is exactly what makes a stuck ``indexing`` revision
# resumable (ticket 02 recoverable-failure discipline).
_ACTIVE_PUBLISHES: set[str] = set()
_PUBLISH_OWNER = uuid.uuid4().hex


def _lease_is_valid(until: datetime | None) -> bool:
    if until is None:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    return until > datetime.now(UTC)


def can_manage_knowledge_revision(resource: Resource, actor: ResourceActor) -> bool:
    return actor.can(ResourceAction.WRITE) and resource.owner_id == actor.user_id and not resource.system_owned


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
        "integrity_status": revision.integrity_status,
        "integrity_checked_at": revision.integrity_checked_at.isoformat() if revision.integrity_checked_at else None,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
        "published_at": revision.published_at.isoformat() if revision.published_at else None,
        "publish_execution_token": revision.publish_execution_token,
    }
    if documents is not None:
        payload["documents"] = documents
    frozen_profiles = next(
        (entry.get("knowledge_profiles") for entry in revision.manifest_json or [] if isinstance(entry, dict) and isinstance(entry.get("knowledge_profiles"), dict)),
        None,
    )
    if frozen_profiles is not None:
        payload["knowledge_profiles"] = frozen_profiles
    return payload


def _copy_atomic(source: Path, destination: Path) -> None:
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
        knowledge_base = await self.session.get(KnowledgeBase, resource_id)
        profiles = {
            "retrieval": dict(knowledge_base.retrieval_profile_json or {}) if knowledge_base else {},
            "embedding": dict(knowledge_base.embedding_profile_json or {}) if knowledge_base else {},
            "ingestion": dict(knowledge_base.ingestion_profile_json or {}) if knowledge_base else {},
        }
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
        entries[0]["knowledge_profiles"] = profiles
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
        resource = await self._knowledge_base(resource_id)
        rows = await self.session.execute(select(KnowledgeRevision).where(KnowledgeRevision.knowledge_base_id == resource_id).order_by(KnowledgeRevision.revision_no))
        revisions = list(rows.scalars())
        can_modify = can_manage_knowledge_revision(resource, self.resource_service.actor)
        if not can_modify:
            revisions = [revision for revision in revisions if revision.status in {"published", "superseded"}]
        return [_revision_payload(revision) for revision in revisions]

    async def get_revision(self, resource_id: str, revision_id: str) -> dict[str, object]:
        resource = await self._knowledge_base(resource_id)
        revision = await self.session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        if revision.status not in {"published", "superseded"} and not can_manage_knowledge_revision(resource, self.resource_service.actor):
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        if revision.status not in {"published", "superseded"}:
            self.resource_service.assert_modify(resource)
        return _revision_payload(revision, documents=list(revision.manifest_json or []))

    async def _owned_revision(self, resource_id: str, revision_id: str) -> KnowledgeRevision:
        revision = await self.session.get(KnowledgeRevision, revision_id)
        if revision is None or revision.knowledge_base_id != resource_id:
            raise ResourceNotFound(f"Knowledge revision {revision_id} not found")
        return revision

    def _verify_frozen_content(self, revision: KnowledgeRevision) -> None:
        """Integrity gate: every frozen file must exist and its bytes must
        hash to the manifest's per-document content hash, and the manifest
        entries must still hash to the revision manifest hash."""

        base_dir = get_paths().base_dir
        for entry in revision.manifest_json or []:
            key = revision_document_key(revision.id, str(entry["document_id"]), str(entry["filename"]))
            frozen = base_dir / key
            if not frozen.is_file():
                raise ResourceConflict(f"Frozen revision content is missing or corrupted: {entry['filename']}")
            digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
            if digest != str(entry.get("content_hash")):
                raise ResourceConflict(f"Frozen revision content is corrupted: {entry['filename']}")
        if canonical_manifest_hash(list(revision.manifest_json or [])) != revision.manifest_hash:
            raise ResourceConflict("Frozen revision content no longer matches the manifest hash")

    async def publish_revision(
        self,
        resource_id: str,
        revision_id: str,
        *,
        provider: KnowledgeProvider,
    ) -> dict[str, object]:
        """Gate and transition a candidate into the ``indexing`` build state.

        Pointer switching happens in :func:`execute_publish` only after the
        provider dataset is built and verified; this phase never touches it.
        A revision already in ``indexing`` is a 409 while this process is
        still building it; after a process restart (build executor gone) the
        same call resumes the build instead, without consuming an attempt.
        """

        await self._knowledge_base(resource_id, modify=True)
        revision = await self._owned_revision(resource_id, revision_id)
        if revision.integrity_status in UNUSABLE_INTEGRITY:
            raise ResourceConflict(f"Revision {revision_id} failed reconciliation and is not publishable")
        if revision.status == "indexing":
            if revision_id in _ACTIVE_PUBLISHES:
                raise ResourceConflict("This revision is already publishing")
            if _lease_is_valid(revision.publish_lease_until) and revision.publish_lease_owner != _PUBLISH_OWNER:
                raise ResourceConflict("This revision is already publishing")
            # Executor lost (process restart): the build state on disk and at
            # the provider is durable, so re-verify integrity and resume.
            self._verify_frozen_content(revision)
            if not (_lease_is_valid(revision.publish_lease_until) and revision.publish_lease_owner == _PUBLISH_OWNER):
                revision.publish_lease_owner = _PUBLISH_OWNER
                revision.publish_execution_token = uuid.uuid4().hex
                revision.publish_lease_until = datetime.now(UTC) + timedelta(seconds=PUBLISH_LEASE_SECONDS)
                await self.session.flush()
            _ACTIVE_PUBLISHES.add(revision_id)
            return _revision_payload(revision)
        if revision.status == "ready":
            self._verify_frozen_content(revision)
            if eval_required() and load_eval_evidence(resource_id, revision.manifest_hash) is None:
                raise ResourceConflict("Publishing requires evaluation evidence matching this revision")
            revision.status = "indexing"
            revision.failure_code = None
            revision.failure_message = None
            revision.publish_lease_owner = _PUBLISH_OWNER
            revision.publish_execution_token = uuid.uuid4().hex
            revision.publish_lease_until = datetime.now(UTC) + timedelta(seconds=PUBLISH_LEASE_SECONDS)
            await self.session.flush()
            _ACTIVE_PUBLISHES.add(revision_id)
            return _revision_payload(revision)
        if revision.status != "draft" and revision.status != "failed":
            raise ResourceConflict(f"Revision {revision_id} is not publishable (status={revision.status})")
        if revision.publish_attempt >= MAX_PUBLISH_ATTEMPTS:
            raise ResourceConflict("Publish attempts exhausted for this revision")
        self._verify_frozen_content(revision)
        if eval_required() and load_eval_evidence(resource_id, revision.manifest_hash) is None:
            raise ResourceConflict("Publishing requires evaluation evidence matching this revision")

        revision.status = "indexing"
        revision.publish_attempt += 1
        revision.failure_code = None
        revision.failure_message = None
        revision.publish_lease_owner = _PUBLISH_OWNER
        revision.publish_execution_token = uuid.uuid4().hex
        revision.publish_lease_until = datetime.now(UTC) + timedelta(seconds=PUBLISH_LEASE_SECONDS)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            # The partial unique index admits at most one ``indexing`` revision
            # per KnowledgeBase, so a concurrent publish loses here.
            await self.session.rollback()
            raise ResourceConflict("Another revision of this KnowledgeBase is already publishing") from exc
        _ACTIVE_PUBLISHES.add(revision_id)
        return _revision_payload(revision)

    async def prepare_revision(
        self,
        resource_id: str,
        revision_id: str,
        *,
        provider: KnowledgeProvider,
    ) -> dict[str, object]:
        """Start building a candidate index without applying the publish gate."""

        await self._knowledge_base(resource_id, modify=True)
        revision = await self._owned_revision(resource_id, revision_id)
        if revision.integrity_status in UNUSABLE_INTEGRITY:
            raise ResourceConflict(f"Revision {revision_id} failed reconciliation and is not preparable")
        if revision.status == "indexing":
            if revision_id in _ACTIVE_PUBLISHES:
                raise ResourceConflict(f"Revision {revision_id} is already preparing")
            if _lease_is_valid(revision.publish_lease_until) and revision.publish_lease_owner != _PUBLISH_OWNER:
                raise ResourceConflict(f"Revision {revision_id} is already preparing")
            self._verify_frozen_content(revision)
            if not (_lease_is_valid(revision.publish_lease_until) and revision.publish_lease_owner == _PUBLISH_OWNER):
                revision.publish_lease_owner = _PUBLISH_OWNER
                revision.publish_execution_token = uuid.uuid4().hex
                revision.publish_lease_until = datetime.now(UTC) + timedelta(seconds=PUBLISH_LEASE_SECONDS)
                await self.session.flush()
            _ACTIVE_PUBLISHES.add(revision_id)
            return _revision_payload(revision)
        if revision.status == "ready":
            return _revision_payload(revision)
        if revision.status not in {"draft", "failed"}:
            raise ResourceConflict(f"Revision {revision_id} is not preparable (status={revision.status})")
        if revision.publish_attempt >= MAX_PUBLISH_ATTEMPTS:
            raise ResourceConflict("Preparation attempts exhausted for this revision")
        self._verify_frozen_content(revision)
        revision.status = "indexing"
        revision.publish_attempt += 1
        revision.failure_code = None
        revision.failure_message = None
        revision.publish_lease_owner = _PUBLISH_OWNER
        revision.publish_execution_token = uuid.uuid4().hex
        revision.publish_lease_until = datetime.now(UTC) + timedelta(seconds=PUBLISH_LEASE_SECONDS)
        await self.session.flush()
        _ACTIVE_PUBLISHES.add(revision_id)
        return _revision_payload(revision)


def _dataset_name(revision: KnowledgeRevision) -> str:
    return f"{PUBLISHED_DATASET_NAME_PREFIX}{revision.knowledge_base_id[:8]}-rev{revision.revision_no}-{revision.id[:8]}"


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
    session_factory: Callable[[], AsyncSession],
    *,
    resource_id: str,
    revision_id: str,
    actor_id: str,
    provider: KnowledgeProvider,
    execution_token: str | None = None,
    poll_interval: float = 2.0,
    parse_timeout: float = 300.0,
    activate: bool = True,
) -> None:
    """Build the immutable provider dataset, verify it, then switch the pointer.

    Clears the in-process active-publish mark on exit so a crash-and-restart
    can resume the revision (see :meth:`KnowledgeRevisionService.publish_revision`).
    """

    try:
        await _run_publish_build(
            session_factory,
            resource_id=resource_id,
            revision_id=revision_id,
            actor_id=actor_id,
            provider=provider,
            execution_token=execution_token,
            poll_interval=poll_interval,
            parse_timeout=parse_timeout,
            activate=activate,
        )
    finally:
        _ACTIVE_PUBLISHES.discard(revision_id)


async def _run_publish_build(
    session_factory: Callable[[], AsyncSession],
    *,
    resource_id: str,
    revision_id: str,
    actor_id: str,
    provider: KnowledgeProvider,
    execution_token: str | None = None,
    poll_interval: float = 2.0,
    parse_timeout: float = 300.0,
    activate: bool = True,
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
        execution_token = execution_token or revision.publish_execution_token
        if not execution_token or execution_token != revision.publish_execution_token:
            return
        entries = list(revision.manifest_json or [])
        base_dir = get_paths().base_dir
        try:

            def renew_lease() -> None:
                if revision.publish_execution_token != execution_token:
                    raise ResourceConflict("Publish execution token is no longer valid")
                revision.publish_lease_until = datetime.now(UTC) + timedelta(seconds=PUBLISH_LEASE_SECONDS)

            dataset_id = revision.provider_dataset_id
            if not dataset_id:
                renew_lease()
                profiles = entries[0].get("knowledge_profiles") if entries else None
                embedding = profiles.get("embedding") if isinstance(profiles, dict) else None
                embedding_model = embedding.get("model") if isinstance(embedding, dict) else None
                if embedding_model is not None and not isinstance(embedding_model, str):
                    embedding_model = str(embedding_model)
                try:
                    dataset_id = await provider.create_dataset(
                        name=_dataset_name(revision),
                        embedding_model=embedding_model,
                    )
                except TypeError:
                    # Keep compatibility with older provider implementations
                    # while passing the frozen model to providers that support
                    # the current contract.
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
                renew_lease()
                result = await provider.ingest(
                    dataset_id=dataset_id,
                    filename=str(entry["filename"]),
                    mime_type=str(entry["mime_type"]),
                    content=content,
                )
                if not result.provider_document_id:
                    raise KnowledgeProviderError("invalid_response")
                document_map[key] = result.provider_document_id
                revision.provider_doc_map_json = dict(document_map)
                renew_lease()
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
            renew_lease()
            listed_ids = {str(item.get("id")) for item in provider_documents if isinstance(item, dict)}
            if listed_ids != set(document_map.values()) or len(provider_documents) != len(document_map):
                raise KnowledgeProviderError("verification_failed")
            provider_by_id = {str(item.get("id")): item for item in provider_documents if isinstance(item, dict)}
            provider_hash_unverified = False
            for entry in entries:
                provider_document = provider_by_id.get(document_map[str(entry["document_id"])])
                if provider_document is None:
                    raise KnowledgeProviderError("verification_failed")
                provider_hash = provider_document.get("content_hash")
                if provider_hash is None or not isinstance(provider_hash, str) or len(provider_hash) != 64 or any(character not in "0123456789abcdefABCDEF" for character in provider_hash):
                    # Some providers expose an opaque internal digest (or no
                    # digest). The document set and frozen bytes have already
                    # been verified locally; retain an explicit UNVERIFIED
                    # status instead of rejecting an otherwise valid publish.
                    provider_hash_unverified = True
                elif provider_hash.lower() != str(entry.get("content_hash", "")).lower():
                    raise KnowledgeProviderError("verification_failed")
            if canonical_manifest_hash(entries) != revision.manifest_hash:
                raise KnowledgeProviderError("verification_failed")

            renew_lease()

            if not activate:
                revision.status = "ready"
                revision.failure_code = None
                revision.failure_message = None
                revision.integrity_status = INTEGRITY_UNVERIFIED if provider_hash_unverified else None
                revision.publish_lease_owner = None
                revision.publish_lease_until = None
                revision.publish_execution_token = None
                await session.commit()
                await record_audit(
                    actor_id,
                    "knowledge_revision_prepared",
                    "knowledge_revision",
                    revision_id,
                    {"resource_id": resource_id, "revision_no": revision.revision_no, "document_count": revision.document_count},
                )
                return

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
            revision.integrity_status = INTEGRITY_UNVERIFIED if provider_hash_unverified else None
            revision.publish_lease_owner = None
            revision.publish_lease_until = None
            revision.publish_execution_token = None
            kb_row = await session.get(KnowledgeBase, resource_id)
            if kb_row is not None:
                kb_row.active_revision_id = revision.id
            await session.commit()
        except Exception as exc:  # provider/storage boundary: keep a recoverable record
            revision.status = "failed"
            revision.failure_code, revision.failure_message = stable_provider_error(exc)
            revision.publish_lease_owner = None
            revision.publish_lease_until = None
            revision.publish_execution_token = None
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
