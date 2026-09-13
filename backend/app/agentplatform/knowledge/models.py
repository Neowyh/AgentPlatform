"""Persistence models for the knowledge domain (M2 ticket 02).

The KnowledgeBase is a 1:1 extension of a canonical ``resources`` row: the
enterprise identity is the Resource UUID (dual source-of-truth ADR), and the
provider binding is an opaque external mapping that never becomes the
enterprise ID nor enters exportable Resource Content.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from deerflow.persistence.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ragflow")
    provider_dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieval_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ingestion_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    embedding_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        CheckConstraint("provider_type <> ''", name="ck_knowledge_bases_provider_type"),
        UniqueConstraint("provider_type", "provider_dataset_id", name="uq_knowledge_bases_provider_binding"),
        Index("ix_knowledge_bases_provider_dataset", "provider_dataset_id"),
    )


class KnowledgeDocument(Base):
    """A durable logical document and its platform-owned original file."""

    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    provider_document_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    created_by: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("resource_id", "content_hash", name="uq_knowledge_documents_resource_hash"),
        CheckConstraint("source = 'upload'", name="ck_knowledge_documents_source"),
        CheckConstraint("size_bytes >= 0", name="ck_knowledge_documents_size"),
        Index("ix_knowledge_documents_resource_created", "resource_id", "created_at"),
    )
