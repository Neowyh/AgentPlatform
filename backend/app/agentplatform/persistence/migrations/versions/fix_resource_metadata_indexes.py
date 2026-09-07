"""fix resource_metadata indexes: replace low-selectivity visibility index with composite partial indexes

Revision ID: fix_idx_001
Revises: add_is_favorited
Create Date: 2026-07-06 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_idx_001"
down_revision: str | None = "add_is_favorited"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop low-selectivity index and add 3 composite partial indexes."""
    with op.batch_alter_table("resource_metadata", schema=None) as batch_op:
        batch_op.drop_index("ix_resource_metadata_visibility")
        batch_op.drop_index("ix_resource_metadata_type")
        batch_op.create_index("ix_resource_meta_type_visibility", ["resource_type", "visibility", "deleted_at"], unique=False)
        batch_op.create_index("ix_resource_meta_owner_active", ["owner_id", "deleted_at"], unique=False)
        batch_op.create_index("ix_resource_meta_dept_active", ["department_id", "deleted_at"], unique=False)


def downgrade() -> None:
    """Drop composite indexes and restore the original visibility index."""
    with op.batch_alter_table("resource_metadata", schema=None) as batch_op:
        batch_op.drop_index("ix_resource_meta_type_visibility")
        batch_op.drop_index("ix_resource_meta_owner_active")
        batch_op.drop_index("ix_resource_meta_dept_active")
        batch_op.create_index("ix_resource_metadata_visibility", ["visibility"], unique=False)
        batch_op.create_index("ix_resource_metadata_type", ["resource_type"], unique=False)
