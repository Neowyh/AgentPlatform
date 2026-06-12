"""fix role column server_default and NULL values

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fix role column: set NULL values to 'user' and add server_default.

    This migration addresses the security issue where NULL role values
    would bypass RBAC checks (fail-open). All NULL roles are set to 'user'
    and the column is made NOT NULL with a server_default.
    """
    # Step 1: Set all NULL role values to 'user'
    op.execute("UPDATE users_ext SET role = 'user' WHERE role IS NULL")

    # Step 2: Add server_default and NOT NULL constraint
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table("users_ext", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default=sa.text("'user'"),
        )


def downgrade() -> None:
    """Revert role column changes."""
    with op.batch_alter_table("users_ext", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=32),
            nullable=True,
            server_default=None,
        )
