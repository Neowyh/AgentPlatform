"""add knowledge_bases table and admit knowledge_base resource type

KnowledgeBase becomes the fourth first-class Resource (M2 ticket 02). The
table is a 1:1 extension of ``resources`` keyed by the canonical Resource
UUID; the provider binding is an opaque external mapping, never the
enterprise identity.

Revision ID: 20260911_knowledge_bases
Revises: 20260909_device_control_plane
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_knowledge_bases"
down_revision: str | None = "20260909_device_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Gateway bootstrap may encounter a pre-versioned database whose current
    # ORM metadata was already created by ``create_all``.  In that shape the
    # resources type CHECK already admits knowledge_base, so only the
    # versioned chain needs the new table.
    if sa.inspect(op.get_bind()).has_table("knowledge_bases"):
        return
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_constraint("ck_resources_type", type_="check")
        batch_op.create_check_constraint(
            "ck_resources_type",
            "type IN ('skill', 'agent', 'workflow', 'knowledge_base')",
        )
    op.create_table(
        "knowledge_bases",
        sa.Column("resource_id", sa.String(length=36), sa.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("provider_dataset_id", sa.String(length=128), nullable=True),
        sa.Column("retrieval_profile_json", sa.JSON(), nullable=False),
        sa.Column("ingestion_profile_json", sa.JSON(), nullable=False),
        sa.Column("embedding_profile_json", sa.JSON(), nullable=False),
        sa.Column("active_revision_id", sa.String(length=36), nullable=True),
        sa.Column("sync_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider_type <> ''", name="ck_knowledge_bases_provider_type"),
        sa.UniqueConstraint("provider_type", "provider_dataset_id", name="uq_knowledge_bases_provider_binding"),
    )
    op.create_index("ix_knowledge_bases_provider_dataset", "knowledge_bases", ["provider_dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_bases_provider_dataset", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_constraint("ck_resources_type", type_="check")
        batch_op.create_check_constraint("ck_resources_type", "type IN ('skill', 'agent', 'workflow')")
