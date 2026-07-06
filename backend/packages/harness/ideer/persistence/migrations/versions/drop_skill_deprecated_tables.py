"""drop deprecated user_skill_preferences and skill_default_configs

Revision ID: drop_skill_deprecated_tables
Revises: add_audit_logs
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "drop_skill_deprecated_tables"
down_revision: str | None = "add_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop deprecated user_skill_preferences and skill_default_configs tables."""
    op.drop_table("user_skill_preferences")
    op.drop_table("skill_default_configs")


def downgrade() -> None:
    """Recreate dropped tables from the original migration schema."""
    op.create_table(
        "user_skill_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "skill_name"),
    )
    op.create_table(
        "skill_default_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=36), nullable=True),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("user_override_allowed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "scope_id", "skill_name", name="uq_skill_default_scope_skill"),
    )
