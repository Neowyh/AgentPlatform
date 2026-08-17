"""Canonical catalog models for Skill, Agent, and Workflow resources."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ideer.persistence.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class ResourceType(StrEnum):
    SKILL = "skill"
    AGENT = "agent"
    WORKFLOW = "workflow"


class ResourceLifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"


class ResourceStorageKind(StrEnum):
    FILESYSTEM = "filesystem"
    DATABASE = "database"
    BUNDLED = "bundled"


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    scope_department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(16), nullable=False, default=ResourceLifecycleStatus.ACTIVE)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    system_owned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authz_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("type", "owner_id", "slug", name="uq_resources_type_owner_slug"),
        CheckConstraint("type IN ('skill', 'agent', 'workflow')", name="ck_resources_type"),
        CheckConstraint("visibility IN ('private', 'department', 'public')", name="ck_resources_visibility"),
        CheckConstraint("lifecycle_status IN ('active', 'archived', 'suspended')", name="ck_resources_lifecycle"),
        CheckConstraint("storage_kind IN ('filesystem', 'database', 'bundled')", name="ck_resources_storage_kind"),
        CheckConstraint("latest_version >= 0", name="ck_resources_latest_version"),
        CheckConstraint("draft_revision >= 0", name="ck_resources_draft_revision"),
        CheckConstraint("authz_revision >= 1", name="ck_resources_authz_revision"),
        Index("ix_resources_owner", "owner_id"),
        Index("ix_resources_visibility_scope", "visibility", "scope_department_id"),
        Index("ix_resources_type_lifecycle", "type", "lifecycle_status"),
    )


class ResourceVersion(Base):
    __tablename__ = "resource_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    scan_result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    source_resource_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id", ondelete="SET NULL"), nullable=True)
    source_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("resource_id", "version", name="uq_resource_versions_resource_version"),
        CheckConstraint("version >= 1", name="ck_resource_versions_version"),
        CheckConstraint("source_version IS NULL OR source_version >= 1", name="ck_resource_versions_source_version"),
        Index("ix_resource_versions_hash", "content_hash"),
    )


class ResourceDependency(Base):
    __tablename__ = "resource_dependencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    target_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("source_resource_id", "target_resource_id", name="uq_resource_dependencies_edge"),
        CheckConstraint("source_resource_id <> target_resource_id", name="ck_resource_dependencies_not_self"),
        Index("ix_resource_dependencies_target", "target_resource_id"),
    )


class RunResourceSnapshot(Base):
    __tablename__ = "run_resource_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    root_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="RESTRICT"), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    authz_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("run_id", "resource_id", name="uq_run_resource_snapshots_run_resource"),
        CheckConstraint("version >= 1", name="ck_run_resource_snapshots_version"),
        CheckConstraint("authz_revision >= 1", name="ck_run_resource_snapshots_authz_revision"),
        Index("ix_run_resource_snapshots_resource", "resource_id", "run_id"),
    )


class ResourceFavorite(Base):
    __tablename__ = "resource_favorites"

    user_id: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="CASCADE"), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class ResourceNotification(Base):
    __tablename__ = "resource_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    recipient_id: Mapped[str] = mapped_column(
        ForeignKey("users_ext.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
    )

    __table_args__ = (
        Index(
            "ix_resource_notifications_recipient_created",
            "recipient_id",
            "created_at",
        ),
    )


class ResourceDraft(Base):
    __tablename__ = "resource_drafts"

    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    modified_by: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (CheckConstraint("revision >= 1", name="ck_resource_drafts_revision"),)
