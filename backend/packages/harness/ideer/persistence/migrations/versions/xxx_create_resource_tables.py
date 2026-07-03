"""create resource_metadata and visibility_applications tables

Revision ID: xxx_create_resource_tables
Revises: e5f6a7b8c9d0
Create Date: 2026-07-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "xxx_create_resource_tables"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create resource_metadata and visibility_applications tables."""
    # resource_metadata table
    op.create_table(
        "resource_metadata",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("department_id", sa.String(length=64), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"),
        sa.Column("imported_from", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_type", "resource_id", name="uq_resource_type_id"),
    )
    with op.batch_alter_table("resource_metadata", schema=None) as batch_op:
        batch_op.create_index("ix_resource_metadata_type", ["resource_type"], unique=False)
        batch_op.create_index("ix_resource_metadata_owner", ["owner_id"], unique=False)
        batch_op.create_index("ix_resource_metadata_dept", ["department_id"], unique=False)
        batch_op.create_index("ix_resource_metadata_visibility", ["visibility"], unique=False)

    # visibility_applications table
    op.create_table(
        "visibility_applications",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("applicant_id", sa.String(length=64), nullable=False),
        sa.Column("current_visibility", sa.String(length=32), nullable=False),
        sa.Column("target_visibility", sa.String(length=32), nullable=False),
        sa.Column("department_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("visibility_applications", schema=None) as batch_op:
        batch_op.create_index("ix_visibility_app_status", ["status"], unique=False)
        batch_op.create_index("ix_visibility_app_resource", ["resource_type", "resource_id"], unique=False)
        batch_op.create_index("ix_visibility_app_applicant", ["applicant_id"], unique=False)
        batch_op.create_index("ix_visibility_app_type", ["resource_type"], unique=False)


def downgrade() -> None:
    """Drop visibility_applications and resource_metadata tables."""
    op.drop_table("visibility_applications")
    op.drop_table("resource_metadata")
