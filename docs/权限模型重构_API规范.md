# 资源管理体系 — API 接口规范

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|---------|
| v1.0 | 2025-07-03 | — | 初始版本，从 permission-matrix.md 拆分 |
| v1.1 | 2025-07-03 | — | 审查修订：Tool 仅记录元数据不纳入统一 CRUD、移除审计日志引用 |
| v1.2 | 2025-07-03 | — | 审阅修订：支持 visibility 升降级、Tool 创建/删除延至第二期、Tool 配置仅 owner、Agent 导出统一为 GET、安全扫描错误码移除 |

> 本文档定义资源管理体系的所有 API 接口。权限模型与规则见《权限模型重构_主文档》，数据库设计见《权限模型重构_数据库设计》，数据迁移方案见《权限模型重构_迁移方案》。

---

## 1. 公共约定

### 1.1 请求头

| Header | 必填 | 说明 |
|--------|------|------|
| `Authorization` | 是 | Bearer token |
| `Content-Type` | 是 | `application/json`（文件上传为 `multipart/form-data`） |

### 1.2 通用响应格式

```json
{
  "success": true,
  "data": { },
  "error": null
}
```

错误响应：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "无权限执行该操作"
  }
}
```

### 1.3 分页参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码，从 1 开始 |
| `page_size` | int | 20 | 每页条数，最大 100 |
| `sort_by` | string | `created_at` | 排序字段 |
| `sort_order` | string | `desc` | asc / desc |

### 1.4 过滤参数（列表接口通用）

| 参数 | 类型 | 说明 |
|------|------|------|
| `resource_type` | string | 筛选资源类型：tool / skill / workflow / agent |
| `visibility` | string | 筛选 visibility：private / department / public |
| `owner_id` | string | 筛选 owner |
| `keyword` | string | 按名称或描述模糊搜索 |

---

## 2. 资源通用接口（Skill / Workflow / Agent）

### 2.1 列表

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/{resource}` |
| 权限 | 所有认证用户，按 visibility 过滤 |
| 请求体 | 无 |
| 响应 | `{ items: [...], total: int, page: int, page_size: int }` |

### 2.2 详情

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/{resource}/{id}` |
| 权限 | 按 visibility 过滤 |
| 请求体 | 无 |
| 响应 | 资源完整信息（含 version、owner_id、visibility、created_at、updated_at） |

### 2.3 创建

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/{resource}` |
| 权限 | 所有可写角色（user / dept_admin / super_admin） |
| 请求体 | `{ name: string, content: object, visibility?: "private" }` |
| 响应 | 资源完整信息（含 version） |

> name 必须在 resource_type 内全局唯一，visibility 默认 private，仅支持 private。

### 2.4 编辑

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/{resource}/{id}` |
| 权限 | 仅 owner |
| 请求体 | `{ name?: string, content?: object, version: int }` |
| 响应 | 资源完整信息（含新 version） |

> 编辑时必须携带当前 version，version 不匹配返回 `VERSION_CONFLICT`。

### 2.5 删除

| 项目 | 值 |
|------|-----|
| 方法 | `DELETE` |
| 路径 | `/api/{resource}/{id}` |
| 权限 | 仅 owner |
| 请求体 | 无 |
| 响应 | `{ success: true }` |

> soft delete，设置 deleted_at。有 pending 申请时自动驳回。

### 2.6 导出

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/{resource}/{id}/export` |
| 权限 | 按 visibility 过滤 |
| 请求体 | 无 |
| 响应 | 文件流（含完整内容 + 元数据） |

> 导出不改变资源的 visibility 或 owner。

### 2.7 导入

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/{resource}/import` |
| 权限 | 所有可写角色 |
| 请求体 | `multipart/form-data`，字段 `file` |
| 响应 | 资源完整信息 |

> 导入等同于"创建"，visibility 默认 private，owner 为当前用户。需通过安全扫描。

---

## 3. Skill 专属接口

### 3.1 安装 .skill

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/skills/install` |
| 权限 | 所有可写角色 |
| 请求体 | `{ thread_id: string, path: string }` |
| 响应 | `{ success: bool, skill_name: string, message: string }` |

---

## 4. Tool 专属接口

> Tool 的 CRUD 保持现有 MCP 管理方式不变，创建/删除端点在第二期纳入统一管理。以下接口为现有 MCP 管理接口，仅做 visibility 权限校验增强。

### 4.1 创建（第二期）

> 第一期不实现。Tool 创建通过 MCP 配置管理，创建时同步在 resource_metadata 表中插入 Tool 元数据记录（resource_type='tool'）。

### 4.2 编辑

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/tools/{name}` |
| 权限 | 仅 owner |
| 请求体 | `{ name?: string, description?: string, code?: string, config?: object, version: int }` |
| 响应 | 工具完整信息 |

> 编辑时同步更新 resource_metadata 表中的 version 字段。

### 4.3 删除（第二期）

> 第一期不实现。Tool 删除通过 MCP 配置管理，删除时同步设置 resource_metadata.deleted_at。

### 4.4 测试

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/tools/{name}/test` |
| 权限 | 按 visibility（所有有浏览权限的用户） |
| 请求体 | `{ params: object }` |
| 响应 | `{ success: bool, result?: any, error?: string }` |

### 4.5 更新配置

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/tools/{name}/config` |
| 权限 | 仅 owner |
| 请求体 | `{ config: object, version: int }` |
| 响应 | `{ success: bool, message: string, version: int }` |

---

## 5. Workflow 专属接口

### 5.1 执行

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/workflows/{name}/run` |
| 权限 | 所有可写角色（按 visibility） |
| 请求体 | `{ inputs: object }` |
| 响应 | `{ run_id: string, status: string }` |

### 5.2 运行状态

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/workflows/{name}/runs/{run_id}` |
| 权限 | 所有认证用户 |
| 请求体 | 无 |
| 响应 | 运行状态详情（status、started_at、finished_at、output） |

### 5.3 运行历史

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/workflows/{name}/runs` |
| 权限 | 所有认证用户 |
| 请求体 | 无（支持分页） |
| 响应 | `{ runs: [...], total: int, page: int, page_size: int }` |

### 5.4 人工审批

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/workflows/{name}/runs/{run_id}/review` |
| 权限 | 审批人 |
| 请求体 | `{ approved: bool, data?: object }` |
| 响应 | `{ success: true }` |

---

## 6. Agent 专属接口

### 6.1 名称检查

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/agents/check?name=xxx` |
| 权限 | 所有认证用户 |
| 请求体 | 无 |
| 响应 | `{ available: bool, name: string }` |

### 6.2 统计

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/agents/{name}/stats` |
| 权限 | 按 visibility |
| 请求体 | 无 |
| 响应 | 统计信息（调用次数、最近使用时间等） |

### 6.3 用户配置

| 项目 | 值 |
|------|-----|
| 方法 | `GET / PUT` |
| 路径 | `/api/user-profile` |
| 权限 | 所有可写角色 |
| 请求体（PUT） | `{ content: object }` |
| 响应 | `{ content: object }` |

### 6.4 导出

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/agents/{name}/export` |
| 权限 | 按 visibility |
| 请求体 | 无 |
| 响应 | ZIP 文件流（含 config.yaml + SOUL.md + meta.json） |

> 导出格式与通用导出接口一致（ZIP 包），包含 Agent 的配置文件、SOUL.md 和元数据。

### 6.5 导入

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/agents/import` |
| 权限 | 所有可写角色 |
| 请求体 | `{ name: string, config: object, soul: string, visibility?: "private" }` |
| 响应 | 资源完整信息 |

---

## 7. Visibility 审批接口

### 7.1 提交申请

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/visibility-applications` |
| 权限 | 所有可写角色 |
| 请求体 | `{ resource_type: string, resource_id: string, target_visibility: "private" \| "department" \| "public", reason: string }` |
| 响应 | 申请详情 |

> target_visibility 可以是 private、department、public 中的任意一个（与 current_visibility 不同即可），支持升降级。同一资源同时只能有一个 pending 申请。

### 7.2 撤回申请

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/visibility-applications/{id}/withdraw` |
| 权限 | 申请人（且申请状态为 pending） |
| 请求体 | 无 |
| 响应 | `{ success: true }` |

> 撤回不是删除记录，申请记录保留用于审计追溯。

### 7.3 审批

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/visibility-applications/{id}` |
| 权限 | dept_admin / super_admin |
| 请求体 | `{ action: "approved" \| "rejected", comment: string, version: int }` |
| 响应 | 申请详情（含新 version） |

> dept_admin 不可审批自己提交的申请。审批使用乐观锁。

### 7.4 查看待审批

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/visibility-applications` |
| 权限 | dept_admin / super_admin |
| 查询参数 | `?status=pending&resource_type=string&page=1&page_size=20` |
| 响应 | `{ applications: [...], total: int, page: int, page_size: int }` |

> dept_admin 仅看到同部门资源的申请，super_admin 看到所有。

---

## 8. 错误码汇总

| 错误码 | HTTP 状态码 | 说明 |
|--------|------------|------|
| `PERMISSION_DENIED` | 403 | 无权限执行该操作 |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在 |
| `RESOURCE_CONFLICT` | 409 | 资源名已存在 |
| `VERSION_CONFLICT` | 409 | 乐观锁冲突，需刷新重试 |
| `ADMIN_LIMIT_EXCEEDED` | 400 | 管理员人数已达上限 |
| `INVALID_VISIBILITY` | 400 | 无效的 visibility 值 |
| `PENDING_APPLICATION_EXISTS` | 409 | 该资源已有 pending 的变更申请 |
| `APPROVER_NOT_FOUND` | 400 | 无可用审批人 |
| `SELF_REVIEW_FORBIDDEN` | 403 | dept_admin 不可审批自己的申请 |
| `USER_DISABLED` | 403 | 用户已被禁用 |
| `FILE_FORMAT_INVALID` | 400 | 导入文件格式不合法 |
| `TRANSFER_REQUIRED` | 400 | 用户删除前需完成资源重分配 |
| `INVALID_REQUEST_BODY` | 400 | 请求体格式或字段不合法 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
