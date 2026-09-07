"""mark selected resources in canonical Run snapshots

Revision ID: 20260828_run_snapshot_selection_role
Revises: 20260825_workflow_run_model
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_run_snapshot_selection_role"
down_revision: str | None = "20260825_workflow_run_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_resource_snapshots") as batch_op:
        batch_op.add_column(sa.Column("selection_role", sa.String(length=16), nullable=False, server_default="resolved"))
        batch_op.create_check_constraint(
            "ck_run_resource_snapshots_selection_role",
            "selection_role IN ('root', 'resolved', 'preferred')",
        )


def downgrade() -> None:
    with op.batch_alter_table("run_resource_snapshots") as batch_op:
        batch_op.drop_constraint("ck_run_resource_snapshots_selection_role", type_="check")
        batch_op.drop_column("selection_role")
