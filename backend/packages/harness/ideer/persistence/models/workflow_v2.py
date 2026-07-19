"""Durable workflow v2 definitions, execution state, and event log."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ideer.persistence.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class WorkflowDefinitionVersionRow(Base):
    __tablename__ = "workflow_definition_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    __table_args__ = (UniqueConstraint("workflow_name", "version", name="uq_workflow_definition_version"),)


class WorkflowV2RunRow(Base):
    __tablename__ = "workflow_v2_runs"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_name: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_thread_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
    __table_args__ = (Index("ix_workflow_v2_runs_name", "workflow_name"),)


class WorkflowTaskRow(Base):
    __tablename__ = "workflow_tasks"
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_v2_runs.run_id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    # A resume request is task intent, not inferred from the mutable run status.
    resume_command_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class WorkflowLeaseAuditRow(Base):
    """Append-only ownership history for durable workflow task leases."""

    __tablename__ = "workflow_lease_audit"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_v2_runs.run_id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("workflow_tasks.task_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    __table_args__ = (Index("ix_workflow_lease_audit_run", "run_id", "created_at"),)


class WorkflowV2EventRow(Base):
    __tablename__ = "workflow_v2_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_v2_runs.run_id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_workflow_v2_event_seq"), Index("ix_workflow_v2_events_run_seq", "run_id", "seq"))


class WorkflowCommandRow(Base):
    __tablename__ = "workflow_commands"
    command_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_v2_runs.run_id"), nullable=False)
    command_type: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
