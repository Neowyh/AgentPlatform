"""add disabled column and indexes to users_ext

Revision ID: f3a2b1c4d5e6
Revises: d7e0060b1ebc
Create Date: 2026-06-05 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a2b1c4d5e6"
down_revision: str | None = "d7e0060b1ebc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add disabled column and role/department_id indexes to users_ext."""
    with op.batch_alter_table("users_ext", schema=None) as batch_op:
        batch_op.add_column(sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.create_index("ix_users_ext_role", ["role"], unique=False)
        batch_op.create_index("ix_users_ext_department_id", ["department_id"], unique=False)


def downgrade() -> None:
    """Remove disabled column and indexes from users_ext."""
    with op.batch_alter_table("users_ext", schema=None) as batch_op:
        batch_op.drop_index("ix_users_ext_department_id")
        batch_op.drop_index("ix_users_ext_role")
        batch_op.drop_column("disabled")
