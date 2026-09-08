"""add departments and users_ext tables

Revision ID: 16147afec43b
Revises:
Create Date: 2026-06-03 14:33:15.523757

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16147afec43b"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create departments and users_ext tables for RBAC.

    PATCH (2026-09-08, unified migration chain / PATCH-006 closure): the
    docstring previously claimed ``checkfirst=True`` semantics, but the
    ``op.create_table`` calls were never actually guarded. The unified
    chain (merge revision ``20260908_unify_migration_chains``) can replay
    this revision against databases where the Gateway's ``create_all``
    already created both tables (e.g. TUI-shaped databases recorded at the
    runtime head). The inspector guard below implements the documented
    behavior without changing the applied DDL. Recorded in
    ``docs/upgrades/deerflow-main-0f7d8709/UPSTREAM_PATCH_LEDGER.md``.
    """
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "departments" not in existing:
        op.create_table(
            "departments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    if "users_ext" not in existing:
        op.create_table(
            "users_ext",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("username", sa.String(length=128), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=True),
            sa.Column("department_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )


def downgrade() -> None:
    """Drop departments and users_ext tables."""
    op.drop_table("users_ext")
    op.drop_table("departments")
