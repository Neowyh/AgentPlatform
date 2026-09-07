"""fix visibility_applications pending unique index for cross-DB support

SQLite ignores postgresql_where when the model defines:
  Index("uq_visibility_app_pending", ..., postgresql_where="status = 'pending'")

This created a FULL unique index on (resource_type, resource_id) on SQLite,
blocking any second application per resource regardless of status.

This migration drops the full unique index (if it exists) and recreates it with
a native partial WHERE clause that works on both SQLite 3.25+ and PostgreSQL.

Revision ID: f4b3a2c1d0e9
Revises: drop_skill_deprecated_tables
Create Date: 2026-07-09 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4b3a2c1d0e9"
down_revision: str | None = "drop_skill_deprecated_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace full unique index with a partial unique index on pending only."""
    # Drop the old full unique index if it exists.
    # batch_op.drop_index does not support IF EXISTS on SQLite, so use raw SQL.
    op.execute("DROP INDEX IF EXISTS uq_visibility_app_pending")

    # Create partial unique index — only one PENDING row per resource.
    # Works on SQLite 3.25+ and PostgreSQL.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_visibility_app_pending ON visibility_applications(resource_type, resource_id) WHERE status = 'pending'",
    )


def downgrade() -> None:
    """Restore the old full unique index."""
    op.execute("DROP INDEX IF EXISTS uq_visibility_app_pending")

    with op.batch_alter_table("visibility_applications", schema=None) as batch_op:
        batch_op.create_index("uq_visibility_app_pending", ["resource_type", "resource_id"], unique=True)
