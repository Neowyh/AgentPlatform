"""User skill preference model for RBAC."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, String, func

from ideer.persistence.base import Base


class UserSkillPreference(Base):
    __tablename__ = "user_skill_preferences"

    user_id = Column(String, primary_key=True)
    skill_name = Column(String, primary_key=True)
    enabled = Column(Boolean, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
