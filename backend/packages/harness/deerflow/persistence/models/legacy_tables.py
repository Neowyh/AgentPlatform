"""Tables retained by migrations without an active ORM entity.

These definitions keep the fresh ``Base.metadata.create_all`` path aligned
with the unified Alembic chain.  Runtime code that needs these historical
records continues to use its dedicated SQL/query layer.
"""

from __future__ import annotations

import sqlalchemy as sa

from deerflow.persistence.base import Base

workflow_runs = sa.Table(
    "workflow_runs",
    Base.metadata,
    sa.Column("run_id", sa.String(64), primary_key=True),
    sa.Column("workflow_name", sa.String(128), nullable=False),
    sa.Column("workflow_yaml", sa.Text, nullable=False),
    sa.Column("status", sa.String(20), nullable=False),
    sa.Column("inputs", sa.JSON, nullable=False),
    sa.Column("steps_state", sa.JSON, nullable=False),
    sa.Column("current_step", sa.String(128), nullable=True),
    sa.Column("error", sa.Text, nullable=True),
    sa.Column("review_result", sa.JSON, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("loop_vars", sa.JSON, nullable=False, server_default=sa.text("'{}'")),
    sa.Index("ix_workflow_runs_name", "workflow_name"),
)

skill_applications = sa.Table(
    "skill_applications",
    Base.metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("skill_id", sa.String(128), nullable=False),
    sa.Column("skill_name", sa.String(128), nullable=False),
    sa.Column("applicant_id", sa.String(36), nullable=False),
    sa.Column("request_level", sa.String(32), nullable=False),
    sa.Column("department_id", sa.String(36), nullable=True),
    sa.Column("reason", sa.Text, nullable=True),
    sa.Column("status", sa.String(32), nullable=True),
    sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.Column("reviewed_by", sa.String(36), nullable=True),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("review_comment", sa.Text, nullable=True),
)


__all__ = ["skill_applications", "workflow_runs"]
