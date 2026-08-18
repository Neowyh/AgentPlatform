# 权限模型重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一资源管理体系，将 Skill/Agent/Workflow/Tool 的权限模型重构为基于 resource_metadata 表的统一架构，支持 visibility 审批流程，移除管理员直接修改权限。

**Architecture:** 新增 resource_metadata 和 visibility_applications 两张核心表，替代 .meta.json 文件存储和 skill_applications 表。统一 authz.py 权限检查函数，移除重复的 _check_resource_modify 和 _is_visible_to_user 函数。所有资源 CRUD 操作改为查询 resource_metadata 表。Tool 仅在 resource_metadata 中记录元数据，CRUD 保持现有 MCP 方式不变。

**Tech Stack:** Python 3.12, SQLAlchemy, FastAPI, Alembic, PostgreSQL/SQLite

---

## 文件结构

### 新建文件
- `backend/packages/harness/ideer/persistence/models/resource_metadata.py` — resource_metadata 表模型
- `backend/packages/harness/ideer/persistence/models/visibility_application.py` — visibility_applications 表模型
- `backend/packages/harness/ideer/persistence/migrations/versions/xxx_create_resource_tables.py` — Alembic 迁移脚本
- `backend/packages/harness/ideer/scripts/migrate_meta_json.py` — .meta.json 数据迁移脚本
- `backend/packages/harness/ideer/scripts/migrate_skill_applications.py` — skill_applications 数据迁移脚本
- `backend/app/gateway/routers/visibility_applications.py` — 统一审批 API
- `frontend/src/app/workspace/admin/visibility-applications/page.tsx` — 统一审批中心页面

### 修改文件
- `backend/app/gateway/authz.py:492-521` — 移除 admin 直接修改权限
- `backend/app/gateway/authz.py:448-489` — 移除 dept_admin 隐式同部门浏览
- `backend/app/gateway/routers/skills.py:51-86` — 删除重复函数，使用统一 authz
- `backend/app/gateway/routers/skills.py:570-657` — 删除 update_skill_visibility 端点
- `backend/app/gateway/routers/agents.py:33-59` — 删除重复函数，使用统一 authz
- `backend/app/gateway/routers/agents.py:44-59` — 删除 _can_set_visibility 函数
- `backend/app/gateway/routers/admin_skill_applications.py` — 废弃旧端点

### 删除文件（废弃）
- `backend/packages/harness/ideer/persistence/models/skill_default_config.py` — 废弃
- `backend/packages/harness/ideer/persistence/models/user_skill_preference.py` — 废弃

---

## Task 1: 创建 resource_metadata 数据库模型

**Covers:** 数据库设计 §1.1, 迁移方案 Phase 1

**Files:**
- Create: `backend/packages/harness/ideer/persistence/models/resource_metadata.py`

- [ ] **Step 1: 创建 ResourceMetadata SQLAlchemy 模型**

```python
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
```

- [ ] **Step 2: 在 models/__init__.py 中导出新模型**

在 `backend/packages/harness/ideer/persistence/models/__init__.py` 中添加：
```python
from ideer.persistence.models.resource_metadata import ResourceMetadata
```

- [ ] **Step 3: 运行测试验证模型可以正常导入**

```bash
cd backend && python -c "from ideer.persistence.models.resource_metadata import ResourceMetadata; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/ideer/persistence/models/resource_metadata.py backend/packages/harness/ideer/persistence/models/__init__.py
git commit -m "feat(models): add resource_metadata table model"
```

---

## Task 2: 创建 visibility_applications 数据库模型

**Covers:** 数据库设计 §1.2, 迁移方案 Phase 1

**Files:**
- Create: `backend/packages/harness/ideer/persistence/models/visibility_application.py`

- [ ] **Step 1: 创建 VisibilityApplication SQLAlchemy 模型**

```python
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
    resource_type = Column(String(32), nullable=False)  # 'tool' | 'skill' | 'workflow' | 'agent'
    resource_id = Column(String(255), nullable=False)  # 资源名/标识
    applicant_id = Column(String(64), nullable=False)  # 申请人用户 ID
    current_visibility = Column(String(32), nullable=False)  # 申请时的当前 visibility
    target_visibility = Column(String(32), nullable=False)  # 目标 visibility
    department_id = Column(String(64), nullable=True)  # 资源所属部门
    reason = Column(Text, nullable=False, default="")  # 申请理由
    status = Column(String(20), nullable=False, default="pending")  # pending / approved / rejected / withdrawn
    submitted_at = Column(DateTime, nullable=False)
    reviewed_by = Column(String(64), nullable=True)  # 审批人用户 ID
    reviewed_at = Column(DateTime, nullable=True)  # 审批时间
    review_comment = Column(Text, nullable=False, default="")  # 审批意见
    version = Column(Integer, nullable=False, default=1)  # 乐观锁版本号
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
```

- [ ] **Step 2: 在 models/__init__.py 中导出新模型**

在 `backend/packages/harness/ideer/persistence/models/__init__.py` 中添加：
```python
from ideer.persistence.models.visibility_application import VisibilityApplication, VisibilityApplicationStatus
```

- [ ] **Step 3: 运行测试验证模型可以正常导入**

```bash
cd backend && python -c "from ideer.persistence.models.visibility_application import VisibilityApplication, VisibilityApplicationStatus; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/ideer/persistence/models/visibility_application.py backend/packages/harness/ideer/persistence/models/__init__.py
git commit -m "feat(models): add visibility_applications table model"
```

---

## Task 3: 创建 Alembic 迁移脚本

**Covers:** 迁移方案 Phase 1

**Files:**
- Create: `backend/packages/harness/ideer/persistence/migrations/versions/xxx_create_resource_tables.py`

- [ ] **Step 1: 创建迁移脚本**

```python
"""Create resource_metadata and visibility_applications tables.

Revision ID: xxx_create_resource_tables
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa

revision = "xxx_create_resource_tables"
down_revision = None  # 设置为正确的前序 revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # resource_metadata 表
    op.create_table(
        "resource_metadata",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("department_id", sa.String(64), nullable=True),
        sa.Column("visibility", sa.String(32), nullable=False, server_default="private"),
        sa.Column("imported_from", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("resource_type", "resource_id", name="uq_resource_type_id"),
    )
    op.create_index("ix_resource_metadata_type", "resource_metadata", ["resource_type"])
    op.create_index("ix_resource_metadata_owner", "resource_metadata", ["owner_id"])
    op.create_index("ix_resource_metadata_dept", "resource_metadata", ["department_id"])
    op.create_index("ix_resource_metadata_visibility", "resource_metadata", ["visibility"])
    op.create_index("ix_resource_metadata_deleted", "resource_metadata", ["deleted_at"],
                    postgresql_where="deleted_at IS NOT NULL")

    # visibility_applications 表
    op.create_table(
        "visibility_applications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("applicant_id", sa.String(64), nullable=False),
        sa.Column("current_visibility", sa.String(32), nullable=False),
        sa.Column("target_visibility", sa.String(32), nullable=False),
        sa.Column("department_id", sa.String(64), nullable=True),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("submitted_at", sa.DateTime, nullable=False),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("review_comment", sa.Text, nullable=False, server_default=""),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_visibility_app_status", "visibility_applications", ["status"])
    op.create_index("ix_visibility_app_resource", "visibility_applications", ["resource_type", "resource_id"])
    op.create_index("ix_visibility_app_applicant", "visibility_applications", ["applicant_id"])
    op.create_index("ix_visibility_app_type", "visibility_applications", ["resource_type"])


def downgrade() -> None:
    op.drop_table("visibility_applications")
    op.drop_table("resource_metadata")
```

- [ ] **Step 2: 运行迁移验证**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/ideer/persistence/migrations/
git commit -m "feat(migration): create resource_metadata and visibility_applications tables"
```

---

## Task 4: 重构 authz.py 权限函数

**Covers:** 主文档 §3.2, 迁移方案 Phase 5.1

**Files:**
- Modify: `backend/app/gateway/authz.py:448-521`

- [ ] **Step 1: 修改 check_resource_access 函数**

移除 department_admin 隐式同部门浏览权限（第 484-487 行），使 department_admin 与普通用户一样按 visibility 控制：

```python
def check_resource_access(
    user: UserModel,
    resource_owner_id: str | None,
    resource_department_id: str | None,
    resource_visibility: str,
) -> bool:
    """Check if *user* can read a resource based on RBAC visibility rules.

    Rules (in evaluation order):
    1. ``super_admin`` -- always allowed.
    2. Owner -- always allowed for own resources.
    3. ``public`` visibility -- allowed for everyone.
    4. ``department`` visibility -- allowed if user belongs to the same department.
    5. ``private`` visibility -- only owner and super_admin.

    Returns ``True`` when access is granted, ``False`` otherwise.
    """
    from ideer.persistence.models.user import ResourceVisibility, UserRole

    # super_admin: access everything
    if user.role == UserRole.SUPER_ADMIN:
        return True

    # Owner: always access own resources
    if resource_owner_id and user.id == resource_owner_id:
        return True

    # Public resources: everyone can access
    if resource_visibility == ResourceVisibility.PUBLIC:
        return True

    # Department resources: same department
    if resource_visibility == ResourceVisibility.DEPARTMENT:
        if user.department_id and resource_department_id and user.department_id == resource_department_id:
            return True

    return False
```

- [ ] **Step 2: 修改 check_resource_modify 函数**

移除 super_admin 和 department_admin 的直接修改权限（第 508-519 行），仅保留 owner 检查：

```python
def check_resource_modify(
    user: UserModel,
    resource_owner_id: str | None,
    resource_department_id: str | None,
) -> bool:
    """Check if *user* can modify (edit/delete) a resource.

    Rules:
    1. Owner -- can modify own resources.

    Returns ``True`` when modification is allowed, ``False`` otherwise.
    """
    # Owner: modify own resources
    if resource_owner_id and user.id == resource_owner_id:
        return True

    return False
```

- [ ] **Step 3: 运行现有测试验证修改**

```bash
cd backend && python -m pytest tests/test_authz.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/gateway/authz.py
git commit -m "refactor(authz): remove admin direct modify permissions, enforce owner-only edit"
```

---

## Task 5: 重构 skills.py — 删除重复函数

**Covers:** 主文档 §3.2, 迁移方案 Phase 5.1

**Files:**
- Modify: `backend/app/gateway/routers/skills.py:51-86`

- [ ] **Step 1: 删除 _check_resource_modify 函数（第 51-59 行）**

该函数仅调用 authz.check_resource_modify，应直接使用 authz 函数。

- [ ] **Step 2: 删除 _is_visible_to_user 函数（第 62-86 行）**

该函数功能与 authz.check_resource_access 重叠，应统一使用 authz 函数。

- [ ] **Step 3: 修改所有调用点**

将 skills.py 中所有 `_check_resource_modify(...)` 调用改为直接使用 `authz.check_resource_modify(...)` 或在 HTTP 端点中添加权限检查。

将 skills.py 中所有 `_is_visible_to_user(...)` 调用改为使用 `authz.check_resource_access(...)`。

- [ ] **Step 4: 运行测试验证修改**

```bash
cd backend && python -m pytest tests/test_skills.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/gateway/routers/skills.py
git commit -m "refactor(skills): remove duplicate RBAC functions, use unified authz"
```

---

## Task 6: 重构 agents.py — 删除重复函数

**Covers:** 主文档 §3.2, 迁移方案 Phase 5.1

**Files:**
- Modify: `backend/app/gateway/routers/agents.py:33-59`

- [ ] **Step 1: 删除 _check_resource_modify 函数（第 33-41 行）**

该函数仅调用 authz.check_resource_modify，应直接使用 authz 函数。

- [ ] **Step 2: 删除 _can_set_visibility 函数（第 44-59 行）**

visibility 变更改为通过审批流程，不再需要直接设置权限检查。

- [ ] **Step 3: 删除 _is_visible_to_user 函数（第 172-196 行）**

该函数功能与 authz.check_resource_access 重叠，应统一使用 authz 函数。

- [ ] **Step 4: 修改所有调用点**

将 agents.py 中所有 `_check_resource_modify(...)` 调用改为直接使用 `authz.check_resource_modify(...)` 或在 HTTP 端点中添加权限检查。

将 agents.py 中所有 `_is_visible_to_user(...)` 调用改为使用 `authz.check_resource_access(...)`。

- [ ] **Step 5: 运行测试验证修改**

```bash
cd backend && python -m pytest tests/test_agents.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/gateway/routers/agents.py
git commit -m "refactor(agents): remove duplicate RBAC functions, use unified authz"
```

---

## Task 7: 创建 visibility_applications API

**Covers:** API 规范 §7, 迁移方案 Phase 5.2

**Files:**
- Create: `backend/app/gateway/routers/visibility_applications.py`

- [ ] **Step 1: 创建提交申请端点 POST /api/visibility-applications**

```python
"""Unified visibility application API routes."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.gateway.authz import get_current_rbac_user
from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.user import UserModel, UserRole
from ideer.persistence.models.visibility_application import VisibilityApplication, VisibilityApplicationStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visibility-applications", tags=["visibility-applications"])


class SubmitApplicationRequest(BaseModel):
    resource_type: str = Field(..., description="Resource type: tool/skill/workflow/agent")
    resource_id: str = Field(..., description="Resource name/identifier")
    target_visibility: str = Field(..., pattern="^(private|department|public)$")
    reason: str = ""


class ReviewApplicationRequest(BaseModel):
    action: str = Field(..., pattern="^(approved|rejected)$")
    comment: str = ""
    version: int = Field(..., description="Current version for optimistic locking")


@router.post("")
async def submit_application(
    request: SubmitApplicationRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict:
    """Submit a visibility change application."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            # 查找资源元数据
            stmt = select(ResourceMetadata).where(
                ResourceMetadata.resource_type == request.resource_type,
                ResourceMetadata.resource_id == request.resource_id,
                ResourceMetadata.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()

            if not resource:
                raise HTTPException(status_code=404, detail="Resource not found")

            # 检查权限：仅 owner 可以提交申请
            if resource.owner_id != current_user.id:
                raise HTTPException(status_code=403, detail="Only resource owner can submit visibility application")

            # 检查 target_visibility 不能与 current_visibility 相同
            if request.target_visibility == resource.visibility:
                raise HTTPException(status_code=400, detail="Target visibility cannot be the same as current visibility")

            # 检查是否已有 pending 申请
            stmt = select(VisibilityApplication).where(
                VisibilityApplication.resource_type == request.resource_type,
                VisibilityApplication.resource_id == request.resource_id,
                VisibilityApplication.status == VisibilityApplicationStatus.PENDING,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                raise HTTPException(status_code=409, detail="A pending application already exists for this resource")

            # 创建新申请
            application = VisibilityApplication(
                id=str(uuid.uuid4()),
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                applicant_id=current_user.id,
                current_visibility=resource.visibility,
                target_visibility=request.target_visibility,
                department_id=resource.department_id,
                reason=request.reason,
                status=VisibilityApplicationStatus.PENDING,
                submitted_at=datetime.now(UTC),
                version=1,
                created_at=datetime.now(UTC),
            )
            session.add(application)
            await session.commit()

            return {
                "id": application.id,
                "resource_type": application.resource_type,
                "resource_id": application.resource_id,
                "applicant_id": application.applicant_id,
                "current_visibility": application.current_visibility,
                "target_visibility": application.target_visibility,
                "status": application.status,
                "submitted_at": str(application.submitted_at),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit visibility application: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

- [ ] **Step 2: 创建撤回申请端点 PUT /api/visibility-applications/{id}/withdraw**

```python
@router.put("/{application_id}/withdraw")
async def withdraw_application(
    application_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict:
    """Withdraw a pending visibility application."""
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(VisibilityApplication).where(
                VisibilityApplication.id == application_id,
                VisibilityApplication.status == VisibilityApplicationStatus.PENDING,
            )
            result = await session.execute(stmt)
            application = result.scalar_one_or_none()

            if not application:
                raise HTTPException(status_code=404, detail="Pending application not found")

            # 检查权限：申请人或 super_admin 可以撤回
            if application.applicant_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
                raise HTTPException(status_code=403, detail="Only applicant or super_admin can withdraw application")

            application.status = VisibilityApplicationStatus.WITHDRAWN
            await session.commit()

            return {"message": "Application withdrawn successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to withdraw visibility application %s: %s", application_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

- [ ] **Step 3: 创建审批端点 PUT /api/visibility-applications/{id}**

```python
@router.put("/{application_id}")
async def review_application(
    application_id: str,
    request: ReviewApplicationRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict:
    """Review a visibility application (approve or reject)."""
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(VisibilityApplication).where(
                VisibilityApplication.id == application_id,
            )
            result = await session.execute(stmt)
            application = result.scalar_one_or_none()

            if not application:
                raise HTTPException(status_code=404, detail="Application not found")

            if application.status != VisibilityApplicationStatus.PENDING:
                raise HTTPException(status_code=400, detail="Application is not pending")

            # 检查乐观锁
            if application.version != request.version:
                raise HTTPException(status_code=409, detail="Version conflict, please refresh and retry")

            # dept_admin 不可审批自己的申请
            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                if application.applicant_id == current_user.id:
                    raise HTTPException(status_code=403, detail="Cannot review your own application")
                # dept_admin 仅可审批 department 级
                if application.target_visibility == "public":
                    raise HTTPException(status_code=403, detail="Department admins cannot approve public-level applications")
                # dept_admin 仅可审批同部门
                if application.department_id and application.department_id != current_user.department_id:
                    raise HTTPException(status_code=403, detail="Department admins can only review applications from their own department")

            # 更新审批状态
            application.status = request.action
            application.reviewed_by = current_user.id
            application.reviewed_at = datetime.now(UTC)
            application.review_comment = request.comment
            application.version += 1

            # 如果审批通过，更新资源 visibility
            if request.action == VisibilityApplicationStatus.APPROVED:
                resource_stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == application.resource_type,
                    ResourceMetadata.resource_id == application.resource_id,
                    ResourceMetadata.deleted_at.is_(None),
                )
                resource_result = await session.execute(resource_stmt)
                resource = resource_result.scalar_one_or_none()
                if resource:
                    resource.visibility = application.target_visibility
                    resource.version += 1

            await session.commit()

            return {
                "id": application.id,
                "status": application.status,
                "version": application.version,
                "reviewed_by": application.reviewed_by,
                "reviewed_at": str(application.reviewed_at),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to review visibility application %s: %s", application_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

- [ ] **Step 4: 创建查看待审批端点 GET /api/visibility-applications**

```python
@router.get("")
async def list_applications(
    status: str | None = None,
    resource_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: UserModel = Depends(get_current_rbac_user),
) -> dict:
    """List visibility applications (filtered by status and resource type)."""
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    try:
        async with sf() as session:
            stmt = select(VisibilityApplication)

            if status:
                stmt = stmt.where(VisibilityApplication.status == status)
            if resource_type:
                stmt = stmt.where(VisibilityApplication.resource_type == resource_type)

            # dept_admin 仅看到同部门的申请
            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                stmt = stmt.where(
                    VisibilityApplication.department_id == current_user.department_id,
                    VisibilityApplication.target_visibility != "public",
                )

            # 分页
            offset = (page - 1) * page_size
            stmt = stmt.order_by(VisibilityApplication.submitted_at.desc()).offset(offset).limit(page_size)

            result = await session.execute(stmt)
            applications = result.scalars().all()

            # 获取总数
            count_stmt = select(VisibilityApplication)
            if status:
                count_stmt = count_stmt.where(VisibilityApplication.status == status)
            if resource_type:
                count_stmt = count_stmt.where(VisibilityApplication.resource_type == resource_type)
            if current_user.role == UserRole.DEPARTMENT_ADMIN:
                count_stmt = count_stmt.where(
                    VisibilityApplication.department_id == current_user.department_id,
                    VisibilityApplication.target_visibility != "public",
                )
            total = (await session.execute(count_stmt)).scalar() or 0

            return {
                "applications": [
                    {
                        "id": app.id,
                        "resource_type": app.resource_type,
                        "resource_id": app.resource_id,
                        "applicant_id": app.applicant_id,
                        "current_visibility": app.current_visibility,
                        "target_visibility": app.target_visibility,
                        "reason": app.reason,
                        "status": app.status,
                        "submitted_at": str(app.submitted_at),
                        "reviewed_by": app.reviewed_by,
                        "reviewed_at": str(app.reviewed_at) if app.reviewed_at else None,
                        "review_comment": app.review_comment,
                        "version": app.version,
                    }
                    for app in applications
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
    except Exception as e:
        logger.error("Failed to list visibility applications: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

- [ ] **Step 5: 在 FastAPI 应用中注册新路由**

在 `backend/app/gateway/app.py` 中添加：
```python
from app.gateway.routers import visibility_applications
app.include_router(visibility_applications.router)
```

- [ ] **Step 6: 运行测试验证新 API**

```bash
cd backend && python -m pytest tests/test_visibility_applications.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/gateway/routers/visibility_applications.py backend/app/gateway/app.py
git commit -m "feat(api): add unified visibility_applications API endpoints"
```

---

## Task 8: 废弃旧的 admin skill-applications 端点

**Covers:** 迁移方案 Phase 5.2

**Files:**
- Modify: `backend/app/gateway/routers/admin_skill_applications.py`

- [ ] **Step 1: 修改旧端点返回 410 Gone**

```python
"""Admin skill applications API routes (DEPRECATED)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/admin", tags=["admin-skill-applications"])


@router.get("/skill-applications")
async def list_applications_deprecated():
    """DEPRECATED: Use /api/visibility-applications instead."""
    raise HTTPException(
        status_code=410,
        detail={
            "code": "ENDPOINT_DEPRECATED",
            "message": "This endpoint is deprecated. Use /api/visibility-applications instead.",
        },
    )


@router.get("/skill-applications/{application_id}")
async def get_application_deprecated(application_id: str):
    """DEPRECATED: Use /api/visibility-applications instead."""
    raise HTTPException(
        status_code=410,
        detail={
            "code": "ENDPOINT_DEPRECATED",
            "message": "This endpoint is deprecated. Use /api/visibility-applications instead.",
        },
    )


@router.put("/skill-applications/{application_id}")
async def review_application_deprecated(application_id: str):
    """DEPRECATED: Use /api/visibility-applications instead."""
    raise HTTPException(
        status_code=410,
        detail={
            "code": "ENDPOINT_DEPRECATED",
            "message": "This endpoint is deprecated. Use /api/visibility-applications instead.",
        },
    )
```

- [ ] **Step 2: 运行测试验证旧端点返回 410**

```bash
cd backend && python -m pytest tests/test_admin_skill_applications.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/gateway/routers/admin_skill_applications.py
git commit -m "refactor(api): deprecate old admin skill-applications endpoints"
```

---

## Task 9: 创建 .meta.json 数据迁移脚本

**Covers:** 迁移方案 Phase 2

**Files:**
- Create: `backend/packages/harness/ideer/scripts/migrate_meta_json.py`

- [ ] **Step 1: 创建迁移脚本**

```python
"""Migrate .meta.json files to resource_metadata table.

Usage: python -m ideer.scripts.migrate_meta_json
"""

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import select

from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.resource_metadata import ResourceMetadata

logger = logging.getLogger(__name__)


def migrate_meta_json():
    """Migrate all .meta.json files to resource_metadata table."""
    sf = get_session_factory()
    if sf is None:
        logger.error("Database not initialized")
        return

    # 扫描 skill 和 agent 目录
    meta_files = []

    # Skill .meta.json files
    skills_dir = Path("resources/skills/") / "skills" / "custom"
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            meta_file = skill_dir / ".meta.json"
            if meta_file.exists():
                meta_files.append(("skill", meta_file))

    # Agent .meta.json files
    agents_dir = Path("agents")
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            meta_file = agent_dir / ".meta.json"
            if meta_file.exists():
                meta_files.append(("agent", meta_file))

    imported = 0
    skipped = 0

    for resource_type, meta_file in meta_files:
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            resource_id = meta.get("name", meta_file.parent.name)
            owner_id = meta.get("owner_id", "super_admin")
            department_id = meta.get("department_id")
            visibility = meta.get("visibility", "private")

            async with sf() as session:
                # 幂等检查
                stmt = select(ResourceMetadata).where(
                    ResourceMetadata.resource_type == resource_type,
                    ResourceMetadata.resource_id == resource_id,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    skipped += 1
                    continue

                # 插入新记录
                resource = ResourceMetadata(
                    id=str(uuid.uuid4()),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    owner_id=owner_id,
                    department_id=department_id,
                    visibility=visibility,
                    version=1,
                )
                session.add(resource)
                await session.commit()
                imported += 1

        except Exception as e:
            logger.error("Failed to migrate %s: %s", meta_file, e)

    logger.info("Migration complete: %d imported, %d skipped", imported, skipped)


if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate_meta_json())
```

- [ ] **Step 2: 运行迁移脚本验证**

```bash
cd backend && python -m ideer.scripts.migrate_meta_json
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/ideer/scripts/migrate_meta_json.py
git commit -m "feat(migration): add .meta.json to resource_metadata migration script"
```

---

## Task 10: 创建 skill_applications 数据迁移脚本

**Covers:** 迁移方案 Phase 3

**Files:**
- Create: `backend/packages/harness/ideer/scripts/migrate_skill_applications.py`

- [ ] **Step 1: 创建迁移脚本**

```python
"""Migrate skill_applications to visibility_applications table.

Usage: python -m ideer.scripts.migrate_skill_applications
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from ideer.persistence.engine import get_session_factory
from ideer.persistence.models.skill_application import SkillApplication
from ideer.persistence.models.visibility_application import VisibilityApplication, VisibilityApplicationStatus

logger = logging.getLogger(__name__)


def migrate_skill_applications():
    """Migrate all skill_applications to visibility_applications table."""
    sf = get_session_factory()
    if sf is None:
        logger.error("Database not initialized")
        return

    async def _migrate():
        async with sf() as session:
            # 读取所有 skill_applications
            stmt = select(SkillApplication)
            result = await session.execute(stmt)
            applications = result.scalars().all()

            imported = 0
            skipped = 0

            for app in applications:
                # 幂等检查
                check_stmt = select(VisibilityApplication).where(
                    VisibilityApplication.id == app.id,
                )
                check_result = await session.execute(check_stmt)
                if check_result.scalar_one_or_none():
                    skipped += 1
                    continue

                # 字段映射
                visibility_app = VisibilityApplication(
                    id=app.id,
                    resource_type="skill",
                    resource_id=app.skill_id,
                    applicant_id=app.applicant_id,
                    current_visibility="private",  # 默认值，需要从 resource_metadata 获取
                    target_visibility=app.request_level,
                    department_id=app.department_id,
                    reason=app.reason or "",
                    status=app.status,
                    submitted_at=app.submitted_at or datetime.now(UTC),
                    reviewed_by=app.reviewed_by,
                    reviewed_at=app.reviewed_at,
                    review_comment=app.review_comment or "",
                    version=1,
                    created_at=app.submitted_at or datetime.now(UTC),
                )
                session.add(visibility_app)
                imported += 1

            await session.commit()
            logger.info("Migration complete: %d imported, %d skipped", imported, skipped)

    import asyncio
    asyncio.run(_migrate())


if __name__ == "__main__":
    migrate_skill_applications()
```

- [ ] **Step 2: 运行迁移脚本验证**

```bash
cd backend && python -m ideer.scripts.migrate_skill_applications
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/ideer/scripts/migrate_skill_applications.py
git commit -m "feat(migration): add skill_applications to visibility_applications migration script"
```

---

## Task 11: 删除 skills.py 中的 update_skill_visibility 端点

**Covers:** 迁移方案 Phase 5.2, 主文档 §4.2

**Files:**
- Modify: `backend/app/gateway/routers/skills.py:570-657`

- [ ] **Step 1: 删除 update_skill_visibility 端点（第 570-657 行）**

该端点允许直接修改 visibility，违反设计原则。visibility 变更必须通过审批流程。

- [ ] **Step 2: 运行测试验证修改**

```bash
cd backend && python -m pytest tests/test_skills.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/gateway/routers/skills.py
git commit -m "refactor(skills): remove direct visibility update endpoint"
```

---

## Task 12: 创建前端统一审批中心页面

**Covers:** 主文档 §13.2, 迁移方案 Phase 6

**Files:**
- Create: `frontend/src/app/workspace/admin/visibility-applications/page.tsx`

- [ ] **Step 1: 创建审批中心页面组件**

```tsx
"use client";

import { useEffect, useState } from "react";

interface Application {
  id: string;
  resource_type: string;
  resource_id: string;
  applicant_id: string;
  current_visibility: string;
  target_visibility: string;
  reason: string;
  status: string;
  submitted_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string;
  version: number;
}

export default function VisibilityApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: "pending", resource_type: "" });

  useEffect(() => {
    fetchApplications();
  }, [filter]);

  const fetchApplications = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.status) params.append("status", filter.status);
      if (filter.resource_type) params.append("resource_type", filter.resource_type);

      const response = await fetch(`/api/visibility-applications?${params}`);
      const data = await response.json();
      setApplications(data.applications || []);
    } catch (error) {
      console.error("Failed to fetch applications:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (applicationId: string, action: "approved" | "rejected", comment: string, version: number) => {
    try {
      const response = await fetch(`/api/visibility-applications/${applicationId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, comment, version }),
      });

      if (response.ok) {
        fetchApplications();
      } else {
        const error = await response.json();
        alert(error.detail || "Failed to review application");
      }
    } catch (error) {
      console.error("Failed to review application:", error);
    }
  };

  const handleWithdraw = async (applicationId: string) => {
    try {
      const response = await fetch(`/api/visibility-applications/${applicationId}/withdraw`, {
        method: "PUT",
      });

      if (response.ok) {
        fetchApplications();
      } else {
        const error = await response.json();
        alert(error.detail || "Failed to withdraw application");
      }
    } catch (error) {
      console.error("Failed to withdraw application:", error);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Visibility Applications</h1>

      {/* 筛选器 */}
      <div className="flex gap-4 mb-6">
        <select
          value={filter.status}
          onChange={(e) => setFilter({ ...filter, status: e.target.value })}
          className="border rounded px-3 py-2"
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="withdrawn">Withdrawn</option>
          <option value="">All</option>
        </select>

        <select
          value={filter.resource_type}
          onChange={(e) => setFilter({ ...filter, resource_type: e.target.value })}
          className="border rounded px-3 py-2"
        >
          <option value="">All Types</option>
          <option value="tool">Tool</option>
          <option value="skill">Skill</option>
          <option value="workflow">Workflow</option>
          <option value="agent">Agent</option>
        </select>
      </div>

      {/* 申请列表 */}
      {loading ? (
        <div className="text-center py-8">Loading...</div>
      ) : applications.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No applications found</div>
      ) : (
        <div className="space-y-4">
          {applications.map((app) => (
            <div key={app.id} className="border rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-semibold">
                    {app.resource_type.toUpperCase()}: {app.resource_id}
                  </div>
                  <div className="text-sm text-gray-500">
                    Applicant: {app.applicant_id}
                  </div>
                  <div className="text-sm text-gray-500">
                    {app.current_visibility} → {app.target_visibility}
                  </div>
                  {app.reason && (
                    <div className="text-sm mt-2">Reason: {app.reason}</div>
                  )}
                </div>
                <div className="text-right">
                  <div className={`inline-block px-2 py-1 rounded text-sm ${
                    app.status === "pending" ? "bg-yellow-100 text-yellow-800" :
                    app.status === "approved" ? "bg-green-100 text-green-800" :
                    "bg-red-100 text-red-800"
                  }`}>
                    {app.status}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {new Date(app.submitted_at).toLocaleString()}
                  </div>
                </div>
              </div>

              {/* 操作按钮 */}
              {app.status === "pending" && (
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => {
                      const comment = prompt("Review comment (optional):");
                      handleReview(app.id, "approved", comment || "", app.version);
                    }}
                    className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => {
                      const comment = prompt("Rejection reason:");
                      if (comment) handleReview(app.id, "rejected", comment, app.version);
                    }}
                    className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => handleWithdraw(app.id)}
                    className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
                  >
                    Withdraw
                  </button>
                </div>
              )}

              {/* 审批结果 */}
              {app.reviewed_at && (
                <div className="mt-4 text-sm text-gray-500">
                  Reviewed by {app.reviewed_by} at {new Date(app.reviewed_at).toLocaleString()}
                  {app.review_comment && ` - "${app.review_comment}"`}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 在前端路由中注册新页面**

确保 Next.js App Router 能识别新页面。

- [ ] **Step 3: 运行前端测试验证**

```bash
cd frontend && pnpm test
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/workspace/admin/visibility-applications/
git commit -m "feat(frontend): add unified visibility applications approval center"
```

---

## Task 13: 废弃旧的 skill_default_configs 和 user_skill_preferences 表引用

**Covers:** 迁移方案 Phase 4

**Files:**
- Search and modify: All files referencing skill_default_configs or user_skill_preferences

- [ ] **Step 1: 全局搜索旧表引用**

```bash
cd backend && grep -r "skill_default_configs\|user_skill_preferences" --include="*.py"
```

- [ ] **Step 2: 移除所有引用**

逐一删除或注释掉所有对旧表的引用。

- [ ] **Step 3: 运行测试验证修改**

```bash
cd backend && python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove deprecated skill_default_configs and user_skill_preferences references"
```

---

## Task 14: 运行完整测试套件

**Covers:** 所有任务的验证

**Files:** 无

- [ ] **Step 1: 运行后端测试**

```bash
cd backend && python -m pytest tests/ -v
```

- [ ] **Step 2: 运行前端测试**

```bash
cd frontend && pnpm test
```

- [ ] **Step 3: 运行 lint 检查**

```bash
cd backend && make lint
cd frontend && pnpm check
```

- [ ] **Step 4: 确认所有测试通过后提交最终代码**

```bash
git add -A
git commit -m "chore: complete permission model refactoring - all tests passing"
```

---

## 完成标准

- [ ] 所有新表创建成功（resource_metadata, visibility_applications）
- [ ] 所有索引创建成功
- [ ] authz.py 权限函数统一完成
- [ ] 重复函数（_check_resource_modify、_is_visible_to_user）已删除
- [ ] 审批接口迁移到 visibility_applications
- [ ] 旧端点已废弃（返回 410 Gone）
- [ ] 所有 API 接口测试通过
- [ ] 权限边界测试通过
- [ ] 并发编辑测试通过
- [ ] 前端审批中心页面功能正常
