"""Skill application model for RBAC."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, String, Text, func

from ideer.persistence.base import Base


class SkillApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SkillApplication(Base):
    __tablename__ = "skill_applications"

    id = Column(String, primary_key=True)
    skill_id = Column(String, nullable=False)
    skill_name = Column(String, nullable=False)
    applicant_id = Column(String, nullable=False)
    request_level = Column(String, nullable=False)  # department/public
    department_id = Column(String, nullable=True)  # applicant's department
    reason = Column(Text, default="")
    status = Column(String, default=SkillApplicationStatus.PENDING)
    submitted_at = Column(DateTime, server_default=func.now())
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, default="")


class SkillApplicationResponse(BaseModel):
    """Shared response model for skill applications."""

    id: str
    skill_id: str
    skill_name: str
    applicant_id: str
    request_level: str
    department_id: str | None = None
    reason: str
    status: str
    submitted_at: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_comment: str | None = None
