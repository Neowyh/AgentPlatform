"""add ix_resource_metadata_deleted index to resource_metadata

Revision ID: a2b3c4d5e6f7
Revises: xxx_create_resource_tables
Create Date: 2026-07-06 00:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "xxx_create_resource_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: ix_resource_metadata_deleted was already created by xxx_create_resource_tables."""


def downgrade() -> None:
    """No-op: table drop in xxx_create_resource_tables handles cleanup."""
