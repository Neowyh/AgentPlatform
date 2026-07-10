"""Add owner_id to resource_metadata unique constraint

Previously: UNIQUE(resource_type, resource_id)
Now:        UNIQUE(resource_type, resource_id, owner_id)

This allows two users to each have agent/skill/workflow metadata
for the same resource name, enabling per-user metadata isolation.

Revision ID: add_owner_id_unique
Revises: f4b3a2c1d0e9
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_owner_id_unique"
down_revision: str | None = "f4b3a2c1d0e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace (resource_type, resource_id) unique constraint with
    (resource_type, resource_id, owner_id)."""
    with op.batch_alter_table("resource_metadata", schema=None) as batch_op:
        batch_op.drop_constraint("uq_resource_type_id", type_="unique")
        batch_op.create_unique_constraint(
            "uq_resource_type_id_owner",
            ["resource_type", "resource_id", "owner_id"],
        )


def downgrade() -> None:
    """Restore the old (resource_type, resource_id) unique constraint."""
    with op.batch_alter_table("resource_metadata", schema=None) as batch_op:
        batch_op.drop_constraint("uq_resource_type_id_owner", type_="unique")
        batch_op.create_unique_constraint(
            "uq_resource_type_id",
            ["resource_type", "resource_id"],
        )
