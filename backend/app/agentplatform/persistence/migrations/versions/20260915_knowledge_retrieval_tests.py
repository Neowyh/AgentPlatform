"""create knowledge_retrieval_tests for archived management retrieval tests (M6 ticket 01)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_knowledge_retrieval_tests"
down_revision: str | Sequence[str] | None = "20260915_knowledge_eval_cases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("knowledge_retrieval_tests"):
        return
    op.create_table(
        "knowledge_retrieval_tests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("revision_id", sa.String(length=36), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("requested_top_k", sa.Integer(), nullable=False),
        sa.Column("retrieval_profile_json", sa.JSON(), nullable=False),
        sa.Column("applied_parameters_json", sa.JSON(), nullable=False),
        sa.Column("result_status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("returned_count", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "result_status in ('success','empty_hit','provider_error')",
            name="ck_knowledge_retrieval_tests_result_status",
        ),
        sa.CheckConstraint("requested_top_k >= 1", name="ck_knowledge_retrieval_tests_top_k"),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.resource_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["knowledge_base_revisions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users_ext.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_retrieval_tests_kb_created",
        "knowledge_retrieval_tests",
        ["knowledge_base_id", "created_at"],
    )
    op.create_index(
        "ix_knowledge_retrieval_tests_revision",
        "knowledge_retrieval_tests",
        ["revision_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_retrieval_tests_revision", table_name="knowledge_retrieval_tests")
    op.drop_index("ix_knowledge_retrieval_tests_kb_created", table_name="knowledge_retrieval_tests")
    op.drop_table("knowledge_retrieval_tests")
