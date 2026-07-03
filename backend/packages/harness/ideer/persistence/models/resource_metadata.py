"""Resource metadata model for unified resource management."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from ideer.persistence.base import Base


class ResourceMetadata(Base):
    """Unified metadata for all resource types (skill/workflow/agent/tool)."""

    __tablename__ = "resource_metadata"

    id = Column(String(64), primary_key=True)
    resource_type = Column(String(32), nullable=False)  # 'tool' | 'skill' | 'workflow' | 'agent'
    resource_id = Column(String(255), nullable=False)  # 资源名/标识
    owner_id = Column(String(64), nullable=False)  # 创建者用户 ID
    department_id = Column(String(64), nullable=True)  # 创建者所属部门
    visibility = Column(String(32), nullable=False, default="private")  # private | department | public
    imported_from = Column(Text, nullable=True)  # 导入来源信息
    version = Column(Integer, nullable=False, default=1)  # 乐观锁版本号
    deleted_at = Column(DateTime, nullable=True)  # soft delete 时间戳
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("resource_type", "resource_id", name="uq_resource_type_id"),
        Index("ix_resource_metadata_type", "resource_type"),
        Index("ix_resource_metadata_owner", "owner_id"),
        Index("ix_resource_metadata_dept", "department_id"),
        Index("ix_resource_metadata_visibility", "visibility"),
        Index("ix_resource_metadata_deleted", "deleted_at", postgresql_where="deleted_at IS NOT NULL"),
    )
