"""add durable A/B knowledge evaluation comparisons (M6 ticket 05)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_knowledge_eval_comparisons"
down_revision: str | Sequence[str] | None = "20260916_knowledge_evaluation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("knowledge_eval_comparisons"):
        return
    op.create_table(
        "knowledge_eval_comparisons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("knowledge_base_id", sa.String(36), nullable=False),
        sa.Column("left_run_id", sa.String(36), nullable=False),
        sa.Column("right_run_id", sa.String(36), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("metrics_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("top_k >= 1", name="ck_knowledge_eval_comparisons_top_k"),
        sa.CheckConstraint("status in ('queued','running','completed','incomplete')", name="ck_knowledge_eval_comparisons_status"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.resource_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["left_run_id"], ["knowledge_eval_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["right_run_id"], ["knowledge_eval_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users_ext.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_knowledge_eval_comparisons_kb_created", "knowledge_eval_comparisons", ["knowledge_base_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_eval_comparisons_kb_created", table_name="knowledge_eval_comparisons")
    op.drop_table("knowledge_eval_comparisons")
