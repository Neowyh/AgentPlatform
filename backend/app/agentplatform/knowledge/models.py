"""Persistence models for the knowledge domain (M2 ticket 02).

The KnowledgeBase is a 1:1 extension of a canonical ``resources`` row: the
enterprise identity is the Resource UUID (dual source-of-truth ADR), and the
provider binding is an opaque external mapping that never becomes the
enterprise ID nor enters exportable Resource Content.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
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
    initialization_status: Mapped[str] = mapped_column(String(16), nullable=False, default="initializing")
    initialization_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    initialization_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    initialization_step: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    initialization_next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initialization_lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    initialization_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    provider_document_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ingestion_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_step: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        CheckConstraint("source = 'upload'", name="ck_knowledge_documents_source"),
        CheckConstraint("size_bytes >= 0", name="ck_knowledge_documents_size"),
        Index("ix_knowledge_documents_resource_created", "resource_id", "created_at"),
    )


class KnowledgeRevision(Base):
    """Immutable manifest of KnowledgeBase content at candidate creation (M4).

    A revision freezes the logical documents and content versions that are
    ready at creation time; the manifest hash is computed deterministically so
    identical content yields an identical hash. Published revisions and their
    provider datasets never change afterwards.
    """

    __tablename__ = "knowledge_base_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_bases.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    provider_doc_map_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_revision_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publish_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    publish_lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publish_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_execution_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    integrity_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    integrity_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "revision_no", name="uq_knowledge_base_revisions_no"),
        CheckConstraint(
            "status in ('draft','indexing','ready','published','failed','superseded','archived')",
            name="ck_knowledge_base_revisions_status",
        ),
        CheckConstraint("document_count >= 0", name="ck_knowledge_base_revisions_document_count"),
        Index(
            "uq_knowledge_base_revisions_active_publish",
            "knowledge_base_id",
            unique=True,
            sqlite_where=text("status = 'indexing'"),
            postgresql_where=text("status = 'indexing'"),
        ),
    )


class KnowledgeRevisionCheck(Base):
    """One read-only reconciliation observation recorded by a run (M4).

    KB-bound rows carry per-revision findings; run-scoped rows (nullable
    ``knowledge_base_id``) carry workspace-level findings such as orphan
    provider datasets. Findings are immutable history: reconciliation never
    rewrites manifests, never deletes provider resources, and never replaces
    run snapshots.
    """

    __tablename__ = "knowledge_revision_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_base_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_bases.resource_id", ondelete="CASCADE"),
        nullable=True,
    )
    revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_base_revisions.id", ondelete="CASCADE"),
        nullable=True,
    )
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    findings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    checked_by: Mapped[str | None] = mapped_column(ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("trigger in ('manual','scheduled')", name="ck_knowledge_revision_checks_trigger"),
        Index("ix_knowledge_revision_checks_kb_checked", "knowledge_base_id", "checked_at"),
    )
