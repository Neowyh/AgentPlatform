"""add immutable workflow v2 runtime tables"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_workflow_v2"
down_revision: str | None = "9a8b7c6d5e4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # v1 stays queryable but can never be resumed by the v2 runtime.  The
    # status/error pair makes interrupted work explicit to historical readers.
    op.execute("UPDATE workflow_runs SET status = 'failed', error = 'workflow_runtime_replaced' WHERE run_id NOT LIKE 'def:%' AND status NOT IN ('completed', 'failed', 'cancelled')")
    op.create_table(
        "workflow_definition_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workflow_name", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("department_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_name", "version", name="uq_workflow_definition_version"),
    )
    op.create_index("ix_workflow_definition_versions_name", "workflow_definition_versions", ["workflow_name"])
    op.create_table(
        "workflow_v2_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("workflow_name", sa.String(128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("checkpoint_thread_id", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_tasks",
        sa.Column("task_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("workflow_v2_runs.run_id"), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("resume_command_id", sa.String(64)),
    )
    op.create_table(
        "workflow_v2_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("workflow_v2_runs.run_id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "seq", name="uq_workflow_v2_event_seq"),
    )
    op.create_index("ix_workflow_v2_runs_name", "workflow_v2_runs", ["workflow_name"])
    op.create_index("ix_workflow_v2_events_run_seq", "workflow_v2_events", ["run_id", "seq"])
    op.create_table(
        "workflow_commands",
        sa.Column("command_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("workflow_v2_runs.run_id"), nullable=False),
        sa.Column("command_type", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_v2_events_run_seq", table_name="workflow_v2_events")
    op.drop_index("ix_workflow_v2_runs_name", table_name="workflow_v2_runs")
    op.drop_index("ix_workflow_definition_versions_name", table_name="workflow_definition_versions")
    op.drop_table("workflow_commands")
    op.drop_table("workflow_v2_events")
    op.drop_table("workflow_tasks")
    op.drop_table("workflow_v2_runs")
    op.drop_table("workflow_definition_versions")
