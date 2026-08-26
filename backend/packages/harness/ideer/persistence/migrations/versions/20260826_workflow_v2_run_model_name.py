"""add workflow-v2 run model_name"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_workflow_v2_run_model_name"
down_revision: str | None = "20260814_resource_catalog_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_v2_runs", sa.Column("model_name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_v2_runs", "model_name")
