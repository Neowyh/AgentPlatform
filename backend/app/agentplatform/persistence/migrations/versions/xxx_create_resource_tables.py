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
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names()) if bind is not None else set()

    # resource_metadata table
    if "resource_metadata" not in existing_tables:
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
            sa.ForeignKeyConstraint(["owner_id"], ["users_ext.id"], name="fk_resource_metadata_owner", ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_resource_metadata_department", ondelete="SET NULL"),
        )
    resource_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("resource_metadata")} if bind is not None and "resource_metadata" in existing_tables else set()
    resource_columns = {column["name"] for column in sa.inspect(bind).get_columns("resource_metadata")} if bind is not None else set()
    with op.batch_alter_table("resource_metadata", schema=None) as batch_op:
        for name, columns in {
            "ix_resource_metadata_type": ["resource_type"],
            "ix_resource_metadata_owner": ["owner_id"],
            "ix_resource_metadata_dept": ["department_id"],
            "ix_resource_metadata_visibility": ["visibility"],
            "ix_resource_metadata_deleted": ["deleted_at"],
        }.items():
            if name not in resource_indexes and (not resource_columns or set(columns).issubset(resource_columns)):
                batch_op.create_index(name, columns, unique=False)

    # visibility_applications table
    if "visibility_applications" not in existing_tables:
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
            sa.ForeignKeyConstraint(["applicant_id"], ["users_ext.id"], name="fk_visibility_app_applicant", ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_visibility_app_department", ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users_ext.id"], name="fk_visibility_app_reviewer", ondelete="SET NULL"),
        )
    visibility_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("visibility_applications")} if bind is not None and "visibility_applications" in existing_tables else set()
    with op.batch_alter_table("visibility_applications", schema=None) as batch_op:
        for name, columns in {
            "ix_visibility_app_status": ["status"],
            "ix_visibility_app_resource": ["resource_type", "resource_id"],
            "ix_visibility_app_applicant": ["applicant_id"],
            "ix_visibility_app_type": ["resource_type"],
        }.items():
            if name not in visibility_indexes:
                batch_op.create_index(name, columns, unique=False)


def downgrade() -> None:
    """Drop visibility_applications and resource_metadata tables."""
    op.drop_table("visibility_applications")
    op.drop_table("resource_metadata")
