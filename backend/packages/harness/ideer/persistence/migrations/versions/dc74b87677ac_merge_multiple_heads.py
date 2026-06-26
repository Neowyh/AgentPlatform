"""merge multiple heads

Revision ID: dc74b87677ac
Revises: b2c3d4e5f6a7, c4d5e6f7a8b9
Create Date: 2026-06-24 17:04:39.271051

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "dc74b87677ac"
down_revision: str | None = ("b2c3d4e5f6a7", "c4d5e6f7a8b9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
