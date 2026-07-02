"""Skill default config model for RBAC."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint, func

from ideer.persistence.base import Base


class SkillDefaultConfig(Base):
    __tablename__ = "skill_default_configs"
    __table_args__ = (UniqueConstraint("scope", "scope_id", "skill_name", name="uq_skill_default_scope_skill"),)

    id = Column(String, primary_key=True)
    scope = Column(String, nullable=False)  # global/department
    scope_id = Column(String, nullable=True)  # department_id (仅 department scope)
    skill_name = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False)
    user_override_allowed = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
