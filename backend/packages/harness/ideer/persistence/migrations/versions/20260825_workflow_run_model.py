"""add selected model to workflow v2 runs

Revision ID: 20260825_workflow_run_model
Revises: 20260817_split_bundled_provenance
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_workflow_run_model"
down_revision: str | None = "20260817_split_bundled_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workflow_v2_runs") as batch_op:
        batch_op.add_column(sa.Column("model_name", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("workflow_v2_runs") as batch_op:
        batch_op.drop_column("model_name")
