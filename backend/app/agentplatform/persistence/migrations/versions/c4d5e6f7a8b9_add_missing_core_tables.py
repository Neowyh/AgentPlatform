"""add missing core tables (runs, threads_meta, run_events, feedback, users)

Revision ID: c4d5e6f7a8b9
Revises: a1b2c3d4e5f6
Create Date: 2026-06-20 12:00:00.000000

PATCH (2026-09-08, unified migration chain / PATCH-006 closure): each
``create_table`` block is guarded with an inspector check. The unified chain
(merge revision ``20260908_unify_migration_chains``) can replay this
revision against databases that already hold these tables -- e.g. TUI-shaped
databases where ``Base.metadata.create_all`` created the core tables but no
control-plane revision was ever recorded. The guard mirrors ``create_all``'s
``checkfirst`` semantics and changes nothing for databases that recorded
this revision when it originally shipped (their tables exist, so every
block is skipped). Recorded in
``docs/upgrades/deerflow-main-0f7d8709/UPSTREAM_PATCH_LEDGER.md``.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create core tables that were previously only created by create_all().

    These tables are needed for alembic upgrade head to work on fresh databases
    without going through the init_engine create_all path.
    """
    # Inspect once; every block below is guarded so the revision is a
    # no-op on databases where create_all (or an earlier era) already
    # created the table -- see the module docstring PATCH note.
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "runs" not in existing:
        # runs table
        op.create_table(
            "runs",
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("thread_id", sa.String(length=64), nullable=False),
            sa.Column("assistant_id", sa.String(length=128), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True),
            sa.Column("model_name", sa.String(length=128), nullable=True),
            sa.Column("multitask_strategy", sa.String(length=20), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("kwargs_json", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("message_count", sa.Integer(), nullable=True),
            sa.Column("first_human_message", sa.Text(), nullable=True),
            sa.Column("last_ai_message", sa.Text(), nullable=True),
            sa.Column("total_input_tokens", sa.Integer(), nullable=True),
            sa.Column("total_output_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("llm_call_count", sa.Integer(), nullable=True),
            sa.Column("lead_agent_tokens", sa.Integer(), nullable=True),
            sa.Column("subagent_tokens", sa.Integer(), nullable=True),
            sa.Column("middleware_tokens", sa.Integer(), nullable=True),
            sa.Column("follow_up_to_run_id", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("run_id"),
        )
        with op.batch_alter_table("runs", schema=None) as batch_op:
            batch_op.create_index("ix_runs_thread_id", ["thread_id"], unique=False)
            batch_op.create_index("ix_runs_user_id", ["user_id"], unique=False)
            batch_op.create_index("ix_runs_thread_status", ["thread_id", "status"], unique=False)

    if "threads_meta" not in existing:
        # threads_meta table
        op.create_table(
            "threads_meta",
            sa.Column("thread_id", sa.String(length=64), nullable=False),
            sa.Column("assistant_id", sa.String(length=128), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("display_name", sa.String(length=256), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("thread_id"),
        )
        with op.batch_alter_table("threads_meta", schema=None) as batch_op:
            batch_op.create_index("ix_threads_meta_assistant_id", ["assistant_id"], unique=False)
            batch_op.create_index("ix_threads_meta_user_id", ["user_id"], unique=False)

    if "run_events" not in existing:
        # run_events table
        op.create_table(
            "run_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("thread_id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("category", sa.String(length=16), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("event_metadata", sa.JSON(), nullable=True),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("thread_id", "seq", name="uq_events_thread_seq"),
        )
        with op.batch_alter_table("run_events", schema=None) as batch_op:
            batch_op.create_index("ix_run_events_user_id", ["user_id"], unique=False)
            batch_op.create_index("ix_events_thread_cat_seq", ["thread_id", "category", "seq"], unique=False)
            batch_op.create_index("ix_events_run", ["thread_id", "run_id", "seq"], unique=False)

    if "feedback" not in existing:
        # feedback table
        op.create_table(
            "feedback",
            sa.Column("feedback_id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("thread_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("message_id", sa.String(length=64), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("feedback_id"),
            sa.UniqueConstraint("thread_id", "run_id", "user_id", name="uq_feedback_thread_run_user"),
        )
        with op.batch_alter_table("feedback", schema=None) as batch_op:
            batch_op.create_index("ix_feedback_run_id", ["run_id"], unique=False)
            batch_op.create_index("ix_feedback_thread_id", ["thread_id"], unique=False)
            batch_op.create_index("ix_feedback_user_id", ["user_id"], unique=False)

    if "users" not in existing:
        # users table
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("password_hash", sa.String(length=128), nullable=True),
            sa.Column("system_role", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("oauth_provider", sa.String(length=32), nullable=True),
            sa.Column("oauth_id", sa.String(length=128), nullable=True),
            sa.Column("needs_setup", sa.Boolean(), nullable=False),
            sa.Column("token_version", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.create_index("ix_users_email", ["email"], unique=True)
            batch_op.create_index("idx_users_oauth_identity", ["oauth_provider", "oauth_id"], unique=True)


def downgrade() -> None:
    """Drop all core tables."""
    op.drop_table("users")
    op.drop_table("feedback")
    op.drop_table("run_events")
    op.drop_table("threads_meta")
    op.drop_table("runs")
