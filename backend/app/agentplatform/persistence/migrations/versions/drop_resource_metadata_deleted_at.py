"""drop deleted_at column and related indexes from resource_metadata

Revision ID: drop_deleted_at
Revises: add_owner_id_unique
Create Date: 2026-07-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "drop_deleted_at"
down_revision: str | None = "add_owner_id_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop deleted_at column and its indexes from resource_metadata."""
    with op.batch_alter_table("resource_metadata") as batch_op:
        conn = op.get_bind()
        existing = {row.name for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='resource_metadata'").fetchall()}
        for idx in ("ix_resource_metadata_deleted", "ix_resource_meta_type_visibility", "ix_resource_meta_owner_active", "ix_resource_meta_dept_active"):
            if idx in existing:
                batch_op.drop_index(idx)
        batch_op.drop_column("deleted_at")


def downgrade() -> None:
    """Restore deleted_at column."""
    with op.batch_alter_table("resource_metadata") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
