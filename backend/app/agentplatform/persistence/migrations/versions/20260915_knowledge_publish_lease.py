"""add durable publish lease and execution token for knowledge revisions"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_knowledge_publish_lease"
down_revision: tuple[str, str] = (
    "20260914_run_snapshot_profile_values",
    "20260914_visibility_knowledge_base",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUMNS = (
    ("publish_lease_owner", sa.String(length=128)),
    ("publish_lease_until", sa.DateTime(timezone=True)),
    ("publish_execution_token", sa.String(length=64)),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("knowledge_base_revisions")}
    for name, column_type in _COLUMNS:
        if name not in existing:
            op.add_column("knowledge_base_revisions", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    for name, _column_type in reversed(_COLUMNS):
        op.drop_column("knowledge_base_revisions", name)
