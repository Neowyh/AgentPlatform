"""Add NOT NULL constraints to columns that were created nullable

ORM models define these columns as NOT NULL (Mapped[type] without | None),
but the original migration c4d5e6f7a8b9 created them with nullable=True.
Backfill existing NULLs with default values before adding constraints.

Revision ID: 35830514e3ee
Revises: drop_skill_deprecated_tables
Create Date: 2026-07-08

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "35830514e3ee"
down_revision: str | None = "drop_skill_deprecated_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- feedback ---
    op.execute("UPDATE feedback SET created_at = '2024-01-01 00:00:00+00' WHERE created_at IS NULL")
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.alter_column("created_at", nullable=False)

    # --- run_events ---
    op.execute("UPDATE run_events SET content = '' WHERE content IS NULL")
    op.execute("UPDATE run_events SET event_metadata = '{}' WHERE event_metadata IS NULL")
    op.execute("UPDATE run_events SET created_at = '2024-01-01 00:00:00+00' WHERE created_at IS NULL")
    with op.batch_alter_table("run_events") as batch_op:
        batch_op.alter_column("content", nullable=False)
        batch_op.alter_column("event_metadata", nullable=False)
        batch_op.alter_column("created_at", nullable=False)

    # --- runs ---
    op.execute("UPDATE runs SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE runs SET multitask_strategy = 'reject' WHERE multitask_strategy IS NULL")
    op.execute("UPDATE runs SET metadata_json = '{}' WHERE metadata_json IS NULL")
    op.execute("UPDATE runs SET kwargs_json = '{}' WHERE kwargs_json IS NULL")
    op.execute("UPDATE runs SET message_count = 0 WHERE message_count IS NULL")
    op.execute("UPDATE runs SET total_input_tokens = 0 WHERE total_input_tokens IS NULL")
    op.execute("UPDATE runs SET total_output_tokens = 0 WHERE total_output_tokens IS NULL")
    op.execute("UPDATE runs SET total_tokens = 0 WHERE total_tokens IS NULL")
    op.execute("UPDATE runs SET llm_call_count = 0 WHERE llm_call_count IS NULL")
    op.execute("UPDATE runs SET lead_agent_tokens = 0 WHERE lead_agent_tokens IS NULL")
    op.execute("UPDATE runs SET subagent_tokens = 0 WHERE subagent_tokens IS NULL")
    op.execute("UPDATE runs SET middleware_tokens = 0 WHERE middleware_tokens IS NULL")
    op.execute("UPDATE runs SET created_at = '2024-01-01 00:00:00+00' WHERE created_at IS NULL")
    op.execute("UPDATE runs SET updated_at = '2024-01-01 00:00:00+00' WHERE updated_at IS NULL")
    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column("status", nullable=False)
        batch_op.alter_column("multitask_strategy", nullable=False)
        batch_op.alter_column("metadata_json", nullable=False)
        batch_op.alter_column("kwargs_json", nullable=False)
        batch_op.alter_column("message_count", nullable=False)
        batch_op.alter_column("total_input_tokens", nullable=False)
        batch_op.alter_column("total_output_tokens", nullable=False)
        batch_op.alter_column("total_tokens", nullable=False)
        batch_op.alter_column("llm_call_count", nullable=False)
        batch_op.alter_column("lead_agent_tokens", nullable=False)
        batch_op.alter_column("subagent_tokens", nullable=False)
        batch_op.alter_column("middleware_tokens", nullable=False)
        batch_op.alter_column("created_at", nullable=False)
        batch_op.alter_column("updated_at", nullable=False)

    # --- threads_meta ---
    op.execute("UPDATE threads_meta SET status = 'idle' WHERE status IS NULL")
    op.execute("UPDATE threads_meta SET metadata_json = '{}' WHERE metadata_json IS NULL")
    op.execute("UPDATE threads_meta SET created_at = '2024-01-01 00:00:00+00' WHERE created_at IS NULL")
    op.execute("UPDATE threads_meta SET updated_at = '2024-01-01 00:00:00+00' WHERE updated_at IS NULL")
    with op.batch_alter_table("threads_meta") as batch_op:
        batch_op.alter_column("status", nullable=False)
        batch_op.alter_column("metadata_json", nullable=False)
        batch_op.alter_column("created_at", nullable=False)
        batch_op.alter_column("updated_at", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.alter_column("created_at", nullable=True)
    with op.batch_alter_table("run_events") as batch_op:
        batch_op.alter_column("content", nullable=True)
        batch_op.alter_column("event_metadata", nullable=True)
        batch_op.alter_column("created_at", nullable=True)
    with op.batch_alter_table("runs") as batch_op:
        batch_op.alter_column("status", nullable=True)
        batch_op.alter_column("multitask_strategy", nullable=True)
        batch_op.alter_column("metadata_json", nullable=True)
        batch_op.alter_column("kwargs_json", nullable=True)
        batch_op.alter_column("message_count", nullable=True)
        batch_op.alter_column("total_input_tokens", nullable=True)
        batch_op.alter_column("total_output_tokens", nullable=True)
        batch_op.alter_column("total_tokens", nullable=True)
        batch_op.alter_column("llm_call_count", nullable=True)
        batch_op.alter_column("lead_agent_tokens", nullable=True)
        batch_op.alter_column("subagent_tokens", nullable=True)
        batch_op.alter_column("middleware_tokens", nullable=True)
        batch_op.alter_column("created_at", nullable=True)
        batch_op.alter_column("updated_at", nullable=True)
    with op.batch_alter_table("threads_meta") as batch_op:
        batch_op.alter_column("status", nullable=True)
        batch_op.alter_column("metadata_json", nullable=True)
        batch_op.alter_column("created_at", nullable=True)
        batch_op.alter_column("updated_at", nullable=True)
