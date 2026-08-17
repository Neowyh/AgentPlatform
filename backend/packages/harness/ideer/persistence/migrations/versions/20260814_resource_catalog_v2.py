"""add canonical resource catalog tables

Revision ID: 20260814_resource_catalog_v2
Revises: 20260718_workflow_v2_lease_audit
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_resource_catalog_v2"
down_revision: str | None = "20260718_workflow_v2_lease_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="private"),
        sa.Column("scope_department_id", sa.String(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("latest_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("storage_kind", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("system_owned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("authz_revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("type IN ('skill', 'agent', 'workflow')", name="ck_resources_type"),
        sa.CheckConstraint("visibility IN ('private', 'department', 'public')", name="ck_resources_visibility"),
        sa.CheckConstraint("lifecycle_status IN ('active', 'archived', 'suspended')", name="ck_resources_lifecycle"),
        sa.CheckConstraint("storage_kind IN ('filesystem', 'database', 'bundled')", name="ck_resources_storage_kind"),
        sa.CheckConstraint("latest_version >= 0", name="ck_resources_latest_version"),
        sa.CheckConstraint("draft_revision >= 0", name="ck_resources_draft_revision"),
        sa.CheckConstraint("authz_revision >= 1", name="ck_resources_authz_revision"),
        sa.ForeignKeyConstraint(["owner_id"], ["users_ext.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scope_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "owner_id", "slug", name="uq_resources_type_owner_slug"),
    )
    op.create_index("ix_resources_owner", "resources", ["owner_id"])
    op.create_index("ix_resources_visibility_scope", "resources", ["visibility", "scope_department_id"])
    op.create_index("ix_resources_type_lifecycle", "resources", ["type", "lifecycle_status"])

    with op.batch_alter_table("workflow_v2_runs") as batch_op:
        batch_op.add_column(sa.Column("workflow_resource_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("runner_tool_groups", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            "fk_workflow_v2_runs_resource",
            "resources",
            ["workflow_resource_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_workflow_v2_runs_resource", ["workflow_resource_id"])

    with op.batch_alter_table("visibility_applications") as batch_op:
        batch_op.add_column(sa.Column("canonical_resource_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("requested_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("requested_hash", sa.String(length=64), nullable=True))
        batch_op.create_check_constraint("ck_visibility_app_requested_version", "requested_version IS NULL OR requested_version >= 1")
        batch_op.create_foreign_key(
            "fk_visibility_app_canonical_resource",
            "resources",
            ["canonical_resource_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_visibility_app_canonical_resource", ["canonical_resource_id"])
    op.create_index(
        "uq_visibility_app_pending_canonical",
        "visibility_applications",
        ["canonical_resource_id"],
        unique=True,
        sqlite_where=sa.text("canonical_resource_id IS NOT NULL AND status = 'pending'"),
        postgresql_where=sa.text("canonical_resource_id IS NOT NULL AND status = 'pending'"),
    )

    op.create_table(
        "resource_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("scan_result", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_resource_id", sa.String(length=36), nullable=True),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_resource_versions_version"),
        sa.CheckConstraint("source_version IS NULL OR source_version >= 1", name="ck_resource_versions_source_version"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_resource_id"], ["resources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users_ext.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_id", "version", name="uq_resource_versions_resource_version"),
    )
    op.create_index("ix_resource_versions_hash", "resource_versions", ["content_hash"])

    op.create_table(
        "resource_dependencies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_resource_id", sa.String(length=36), nullable=False),
        sa.Column("target_resource_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source_resource_id <> target_resource_id", name="ck_resource_dependencies_not_self"),
        sa.ForeignKeyConstraint(["source_resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_resource_id"], ["resources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_resource_id", "target_resource_id", name="uq_resource_dependencies_edge"),
    )
    op.create_index("ix_resource_dependencies_target", "resource_dependencies", ["target_resource_id"])

    op.create_table(
        "run_resource_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("root_resource_id", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("authz_revision", sa.Integer(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("version >= 1", name="ck_run_resource_snapshots_version"),
        sa.CheckConstraint("authz_revision >= 1", name="ck_run_resource_snapshots_authz_revision"),
        sa.ForeignKeyConstraint(["root_resource_id"], ["resources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "resource_id", name="uq_run_resource_snapshots_run_resource"),
    )
    op.create_index("ix_run_resource_snapshots_resource", "run_resource_snapshots", ["resource_id", "run_id"])

    op.create_table(
        "resource_favorites",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users_ext.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "resource_id"),
    )

    op.create_table(
        "resource_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recipient_id", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recipient_id"], ["users_ext.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resource_notifications_recipient_created",
        "resource_notifications",
        ["recipient_id", "created_at"],
    )

    op.create_table(
        "resource_drafts",
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("modified_by", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("revision >= 1", name="ck_resource_drafts_revision"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["modified_by"], ["users_ext.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("resource_id"),
    )


def downgrade() -> None:
    op.drop_table("resource_drafts")
    op.drop_index(
        "ix_resource_notifications_recipient_created",
        table_name="resource_notifications",
    )
    op.drop_table("resource_notifications")
    op.drop_table("resource_favorites")
    op.drop_index("ix_run_resource_snapshots_resource", table_name="run_resource_snapshots")
    op.drop_table("run_resource_snapshots")
    op.drop_index("ix_resource_dependencies_target", table_name="resource_dependencies")
    op.drop_table("resource_dependencies")
    op.drop_index("ix_resource_versions_hash", table_name="resource_versions")
    op.drop_table("resource_versions")
    op.drop_index("ix_resources_type_lifecycle", table_name="resources")
    op.drop_index("ix_resources_visibility_scope", table_name="resources")
    op.drop_index("ix_resources_owner", table_name="resources")
    op.drop_index("uq_visibility_app_pending_canonical", table_name="visibility_applications")
    with op.batch_alter_table("visibility_applications") as batch_op:
        batch_op.drop_index("ix_visibility_app_canonical_resource")
        batch_op.drop_constraint("fk_visibility_app_canonical_resource", type_="foreignkey")
        batch_op.drop_constraint("ck_visibility_app_requested_version", type_="check")
        batch_op.drop_column("requested_hash")
        batch_op.drop_column("requested_version")
        batch_op.drop_column("canonical_resource_id")
    with op.batch_alter_table("workflow_v2_runs") as batch_op:
        batch_op.drop_index("ix_workflow_v2_runs_resource")
        batch_op.drop_constraint("fk_workflow_v2_runs_resource", type_="foreignkey")
        batch_op.drop_column("runner_tool_groups")
        batch_op.drop_column("workflow_resource_id")
    op.drop_table("resources")
