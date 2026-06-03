"""User and Department models for RBAC."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from ideer.persistence.base import Base


class UserRole(StrEnum):
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

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    role = Column(String, default=UserRole.USER)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)

    department = relationship("DepartmentModel", back_populates="members")
