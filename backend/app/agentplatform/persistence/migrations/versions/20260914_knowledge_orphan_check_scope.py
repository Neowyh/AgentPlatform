"""add orphan checks scoped to the reconciliation run (M4 review fix)

Orphan findings belong to a reconciliation run, not to one KnowledgeBase:
``knowledge_revision_checks.knowledge_base_id`` becomes nullable so a run
records its orphan observation once instead of duplicating it per KB (or
losing it when no published revisions exist).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_knowledge_orphan_check_scope"
down_revision: str | None = "20260913_knowledge_revision_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"]: column for column in inspector.get_columns("knowledge_revision_checks")}
    column = existing.get("knowledge_base_id")
    if column is not None and column.get("nullable") is False:
        with op.batch_alter_table("knowledge_revision_checks") as batch_op:
            batch_op.alter_column("knowledge_base_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("knowledge_revision_checks") as batch_op:
        batch_op.alter_column("knowledge_base_id", existing_type=sa.String(length=36), nullable=False)
