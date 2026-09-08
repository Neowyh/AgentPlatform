"""add disabled column and indexes to users_ext

Revision ID: f3a2b1c4d5e6
Revises: d7e0060b1ebc
Create Date: 2026-06-05 10:00:00.000000

PATCH (2026-09-08, unified migration chain replay safety): the
``batch_op.add_column`` / ``create_index`` calls are guarded with
inspector checks. A bare ``batch_op.add_column`` on SQLite forces the
batch-recreate path, where alembic assumes the new column is appended
after the current last column; replaying the revision against a table
that already has the column (created by ``Base.metadata.create_all`` at
its post-revision position) builds a contradictory column-order
dependency and dies with ``CircularDependencyError``. The guards make
replay a no-op and change nothing for databases that recorded this
revision when it originally shipped (the column and indexes exist there,
so every branch is skipped). See the unified-chain PATCH notes in
``0001_baseline`` / ``c4d5e6f7a8b9`` and PATCH-014 in the ledger.
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
    insp = sa.inspect(op.get_bind())
    existing_columns = {c["name"] for c in insp.get_columns("users_ext")}
    existing_indexes = {i["name"] for i in insp.get_indexes("users_ext")}

    with op.batch_alter_table("users_ext", schema=None) as batch_op:
        # sa.false() renders 0 on SQLite and false on PostgreSQL; a literal
        # "0" is rejected by PostgreSQL for a boolean column.
        if "disabled" not in existing_columns:
            batch_op.add_column(sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "ix_users_ext_role" not in existing_indexes:
            batch_op.create_index("ix_users_ext_role", ["role"], unique=False)
        if "ix_users_ext_department_id" not in existing_indexes:
            batch_op.create_index("ix_users_ext_department_id", ["department_id"], unique=False)


def downgrade() -> None:
    """Remove disabled column and indexes from users_ext."""
    with op.batch_alter_table("users_ext", schema=None) as batch_op:
        batch_op.drop_index("ix_users_ext_department_id")
        batch_op.drop_index("ix_users_ext_role")
        batch_op.drop_column("disabled")
