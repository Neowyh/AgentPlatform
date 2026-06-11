"""add loop_vars column to workflow_runs

Revision ID: a1b2c3d4e5f6
Revises: f3a2b1c4d5e6
Create Date: 2026-06-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f3a2b1c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add loop_vars JSON column to workflow_runs for loop variable persistence."""
    with op.batch_alter_table("workflow_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("loop_vars", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    """Remove loop_vars column from workflow_runs."""
    with op.batch_alter_table("workflow_runs", schema=None) as batch_op:
        batch_op.drop_column("loop_vars")
