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
    if inspector.has_table("knowledge_bases"):
        kb_columns = {column["name"] for column in inspector.get_columns("knowledge_bases")}
        with op.batch_alter_table("knowledge_bases", recreate="always") as batch:
            if "initialization_status" not in kb_columns:
                batch.add_column(sa.Column("initialization_status", sa.String(length=16), nullable=True))
            if "initialization_error" not in kb_columns:
                batch.add_column(sa.Column("initialization_error", sa.String(length=255), nullable=True))
            if "initialization_attempt" not in kb_columns:
                batch.add_column(sa.Column("initialization_attempt", sa.Integer(), nullable=True))
            if "initialization_step" not in kb_columns:
                batch.add_column(sa.Column("initialization_step", sa.String(length=32), nullable=True))
            if "initialization_next_attempt_at" not in kb_columns:
                batch.add_column(sa.Column("initialization_next_attempt_at", sa.DateTime(timezone=True), nullable=True))
            if "initialization_lease_owner" not in kb_columns:
                batch.add_column(sa.Column("initialization_lease_owner", sa.String(length=128), nullable=True))
            if "initialization_lease_until" not in kb_columns:
                batch.add_column(sa.Column("initialization_lease_until", sa.DateTime(timezone=True), nullable=True))
        op.execute(sa.text("UPDATE knowledge_bases SET initialization_status = CASE WHEN provider_dataset_id IS NULL THEN 'initializing' ELSE 'ready' END WHERE initialization_status IS NULL"))
        op.execute(sa.text("UPDATE knowledge_bases SET initialization_attempt = 0 WHERE initialization_attempt IS NULL"))
        op.execute(sa.text("UPDATE knowledge_bases SET initialization_step = CASE WHEN provider_dataset_id IS NULL THEN 'pending' ELSE 'complete' END WHERE initialization_step IS NULL"))
        with op.batch_alter_table("knowledge_bases") as batch:
            batch.alter_column("initialization_status", nullable=False)
            batch.alter_column("initialization_attempt", nullable=False)
            batch.alter_column("initialization_step", nullable=False)
    if inspector.has_table("knowledge_documents"):
        existing = {column["name"] for column in inspector.get_columns("knowledge_documents")}
        if "failure_code" not in existing:
            op.add_column("knowledge_documents", sa.Column("failure_code", sa.String(length=64), nullable=True))
        if "title" not in existing:
            op.add_column("knowledge_documents", sa.Column("title", sa.String(length=255), nullable=True))
        if "failure_message" not in existing:
            op.add_column("knowledge_documents", sa.Column("failure_message", sa.String(length=255), nullable=True))
        if "ingestion_attempt" not in existing:
            op.add_column("knowledge_documents", sa.Column("ingestion_attempt", sa.Integer(), nullable=True))
        for name, column in (
            ("processing_step", sa.Column("processing_step", sa.String(length=32), nullable=True)),
            ("next_attempt_at", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)),
            ("lease_owner", sa.Column("lease_owner", sa.String(length=128), nullable=True)),
            ("lease_until", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True)),
        ):
            if name not in existing:
                op.add_column("knowledge_documents", column)
        op.execute(sa.text("UPDATE knowledge_documents SET ingestion_attempt = 0 WHERE ingestion_attempt IS NULL"))
        op.execute(sa.text("UPDATE knowledge_documents SET processing_step = CASE WHEN status = 'ready' THEN 'complete' ELSE 'pending' END WHERE processing_step IS NULL"))
        with op.batch_alter_table("knowledge_documents") as batch_op:
            batch_op.alter_column("ingestion_attempt", nullable=False)
            batch_op.alter_column("processing_step", nullable=False)
        constraints = {item.get("name") for item in sa.inspect(op.get_bind()).get_unique_constraints("knowledge_documents")}
        if "uq_knowledge_documents_resource_hash" in constraints:
            with op.batch_alter_table("knowledge_documents", recreate="always") as batch_op:
                batch_op.drop_constraint("uq_knowledge_documents_resource_hash", type_="unique")
        return
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("resource_id", sa.String(length=36), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
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
        sa.Column("processing_step", sa.String(length=32), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=64), sa.ForeignKey("users_ext.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source = 'upload'", name="ck_knowledge_documents_source"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_knowledge_documents_size"),
    )
    op.create_index("ix_knowledge_documents_resource_created", "knowledge_documents", ["resource_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_resource_created", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
