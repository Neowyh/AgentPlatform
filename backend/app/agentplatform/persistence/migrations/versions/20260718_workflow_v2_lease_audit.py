"""add append-only workflow lease audit history"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_workflow_v2_lease_audit"
down_revision: str | None = "20260718_workflow_v2_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_lease_audit",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("workflow_v2_runs.run_id"), nullable=False),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("workflow_tasks.task_id"), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_lease_audit_run", "workflow_lease_audit", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_lease_audit_run", table_name="workflow_lease_audit")
    op.drop_table("workflow_lease_audit")
