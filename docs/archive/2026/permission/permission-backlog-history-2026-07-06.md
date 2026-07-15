# 权限模型重构 — 待实现代码功能清单

> 本文档记录经 v1.3 文档修订后，尚未实现的代码功能。各条目来源于《权限模型重构_对抗式审查报告》中识别的问题，经决策后写入设计文档，待落地执行。

> 生成日期：2026-07-06 | 关联版本：主文档 v1.3、API规范 v1.3、数据库设计 v1.3、迁移方案 v1.3

---

## 目录

1. [MCP_GET_AUTH — GET /api/mcp/config 增加认证](#1-mcp_get_auth)
2. [MCP_PUT_TIGHTEN — PUT /api/mcp/config 权限收紧](#2-mcp_put_tighten)
3. [AUDIT_TABLE — audit_logs 建表与模型](#3-audit_table)
4. [INDEX_FIX — resource_metadata 索引修正](#4-index_fix)
5. [TOOL_BACKFILL — 存量 Tool 数据回填脚本](#5-tool_backfill)
6. [WORKFLOW_BACKFILL — 存量 Workflow 数据回填脚本](#6-workflow_backfill)
7. [DEPRECATE_TABLES — 废弃表 DROP 迁移](#7-deprecate_tables)
8. [TOOL_API — 修复 Tool API 数据源 + 收紧 MCP 写通道](#8-tool_api)
9. [AUDIT_LOGGING — 审计日志埋点](#9-audit_logging)
10. [AUDIT_API — 审计日志 API](#10-audit_api)
11. [WORKFLOW_RUN_VISIBILITY — Workflow 运行历史 visibility 校验](#11-workflow_run_visibility)
12. [WITHDRAW_LOCK — 撤回申请乐观锁](#12-withdraw_lock)
13. [AUDIT_PAGE — 审计日志前端页面](#13-audit_page)

---

## 1. MCP_GET_AUTH — GET /api/mcp/config 增加认证

### 需求来源

- **问题**: A1（MCP 接口绕过全部权限模型）
- **文档依据**: 迁移方案 v1.3 §2.3（MCP 接口权限收紧过渡措施）
- **API 规范**: §4（Tool CRUD 已纳入统一管理）
- **严重度**: 🔴 严重 — 未登录用户可读取全量 MCP 配置

### 现状

`mcp.py:161-191` — `GET /api/mcp/config` 端点**完全无认证装饰器**，无 `Depends(get_current_rbac_user)`。任何未登录请求可读取 MCP 服务器配置（含已 mask 的秘钥元信息、服务器地址、传输类型等）。

### 解决方案

```python
# mcp.py:161 修改
# 当前：
@router.get("/config")
async def get_mcp_configuration(request: Request):
    ...

# 改为：
@router.get("/config")
async def get_mcp_configuration(
    request: Request,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    ...
```

增加 `Depends(get_current_rbac_user)` 即可，无需特定角色校验（任何认证用户可读）。

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | `backend/app/gateway/routers/mcp.py` |
| 修改量 | +3 行（增加 import + 参数） |
| 影响范围 | 极小，仅认证拦截 |
| 测试 | 验证未认证请求返回 401，认证用户正常返回 |
| 耗时 | 0.2 人天 |
| 所属 Phase | Phase 1 |

---

## 2. MCP_PUT_TIGHTEN — PUT /api/mcp/config 权限收紧（已合并到 #8）

> **本条目已合并到 Phase 5 的 [#8 TOOL_API](#8-tool_api)。** 同一个变更（装饰器从 `USER+` 改为 `SUPER_ADMIN`）将在 #8 中一并执行，不在 Phase 1 单独执行。

---

## 3. AUDIT_TABLE — audit_logs 建表与模型

### 需求来源

- **问题**: A2（无审计日志，安全事件不可追溯）
- **文档依据**: 主文档 v1.3 §0（第一期清单新增 audit_logs）、数据库设计 v1.3 §1.3
- **严重度**: 🔴 严重 — 违规安全基线（不可否认性）

### 现状

- 无 `audit_logs` 表（数据库不存在）
- 无迁移文件创建该表
- 无 ORM 模型定义
- 无 `record_audit()` 工具函数

### 解决方案

**步骤 A — 编写数据库迁移**（Alembic）：

```python
"""add audit_logs table

Revision ID: xyz
Revises: <current_head>
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.String(64), sa.ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_time", "audit_logs", ["created_at"])

def downgrade():
    op.drop_table("audit_logs")
```

**步骤 B — 编写 ORM 模型**：

```python
# backend/packages/harness/ideer/persistence/models/audit_log.py
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from harness.ideer.persistence.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True)
    actor_id = Column(String(64), ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=False)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(32), nullable=True)
    resource_id = Column(String(255), nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
```

**步骤 C — 编写 `record_audit()` 工具函数**：

```python
# backend/app/gateway/audit.py
from sqlalchemy import text
from app.db import get_db

def record_audit(actor_id: str, action: str, resource_type: str | None = None,
                 resource_id: str | None = None, detail: dict | None = None,
                 ip_address: str | None = None):
    """记录审计日志的统一入口。所有关键操作路径调用此函数。"""
    sql = text("""
        INSERT INTO audit_logs (id, actor_id, action, resource_type, resource_id, detail, ip_address)
        VALUES (:id, :actor_id, :action, :resource_type, :resource_id, :detail, :ip_address)
    """)
    with get_db() as db:
        db.execute(sql, {
            "id": uuid.uuid4().hex,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "detail": json.dumps(detail, ensure_ascii=False) if detail else None,
            "ip_address": ip_address,
        })
```

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | 新 migration + `models/audit_log.py` + `gateway/audit.py` |
| 修改量 | 新建 3 个文件，约 80 行 |
| 影响范围 | 无（新建表，不影响现有数据） |
| 测试 | 建表迁移执行成功；`record_audit()` 成功后 audit_logs 有记录 |
| 耗时 | 1 人天 |
| 所属 Phase | Phase 1（迁移+模型） + Phase 5（工具函数） |

---

## 4. INDEX_FIX — resource_metadata 索引修正

### 需求来源

- **问题**: D3（visibility 索引无效 + 缺失覆盖索引）
- **文档依据**: 数据库设计 v1.3 §1.1（修正后索引）、迁移方案 v1.3 §2.2
- **严重度**: 🟡 中-高 — 查询性能隐患

### 现状

当前索引结构：
| 索引名 | 列 | 问题 |
|--------|-----|------|
| `ix_resource_metadata_visibility` | `visibility` | 仅 3 个枚举值，选择性极低，近乎无用 |
| `ix_resource_metadata_deleted` | `deleted_at` | 无 `WHERE` 条件，99% 查询查未删除资源但此索引未服务该方向 |
| `ix_resource_metadata_type` | `resource_type` | 保留 |
| `ix_resource_metadata_owner` | `owner_id` | 保留 |
| `ix_resource_metadata_dept` | `department_id` | 保留 |

缺失复合索引：
- `(resource_type, visibility, deleted_at) WHERE deleted_at IS NULL` — 列表页通用过滤
- `(owner_id, deleted_at) WHERE deleted_at IS NULL` — 用户资源列表
- `(department_id, deleted_at) WHERE deleted_at IS NULL` — 部门 visibility 查询

另外 `a2b3c4d5e6f7_add_ix_resource_metadata_deleted.py` 与 `xxx_create_resource_tables.py` 存在重复创建 `ix_resource_metadata_deleted` 的问题。

### 解决方案

新增迁移文件（依赖当前 head）：

```python
"""fix resource_metadata indexes

Revision ID: fix_idx_001
Revises: <current_head>
"""
from alembic import op

def upgrade():
    # 移除低效索引
    op.drop_index("ix_resource_metadata_visibility", table_name="resource_metadata")
    # 保留 ix_resource_metadata_deleted，但新增活性查询方向索引
    op.create_index(
        "ix_resource_meta_type_visibility", "resource_metadata",
        ["resource_type", "visibility", "deleted_at"],
        postgresql_where=text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_resource_meta_owner_active", "resource_metadata",
        ["owner_id", "deleted_at"],
        postgresql_where=text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_resource_meta_dept_active", "resource_metadata",
        ["department_id", "deleted_at"],
        postgresql_where=text("deleted_at IS NULL"),
    )

def downgrade():
    op.drop_index("ix_resource_meta_dept_active", table_name="resource_metadata")
    op.drop_index("ix_resource_meta_owner_active", table_name="resource_metadata")
    op.drop_index("ix_resource_meta_type_visibility", table_name="resource_metadata")
    op.create_index("ix_resource_metadata_visibility", "resource_metadata", ["visibility"])
```

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | 新 migration 文件 |
| 修改量 | 约 40 行 |
| 风险 | 索引重建在数据量大时可能锁表。需在低峰期执行或使用 `CONCURRENTLY` |
| 测试 | `EXPLAIN ANALYZE` 验证复合索引被查询使用 |
| 耗时 | 0.5 人天 |
| 所属 Phase | Phase 1 |

---

## 5. TOOL_BACKFILL — 存量 Tool 数据回填脚本

### 需求来源

- **问题**: D1（存量 Tool 无 resource_metadata）
- **文档依据**: 迁移方案 v1.3 §3.2 步骤 B
- **严重度**: 🔴 严重 — 存量 Tool 的 owner/visibility 永远为空，权限模型对存量 Tool 失效

### 现状

仅 `migrate_meta_json.py` 存在，只覆盖 Skill/Agent。所有已存在的 Tool 无 `resource_metadata` 记录，导致 `_load_tool_meta()` 返回空 → owner_id = None → `check_resource_modify` 无法校验 → owner 校验失效。

### 解决方案

在 `scripts/` 目录下新增迁移脚本或在现有 `migrate_meta_json.py` 中增加步骤 B：

```python
def backfill_tools(db):
    """遍历 MCP 配置中注册的所有 Tool，回填 resource_metadata。"""
    # 从 ToolRegistry 或 MCP 配置获取所有 Tool 名称
    tools = get_all_registered_tools()
    for tool_name, tool_config in tools.items():
        # 幂等检查
        exists = db.execute(
            text("SELECT 1 FROM resource_metadata WHERE resource_type='tool' AND resource_id=:rid"),
            {"rid": tool_name},
        ).fetchone()
        if exists:
            continue

        # 推断 owner（从 MCP 创建记录，无法确定则设为 super_admin）
        owner_id = tool_config.get("owner_id") or DEFAULT_SUPER_ADMIN_ID

        db.execute(text("""
            INSERT INTO resource_metadata (id, resource_type, resource_id, owner_id, department_id, visibility, version)
            VALUES (:id, 'tool', :rid, :owner_id, NULL, 'public', 1)
        """), {
            "id": uuid.uuid4().hex,
            "rid": tool_name,
            "owner_id": owner_id,
        })
```

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | `scripts/migrate_meta_json.py`（修改）或新建 `scripts/migrate_tool_workflow_metadata.py` |
| 修改量 | 约 40 行 |
| 风险 | 须确认 `get_all_registered_tools()` 的实现路径（MCP 配置 vs ToolRegistry） |
| 测试 | 运行前记录 Tool 数量，运行后对比 resource_metadata 行数一致 |
| 耗时 | 1 人天 |
| 所属 Phase | Phase 2 |

---

## 6. WORKFLOW_BACKFILL — 存量 Workflow 数据回填脚本

### 需求来源

- **问题**: D2（Workflow 存量迁移缺失）
- **文档依据**: 迁移方案 v1.3 §3.2 步骤 C
- **严重度**: 🔴 严重 — 存量 Workflow 无 resource_metadata，visibility 控制不生效

### 现状

新创建的 Workflow 由 `workflows.py:255` 的 `create_workflow()` 自动插入 `resource_metadata`。但此前已存在的 Workflow 从 `workflow_runs` 表读取 `run_id LIKE 'def:%'` 的记录，这些记录从未被迁移到 `resource_metadata`。

### 解决方案

在回填脚本中增加步骤 C：

```python
def backfill_workflows(db):
    """从 workflow_runs 表读取存量 Workflow 定义，回填 resource_metadata。"""
    rows = db.execute(text("""
        SELECT DISTINCT SUBSTRING(run_id FROM 5) AS resource_id, owner_id, department_id, created_at
        FROM workflow_runs
        WHERE run_id LIKE 'def:%'
    """)).fetchall()

    for row in rows:
        exists = db.execute(
            text("SELECT 1 FROM resource_metadata WHERE resource_type='workflow' AND resource_id=:rid"),
            {"rid": row.resource_id},
        ).fetchone()
        if exists:
            continue

        db.execute(text("""
            INSERT INTO resource_metadata (id, resource_type, resource_id, owner_id, department_id, visibility, version, created_at)
            VALUES (:id, 'workflow', :rid, :owner_id, :dept_id, 'private', 1, :created_at)
        """), {
            "id": uuid.uuid4().hex,
            "rid": row.resource_id,
            "owner_id": row.owner_id or DEFAULT_SUPER_ADMIN_ID,
            "dept_id": row.department_id,
            "created_at": row.created_at,
        })
```

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | 与 #5 同一脚本 |
| 修改量 | 约 30 行 |
| 风险 | 需要确认 `workflow_runs.owner_id` 字段存在且非空 |
| 测试 | 运行前 `SELECT COUNT(*) FROM workflow_runs WHERE run_id LIKE 'def:%'`，运行后对比 resource_metadata 行数 |
| 耗时 | 0.5 人天 |
| 所属 Phase | Phase 2 |

---

## 7. DEPRECATE_TABLES — 废弃表 DROP 迁移

### 需求来源

- **文档依据**: 迁移方案 v1.3 §5（Phase 4：废弃旧表）
- **严重度**: ⚪ 轻微 — 不影响功能，仅数据库整洁度

### 现状

`skill_default_configs` 和 `user_skill_preferences` 表在迁移文件 `e1f2a3b4c5d6_add_skill_rbac_tables.py` 中创建，且有合并迁移 `e5f6a7b8c9d0_merge_skill_rbac_head.py`。当前 ORM 代码中无模型引用，应用代码零引用。表在数据库中驻留但不再使用。

### 解决方案

新增迁移文件：

```python
"""drop deprecated skill_* tables

Revision ID: drop_skill_tables_001
Revises: <current_head>
"""
from alembic import op

def upgrade():
    op.drop_table("user_skill_preferences")
    op.drop_table("skill_default_configs")

def downgrade():
    # 从原迁移文件恢复表结构
    op.create_table("skill_default_configs", ...)
    op.create_table("user_skill_preferences", ...)
```

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | 新 migration 文件 |
| 修改量 | 约 20 行 |
| 前置条件 | 全局搜索确认无引用（已完成——零引用） |
| 风险 | 如需回滚需 30 天内，超期后数据不可恢复。建议先备份数据再 DROP |
| 耗时 | 0.3 人天 |
| 所属 Phase | Phase 4 |

---

## 8. TOOL_API — 修复 Tool API 数据源 + 收紧 MCP 写通道

### 需求来源

- **问题**: A1（MCP 接口绕过全部权限模型）+ `/api/tools` 端点返回空数据（线上不可用）
- **严重度**: 🔴 严重 — 旧 MCP 直写通道未收紧，Tool API 形同虚设

### 现状

#### 工具供给链路

系统中有两类工具，供给链路不同：

- **平台内置工具** — 定义在 `config.yaml` 的 `tools:` 项（`web_search`、`read_file` 等）和 `ideer/tools/builtins/*.py`（`present_file`、`ask_clarification` 等），系统启动时通过 `resolve_variable()` 导入 Python 类
- **MCP 工具** — 定义在 `extensions_config.json` 的 `mcpServers:` 项，运行时通过 `langchain-mcp-adapters` 自动发现

两类工具最终汇入 **`get_available_tools()`**（返回 `list[BaseTool]`），供给 AI agent 调用。agent 侧**正常工作**。

#### 关键问题

```
get_available_tools()
  ├─ config.yaml 工具 → BaseTool    ─┐
  ├─ builtins/*.py 工具 → BaseTool    ├─→ AI agent 可用 ✅
  ├─ MCP 工具 → BaseTool (自动发现)   │
  └─ ACP 工具 → BaseTool             ┘

ToolRegistry（空的）
  └─ GET /api/tools → 返回 [] ❌
```

`ToolRegistry` 是独立于真实工具链路的元数据注册表，生产代码中**从未被写入**。`GET /api/tools`、`GET /api/tools/groups`、`PUT /api/tools/{name}/config` 等端点全都返回空。

**此外**，`PUT /api/mcp/config` 当前允许任意登录用户（USER+）批量替换全部 MCP 服务器配置，是绕过资源级权限的旁路通道。

#### 端点现状与消费方

| 端点 | 前端是否消费 | 当前可用性 |
|------|------------|-----------|
| `GET /api/tools` | ✅ 管理员工具页面列表 | ❌ 返回空（数据源不对）|
| `GET /api/tools/{tool_name}` | ✅ 管理员工具页面详情 | ❌ 同上 |
| `POST /api/tools/{tool_name}/test` | ✅ 管理员工具页面测试 | ✅ 正常工作（直接调用 `get_available_tools()`）|
| `PUT /api/tools/{tool_name}/config` | ❌ 无前端引用 | ❌ 数据源为空，且无实际用途 |
| `GET /api/tools/groups` | ❌ 无前端引用 | ❌ 同上 |
| `POST /api/tools` | ❌ 无 | ❌ 不存在 |
| `DELETE /api/tools/{tool_name}` | ❌ 无 | ❌ 不存在 |
| `PUT /api/mcp/config` | ❌ 无前端消费 | ⚠️ 当前 USER+，是旁路通道 |

### 解决方案

**删除多余的中间层 `ToolRegistry`，让 `/api/tools` 直接读取 `get_available_tools()`。**

`ToolRegistry` 的唯一作用是存 `ToolInfo`（name、description、param_schema），而这些信息 `BaseTool` 本身已经全部携带。没有理由维护一套平行的数据表示。

```python
# tools.py 重构要点：
# GET /api/tools — 数据源从 get_tool_registry().list_all() 改为 get_available_tools()
# GET /api/tools/{tool_name} — 同上
# 删除：GET /api/tools/groups（无消费）
# 删除：PUT /api/tools/{tool_name}/config（无消费，且工具配置不是通过 API 管理的）
# 保留：POST /api/tools/{tool_name}/test（已正常工作）
```

**同时**，收紧 `PUT /api/mcp/config` 为仅 `SUPER_ADMIN`：

```python
# mcp.py:200 修改装饰器
# 当前：
@require_role(UserRole.USER, UserRole.DEPARTMENT_ADMIN, UserRole.SUPER_ADMIN)
# 改为：
@require_role(UserRole.SUPER_ADMIN)
```

理由：`PUT /api/mcp/config` 是服务器级操作（管理进程定义、秘钥、批量替换），不应由普通用户执行。收紧后作为 SUPER_ADMIN 的后备管理通道保留。

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | `tools.py`（改写 `GET /api/tools` 和 `GET /api/tools/{name}` 的数据源，删除 groups/config 端点）+ `mcp.py`（改装饰器）|
| 修改量 | 约 20 行 |
| 影响范围 | 断裂变更——之前通过 PUT 管理 MCP 配置的非 SUPER_ADMIN 用户将无法继续；`GET /api/tools/groups` 和 `PUT /api/tools/{name}/config` 对前端无影响（零消费者）|
| 测试 | SUPER_ADMIN 可正常 PUT；USER/DEPT_ADMIN 返回 403；验证 `/api/tools` 返回真实工具列表 |
| 耗时 | 0.2 人天 |
| 所属 Phase | Phase 5 |

---

## 9. AUDIT_LOGGING — 审计日志埋点

### 需求来源

- **问题**: A2（无审计日志）
- **文档依据**: 迁移方案 v1.3 §6.5（审计日志埋点）
- **严重度**: 🟡 中等 — 关键操作无记录，但功能不受阻

### 现状

`record_audit()` 工具函数不存在。各关键操作路径无审计日志写入。

### 解决方案

在以下路径注入 `record_audit()` 调用（需先完成 #3 的工具函数）：

| 操作位置 | 代码文件 | 注入点 | 记录内容 |
|---------|---------|--------|---------|
| 资源编辑（通过 owner 校验后）| skills.py PUT、agents.py PUT、workflows.py PUT、tools.py PUT | 更新成功提交后 | `action='update', resource_type, resource_id, detail={"old": ..., "new": ...}` |
| 资源删除 | skills.py DELETE、agents.py DELETE、workflows.py DELETE、tools.py DELETE | soft delete 后 | `action='delete', resource_type, resource_id` |
| visibility 审批通过/驳回 | visibility_applications.py PUT approve/reject | 状态变更后 | `action='visibility_change', detail={"old": current, "new": target, "reviewer": ...}` |
| 角色变更 | admin.py update_user | role 字段变更检测后 | `action='role_change', resource_type='user', detail={"old_role": ..., "new_role": ...}` |
| 用户禁用 | admin.py disable_user | 禁用执行后 | `action='update', resource_type='user', detail={"status": "disabled"}` |
| 导入 | import 端点 | 导入成功后 | `action='import', detail={"source": ...}` |
| 导出 | export 端点 | 导出完成后 | `action='export', resource_type, resource_id` |

**实现模式**（以 skills.py PUT 为例）：

```python
# 在更新成功提交后
from app.audit import record_audit

record_audit(
    actor_id=current_user.id,
    action="update",
    resource_type="skill",
    resource_id=name,
    detail={"old": old_meta, "new": new_meta},
    ip_address=request.client.host if request.client else None,
)
```

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | ~10 个文件（各端点逐一注入） |
| 修改量 | 每处 +3~5 行，总计约 50 行 |
| 影响范围 | 无（纯写入，不影响业务逻辑） |
| 测试 | 执行关键操作后验证 `audit_logs` 表有对应记录 |
| 耗时 | 1.5 人天（含各个端点的埋入和测试） |
| 所属 Phase | Phase 5 |

---

## 10. AUDIT_API — 审计日志 API

### 需求来源

- **文档依据**: API 规范 v1.3 §9
- **严重度**: 🟡 中等 — 无 API 则审计数据只能直查数据库

### 现状

不存在审计日志相关的路由文件或 API 端点。

### 解决方案

新建 `backend/app/gateway/routers/audit_logs.py`：

```python
from fastapi import APIRouter, Depends, Query
from app.authz import require_role, UserRole
from app.models.user import UserModel
from app.dependencies import get_current_rbac_user

router = APIRouter(prefix="/api/admin/audit-logs")

@router.get("")
@require_role(UserRole.SUPER_ADMIN)
async def list_audit_logs(
    actor_id: str | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    start_date: str | None = Query(None),   # ISO datetime
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """审计日志列表，支持按操作人/操作类型/资源类型/时间范围筛选 + 分页"""
    ...

@router.get("/{log_id}")
@require_role(UserRole.SUPER_ADMIN)
async def get_audit_log_detail(
    log_id: str,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """审计日志详情，含完整 detail JSON"""
    ...
```

在主路由注册：`app.include_router(audit_logs_router)`。

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | 新建 `routers/audit_logs.py` + `app.py` 注册 |
| 修改量 | 约 100 行 |
| 影响范围 | 无（新端点）|
| 测试 | super_admin 可查看和筛选；非 super_admin 返回 403 |
| 耗时 | 1 人天 |
| 所属 Phase | Phase 5 |

---

## 11. WORKFLOW_RUN_VISIBILITY — Workflow 运行历史 visibility 校验

### 需求来源

- **问题**: API1（Workflow 运行历史不设 visibility 校验）
- **文档依据**: API 规范 v1.3 §5.2/§5.3（权限改为"按 visibility 过滤"）
- **严重度**: 🔴 严重 — 信息泄露漏洞

### 现状

`workflows.py` 中两个端点完全不检查 visibility：

| 端点 | 行 | 当前行为 | 问题 |
|------|-----|---------|------|
| `get_run_status()` | 542-571 | 直接加载 run state 返回 | 任意用户可读取 private workflow 的运行输出 |
| `list_runs()` | 574-588 | 直接查询 `store.list_runs()` 返回 | 任意用户可列举 private workflow 的运行记录 |

### 解决方案

在两个端点开头增加 visibility 校验（参照 `run_workflow()` 第 488-494 行的模式）：

```python
# get_run_status() 开头增加：
meta = _load_workflow_meta(workflow_name)
if not meta:
    raise HTTPException(status_code=404, detail="Workflow not found")
if not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
    raise HTTPException(status_code=404, detail="Workflow not found")

# list_runs() 开头增加：（同上）
meta = _load_workflow_meta(name)
if not meta:
    raise HTTPException(status_code=404, detail="Workflow not found")
if not check_resource_access(current_user, meta.get("owner_id"), meta.get("department_id"), meta.get("visibility")):
    raise HTTPException(status_code=404, detail="Workflow not found")
```

> 注意：无权限时返回 404 而非 403，防止通过错误码推断资源存在性。

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | `workflows.py` |
| 修改量 | 约 12 行（两处各 +6 行） |
| 影响范围 | private/department workflow 的运行历史不再对非授权用户可见 |
| 测试 | 用无权限用户访问运行历史端点 → 404；owner/super_admin 正常访问 |
| 耗时 | 0.3 人天 |
| 所属 Phase | Phase 5 |

---

## 12. WITHDRAW_LOCK — 撤回申请乐观锁

### 需求来源

- **问题**: 验证报告遗留问题（撤回与审批并发 race condition）
- **文档依据**: 主文档 v1.3 §10（所有审批操作使用乐观锁）
- **严重度**: 🟡 中-高 — 并发撤回+审批可能导致状态不一致

### 现状

`visibility_applications.py:179-209` — `withdraw_application()` 无任何 version 校验：

```python
async def withdraw_application(application_id: str, current_user: ...):
    application = await get_application(application_id)
    if application.applicant_id != current_user.id:  # 申请人校验
        raise HTTPException(403, ...)
    if application.status != "pending":               # 状态校验
        raise HTTPException(400, ...)
    application.status = "withdrawn"                  # 直接修改
    db.commit()                                       # 提交
    # 无 version 比较，无 version 递增
```

若申请人撤回的同时审批人通过，两个操作都可能成功——撤回将状态设为 withdrawn，审批将 visibility 修改并将状态设为 approved。最终状态取决于最后一个提交的，但 visibility 可能已被意外修改。

### 解决方案

```python
# withdraw_application() 增加 version 参数
@router.put("/{application_id}/withdraw")
async def withdraw_application(
    application_id: str,
    body: WithdrawRequest,  # 新增：{ version: int }
    current_user: UserModel = Depends(get_current_rbac_user),
):
    application = await get_application(application_id)

    # 乐观锁校验
    if application.version != body.version:
        raise ApiException("VERSION_CONFLICT", "申请已被其他人处理，请刷新后重试")

    if application.applicant_id != current_user.id:
        raise HTTPException(403, detail="SELF_REVIEW_FORBIDDEN")
    if application.status != "pending":
        raise HTTPException(400, detail="申请状态不是 pending")

    application.status = "withdrawn"
    application.version += 1
    db.commit()
```

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | `visibility_applications.py` |
| 修改量 | 约 15 行（增加 `WithdrawRequest` 模型 + version 校验） |
| 影响范围 | 撤回 API 新增 `version` 必填参数（断裂变更——前端需同步修改） |
| 测试 | 并发撤回+审批 → 一个成功一个 409；正常撤回流程正常 |
| 耗时 | 0.3 人天 |
| 所属 Phase | Phase 5 |

---

## 13. AUDIT_PAGE — 审计日志前端页面

### 需求来源

- **文档依据**: 迁移方案 v1.3 §7.3（新增审计日志页面）
- **严重度**: 🟡 中等 — 无页面则 super_admin 无法在 UI 中查看审计数据

### 现状

`frontend/src/app/workspace/admin/` 下无 `audit-logs/` 目录。搜索全前端无"audit"相关页面。

现有 admin 页面列表：
```
/workspace/admin/
/workspace/admin/tools/
/workspace/admin/departments/
/workspace/admin/users/
/workspace/admin/skill-applications/
/workspace/admin/visibility-applications/
```

### 解决方案

新建 `frontend/src/app/workspace/admin/audit-logs/page.tsx`，参考 `visibility-applications` 页面的实现风格：

**页面功能要求**：

| 功能 | 说明 |
|------|------|
| 日志列表 | 分页表格，每行显示：时间、操作人、操作类型、资源类型、资源名称 |
| 操作类型标签 | 用不同颜色标签区分：create(绿)、update(蓝)、delete(红)、visibility_change(橙)、role_change(紫)、import(青)、export(灰) |
| 筛选栏 | 按操作人搜索、操作类型下拉、资源类型下拉、日期范围选择 |
| 详情弹窗 | 点击单行弹出详情，展示完整 `detail` JSON（格式化显示 old/new 对比） |
| 空状态 | 无日志时显示"暂无审计日志" |

**参考实现**（基于现有页面模式）：

```tsx
// page.tsx 骨架
"use client";
import { useState, useEffect } from "react";
import { AdminPage } from "@/components/admin/page";
import { AuditLogTable } from "@/components/admin/audit-logs/table";
import { AuditLogFilters } from "@/components/admin/audit-logs/filters";
import { AuditLogDetail } from "@/components/admin/audit-logs/detail";

export default function AuditLogsPage() {
    const [logs, setLogs] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [filters, setFilters] = useState({});

    // GET /api/admin/audit-logs?page=&actor_id=&action=&resource_type=&start_date=&end_date=
    const fetchLogs = async () => { ... };

    return (
        <AdminPage title="审计日志">
            <AuditLogFilters value={filters} onChange={setFilters} />
            <AuditLogTable logs={logs} total={total} page={page} onPageChange={setPage} />
        </AdminPage>
    );
}
```

**导航栏更新**：需在 admin 侧边栏增加"审计日志"入口，仅 super_admin 可见。

### 工作计划

| 项 | 值 |
|----|-----|
| 文件 | 新建 `frontend/src/app/workspace/admin/audit-logs/page.tsx` + 可能 1-2 个组件文件 |
| 修改量 | 约 150-200 行（页面 + 组件 + 导航配置） |
| 影响范围 | 无（新页面）|
| 测试 | super_admin 可查看、筛选、展开详情；非 super_admin 访问时路由保护 |
| 耗时 | 1.5 人天 |
| 所属 Phase | Phase 6 |

---

## 工作量汇总

| 序号 | 功能 | 所属 Phase | 预估人天 | 安全风险 | 断裂变更 |
|------|------|-----------|---------|---------|---------|
| 1 | MCP_GET_AUTH | Phase 1 | 0.2 | 高 | 否 |
| 2 | MCP_PUT_TIGHTEN | — | — | — | — |
| 3 | AUDIT_TABLE | Phase 1+5 | 1.0 | 中 | 否 |
| 4 | INDEX_FIX | Phase 1 | 0.5 | 低 | 否 |
| 5 | TOOL_BACKFILL | Phase 2 | 1.0 | 高 | 否 |
| 6 | WORKFLOW_BACKFILL | Phase 2 | 0.5 | 高 | 否 |
| 7 | DEPRECATE_TABLES | Phase 4 | 0.3 | 低 | 否 |
| 8 | TOOL_API | Phase 5 | 0.2 | 高 | 是 |
| 9 | AUDIT_LOGGING | Phase 5 | 1.5 | 中 | 否 |
| 10 | AUDIT_API | Phase 5 | 1.0 | 低 | 否 |
| 11 | WORKFLOW_RUN_VISIBILITY | Phase 5 | 0.3 | 高 | 是 |
| 12 | WITHDRAW_LOCK | Phase 5 | 0.3 | 中 | 是 |
| 13 | AUDIT_PAGE | Phase 6 | 1.5 | 低 | 否 |
| | **合计** | | **8.2 人天** | | |

> **建议执行顺序**：#1>#4（Phase 1 一天）→ #5>#6（Phase 2 一天半）→ #3>#9>#10>#11>#12>#8（Phase 5 核心五天）→ #13（Phase 6 一天半）→ #7（Phase 4 半天）

---

## 实现状态检查（2026-07-06）

| 序号 | 功能 | 所属 Phase | 完成 | 状态说明 |
|------|------|-----------|------|----------|
| 1 | MCP_GET_AUTH | Phase 1 | ☐ | GET /api/mcp/config 仍无认证装饰器 |
| 2 | MCP_PUT_TIGHTEN | Phase 1 | ☐ | PUT /api/mcp/config 仍允许 USER/DEPT_ADMIN/SUPER_ADMIN |
| 3 | AUDIT_TABLE | Phase 1+5 | ✓ | 模型、迁移、record_audit() 均已实现 |
| 4 | INDEX_FIX | Phase 1 | ✓ | 新迁移文件已创建三个复合索引并删除旧索引 |
| 5 | TOOL_BACKFILL | Phase 2 | ✓ | backfill_tools() 已在 migrate_meta_json.py 中实现 |
| 6 | WORKFLOW_BACKFILL | Phase 2 | ✓ | backfill_workflows() 已在 migrate_meta_json.py 中实现 |
| 7 | DEPRECATE_TABLES | Phase 4 | ☐ | skill_default_configs / user_skill_preferences 未被 DROP |
| 8 | TOOL_CRUD | Phase 5 | ☐ | 无 _populate_tool_registry 桥接；PUT 未收紧 |
| 9 | AUDIT_LOGGING | Phase 5 | ✓ | 各端点均已注入 record_audit() 调用 |
| 10 | AUDIT_API | Phase 5 | ✓ | audit_logs.py 已实现列表+详情端点 |
| 11 | WORKFLOW_RUN_VISIBILITY | Phase 5 | ✓ | get_run_status / list_runs 已增加 visibility 校验 |
| 12 | WITHDRAW_LOCK | Phase 1 | ✓ | withdraw_application() 已实现乐观锁 version 校验 |
| 13 | AUDIT_PAGE | Phase 6 | ✓ | 前端审计日志页面已实现（464 行） |

**待完成项（4 项）**：

1. **MCP_GET_AUTH (#1)** — 给 `GET /api/mcp/config` 添加 `Depends(get_current_rbac_user)` 认证
2. **MCP_PUT_TIGHTEN (#2)** — 将 `PUT /api/mcp/config` 装饰器改为 `@require_role(UserRole.SUPER_ADMIN)`
3. **DEPRECATE_TABLES (#7)** — 编写迁移 DROP `skill_default_configs` 和 `user_skill_preferences` 表
4. **TOOL_CRUD (#8)** — 在 app.py lifespan 中添加 `_populate_tool_registry` 桥接逻辑（#2 收紧属于此条目的一部分）
