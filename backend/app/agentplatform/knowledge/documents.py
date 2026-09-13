"""Authorization, validation, and durable storage for KnowledgeBase uploads."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import uuid
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentplatform.knowledge.models import KnowledgeDocument
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


def _document_payload(document: KnowledgeDocument) -> dict[str, object]:
    return {
        "id": document.id,
        "resource_id": document.resource_id,
        "name": document.original_filename,
        "size": document.size_bytes,
        "mime_type": document.mime_type,
        "content_hash": document.content_hash,
        "source": document.source,
        "status": document.status,
        "metadata": document.metadata_json,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


class KnowledgeDocumentService:
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

    async def list_documents(self, resource_id: str) -> list[dict[str, object]]:
        await self._knowledge_base(resource_id)
        rows = await self.session.execute(select(KnowledgeDocument).where(KnowledgeDocument.resource_id == resource_id).order_by(KnowledgeDocument.created_at, KnowledgeDocument.id))
        return [_document_payload(item) for item in rows.scalars()]

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
