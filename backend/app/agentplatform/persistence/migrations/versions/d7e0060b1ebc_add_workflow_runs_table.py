"""add workflow_runs table

Revision ID: d7e0060b1ebc
Revises: 16147afec43b
Create Date: 2026-06-03 19:46:02.484866

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e0060b1ebc"
down_revision: str | None = "16147afec43b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create workflow_runs table for workflow state persistence."""
    op.create_table(
        "workflow_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_name", sa.String(length=128), nullable=False),
        sa.Column("workflow_yaml", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("steps_state", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.String(length=128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("review_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    with op.batch_alter_table("workflow_runs", schema=None) as batch_op:
        batch_op.create_index("ix_workflow_runs_name", ["workflow_name"], unique=False)


def downgrade() -> None:
    """Drop workflow_runs table."""
    with op.batch_alter_table("workflow_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_workflow_runs_name")
    op.drop_table("workflow_runs")
