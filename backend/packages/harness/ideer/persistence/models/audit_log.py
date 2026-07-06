"""Audit log model for tracking key operations."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.sql import func

from ideer.persistence.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True)
    actor_id = Column(String(64), ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(32), nullable=True)
    resource_id = Column(String(255), nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_actor", "actor_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
        Index("ix_audit_time", "created_at"),
    )
