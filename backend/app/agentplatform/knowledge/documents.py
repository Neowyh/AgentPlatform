"""Authorization, validation, and durable storage for KnowledgeBase uploads."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
import uuid
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.models import KnowledgeDocument
from app.agentplatform.knowledge.provider import KnowledgeProvider, KnowledgeProviderError, stable_provider_error
from app.agentplatform.resource_models import Resource
from app.agentplatform.resources.service import ResourceActor, ResourceNotFound, ResourceService
from deerflow.config.app_config import get_app_config
from deerflow.config.paths import get_paths
from deerflow.uploads.manager import normalize_filename

SUPPORTED_EXTENSIONS = {".csv", ".doc", ".docx", ".json", ".md", ".pdf", ".ppt", ".pptx", ".txt", ".xls", ".xlsx"}
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024


class DocumentValidationError(ValueError):
    """Raised when a document cannot be safely accepted."""


def _configured_upload_limit(name: str, fallback: int) -> int:
    uploads = getattr(get_app_config(), "uploads", None)
    raw = uploads.get(name) if isinstance(uploads, dict) else getattr(uploads, name, None)
    try:
        value = int(raw) if raw is not None else DEFAULT_MAX_FILE_SIZE
        return value if value > 0 else DEFAULT_MAX_FILE_SIZE
    except (TypeError, ValueError):
        return fallback


def _max_document_size() -> int:
    return min(
        _configured_upload_limit("max_file_size", DEFAULT_MAX_FILE_SIZE),
        _configured_upload_limit("max_total_size", DEFAULT_MAX_FILE_SIZE),
    )


def _safe_document_filename(filename: str | None) -> str:
    if not filename or "\x00" in filename or "/" in filename or "\\" in filename:
        raise DocumentValidationError("Filename must be a plain file name")
    safe = normalize_filename(filename)
    if Path(safe).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise DocumentValidationError("Unsupported document type")
    return safe


def _document_payload(document: KnowledgeDocument, *, can_modify: bool | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": document.id,
        "resource_id": document.resource_id,
        "name": document.original_filename,
        "size": document.size_bytes,
        "mime_type": document.mime_type,
        "content_hash": document.content_hash,
        "source": document.source,
        "status": document.status,
        "failure_code": document.failure_code,
        "failure_message": document.failure_message,
        "ingestion_attempt": document.ingestion_attempt,
        "metadata": document.metadata_json,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }
    if can_modify is not None:
        payload["can_modify"] = can_modify
    return payload


class KnowledgeDocumentService:
    def __init__(self, session: AsyncSession, actor: ResourceActor, provider: KnowledgeProvider | None = None) -> None:
        self.session = session
        self.resource_service = ResourceService(session, actor)
        self.provider = provider

    async def _knowledge_base(self, resource_id: str, *, modify: bool = False) -> Resource:
        resource = await self.resource_service.get_visible(resource_id)
        if resource.type != "knowledge_base":
            raise ResourceNotFound(f"KnowledgeBase {resource_id} not found")
        if modify:
            self.resource_service.assert_modify(resource)
        return resource

    async def list_documents(self, resource_id: str) -> list[dict[str, object]]:
        resource = await self._knowledge_base(resource_id)
        rows = await self.session.execute(select(KnowledgeDocument).where(KnowledgeDocument.resource_id == resource_id).order_by(KnowledgeDocument.created_at, KnowledgeDocument.id))
        documents = list(rows.scalars())
        for document in documents:
            await self._refresh(document)
        can_modify = resource.owner_id == self.resource_service.actor.user_id
        return [_document_payload(item, can_modify=can_modify) for item in documents]

    async def upload(self, resource_id: str, upload) -> dict[str, object]:
        await self._knowledge_base(resource_id, modify=True)
        filename = _safe_document_filename(upload.filename)
        max_file_size = _max_document_size()
        content_type = (upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream").lower()
        document_id = str(uuid.uuid4())
        root = (get_paths().base_dir / "knowledge-documents" / resource_id).resolve()
        root.mkdir(parents=True, exist_ok=True)
        temporary = root / f".upload-{document_id}.part"
        destination = root / f"{document_id}-{filename}"
        digest = hashlib.sha256()
        size = 0
        cleanup_registered = False

        def remove_cleanup_listeners() -> None:
            nonlocal cleanup_registered
            if cleanup_registered:
                event.remove(self.session.sync_session, "after_rollback", cleanup_after_rollback)
                event.remove(self.session.sync_session, "after_commit", cleanup_after_commit)
                cleanup_registered = False

        def cleanup_after_rollback(_session) -> None:
            nonlocal cleanup_registered
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            event.remove(self.session.sync_session, "after_commit", cleanup_after_commit)
            cleanup_registered = False

        def cleanup_after_commit(_session) -> None:
            nonlocal cleanup_registered
            event.remove(self.session.sync_session, "after_rollback", cleanup_after_rollback)
            cleanup_registered = False

        try:
            with temporary.open("xb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_file_size:
                        raise DocumentValidationError("Document exceeds the maximum file size")
                    digest.update(chunk)
                    target.write(chunk)
            content_hash = digest.hexdigest()
            duplicate = await self.session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.resource_id == resource_id,
                    KnowledgeDocument.content_hash == content_hash,
                )
            )
            if duplicate is not None:
                raise DocumentValidationError("Document already exists in this KnowledgeBase")
            os.replace(temporary, destination)
            event.listen(self.session.sync_session, "after_rollback", cleanup_after_rollback, once=True)
            event.listen(self.session.sync_session, "after_commit", cleanup_after_commit, once=True)
            cleanup_registered = True
            document = KnowledgeDocument(
                id=document_id,
                resource_id=resource_id,
                original_filename=filename,
                size_bytes=size,
                mime_type=content_type,
                content_hash=content_hash,
                storage_key=destination.relative_to(get_paths().base_dir).as_posix(),
                metadata_json={},
                created_by=self.resource_service.actor.user_id,
            )
            self.session.add(document)
            await self.session.flush()
            return _document_payload(document)
        except BaseException:
            remove_cleanup_listeners()
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    async def process(self, document_id: str, *, resource_id: str | None = None, rebuild: bool = False) -> dict[str, object]:
        document = await self._document(document_id, resource_id=resource_id, modify=True)
        if document.status in {"processing", "ready"} and not rebuild:
            return _document_payload(document)
        document.status = "processing"
        document.failure_code = None
        document.failure_message = None
        document.ingestion_attempt += 1
        await self.session.flush()
        try:
            provider = self.provider
            binding = await self.resource_service.get_knowledge_binding(document.resource_id)
            if provider is None or not binding.provider_dataset_id:
                raise KnowledgeProviderError("unavailable", "No provider binding is configured")
            content = await asyncio.to_thread((get_paths().base_dir / document.storage_key).read_bytes)
            result = await provider.ingest(
                dataset_id=binding.provider_dataset_id,
                filename=document.original_filename,
                mime_type=document.mime_type,
                content=content,
                provider_document_id=document.provider_document_id,
                rebuild=rebuild,
            )
            document.provider_document_id = result.provider_document_id or document.provider_document_id
            document.status = result.status if result.status in {"processing", "ready"} else "ready"
        except Exception as exc:  # provider boundary: persist a recoverable state
            provider_document_id = getattr(exc, "provider_document_id", None)
            if isinstance(provider_document_id, str) and provider_document_id:
                document.provider_document_id = provider_document_id
            document.status = "failed"
            document.failure_code, document.failure_message = stable_provider_error(exc)
        await self.session.flush()
        return _document_payload(document)

    async def retry(self, document_id: str, *, resource_id: str | None = None) -> dict[str, object]:
        return await self.process(document_id, resource_id=resource_id)

    async def _refresh(self, document: KnowledgeDocument) -> None:
        if self.provider is None or document.status != "processing" or not document.provider_document_id:
            return
        try:
            binding = await self.resource_service.get_knowledge_binding(document.resource_id)
            if not binding.provider_dataset_id:
                return
            status = await self.provider.get_status(
                dataset_id=binding.provider_dataset_id,
                provider_document_id=document.provider_document_id,
            )
            if status in {"processing", "ready", "failed"}:
                document.status = status
                if status == "failed":
                    document.failure_code = "index_failed"
                    document.failure_message = "The provider could not index this document."
                else:
                    document.failure_code = None
                    document.failure_message = None
        except Exception as exc:  # provider boundary: retain a retryable state
            document.failure_code, document.failure_message = stable_provider_error(exc)
            document.status = "failed"
        await self.session.flush()

    async def rebuild_index(self, document_id: str, *, resource_id: str | None = None) -> dict[str, object]:
        return await self.process(document_id, resource_id=resource_id, rebuild=True)

    async def delete(self, document_id: str, *, resource_id: str | None = None) -> dict[str, object]:
        document = await self._document(document_id, resource_id=resource_id, modify=True)
        if document.status == "deleted":
            return _document_payload(document)

        document.status = "deleting"
        document.failure_code = None
        document.failure_message = None
        await self.session.flush()
        try:
            binding = await self.resource_service.get_knowledge_binding(document.resource_id)
            if document.provider_document_id and (self.provider is None or not binding.provider_dataset_id):
                raise KnowledgeProviderError("unavailable")
            if self.provider is not None and document.provider_document_id and binding.provider_dataset_id:
                await self.provider.delete_document(
                    dataset_id=binding.provider_dataset_id,
                    provider_document_id=document.provider_document_id,
                )
            (get_paths().base_dir / document.storage_key).unlink(missing_ok=True)
            document.status = "deleted"
        except Exception as exc:  # provider/storage boundary: retain a recovery record
            document.status = "delete_failed"
            document.failure_code, document.failure_message = stable_provider_error(exc)
        await self.session.flush()
        return _document_payload(document)

    async def _document(self, document_id: str, *, resource_id: str | None, modify: bool) -> KnowledgeDocument:
        document = await self.session.get(KnowledgeDocument, document_id)
        if document is None:
            raise ResourceNotFound(f"Knowledge document {document_id} not found")
        if resource_id is not None and document.resource_id != resource_id:
            raise ResourceNotFound(f"Knowledge document {document_id} not found")
        await self._knowledge_base(document.resource_id, modify=modify)
        return document
