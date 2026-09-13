"""add KnowledgeBase dependency declaration fields

Revision ID: 20260911_resource_dependency_kb_fields
Revises: 20260911_knowledge_bases
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_resource_dependency_kb_fields"
down_revision: str | None = "20260911_knowledge_bases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = set()
    if bind is not None:
        existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("resource_dependencies")}
    with op.batch_alter_table("resource_dependencies") as batch_op:
        if "dependency_mode" not in existing_columns:
            batch_op.add_column(sa.Column("dependency_mode", sa.String(length=16), nullable=True))
        if "revision_id" not in existing_columns:
            batch_op.add_column(sa.Column("revision_id", sa.String(length=36), nullable=True))
        if "required" not in existing_columns:
            batch_op.add_column(sa.Column("required", sa.Boolean(), nullable=True))
        if "purpose" not in existing_columns:
            batch_op.add_column(sa.Column("purpose", sa.String(length=256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("resource_dependencies") as batch_op:
        batch_op.drop_column("purpose")
        batch_op.drop_column("required")
        batch_op.drop_column("revision_id")
        batch_op.drop_column("dependency_mode")
