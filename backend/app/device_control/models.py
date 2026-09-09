"""Persistence models for user-bound Local Runtime devices."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from deerflow.persistence.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class DeviceStatus(StrEnum):
    PENDING = "pending"
    ONLINE = "online"
    OFFLINE = "offline"
    REVOKED = "revoked"
    BLOCKED = "blocked"
    OUTDATED = "outdated"


class PairingStatus(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    EXPIRED = "expired"


class DeviceModel(Base):
    """A public-key identity owned by one AgentPlatform user."""

    __tablename__ = "device_control_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DeviceStatus.PENDING)
    protocol_version: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime_version: Mapped[str] = mapped_column(String(64), nullable=False)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_device_control_owner_name"),
        UniqueConstraint("public_key", name="uq_device_control_public_key"),
        Index("ix_device_control_owner_status", "owner_id", "status"),
        Index("ix_device_control_last_seen", "last_seen"),
    )


class PairingSessionModel(Base):
    """Short-lived owner-authorized pairing challenge."""

    __tablename__ = "device_control_pairing_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users_ext.id", ondelete="CASCADE"), nullable=False)
    code_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PairingStatus.OPEN)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (Index("ix_device_control_pairing_owner_status", "owner_id", "status"),)


class DeviceSessionModel(Base):
    """Hashed, short-lived credential for one outbound device session."""

    __tablename__ = "device_control_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("device_control_devices.id", ondelete="CASCADE"), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_device_control_sessions_device", "device_id", "expires_at"),)
