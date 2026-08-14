"""Visibility application model for unified resource approval."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import DDL, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, event, func
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
    applicant_id = Column(String(64), ForeignKey("users_ext.id"), nullable=False)
    current_visibility = Column(String(32), nullable=False)
    target_visibility = Column(String(32), nullable=False)
    department_id = Column(String(64), ForeignKey("departments.id"), nullable=True)
    reason = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")
    submitted_at = Column(DateTime, nullable=False, server_default=func.now())
    reviewed_by = Column(String(64), ForeignKey("users_ext.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("resource_type IN ('tool', 'skill', 'workflow', 'agent')", name="ck_visibility_app_resource_type"),
        CheckConstraint("version >= 1", name="ck_visibility_app_version_positive"),
        Index("ix_visibility_app_status", "status"),
        Index("ix_visibility_app_resource", "resource_type", "resource_id"),
        Index("ix_visibility_app_applicant", "applicant_id"),
        Index("ix_visibility_app_type", "resource_type"),
    )

    @validates("target_visibility", "current_visibility")
    def validate_visibility(self, key, value):
        from ideer.persistence.models.user import ResourceVisibility

        valid_values = {v.value for v in ResourceVisibility}
        if value not in valid_values:
            raise ValueError(f"Invalid visibility: {value}")
        return value

    @validates("status")
    def validate_status(self, key, value):
        valid_values = {v.value for v in VisibilityApplicationStatus}
        if value not in valid_values:
            raise ValueError(f"Invalid status: {value}")
        return value


# Cross-DB partial unique index: only one PENDING application per resource
# owner. Scoped by applicant_id so same-named resources owned by different
# users have independent application flows.
# Uses raw SQL DDL instead of postgresql_where (which SQLite ignores).
event.listen(
    VisibilityApplication.__table__,
    "after_create",
    DDL(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_visibility_app_pending ON visibility_applications(resource_type, resource_id, applicant_id) WHERE status = 'pending'",
    ),
)
