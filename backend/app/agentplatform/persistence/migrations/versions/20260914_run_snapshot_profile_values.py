"""freeze retrieval/embedding profile values into run snapshots (M4 review fix)

A hash alone cannot be resolved back to the values in effect at freeze time;
ticket 03 asks for "actual values or a resolvable immutable reference", so
the snapshot carries both.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_run_snapshot_profile_values"
down_revision: str | None = "20260914_knowledge_orphan_check_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILE_COLUMNS = (
    ("retrieval_profile_json", sa.JSON()),
    ("embedding_profile_json", sa.JSON()),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("run_resource_snapshots")}
    for name, column_type in _PROFILE_COLUMNS:
        if name not in existing:
            op.add_column("run_resource_snapshots", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    for name, _column_type in reversed(_PROFILE_COLUMNS):
        op.drop_column("run_resource_snapshots", name)
