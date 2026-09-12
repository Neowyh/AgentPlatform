"""add workflow-v2 event cursor and immutable run department"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_workflow_v2_governance"
down_revision: str | None = "20260715_workflow_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("workflow_v2_runs")}
    if "department_id" not in columns:
        op.add_column("workflow_v2_runs", sa.Column("department_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_v2_runs", "department_id")
