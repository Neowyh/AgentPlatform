"""User and Department models for RBAC."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import relationship

from ideer.persistence.base import Base


class UserRole(StrEnum):
    VIEWER = "viewer"
    USER = "user"
    DEPARTMENT_ADMIN = "department_admin"
    SUPER_ADMIN = "super_admin"


class ResourceVisibility(StrEnum):
    PRIVATE = "private"
    DEPARTMENT = "department"
    PUBLIC = "public"


class DepartmentModel(Base):
    __tablename__ = "departments"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())

    members = relationship("UserModel", back_populates="department")


class UserModel(Base):
    __tablename__ = "users_ext"
    __table_args__ = (
        Index("ix_users_ext_role", "role"),
        Index("ix_users_ext_department_id", "department_id"),
    )

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    role = Column(String, default=UserRole.USER, server_default=UserRole.USER, nullable=False)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    disabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)

    department = relationship("DepartmentModel", back_populates="members")
