"""create eval case tables for retrieval test regression cases (M6 ticket 03)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_knowledge_eval_cases"
down_revision: str | Sequence[str] | None = "20260915_knowledge_publish_lease"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("knowledge_eval_cases"):
        return
    op.create_table(
        "knowledge_eval_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("question", sa.String(length=4000), nullable=False),
        sa.Column("expected_document_ids_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version_no >= 1", name="ck_knowledge_eval_cases_version_no"),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.resource_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users_ext.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users_ext.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_eval_cases_kb_created",
        "knowledge_eval_cases",
        ["knowledge_base_id", "created_at"],
    )
    op.create_table(
        "knowledge_eval_case_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("question", sa.String(length=4000), nullable=False),
        sa.Column("expected_document_ids_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("change_type", sa.String(length=16), nullable=False),
        sa.Column("changed_by", sa.String(length=64), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "change_type in ('created','updated')",
            name="ck_knowledge_eval_case_versions_change_type",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["knowledge_eval_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users_ext.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "version_no", name="uq_knowledge_eval_case_versions_no"),
    )
    op.create_index(
        "ix_knowledge_eval_case_versions_case",
        "knowledge_eval_case_versions",
        ["case_id", "version_no"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_eval_case_versions_case", table_name="knowledge_eval_case_versions")
    op.drop_table("knowledge_eval_case_versions")
    op.drop_index("ix_knowledge_eval_cases_kb_created", table_name="knowledge_eval_cases")
    op.drop_table("knowledge_eval_cases")
