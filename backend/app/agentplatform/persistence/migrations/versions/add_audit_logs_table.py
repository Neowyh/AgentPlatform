"""add audit_logs table

Revision ID: add_audit_logs
Revises: fix_idx_001
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_audit_logs"
down_revision: str | None = "fix_idx_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names()) if bind is not None else set()
    if "audit_logs" not in existing:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("actor_id", sa.String(length=64), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("resource_type", sa.String(length=32), nullable=True),
            sa.Column("resource_id", sa.String(length=255), nullable=True),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_id"], ["users_ext.id"], name="fk_audit_logs_actor", ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("audit_logs")} if bind is not None and "audit_logs" in existing else set()
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        for name, columns in {
            "ix_audit_actor": ["actor_id"],
            "ix_audit_action": ["action"],
            "ix_audit_resource": ["resource_type", "resource_id"],
            "ix_audit_time": ["created_at"],
        }.items():
            if name not in indexes:
                batch_op.create_index(name, columns)


def downgrade() -> None:
    op.drop_table("audit_logs")
