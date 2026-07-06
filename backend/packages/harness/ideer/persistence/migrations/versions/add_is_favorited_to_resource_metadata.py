"""Add is_favorited column to resource_metadata table.

Revision ID: add_is_favorited
Revises: a2b3c4d5e6f7
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_is_favorited"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add is_favorited column with default value False
    op.add_column("resource_metadata", sa.Column("is_favorited", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("resource_metadata", "is_favorited")
