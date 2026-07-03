"""Visibility application model for unified resource approval."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import validates

from ideer.persistence.base import Base


class VisibilityApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class VisibilityApplication(Base):
    """Visibility change application for all resource types."""

    __tablename__ = "visibility_applications"

    id = Column(String(64), primary_key=True)
    resource_type = Column(String(32), nullable=False)
    resource_id = Column(String(255), nullable=False)
    applicant_id = Column(String(64), nullable=False)
    current_visibility = Column(String(32), nullable=False)
    target_visibility = Column(String(32), nullable=False)
    department_id = Column(String(64), nullable=True)
    reason = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")
    submitted_at = Column(DateTime, nullable=False)
    reviewed_by = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("resource_type", "resource_id", name="uq_visibility_app_pending"),
        Index("ix_visibility_app_status", "status"),
        Index("ix_visibility_app_resource", "resource_type", "resource_id"),
        Index("ix_visibility_app_applicant", "applicant_id"),
        Index("ix_visibility_app_type", "resource_type"),
    )

    @validates("target_visibility", "current_visibility")
    def validate_visibility(self, key, value):
        if value not in ("private", "department", "public"):
            raise ValueError(f"Invalid visibility: {value}")
        return value

    @validates("status")
    def validate_status(self, key, value):
        if value not in ("pending", "approved", "rejected", "withdrawn"):
            raise ValueError(f"Invalid status: {value}")
        return value
