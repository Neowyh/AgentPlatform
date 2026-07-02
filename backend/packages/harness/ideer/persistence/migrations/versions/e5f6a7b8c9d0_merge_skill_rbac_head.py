"""merge skill rbac head into main chain

Revision ID: e5f6a7b8c9d0
Revises: dc74b87677ac, e1f2a3b4c5d6
Create Date: 2026-06-30 22:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = ("dc74b87677ac", "e1f2a3b4c5d6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
