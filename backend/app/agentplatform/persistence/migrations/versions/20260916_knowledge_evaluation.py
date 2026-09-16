"""add durable single-profile knowledge evaluations (M6 ticket 04)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_knowledge_evaluation"
down_revision: str | Sequence[str] | None = "20260915_knowledge_retrieval_tests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("knowledge_eval_runs"):
        return
    op.create_table(
        "knowledge_eval_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("retry_of_run_id", sa.String(36)),
        sa.Column("knowledge_base_id", sa.String(36), nullable=False),
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("profile_id", sa.String(32), nullable=False),
        sa.Column("profile_hash", sa.String(64), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("case_ids_json", sa.JSON(), nullable=False),
        sa.Column("case_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("metrics_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("completed_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("aggregate_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.CheckConstraint("profile_id in ('frozen','configured')", name="ck_knowledge_eval_runs_profile"),
        sa.CheckConstraint("top_k >= 1", name="ck_knowledge_eval_runs_top_k"),
        sa.CheckConstraint("status in ('queued','running','completed','partial','failed')", name="ck_knowledge_eval_runs_status"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.resource_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["knowledge_base_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users_ext.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_knowledge_eval_runs_kb_created", "knowledge_eval_runs", ["knowledge_base_id", "created_at"])
    op.create_index("ix_knowledge_eval_runs_status_lease", "knowledge_eval_runs", ["status", "lease_until"])
    op.create_table(
        "knowledge_eval_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("case_version_no", sa.Integer(), nullable=False),
        sa.Column("case_content_hash", sa.String(64), nullable=False),
        sa.Column("query", sa.String(4000), nullable=False),
        sa.Column("expected_document_ids_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("ranked_items_json", sa.JSON(), nullable=False),
        sa.Column("expected_hit", sa.Boolean(), nullable=False),
        sa.Column("recall_at_k", sa.Float()),
        sa.Column("mrr_at_k", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('success','empty_hit','provider_error','invalid')", name="ck_knowledge_eval_results_status"),
        sa.ForeignKeyConstraint(["run_id"], ["knowledge_eval_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "case_id", name="uq_knowledge_eval_results_case"),
    )
    op.create_index("ix_knowledge_eval_results_run", "knowledge_eval_results", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_eval_results_run", table_name="knowledge_eval_results")
    op.drop_table("knowledge_eval_results")
    op.drop_index("ix_knowledge_eval_runs_status_lease", table_name="knowledge_eval_runs")
    op.drop_index("ix_knowledge_eval_runs_kb_created", table_name="knowledge_eval_runs")
    op.drop_table("knowledge_eval_runs")
