# 资源管理体系需求文档

> audience: developers, security reviewers, maintainers<br>
> status: current<br>
> owner: security and platform maintainers<br>
> last-verified: 2026-07-15<br>
> canonical-path: `docs/permission-matrix.md`

## 设计原则

1. **管理员的定位**：系统治理者，职责是管理用户对资源的浏览和使用权限（visibility）。管理员不能主动变更任何资源的 visibility，只能在 owner 提交申请后通过审批流程变更。资源内容（YAML/JSON/SKILL.md/SOUL.md）的创建、编辑、删除始终归创作者所有。
2. **visibility 的含义**：控制的是**用户**能否浏览和使用某资源，而非 agent 能否调用 tool。agent 对 tool 的调用权限由 agent 配置文件单独控制。Tool 同样受 visibility 控制，初始值为 private，与 Skill 一致，需通过审批流程变更。
3. **只读用户（viewer）**：仅可浏览可见资源和使用资源，不可创建、编辑、删除、导入、导出、提交 visibility 变更申请。
4. **管理员人数限制**：超级管理员不超过 2 人；每个部门的部门管理员不超过 3 人。
5. **编辑权限**：所有对资源的修改（包括名称、描述、主体文件）均算编辑，仅 owner 可执行。编辑不包含 visibility 变更。
6. **Agent 调用 Tool 的权限规则**：Agent 调用 Tool 需同时满足两个条件：(1) Tool 的 visibility 对当前用户可见；(2) Agent 配置中未排除该 Tool。当 Agent 配置未显式指定 Tool 白名单（`tool_groups`）时，默认可调用所有对当前用户可见的 Tool；显式指定白名单时，仅可调用白名单内的 Tool。
7. **社区共建**：所有用户均可创建资源（初始 visibility=private），通过 visibility 审批流程实现资源的逐步公开。
8. **数据一致性**：所有资源操作通过 optimistic locking（version 字段）保证并发安全。

## 核心操作权限表

| 操作 | 资源类型 | 只读用户 | 普通用户 | 部门管理员 | 超级管理员 |
|------|---------|---------|---------|-----------|-----------|
| **创建** | 全部 | ❌ | ✅ 仅自己 | ✅ 仅自己 | ✅ 仅自己 |
| **编辑** | 全部 | ❌ | ✅ 仅自己的 | ✅ 仅自己的 | ✅ 仅自己的 |
| **删除** | 全部 | ❌ | ✅ 仅自己的 | ✅ 仅自己的 | ✅ 仅自己的 |
| **浏览** | 全部 | ✅ 按 visibility | ✅ 按 visibility | ✅ 按 visibility | ✅ 所有 |
| **执行** | Workflow/Agent | ✅ 按 visibility | ✅ 按 visibility | ✅ 按 visibility | ✅ 所有 |
| **提交 visibility 变更申请** | 全部 | ❌ | 🔲 提交申请 | 🔲 提交申请 | 🔲 提交申请 |
| **撤回 visibility 变更申请** | 全部 | ❌ | ✅ 自己的待审批 | ✅ 自己的待审批 | ✅ 所有待审批 |
| **审批 visibility 变更** | 全部 | ❌ | ❌ | ✅ department 级 | ✅ 所有 |
| **收藏/置顶** | Tool/Skill | ❌ | ❌ 隐式无需 | ❌ 隐式无需 | ❌ 隐式无需 |
| | Workflow/Agent | ❌ | ✅ 仅自己 | ✅ 仅自己 | ✅ 仅自己 |
| **导入** | Tool | ❌ | ❌ 不支持 | ❌ 不支持 | ❌ 不支持 |
| | Skill/Workflow/Agent | ❌ | ✅ → private | ✅ → private | ✅ → private |
| **导出** | Tool | ❌ | ❌ 不支持 | ❌ 不支持 | ❌ 不支持 |
| | Skill/Workflow/Agent | ❌ | ✅ 所有可见资源 | ✅ 所有可见资源 | ✅ 所有可见资源 |
| **导出** | Tool | ❌ | ❌ 不支持 | ❌ 不支持 | ❌ 不支持 |
| | Skill/Workflow/Agent | ❌ | ✅ 所有可见资源 | ✅ 所有可见资源 | ✅ 所有可见资源 |

> 收藏/置顶为纯个人快捷方式，仅影响用户自己的列表排序，不影响其他用户，不影响权限。

## 浏览权限（Visibility 控制）

| visibility | Tool | Skill | Workflow | Agent |
|------------|------|-------|----------|-------|
| **private** | 仅创建者 + super_admin | 仅创建者 + super_admin | 仅创建者 + super_admin | 仅创建者 + super_admin |
| **department** | 同部门所有人 | 同部门所有人 | 同部门所有人 | 同部门所有人 |
| **public** | 所有认证用户 | 所有认证用户 | 所有认证用户 | 所有认证用户 |

> 浏览 = 查看资源的配置文件（Tool/Skill: SKILL.md 或 config；Workflow: YAML；Agent: config.yaml + SOUL.md）

## 使用模式对比

| 维度 | 隐式资源（Tool / Skill） | 显式资源（Workflow / Agent） |
|------|------------------------|---------------------------|
| **用户操作** | 无（agent 自动调用） | 主动选择执行/对话 |
| **执行权限** | 由 agent 自动调用，无需用户操作 | 任何对该资源有浏览权限的用户均可执行 |
| **viewer 可用性** | ✅ agent 自动调用时可用 | ✅ 可查看、可执行 |
| **Agent 调用规则** | 需 Tool/Skill visibility 对用户可见 + Agent 配置未排除 | N/A（用户主动选择） |
| **定制方式** | Agent 配置白名单（未配置则默认全部可用） | 收藏/置顶/搜索/最近使用 |
| **admin 控制** | 仅审批 visibility 变更 | 仅审批 visibility 变更 |
| **社区共建** | 开放创建 + 审核发布 | 开放创建 + 审核发布 |

## Visibility 规则

| visibility | 含义 | 谁可见 | 谁可编辑内容 | 谁可提升 | 谁可降低 |
|------------|------|--------|------------|---------|---------|
| **private** | 仅创建者 | 创建者 + super_admin | 仅创建者 | 需提交申请 | N/A（已是最低） |
| **department** | 同部门 | 同部门所有人 | 仅创建者 | 需提交申请 | 需提交申请 |
| **public** | 所有人 | 所有认证用户 | 仅创建者 | N/A（已是最高） | 需提交申请 |

- visibility 变更**仅通过提交申请 + 审批**实现，任何人不可直接修改（包括 super_admin）。
- "谁可编辑内容"始终为仅创建者，与 visibility 等级无关。
- super_admin 对 private 资源有浏览权限，但无编辑权。
- Tool、Skill、Workflow、Agent 四种资源类型共用同一套 visibility 规则。

## 审批流程

### 申请状态机

```
pending → approved（审批通过，终态）
pending → rejected（驳回，可重新提交回到 pending）
pending → withdrawn（申请人撤回，终态）
rejected → pending（重新提交，生成新申请记录）
```

- 同一资源同时只能有一个 pending 状态的申请。
- rejected 后重新提交视为新申请，保留历次记录。
- withdrawn 后可重新提交。

### 审批流程表

| 申请场景 | 申请人 | 审批人 | 特殊规则 |
|---------|--------|--------|---------|
| visibility 变更（任意方向） | 资源 owner | department 级：dept_admin(同部门) / super_admin；public 级：super_admin only | dept_admin 不可自审自己的任何申请，无论是否为 owner |
| 驳回后重新提交 | 原申请人 | 同首次提交 | 生成新申请记录，保留历次审批历史 |

- 所有角色提交申请均需审批，super_admin 不再跳过审批。
- 驳回后申请人可修改内容并重新提交，每次提交/驳回/通过均保留完整记录（申请人、时间、审批人、意见）。
- 驳回记录对申请人和审批人可见。

### 审批人选择规则

- 同一部门多个 dept_admin 时，系统通知所有符合条件的审批人。
- 审批使用乐观锁（version 字段）确保并发安全。
- 谁先完成审批谁处理，后到的审批人看到申请已处理。
- 审批完成后通知其他审批人该申请已处理。

### 删除与 pending 申请冲突

资源被删除时，该资源有 pending 的 visibility 变更申请：
- 允许删除（soft delete）。
- pending 申请自动驳回。
- 系统通知审批人该资源已被删除，申请自动关闭。
- 如资源被恢复，已驳回的申请不会自动恢复，需重新提交。

## 用户禁用与删除

### 用户禁用时

- 资源保持原状，owner 身份保留。
- 禁用期间 owner 无法操作（不可编辑、删除、提交申请等）。
- 其他有浏览权限的用户仍可浏览该资源。
- 资源不自动转移，待用户恢复或删除后再处理。
- 系统通知受影响资源的 owner（如为自己则忽略）。

### 用户删除时

见下方"资源所有权转移机制 > 用户删除时"。

### 禁用/删除时的 pending 申请处理

用户被禁用或删除时，该用户有 pending 的 visibility 变更申请：
- **作为申请人**：申请自动驳回，通知审批人。
- **作为审批人**：申请自动重新分配给同部门其他 dept_admin 或 super_admin，通知新审批人处理。
- 如无其他合适审批人，申请自动驳回，通知申请人。

## 资源所有权转移机制

### 用户调岗时

- 该用户所有 department 级资源降级为 private，owner 不变。
- public 级和 private 级资源不受影响。
- 系统通知受影响资源的 owner。

### 用户删除时

- super_admin 必须在删除用户前完成资源重分配。
- 重分配选项：(1) 自己继承该用户所有资源的 owner；(2) 将资源分配给指定的其他用户。
- 分配完成后不可再变更。
- visibility 保持不变（private/department/public 原样保留）。
- 系统通知新 owner 资源已转移。

### 部门删除时

需 super_admin 先执行资源重分配，再执行部门删除：
- public 级资源：保持 public，owner 不变。
- private 级资源：保持 private，owner 不变。
- department 级资源：全部降级为 private，owner 不变。
- 重分配完成后 super_admin 确认，再正式删除部门。
- 系统通知受影响资源的 owner。

## 管理员人数限制

- 超级管理员：全局不超过 2 人。
- 部门管理员：每个部门不超过 3 人。
- 超限时禁止新增，需先降级或移除现有管理员。

## 并发控制

- 资源编辑使用 optimistic locking（基于 `version` 字段）：更新时 WHERE version = 原版本号，affected rows = 0 表示冲突。
- 审批操作同样使用 optimistic locking（基于 `version` 字段）。
- 冲突时返回提示，由用户刷新后重试。
- **不保留版本历史**，编辑即覆盖。如需历史记录，请通过 visibility_applications 表追溯。

## 导入/导出机制

### 数据存储形式

| 功能 | 存储位置 | 数据格式 | 可序列化 | 可导出 |
|------|---------|---------|---------|--------|
| **Tool** | 数据库（resource_metadata）+ 代码仓库 | Python 代码 + 配置 JSON | ✅ 代码可序列化 | ❌ 代码不可直接导出 |
| **Skill** | 文件系统 | `SKILL.md`（Markdown + frontmatter） | ✅ 天然可序列化 | ✅ 适合 |
| **Workflow** | 数据库（SQLAlchemy） | YAML 字符串 | ✅ 已经是字符串 | ✅ 适合 |
| **Agent** | 文件系统 | `config.yaml` + `SOUL.md` + `.meta.json` | ✅ 天然可序列化 | ✅ 适合 |

### 导入/导出格式

| 功能 | 导出格式 | 导入格式 | 实现难度 | 说明 |
|------|---------|---------|---------|------|
| **Tool** | ❌ 不支持（MCP 配置可导出 JSON） | ❌ 不支持（MCP 配置可导入 JSON） | N/A | 核心是可执行代码，元数据无法独立运行 |
| **Skill** | `.skill` 文件（ZIP） | `.skill` 文件（ZIP） | 低 | 已有安装机制，缺少导出功能 |
| **Workflow** | `.yaml` 文件 | `.yaml` 文件 | 低 | 数据已是 YAML 格式，直接序列化/反序列化 |
| **Agent** | `.json` 文件 | `.json` 文件 | 已实现 | 已有 `POST /api/agents/{name}/export` 和 `POST /api/agents/import` |

> 导入/导出权限见核心操作权限表。

### 导入流程

```
用户上传文件 → 解析格式 → 校验内容（安全扫描） → 创建资源（visibility=private, owner=当前用户）
```

- 导入等同于"创建"，不覆盖已有资源（除非选择"更新已有"且为 owner）。
- 导入后资源为 private，想要公开需走 visibility 变更审批流程。
- 导入时保留原作者信息（meta.imported_from），但 owner 归属导入用户。
- 导入的资源需通过安全扫描（如 Skill 的 SKILL.md 安全检查）。

### 导入冲突处理

- 通过 name 查找已有资源。
- 如不存在：创建新资源，visibility=private，owner=当前用户。
- 如已存在且当前用户为 owner：可选择更新已有资源内容。
- 如已存在但当前用户非 owner：提示冲突，建议创建新副本（名称自动加后缀）。

### 导出流程

```
用户请求导出 → 检查浏览权限 → 打包资源 → 记录审计日志 → 返回文件
```

- 只有可见的资源才能导出。
- 导出文件包含完整内容 + 元数据（owner, visibility, created_at 等）。
- 导出不改变资源的 visibility 或 owner。
- 导出操作记录审计日志（who/when/what）。

## API 接口定义

### 资源通用接口（Skill / Workflow / Agent）

| 操作 | 方法 | 路径 | 请求体 | 响应体 | 权限 |
|------|------|------|--------|--------|------|
| 列表 | GET | `/api/{resource}` | — | `{ items: [...], total: int }` | 按 visibility 过滤 |
| 详情 | GET | `/api/{resource}/{id}` | — | 资源完整信息 | 按 visibility 过滤 |
| 创建 | POST | `/api/{resource}` | `{ name, content, visibility }` | 资源完整信息（含 version） | 所有可写角色 |
| 编辑 | PUT | `/api/{resource}/{id}` | `{ name?, content?, version }` | 资源完整信息（含新 version） | 仅 owner |
| 删除 | DELETE | `/api/{resource}/{id}` | — | `{ success: true }` | 仅 owner |
| 导出 | GET | `/api/{resource}/{id}/export` | — | 文件流 | 按 visibility 过滤 |
| 导入 | POST | `/api/{resource}/import` | 文件上传 | 资源完整信息 | 所有可写角色 |

### Skill 专属接口

| 操作 | 方法 | 路径 | 请求体 | 响应体 | 权限 |
|------|------|------|--------|--------|------|
| 安装 .skill | POST | `/api/skills/install` | `{ thread_id, path }` | `{ success, skill_name, message }` | 所有可写角色 |

### Tool 专属接口

| 操作 | 方法 | 路径 | 请求体 | 响应体 | 权限 |
|------|------|------|--------|--------|------|
| 创建 | POST | `/api/tools` | `{ name, description, code, config, visibility }` | 工具完整信息 | 所有可写角色 |
| 编辑 | PUT | `/api/tools/{name}` | `{ name?, description?, code?, config? }` | 工具完整信息 | 仅 owner |
| 删除 | DELETE | `/api/tools/{name}` | — | `{ success }` | 仅 owner |
| 测试 | POST | `/api/tools/{name}/test` | `{ params }` | `{ success, result/error }` | 按 visibility |
| 更新配置 | PUT | `/api/tools/{name}/config` | `{ config, version }` | `{ success, message, version }` | 按 visibility |

### Workflow 专属接口

| 操作 | 方法 | 路径 | 请求体 | 响应体 | 权限 |
|------|------|------|--------|--------|------|
| 执行 | POST | `/api/workflows/{name}/run` | `{ inputs }` | `{ run_id, status }` | 所有可写角色 |
| 运行状态 | GET | `/api/workflows/{name}/runs/{run_id}` | — | 运行状态详情 | 所有认证用户 |
| 运行历史 | GET | `/api/workflows/{name}/runs` | — | `{ runs: [...], total }` | 所有认证用户 |
| 人工审批 | POST | `/api/workflows/{name}/runs/{run_id}/review` | `{ approved, data }` | `{ success }` | 审批人 |

### Agent 专属接口

| 操作 | 方法 | 路径 | 请求体 | 响应体 | 权限 |
|------|------|------|--------|--------|------|
| 名称检查 | GET | `/api/agents/check?name=xxx` | — | `{ available, name }` | 所有认证用户 |
| 统计 | GET | `/api/agents/{name}/stats` | — | 统计信息 | 按 visibility 过滤 |
| 用户配置 | GET/PUT | `/api/user-profile` | `{ content }` | `{ content }` | 所有可写角色 |
| 导出 | POST | `/api/agents/{name}/export` | — | JSON 文件流 | 按 visibility 过滤 |
| 导入 | POST | `/api/agents/import` | `{ name, config, soul, visibility }` | 资源完整信息 | 所有可写角色 |

### Visibility 审批接口

| 操作 | 方法 | 路径 | 请求体 | 响应体 | 权限 |
|------|------|------|--------|--------|------|
| 提交申请 | POST | `/api/visibility-applications` | `{ resource_type, resource_id, target_visibility, reason }` | 申请详情 | 所有可写角色 |
| 撤回申请 | DELETE | `/api/visibility-applications/{id}` | — | `{ success }` | 申请人 |
| 审批 | PUT | `/api/visibility-applications/{id}` | `{ action: approved/rejected, comment, version }` | 申请详情 | dept_admin / super_admin |
| 查看待审批 | GET | `/api/visibility-applications` | `?status=pending` | `{ applications: [...] }` | dept_admin / super_admin |

> 审批接口使用乐观锁（version 字段），确保并发安全。

## 数据库表结构

### resource_metadata（新增）

统一存储四种资源的元数据，替代现有的 `.meta.json` 文件。

```sql
CREATE TABLE resource_metadata (
    id              VARCHAR(64) PRIMARY KEY,
    resource_type   VARCHAR(32) NOT NULL,   -- 'tool' | 'skill' | 'workflow' | 'agent'
    resource_id     VARCHAR(255) NOT NULL,  -- 资源名/标识
    owner_id        VARCHAR(64),            -- 创建者用户 ID
    department_id   VARCHAR(64),            -- 创建者所属部门
    visibility      VARCHAR(32) DEFAULT 'private',
    imported_from   TEXT,                   -- 导入来源信息（可选）
    version         INTEGER DEFAULT 1,      -- 乐观锁版本号
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(resource_type, resource_id)
);
CREATE INDEX ix_resource_metadata_type ON resource_metadata(resource_type);
CREATE INDEX ix_resource_metadata_owner ON resource_metadata(owner_id);
CREATE INDEX ix_resource_metadata_dept ON resource_metadata(department_id);
```

### visibility_applications（新增，替代现有 skill_applications）

```sql
CREATE TABLE visibility_applications (
    id              VARCHAR(64) PRIMARY KEY,
    resource_type   VARCHAR(32) NOT NULL,
    resource_id     VARCHAR(255) NOT NULL,
    applicant_id    VARCHAR(64) NOT NULL,
    current_visibility VARCHAR(32) NOT NULL,
    target_visibility  VARCHAR(32) NOT NULL,
    department_id   VARCHAR(64),
    reason          TEXT DEFAULT '',
    status          VARCHAR(20) DEFAULT 'pending',  -- pending/approved/rejected/withdrawn
    submitted_at    TIMESTAMP DEFAULT NOW(),
    reviewed_by     VARCHAR(64),
    reviewed_at     TIMESTAMP,
    review_comment  TEXT DEFAULT '',
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_visibility_app_status ON visibility_applications(status);
CREATE INDEX ix_visibility_app_resource ON visibility_applications(resource_type, resource_id);
CREATE INDEX ix_visibility_app_applicant ON visibility_applications(applicant_id);
CREATE INDEX ix_visibility_app_type ON visibility_applications(resource_type);
```

### 现有表保留

| 表名 | 用途 | 变更 |
|------|------|------|
| `users_ext` | 用户 RBAC 信息 | 保留不变 |
| `departments` | 部门信息 | 保留不变 |
| `workflow_runs` | Workflow 运行状态 | 保留不变 |

### 删除/废弃的表

| 表名 | 原用途 | 处置 |
|------|--------|------|
| `skill_applications` | Skill visibility 审批 | 迁移到 `visibility_applications` 后废弃 |
| `skill_default_configs` | Skill 全局/部门默认配置 | 废弃（功能移除） |
| `user_skill_preferences` | 用户个人 skill 偏好 | 废弃（功能移除） |

## 前端页面设计

### 现有页面改造

| 页面路径 | 当前功能 | 改造内容 |
|---------|---------|---------|
| `/workspace/admin/tools` | 工具列表 + MCP 管理 | 增加 tool visibility 管理列、导入/导出按钮 |
| `/workspace/admin/skill-applications` | Skill 审批 | 重构为统一的 visibility 审批页面，支持所有资源类型 |
| `/workspace/admin/skill-defaults` | Skill 默认配置 | 删除（功能移除） |
| `/workspace/admin/users` | 用户管理 | 增加管理员人数限制校验、用户禁用/删除时的资源处理 |
| `/workspace/admin/departments` | 部门管理 | 增加部门删除前的资源重分配流程 |
| `/workspace/workflows` | Workflow 列表 | 增加收藏/置顶/搜索功能、visibility 标签 |
| `/workspace/workflows/[name]` | Workflow 详情 | 增加 visibility 标签、导出按钮、申请 visibility 变更按钮 |
| `/workspace/workflows/[name]/edit` | Workflow 编辑 | 增加 owner 校验（仅 owner 可编辑） |
| `/workspace/agents` | Agent 列表 | 增加收藏/置顶/搜索功能、visibility 标签 |
| `/workspace/agents/[name]` | Agent 详情 | 增加 visibility 标签、导出按钮、申请 visibility 变更按钮 |
| `/workspace/agents/[name]/edit` | Agent 编辑 | 增加 owner 校验（仅 owner 可编辑） |
| 设置 → 技能 | Skill 启用/禁用开关 | 删除（功能移除），改为只读列表 |
| 设置 → 工具 | MCP Server 管理 | 保留不变 |

### 新增页面

| 页面路径 | 功能 | 权限 |
|---------|------|------|
| `/workspace/admin/visibility-applications` | 统一审批中心，显示所有待审批的 visibility 变更申请 | dept_admin / super_admin |
| `/workspace/resources` | 统一资源浏览页，按类型筛选（tool/skill/workflow/agent） | 所有认证用户 |

### 页面交互流程

**创建资源流程：**
```
用户点击"新建" → 选择资源类型 → 填写名称/内容 → 保存（visibility 默认 private）→ 跳转到详情页
```

**提交 visibility 变更流程：**
```
资源详情页 → 点击"申请变更 visibility" → 选择目标等级（department/public）→ 填写理由 → 提交 → 等待审批
```

**审批流程：**
```
审批中心 → 查看待审批列表 → 点击查看详情 → 通过/驳回 → 填写意见 → 确认 → 通知申请人
```

**导入流程：**
```
资源列表页 → 点击"导入" → 选择文件 → 解析预览 → 选择冲突处理方式（创建新副本/更新已有）→ 确认导入
```

**导出流程：**
```
资源详情页 → 点击"导出" → 下载文件
```

## 迁移方案

### 迁移阶段

| 阶段 | 内容 | 影响范围 | 回滚方案 | 预计耗时 |
|------|------|---------|---------|---------|
| Phase 1 | 创建新表（resource_metadata, visibility_applications） | 无影响 | 删除新表 | 1 天 |
| Phase 2 | 迁移 `.meta.json` 数据到 `resource_metadata` 表 | Skill/Agent | 恢复 .meta.json 文件 | 2 天 |
| Phase 3 | 迁移 `skill_applications` 到 `visibility_applications` | Skill 审批 | 恢复旧表 | 1 天 |
| Phase 4 | 废弃 `skill_default_configs` 和 `user_skill_preferences` 表（数据已无用，功能移除） | Skill 配置 | 恢复旧表 | 1 天 |
| Phase 5 | 更新后端 + 前端使用新表和新 API | 全部 | 回退代码 | 7 天 |

### Phase 2 详细步骤（.meta.json → resource_metadata）

```
1. 读取所有 skill 目录下的 .meta.json 文件
2. 读取所有 agent 目录下的 .meta.json 文件
3. 为每条记录生成 resource_metadata 行（id=UUID, resource_type, resource_id, owner_id, department_id, visibility）
4. 写入 resource_metadata 表
5. 验证：对比文件数量和表行数
6. 保留 .meta.json 文件作为备份（不删除）
7. 回滚方案：如需回滚，删除 resource_metadata 中新增的行，恢复 .meta.json 文件
```

### Phase 3 详细步骤（skill_applications → visibility_applications）

```
1. 读取 skill_applications 表所有记录
2. 转换字段映射：
   - skill_id → resource_id
   - skill_name → 保留为冗余字段或去掉
   - request_level → target_visibility
   - 新增 current_visibility 字段（从 .meta.json 或 resource_metadata 读取）
   - 新增 resource_type 字段（固定为 'skill'）
3. 写入 visibility_applications 表
4. 验证：对比记录数和状态一致性
5. 保留旧表作为备份（不删除）
6. 回滚方案：如需回滚，删除 visibility_applications 中新增的行，恢复旧表
```

### 数据一致性校验

每个 Phase 完成后执行：
- 新旧数据行数对比
- 抽样校验关键字段（owner_id, visibility, status）
- 功能回归测试（创建/编辑/删除/审批流程）
- 并发测试（同时编辑同一资源、同时审批同一申请）
- 回滚测试（验证回滚方案可执行）
