"""add versioned knowledge publish evaluation policies"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_knowledge_publish_eval_gate"
down_revision: str | Sequence[str] | None = "20260917_knowledge_eval_comparisons"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("knowledge_evaluation_policies"):
        op.create_table(
            "knowledge_evaluation_policies",
            sa.Column("knowledge_base_id", sa.String(36), primary_key=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("profile_id", sa.String(32), nullable=False),
            sa.Column("top_k", sa.Integer(), nullable=False),
            sa.Column("case_ids_json", sa.JSON(), nullable=False),
            sa.Column("min_expected_hit_rate", sa.Float(), nullable=False),
            sa.Column("min_recall_at_k", sa.Float(), nullable=False),
            sa.Column("min_mrr_at_k", sa.Float(), nullable=False),
            sa.Column("updated_by", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.resource_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["updated_by"], ["users_ext.id"], ondelete="RESTRICT"),
        )
    columns = {column["name"] for column in inspector.get_columns("knowledge_eval_runs")}
    additions = {
        "policy_version": sa.Column("policy_version", sa.Integer(), nullable=True),
        "policy_json": sa.Column("policy_json", sa.JSON(), nullable=True),
        "qualification_status": sa.Column("qualification_status", sa.String(16), nullable=False, server_default="pending"),
        "qualification_reason": sa.Column("qualification_reason", sa.String(255), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("knowledge_eval_runs", column)


def downgrade() -> None:
    op.drop_column("knowledge_eval_runs", "qualification_reason")
    op.drop_column("knowledge_eval_runs", "qualification_status")
    op.drop_column("knowledge_eval_runs", "policy_json")
    op.drop_column("knowledge_eval_runs", "policy_version")
    op.drop_table("knowledge_evaluation_policies")
