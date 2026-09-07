"""merge not null constraints and drop deleted at heads

Revision ID: 9a8b7c6d5e4f
Revises: 35830514e3ee, drop_deleted_at
Create Date: 2026-07-12

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9a8b7c6d5e4f"
down_revision: str | None = ("35830514e3ee", "drop_deleted_at")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
