"""ORM model for workflow runs."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ideer.persistence.base import Base


class WorkflowRunRow(Base):
    """Persisted state of a workflow execution."""

    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_name: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    steps_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    current_step: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    loop_vars: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_workflow_runs_name", "workflow_name"),)
