"""freeze knowledge revision data into run snapshots (M4 ticket 03)"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_run_knowledge_snapshot"
down_revision: str | None = "20260913_knowledge_base_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SNAPSHOT_COLUMNS = (
    ("knowledge_revision_id", sa.String(length=36)),
    ("knowledge_revision_no", sa.Integer()),
    ("manifest_hash", sa.String(length=64)),
    ("provider_type", sa.String(length=32)),
    ("provider_dataset_id", sa.String(length=128)),
    ("retrieval_profile_hash", sa.String(length=64)),
    ("embedding_profile_hash", sa.String(length=64)),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("run_resource_snapshots")}
    for name, column_type in _SNAPSHOT_COLUMNS:
        if name not in existing:
            op.add_column("run_resource_snapshots", sa.Column(name, column_type, nullable=True))

    kb_columns = {column["name"] for column in inspector.get_columns("knowledge_bases")}
    if "active_revision_id" in kb_columns:
        has_fk = any("knowledge_base_revisions" in (fk.get("referred_table") or "") and "active_revision_id" in (fk.get("constrained_columns") or []) for fk in inspector.get_foreign_keys("knowledge_bases"))
        if not has_fk:
            with op.batch_alter_table("knowledge_bases") as batch_op:
                batch_op.create_foreign_key(
                    "fk_knowledge_bases_active_revision",
                    "knowledge_base_revisions",
                    ["active_revision_id"],
                    ["id"],
                )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_bases") as batch_op:
        batch_op.drop_constraint("fk_knowledge_bases_active_revision", type_="foreignkey")
    for name, _column_type in reversed(_SNAPSHOT_COLUMNS):
        op.drop_column("run_resource_snapshots", name)
