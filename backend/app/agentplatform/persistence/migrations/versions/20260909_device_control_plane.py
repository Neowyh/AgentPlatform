"""add device identity, pairing, and session tables

Revision ID: 20260909_device_control_plane
Revises: 20260908_unify_migration_chains
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_device_control_plane"
down_revision: str | None = "20260908_unify_migration_chains"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Gateway bootstrap may encounter a pre-versioned database whose current
    # ORM metadata was already created by ``create_all``.  Treat the device
    # family as already applied in that shape so upgrading from the legacy
    # runtime head does not replay CREATE TABLE statements.
    if sa.inspect(op.get_bind()).has_table("device_control_devices"):
        return
    op.create_table(
        "device_control_devices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=64), sa.ForeignKey("users_ext.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("protocol_version", sa.String(length=32), nullable=False),
        sa.Column("runtime_version", sa.String(length=64), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("policy_hash", sa.String(length=128), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", name="uq_device_control_owner_name"),
        sa.UniqueConstraint("public_key", name="uq_device_control_public_key"),
    )
    op.create_index("ix_device_control_owner_status", "device_control_devices", ["owner_id", "status"])
    op.create_index("ix_device_control_last_seen", "device_control_devices", ["last_seen"])
    op.create_table(
        "device_control_pairing_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=64), sa.ForeignKey("users_ext.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token_digest", sa.String(length=64), nullable=True, unique=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_control_pairing_owner_status", "device_control_pairing_sessions", ["owner_id", "status"])
    op.create_table(
        "device_control_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("device_id", sa.String(length=36), sa.ForeignKey("device_control_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_device_control_sessions_device", "device_control_sessions", ["device_id", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_device_control_sessions_device", table_name="device_control_sessions")
    op.drop_table("device_control_sessions")
    op.drop_index("ix_device_control_pairing_owner_status", table_name="device_control_pairing_sessions")
    op.drop_table("device_control_pairing_sessions")
    op.drop_index("ix_device_control_last_seen", table_name="device_control_devices")
    op.drop_index("ix_device_control_owner_status", table_name="device_control_devices")
    op.drop_table("device_control_devices")
