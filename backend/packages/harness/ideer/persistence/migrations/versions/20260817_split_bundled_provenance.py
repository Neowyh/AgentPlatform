"""Split bundled provenance out of storage_kind

storage_kind becomes a pure storage mechanism dimension with two values
('filesystem' | 'database'); the provenance dimension ('user' | 'bundled')
tracks whether a resource is provisioned from the bundled manifest.

Backfills existing 'bundled' rows: provenance='bundled' and storage_kind
rewritten by resource type (workflow -> database, others -> filesystem).

Revision ID: 20260817_split_bundled_provenance
Revises: 20260814_resource_catalog_v2
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_split_bundled_provenance"
down_revision: str | None = "20260814_resource_catalog_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resources", sa.Column("provenance", sa.String(length=16), nullable=True))
    op.execute("UPDATE resources SET provenance = 'bundled' WHERE storage_kind = 'bundled'")
    op.execute("UPDATE resources SET provenance = 'user' WHERE provenance IS NULL")
    op.execute("UPDATE resources SET storage_kind = 'database' WHERE storage_kind = 'bundled' AND type = 'workflow'")
    op.execute("UPDATE resources SET storage_kind = 'filesystem' WHERE storage_kind = 'bundled'")
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_constraint("ck_resources_storage_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_resources_storage_kind",
            "storage_kind IN ('filesystem', 'database')",
        )
        batch_op.create_check_constraint("ck_resources_provenance", "provenance IN ('user', 'bundled')")
        batch_op.alter_column("provenance", nullable=False, server_default="user")


def downgrade() -> None:
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_constraint("ck_resources_provenance", type_="check")
        batch_op.alter_column("provenance", nullable=True, server_default=None)
    op.execute("UPDATE resources SET storage_kind = 'bundled' WHERE provenance = 'bundled'")
    op.drop_column("resources", "provenance")
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_constraint("ck_resources_storage_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_resources_storage_kind",
            "storage_kind IN ('filesystem', 'database', 'bundled')",
        )
