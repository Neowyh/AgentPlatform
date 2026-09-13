"""add durable KnowledgeBase document records and original storage"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_knowledge_documents"
down_revision: str | None = "20260911_resource_dependency_kb_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("knowledge_documents"):
        existing = {column["name"] for column in inspector.get_columns("knowledge_documents")}
        if "failure_code" not in existing:
            op.add_column("knowledge_documents", sa.Column("failure_code", sa.String(length=64), nullable=True))
        if "failure_message" not in existing:
            op.add_column("knowledge_documents", sa.Column("failure_message", sa.String(length=255), nullable=True))
        if "ingestion_attempt" not in existing:
            op.add_column("knowledge_documents", sa.Column("ingestion_attempt", sa.Integer(), nullable=False))
        return
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("resource_id", sa.String(length=36), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False, unique=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("provider_document_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=255), nullable=True),
        sa.Column("ingestion_attempt", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=64), sa.ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("resource_id", "content_hash", name="uq_knowledge_documents_resource_hash"),
        sa.CheckConstraint("source = 'upload'", name="ck_knowledge_documents_source"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_knowledge_documents_size"),
    )
    op.create_index("ix_knowledge_documents_resource_created", "knowledge_documents", ["resource_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_resource_created", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
