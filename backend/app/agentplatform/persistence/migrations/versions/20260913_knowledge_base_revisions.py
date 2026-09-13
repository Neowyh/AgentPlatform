"""add knowledge_base_revisions for immutable revision candidates (M4 ticket 01)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_knowledge_base_revisions"
down_revision: str | None = "20260913_knowledge_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("knowledge_base_revisions"):
        return
    op.create_table(
        "knowledge_base_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "knowledge_base_id",
            sa.String(length=36),
            sa.ForeignKey("knowledge_bases.resource_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("provider_doc_map_json", sa.JSON(), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("provider_dataset_id", sa.String(length=128), nullable=True),
        sa.Column("provider_revision_hint", sa.String(length=128), nullable=True),
        sa.Column("publish_attempt", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=64), sa.ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("knowledge_base_id", "revision_no", name="uq_knowledge_base_revisions_no"),
        sa.CheckConstraint(
            "status in ('draft','indexing','ready','published','failed','superseded','archived')",
            name="ck_knowledge_base_revisions_status",
        ),
        sa.CheckConstraint("document_count >= 0", name="ck_knowledge_base_revisions_document_count"),
    )
    op.create_index(
        "uq_knowledge_base_revisions_active_publish",
        "knowledge_base_revisions",
        ["knowledge_base_id"],
        unique=True,
        sqlite_where=sa.text("status = 'indexing'"),
        postgresql_where=sa.text("status = 'indexing'"),
    )


def downgrade() -> None:
    op.drop_index("uq_knowledge_base_revisions_active_publish", table_name="knowledge_base_revisions")
    op.drop_table("knowledge_base_revisions")
