"""add skill rbac tables

Revision ID: e1f2a3b4c5d6
Revises: 16147afec43b
Create Date: 2026-06-30 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "16147afec43b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create skill_applications, user_skill_preferences, and skill_default_configs tables for RBAC."""

    # Create skill_applications table
    op.create_table(
        "skill_applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=128), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("applicant_id", sa.String(length=36), nullable=False),
        sa.Column("request_level", sa.String(length=32), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create user_skill_preferences table
    op.create_table(
        "user_skill_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "skill_name"),
    )

    # Create skill_default_configs table
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


def downgrade() -> None:
    """Drop skill_applications, user_skill_preferences, and skill_default_configs tables."""
    op.drop_table("skill_default_configs")
    op.drop_table("user_skill_preferences")
    op.drop_table("skill_applications")
