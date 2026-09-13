"""add revision integrity reconciliation records (M4 ticket 05)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_knowledge_revision_integrity"
down_revision: str | None = "20260913_run_knowledge_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("knowledge_base_revisions")}
    if "integrity_status" not in existing:
        op.add_column("knowledge_base_revisions", sa.Column("integrity_status", sa.String(length=32), nullable=True))
    if "integrity_checked_at" not in existing:
        op.add_column("knowledge_base_revisions", sa.Column("integrity_checked_at", sa.DateTime(timezone=True), nullable=True))
    if not inspector.has_table("knowledge_revision_checks"):
        op.create_table(
            "knowledge_revision_checks",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "knowledge_base_id",
                sa.String(length=36),
                sa.ForeignKey("knowledge_bases.resource_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("revision_id", sa.String(length=36), sa.ForeignKey("knowledge_base_revisions.id", ondelete="CASCADE"), nullable=True),
            sa.Column("trigger", sa.String(length=16), nullable=False),
            sa.Column("outcome", sa.String(length=32), nullable=False),
            sa.Column("findings_json", sa.JSON(), nullable=False),
            sa.Column("checked_by", sa.String(length=64), sa.ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True),
            sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.CheckConstraint("trigger in ('manual','scheduled')", name="ck_knowledge_revision_checks_trigger"),
            sa.Index("ix_knowledge_revision_checks_kb_checked", "knowledge_base_id", "checked_at"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("knowledge_revision_checks"):
        op.drop_table("knowledge_revision_checks")
    existing = {column["name"] for column in inspector.get_columns("knowledge_base_revisions")}
    if "integrity_checked_at" in existing:
        op.drop_column("knowledge_base_revisions", "integrity_checked_at")
    if "integrity_status" in existing:
        op.drop_column("knowledge_base_revisions", "integrity_status")
