# 资源管理体系 — 权限模型重构（主参考文档）

> audience: developers, security reviewers, maintainers<br>
> status: current<br>
> owner: security and platform maintainers<br>
> last-verified: 2026-07-15<br>
> canonical-path: `docs/permission-model-redesign.md`

> 本文档整合了权限模型定义、数据库设计、API 规范、迁移方案。历史审计与验证结论见 [`docs/archive/2026/permission/permission-model-audit-2026-07-05.md`](archive/2026/permission/permission-model-audit-2026-07-05.md)，当前遗留待办见 [`docs/backlog.md`](backlog.md)。

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|---------|
| v1.0 | 2025-07-03 | — | 初始版本，从 permission-matrix.md 拆分 |
| v1.1 | 2025-07-03 | — | 审查修订：明确实施范围、与现有代码差异、Tool 仅记录元数据、审计/通知延后 |
| v1.2 | 2025-07-03 | — | 审阅修订：支持 visibility 升降级、Tool CRUD 第二期纳入、Tool 配置仅 owner、dept_admin 不保留隐式权限、导出 ZIP 格式、安全扫描延后 |
| v1.3 | 2026-07-06 | — | 对抗式审查修订：增加设计原则例外条款（§2-9）、继承托管模式（§8.2）、Tool CRUD 提升至第一期、audit_logs 提升至第一期、修正实施范围 |

---

## 目录

- [一、权限模型与规则](#一权限模型与规则)
  - [0. 实施范围](#0-实施范围)
  - [1. 术语定义](#1-术语定义)
  - [2. 设计原则](#2-设计原则)
  - [3. 角色与权限](#3-角色与权限)
  - [4. 浏览权限（Visibility 控制）](#4-浏览权限visibility-控制)
  - [5. 使用模式对比](#5-使用模式对比)
  - [6. 审批流程](#6-审批流程)
  - [7. 用户生命周期](#7-用户生命周期)
  - [8. 资源所有权转移机制](#8-资源所有权转移机制)
  - [9. 管理员人数限制](#9-管理员人数限制)
  - [10. 并发控制](#10-并发控制)
  - [11. 数据归属与历史追溯](#11-数据归属与历史追溯)
  - [12. 资源约束规则](#12-资源约束规则)
- [二、数据库设计](#二数据库设计)
  - [2.1 新增表](#21-新增表)
  - [2.2 保留表](#22-保留表)
  - [2.3 废弃表](#23-废弃表)
  - [2.4 数据存储形式](#24-数据存储形式)
  - [2.5 ER 关系概览](#25-er-关系概览)
- [三、API 接口规范](#三api-接口规范)
  - [3.1 公共约定](#31-公共约定)
  - [3.2 资源通用接口](#32-资源通用接口)
  - [3.3 Skill 专属接口](#33-skill-专属接口)
  - [3.4 Tool 专属接口](#34-tool-专属接口)
  - [3.5 Workflow 专属接口](#35-workflow-专属接口)
  - [3.6 Agent 专属接口](#36-agent-专属接口)
  - [3.7 Visibility 审批接口](#37-visibility-审批接口)
  - [3.8 审计日志接口](#38-审计日志接口)
  - [3.9 错误码汇总](#39-错误码汇总)
- [四、前端页面设计](#四前端页面设计)
  - [4.1 现有页面改造](#41-现有页面改造)
  - [4.2 新增页面](#42-新增页面)
  - [4.3 页面交互流程](#43-页面交互流程)
- [五、数据迁移方案](#五数据迁移方案)
  - [5.1 迁移总览](#51-迁移总览)
  - [5.2 Phase 1：创建新表](#52-phase-1创建新表)
  - [5.3 Phase 2：迁移 .meta.json → resource_metadata](#53-phase-2迁移-metajson--resource_metadata)
  - [5.4 Phase 3：迁移 skill_applications → visibility_applications](#54-phase-3迁移-skill_applications--visibility_applications)
  - [5.5 Phase 4：废弃旧表](#55-phase-4废弃旧表)
  - [5.6 Phase 5：后端代码重构](#56-phase-5后端代码重构)
  - [5.7 Phase 6：前端页面改造](#57-phase-6前端页面改造)
  - [5.8 数据一致性校验](#58-数据一致性校验)
  - [5.9 风险与缓解](#59-风险与缓解)
  - [5.10 迁移检查清单](#510-迁移检查清单)

---

# 一、权限模型与规则

## 0. 实施范围

本次重构分为两个阶段：

**第一期（本次）：**
- 统一 resource_metadata 表管理 Skill/Agent/Workflow 元数据（替代 .meta.json）
- Tool CRUD 纳入统一管理（新增创建/删除端点），废弃 MCP 配置直写通道
- 扩展 skill_applications → visibility_applications，支持所有资源类型
- 废弃 skill_default_configs 和 user_skill_preferences 表
- 统一 authz.py 权限检查函数，移除 admin 直接修改资源的权限，移除 dept_admin 隐式同部门浏览权限
- 新增 version 字段实现乐观锁
- audit_logs 审计日志表（含审计日志页面）
- 改造现有前端页面

**第二期（后续迭代）：**
- 通知机制（站内信/邮件）
- 统一资源浏览页 `/workspace/resources`

### 与现有代码的主要差异

以下变更会**破坏现有代码行为**，需在迁移方案中明确处理：

| 变更项 | 现有行为 | 目标行为 | 影响范围 |
|--------|---------|---------|---------|
| 编辑权限 | `check_resource_modify` 允许 super_admin/department_admin 修改所有资源 | 仅 owner 可编辑 | `authz.py:509-519` |
| visibility 变更 | 存在直接修改端点（`update_skill_visibility`、`_can_set_visibility`） | 全部通过审批流程 | `skills.py:580+`、`agents.py:44-59` |
| 审批跳过 | 部分场景 super_admin 跳过审批 | 所有角色均需审批 | `admin_skill_applications.py` |
| 数据存储 | Skill/Agent 用 .meta.json 文件 | 统一查询 resource_metadata 表 | 所有读取 .meta.json 的代码 |
| 重复函数 | `_check_resource_modify` 在 skills.py 和 agents.py 重复定义 | 统一到 authz.py | `skills.py:51-59`、`agents.py:33-41` |
| visibility 检查 | `_is_visible_to_user`（skills.py）与 `check_resource_access`（authz.py）功能重叠 | 删除 `_is_visible_to_user`，统一使用 `check_resource_access` | `skills.py:62-86` |

---

## 1. 术语定义

| 术语 | 定义 |
|------|------|
| **owner** | 资源的创建者，拥有该资源的编辑权和删除权。owner 身份随用户删除/调岗时可能发生转移。 |
| **认证用户** | 已登录且通过身份验证的系统用户（含 viewer、普通用户、部门管理员、超级管理员）。 |
| **部门管理员（dept_admin）** | 负责本部门资源 visibility 审批的管理员角色，每部门不超过 3 人。 |
| **超级管理员（super_admin）** | 系统全局治理者，全局不超过 2 人，拥有最高审批权限。 |
| **只读用户（viewer）** | 仅可浏览和使用可见资源，不可创建、编辑、删除、导入、导出、提交审批。 |
| **隐式资源** | Tool 和 Skill，由 agent 自动调用，用户无需主动操作。 |
| **显式资源** | Workflow 和 Agent，用户主动选择执行或对话。 |
| **visibility** | 资源可见性等级，分为 private、department、public 三级。 |
| **乐观锁（optimistic locking）** | 基于 `version` 字段的并发控制机制，更新时校验版本号，冲突时拒绝操作。 |

---

## 2. 设计原则

1. **管理员的定位**：系统治理者，职责是管理用户对资源的浏览和使用权限（visibility）。管理员不能主动变更任何资源的 visibility，只能在 owner 提交申请后通过审批流程变更。资源内容（YAML/JSON/SKILL.md/SOUL.md）的创建、编辑、删除始终归创作者所有。管理员在资源编辑/删除方面与普通用户权限一致（仅 owner 可操作），不具备跨部门或全局直接编辑权限。
2. **visibility 的含义**：控制的是**用户**能否浏览和使用某资源，而非 agent 能否调用 tool。agent 对 tool 的调用权限由 agent 配置文件单独控制。Tool 同样受 visibility 控制，初始值为 private，与 Skill 一致，需通过审批流程变更。**Tool 的 CRUD 已纳入统一管理**，通过 resource_metadata 维护 visibility/owner 元数据以统一权限查询。Tool 的配置更新仅 owner 可操作（不限 admin 角色）。
3. **只读用户（viewer）**：仅可浏览可见资源和使用资源，不可创建、编辑、删除、导入、导出、提交 visibility 变更申请。
4. **管理员人数限制**：超级管理员不超过 2 人；每个部门的部门管理员不超过 3 人。
5. **系统自动操作例外**：用户调岗、部门删除、用户删除等系统生命周期事件触发的 visibility 变更属于自动操作，由系统直接执行，无需经过审批流程。所有自动操作均记录在 audit_logs 中备查。
6. **编辑权限**：所有对资源的修改（包括名称、描述、主体文件）均算编辑，仅 owner 可执行。编辑不包含 visibility 变更。
7. **Agent 调用 Tool 的权限规则**：Agent 调用 Tool 需同时满足两个条件：(1) Tool 的 visibility 对当前用户可见；(2) Agent 配置中未排除该 Tool。当 Agent 配置未显式指定 Tool 白名单（`tool_groups`）时，默认可调用所有对当前用户可见的 Tool；显式指定白名单时，仅可调用白名单内的 Tool。
8. **社区共建**：所有用户均可创建资源（初始 visibility=private），通过 visibility 审批流程实现资源的逐步公开。
9. **数据一致性**：所有资源操作通过 optimistic locking（version 字段）保证并发安全。

---

## 3. 角色与权限

### 3.1 角色定义

| 角色 | 说明 | 人数限制 |
|------|------|---------|
| 超级管理员（super_admin） | 全局治理者，可审批所有 visibility 变更 | 全局 ≤ 2 |
| 部门管理员（dept_admin） | 部门级审批者，可审批同部门 visibility 变更 | 每部门 ≤ 3 |
| 普通用户（user） | 可创建/编辑/删除自己的资源，可提交审批申请 | 无限制 |
| 只读用户（viewer） | 仅浏览和使用可见资源 | 无限制 |

### 3.2 核心操作权限表

| 操作 | 资源类型 | 只读用户 | 普通用户 | 部门管理员 | 超级管理员 |
|------|---------|---------|---------|-----------|-----------|
| **创建** | 全部 | ❌ | ✅ 仅自己 | ✅ 仅自己 | ✅ 仅自己 |
| **编辑** | 全部 | ❌ | ✅ 仅自己的 | ✅ 仅自己的 | ✅ 仅自己的 |
| **删除** | 全部 | ❌ | ✅ 仅自己的 | ✅ 仅自己的 | ✅ 仅自己的 |
| **浏览** | 全部 | ✅ 按 visibility | ✅ 按 visibility | ✅ 按 visibility | ✅ 所有 |
| **执行** | Workflow/Agent | ✅ 按 visibility | ✅ 按 visibility | ✅ 按 visibility | ✅ 所有 |
| **提交 visibility 变更申请** | 全部 | ❌ | 🔲 提交申请（升降级） | 🔲 提交申请（升降级） | 🔲 提交申请（升降级） |
| **撤回 visibility 变更申请** | 全部 | ❌ | ✅ 自己的待审批 | ✅ 自己的待审批 | ✅ 所有待审批 |
| **审批 visibility 变更** | 全部 | ❌ | ❌ | ✅ department 级 | ✅ 所有 |
| **收藏/置顶** | Tool/Skill | ❌ | ❌ 隐式无需 | ❌ 隐式无需 | ❌ 隐式无需 |
| | Workflow/Agent | ❌ | ✅ 仅自己 | ✅ 仅自己 | ✅ 仅自己 |
| **导入** | Tool | ❌ | ❌ 第二期 | ❌ 第二期 | ❌ 第二期 |
| | Skill/Workflow/Agent | ❌ | ✅ → private | ✅ → private | ✅ → private |
| **导出** | Tool | ❌ | ❌ 第二期 | ❌ 第二期 | ❌ 第二期 |
| | Skill/Workflow/Agent | ❌ | ✅ 所有可见资源 | ✅ 所有可见资源 | ✅ 所有可见资源 |
| **测试** | Tool | ❌ | ✅ 按 visibility | ✅ 按 visibility | ✅ 按 visibility |
| **配置更新** | Tool | ❌ | ✅ 仅自己 | ✅ 仅自己 | ✅ 仅自己 |

> 收藏/置顶为纯个人快捷方式，仅影响用户自己的列表排序，不影响其他用户，不影响权限。

### 3.3 角色优先级规则

当用户同时拥有多个角色时，权限取**最高权限**。例如：某用户既是普通用户又是部门管理员，则其审批权限取部门管理员的权限。超级管理员权限始终为系统最高，不可被降级覆盖。

---

## 4. 浏览权限（Visibility 控制）

### 4.1 Visibility 等级

| visibility | Tool | Skill | Workflow | Agent |
|------------|------|-------|----------|-------|
| **private** | 仅创建者 + super_admin | 仅创建者 + super_admin | 仅创建者 + super_admin | 仅创建者 + super_admin |
| **department** | 同部门所有人 | 同部门所有人 | 同部门所有人 | 同部门所有人 |
| **public** | 所有认证用户 | 所有认证用户 | 所有认证用户 | 所有认证用户 |

> 浏览 = 查看资源的配置文件（Tool/Skill: SKILL.md 或 config；Workflow: YAML；Agent: config.yaml + SOUL.md）

### 4.2 Visibility 规则

| visibility | 含义 | 谁可见 | 谁可编辑内容 | 谁可变更 | 特殊规则 |
|------------|------|--------|------------|---------|---------|
| **private** | 仅创建者 | 创建者 + super_admin | 仅创建者 | 需提交申请提升 | N/A（已是最低） |
| **department** | 同部门 | 同部门所有人 | 仅创建者 | 需提交申请升降 | 降级为 private 时需提交申请 |
| **public** | 所有人 | 所有认证用户 | 仅创建者 | 需提交申请降低 | N/A（已是最高） |

- visibility 变更**仅通过提交申请 + 审批**实现，任何人不可直接修改（包括 super_admin）。
- visibility 支持升降级：任何非当前值的 visibility 均可作为 target_visibility（如 private → public、public → department）。
- "谁可编辑内容"始终为仅创建者，与 visibility 等级无关。
- super_admin 对 private 资源有浏览权限，但无编辑权。
- Tool、Skill、Workflow、Agent 四种资源类型共用同一套 visibility 规则。

### 4.3 部门层级规则

- 部门为扁平结构，不支持嵌套。
- "同部门"指用户所属 `department_id` 相同。
- 跨部门资源访问仅通过 public visibility 实现，不支持"跨部门可见"的中间等级。

---

## 5. 使用模式对比

| 维度 | 隐式资源（Tool / Skill） | 显式资源（Workflow / Agent） |
|------|------------------------|---------------------------|
| **用户操作** | 无（agent 自动调用） | 主动选择执行/对话 |
| **执行权限** | 由 agent 自动调用，无需用户操作 | 任何对该资源有浏览权限的用户均可执行 |
| **viewer 可用性** | ✅ agent 自动调用时可用 | ✅ 可查看、可执行 |
| **Agent 调用规则** | 需 Tool/Skill visibility 对用户可见 + Agent 配置未排除 | N/A（用户主动选择） |
| **定制方式** | Agent 配置白名单（未配置则默认全部可用） | 收藏/置顶/搜索/最近使用 |
| **admin 控制** | 仅审批 visibility 变更 | 仅审批 visibility 变更 |
| **社区共建** | 开放创建 + 审核发布 | 开放创建 + 审核发布 |

---

## 6. 审批流程

### 6.1 申请状态机

```
pending → approved（审批通过，终态）
pending → rejected（驳回，可重新提交回到 pending）
pending → withdrawn（申请人撤回，终态）
rejected → pending（重新提交，生成新申请记录）
```

- 同一资源同时只能有一个 pending 状态的申请。
- rejected 后重新提交视为新申请，保留历次记录。
- withdrawn 后可重新提交。
- target_visibility 可以是 private、department、public 中的任意一个（与 current_visibility 不同即可），支持升降级。

### 6.2 审批流程表

| 申请场景 | 申请人 | 审批人 | 特殊规则 |
|---------|--------|--------|---------|
| visibility 变更（升降级） | 资源 owner | department 级：dept_admin(同部门) / super_admin；public 级：super_admin only | dept_admin 不可自审自己的任何申请，无论是否为 owner |
| 驳回后重新提交 | 原申请人 | 同首次提交 | 生成新申请记录，保留历次审批历史 |

- 所有角色提交申请均需审批，super_admin 不再跳过审批。
- 驳回后申请人可修改内容并重新提交，每次提交/驳回/通过均保留完整记录（申请人、时间、审批人、意见）。
- 驳回记录对申请人和审批人可见。

### 6.3 审批人选择规则

- 同一部门多个 dept_admin 时，系统通知所有符合条件的审批人。
- 审批使用乐观锁（version 字段）确保并发安全。
- 谁先完成审批谁处理，后到的审批人看到申请已处理。
- 审批完成后通知其他审批人该申请已处理。

### 6.4 通知机制（第二期）

> 通知基础设施（站内信/邮件）在第二期实现。第一期仅通过日志记录关键事件，不实现通知发送。

以下为完整的事件清单，供第二期实现参考：

| 触发事件 | 通知对象 | 通知渠道 | 通知内容 |
|---------|---------|---------|---------|
| 提交 visibility 变更申请 | 符合条件的审批人 | 站内信 + 邮件 | 申请人、资源名称、当前/目标 visibility、理由 |
| 审批通过 | 申请人 | 站内信 + 邮件 | 审批人、审批意见 |
| 审批驳回 | 申请人 | 站内信 + 邮件 | 驳回原因、可重新提交 |
| 申请撤回 | 审批人 | 站内信 | 申请人撤回了某申请 |
| 资源被删除（有 pending 申请） | 审批人 | 站内信 | 资源已删除，申请自动关闭 |
| 用户禁用/删除 | 受影响的 owner | 站内信 | 说明影响范围和后续处理方式 |
| 审批人被禁用/删除 | 新审批人 | 站内信 | 申请已重新分配，请及时处理 |
| 资源 owner 变更 | 新 owner | 站内信 | 资源已转移至你名下 |
| 部门删除 | 受影响资源的 owner | 站内信 | visibility 降级说明 |

### 6.5 删除与 pending 申请冲突

资源被删除时，该资源有 pending 的 visibility 变更申请：
- 允许删除（soft delete）。
- pending 申请自动驳回。
- 系统通知审批人该资源已被删除，申请自动关闭。
- 如资源被恢复，已驳回的申请不会自动恢复，需重新提交。

---

## 7. 用户生命周期

### 7.1 用户禁用时

- 资源保持原状，owner 身份保留。
- 禁用期间 owner 无法操作（不可编辑、删除、提交申请等）。
- 其他有浏览权限的用户仍可浏览该资源。
- 资源不自动转移，待用户恢复或删除后再处理。
- 系统通知受影响资源的 owner（如为自己则忽略）。

### 7.2 用户删除时

见下方"资源所有权转移机制 > 用户删除时"。

### 7.3 禁用/删除时的 pending 申请处理

用户被禁用或删除时，该用户有 pending 的 visibility 变更申请：
- **作为申请人**：申请自动驳回，通知审批人。
- **作为审批人**：申请自动重新分配给同部门其他 dept_admin 或 super_admin，通知新审批人处理。
- 如无其他合适审批人，申请自动驳回，通知申请人。

---

## 8. 资源所有权转移机制

### 8.1 用户调岗时

- 该用户所有 department 级资源降级为 private，owner 不变。[系统自动操作，不经过审批]
- public 级和 private 级资源不受影响。
- 系统通知受影响资源的 owner。
- **调岗期间有 pending 审批时**：申请人 pending 的申请自动驳回；审批人 pending 的申请自动重新分配。

### 8.2 用户删除时

- super_admin 必须在删除用户前完成资源重分配。
- 重分配选项：(1) 自己继承该用户所有资源的 owner（进入托管模式）；(2) 将资源分配给指定的其他用户。
- 分配完成后不可再变更。
- visibility 保持不变（private/department/public 原样保留）。
- **继承限制**：若 super_admin 选择自己继承（选项 1），该资源进入**托管模式**：(a) super_admin 仅可转交资源给其他用户，不可编辑资源内容；(b) 托管资源在详情页标注"托管中"；(c) 转交完成后新 owner 获得完整编辑权，托管标记自动移除。
- 系统通知新 owner 资源已转移。

### 8.3 部门删除时

需 super_admin 先执行资源重分配，再执行部门删除：
- public 级资源：保持 public，owner 不变。
- private 级资源：保持 private，owner 不变。
- department 级资源：全部降级为 private，owner 不变。[系统自动操作，不经过审批]
- 重分配完成后 super_admin 确认，再正式删除部门。
- 系统通知受影响资源的 owner。

---

## 9. 管理员人数限制

- 超级管理员：全局不超过 2 人。
- 部门管理员：每个部门不超过 3 人。
- 超限时禁止新增，需先降级或移除现有管理员。

---

## 10. 并发控制

- 资源编辑使用 optimistic locking（基于 `version` 字段）：更新时 WHERE version = 原版本号，affected rows = 0 表示冲突。
- 审批操作同样使用 optimistic locking（基于 `version` 字段）。
- 冲突时返回提示，由用户刷新后重试。
- **不保留版本历史**，编辑即覆盖。如需历史记录，请通过 visibility_applications 表追溯。

---

## 11. 数据归属与历史追溯

- 资源的 created_at 和 updated_at 记录基本的时间线信息。
- visibility 变更历史通过 visibility_applications 表追溯（每次审批/驳回/撤回均有完整记录）。
- **audit_logs 审计日志表在第二期实现**，届时将记录所有关键操作的详细日志。

---

## 12. 资源约束规则

| 约束项 | 规则 |
|--------|------|
| 资源 name 长度 | 1–128 字符，仅允许字母、数字、中文、下划线、连字符 |
| 资源 name 唯一性 | 同一 resource_type 内全局唯一 |
| description 长度 | 最长 512 字符 |
| 可见资源上限 | 按用户角色无硬性上限，前端分页展示 |
| 批量操作 | 不支持批量审批、批量删除、批量导出，需逐条操作 |
| 资源内容存储 | 元数据存 resource_metadata 表，内容存文件系统（Skill: SKILL.md；Workflow: workflow.yaml；Agent: config.yaml + SOUL.md；Tool: MCP 配置） |

---

# 二、数据库设计

## 2.1 新增表

### 2.1.1 resource_metadata

统一存储资源的元数据。Skill/Agent/Workflow/Tool 的 CRUD 均通过此表管理。**资源内容（SKILL.md、workflow.yaml、config.yaml、SOUL.md 等）仍存文件系统，resource_metadata 仅存元数据。**

```sql
CREATE TABLE resource_metadata (
    id              VARCHAR(64) PRIMARY KEY,
    resource_type   VARCHAR(32) NOT NULL,       -- 'tool' | 'skill' | 'workflow' | 'agent'
    resource_id     VARCHAR(255) NOT NULL,      -- 资源名/标识
    owner_id        VARCHAR(64) NOT NULL,       -- 创建者用户 ID
    department_id   VARCHAR(64),                -- 创建者所属部门
    visibility      VARCHAR(32) NOT NULL DEFAULT 'private',
    imported_from   TEXT,                       -- 导入来源信息（可选）
    version         INTEGER NOT NULL DEFAULT 1, -- 乐观锁版本号
    deleted_at      TIMESTAMP NULL,             -- soft delete 时间戳
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(resource_type, resource_id)
);

-- 基础索引
CREATE INDEX ix_resource_metadata_type ON resource_metadata(resource_type);
CREATE INDEX ix_resource_metadata_owner ON resource_metadata(owner_id);
CREATE INDEX ix_resource_metadata_dept ON resource_metadata(department_id);

-- 复合覆盖索引（列表页通用过滤）
CREATE INDEX ix_resource_meta_type_visibility ON resource_metadata(resource_type, visibility, deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_resource_meta_owner_active ON resource_metadata(owner_id, deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_resource_meta_dept_active ON resource_metadata(department_id, deleted_at) WHERE deleted_at IS NULL;
```

**字段约束说明：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `id` | VARCHAR(64) | 是 | 主键，UUID | 全局唯一标识 |
| `resource_type` | VARCHAR(32) | 是 | 枚举：tool / skill / workflow / agent | 资源类型 |
| `resource_id` | VARCHAR(255) | 是 | 同 resource_type 内唯一 | 资源名称/标识 |
| `owner_id` | VARCHAR(64) | 是 | 外键 → users_ext.id | 资源所有者 |
| `department_id` | VARCHAR(64) | 否 | 外键 → departments.id | 所有者所属部门 |
| `visibility` | VARCHAR(32) | 是 | 枚举：private / department / public，默认 private | 可见性等级 |
| `imported_from` | TEXT | 否 | — | 导入来源信息 |
| `version` | INTEGER | 是 | ≥ 1 | 乐观锁版本号，每次更新 +1 |
| `deleted_at` | TIMESTAMP | 否 | NULL 表示未删除 | soft delete 时间戳 |
| `created_at` | TIMESTAMP | 是 | 默认 NOW() | 创建时间 |
| `updated_at` | TIMESTAMP | 是 | 默认 NOW()，每次更新时刷新 | 最后更新时间 |

### 2.1.2 visibility_applications

替代现有的 `skill_applications` 表，统一管理所有资源类型的 visibility 变更审批。

```sql
CREATE TABLE visibility_applications (
    id                  VARCHAR(64) PRIMARY KEY,
    resource_type       VARCHAR(32) NOT NULL,       -- 'tool' | 'skill' | 'workflow' | 'agent'
    resource_id         VARCHAR(255) NOT NULL,      -- 资源名/标识
    applicant_id        VARCHAR(64) NOT NULL,       -- 申请人用户 ID
    current_visibility  VARCHAR(32) NOT NULL,       -- 申请时的当前 visibility
    target_visibility   VARCHAR(32) NOT NULL,       -- 目标 visibility
    department_id       VARCHAR(64),                -- 资源所属部门（用于审批人匹配）
    reason              TEXT NOT NULL DEFAULT '',    -- 申请理由
    status              VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending / approved / rejected / withdrawn
    submitted_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    reviewed_by         VARCHAR(64),                -- 审批人用户 ID
    reviewed_at         TIMESTAMP,                  -- 审批时间
    review_comment      TEXT NOT NULL DEFAULT '',    -- 审批意见
    version             INTEGER NOT NULL DEFAULT 1, -- 乐观锁版本号
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_visibility_app_status ON visibility_applications(status);
CREATE INDEX ix_visibility_app_resource ON visibility_applications(resource_type, resource_id);
CREATE INDEX ix_visibility_app_applicant ON visibility_applications(applicant_id);
CREATE INDEX ix_visibility_app_type ON visibility_applications(resource_type);
CREATE INDEX ix_visibility_app_pending ON visibility_applications(resource_type, resource_id, status) WHERE status = 'pending';

-- 确保同一资源同时只有一个 pending 申请（数据库级约束）
CREATE UNIQUE INDEX uq_visibility_app_pending ON visibility_applications(resource_type, resource_id) WHERE status = 'pending';
```

**字段约束说明：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `id` | VARCHAR(64) | 是 | 主键，UUID | 全局唯一标识 |
| `resource_type` | VARCHAR(32) | 是 | 枚举：tool / skill / workflow / agent | 资源类型 |
| `resource_id` | VARCHAR(255) | 是 | — | 资源名称/标识（与 resource_metadata.resource_id 对应） |
| `applicant_id` | VARCHAR(64) | 是 | 外键 → users_ext.id | 申请人 |
| `current_visibility` | VARCHAR(32) | 是 | 枚举：private / department / public | 提交申请时的 visibility |
| `target_visibility` | VARCHAR(32) | 是 | 枚举：private / department / public，且 ≠ current_visibility | 目标 visibility |
| `department_id` | VARCHAR(64) | 否 | 外键 → departments.id | 资源所属部门，用于匹配 dept_admin |
| `reason` | TEXT | 是 | 默认空串 | 申请理由 |
| `status` | VARCHAR(20) | 是 | 枚举：pending / approved / rejected / withdrawn | 申请状态 |
| `submitted_at` | TIMESTAMP | 是 | 默认 NOW() | 提交时间 |
| `reviewed_by` | VARCHAR(64) | 否 | 外键 → users_ext.id | 审批人 |
| `reviewed_at` | TIMESTAMP | 否 | — | 审批时间 |
| `review_comment` | TEXT | 是 | 默认空串 | 审批意见 |
| `version` | INTEGER | 是 | ≥ 1 | 乐观锁版本号 |
| `created_at` | TIMESTAMP | 是 | 默认 NOW() | 记录创建时间 |

**业务约束（数据库级 + 应用层双重保证）：**

- 同一 `resource_type + resource_id` 同时只能有一条 `status = 'pending'` 的记录——通过 partial unique index `uq_visibility_app_pending` 在数据库级强制保证。
- `dept_admin` 不可审批自己提交的申请（应用层校验）。
- `target_visibility` 不能与 `current_visibility` 相同（应用层校验）。

### 2.1.3 audit_logs

审计日志表，记录所有关键资源操作的审计轨迹。

```sql
CREATE TABLE audit_logs (
    id              VARCHAR(64) PRIMARY KEY,
    actor_id        VARCHAR(64) NOT NULL,       -- 操作人用户 ID
    action          VARCHAR(64) NOT NULL,       -- 'create' | 'update' | 'delete' | 'visibility_change' | 'role_change' | 'import' | 'export'
    resource_type   VARCHAR(32),                -- 'tool' | 'skill' | 'workflow' | 'agent' | 'user'
    resource_id     VARCHAR(255),               -- 资源名称/标识
    detail          TEXT,                       -- 变更详情 JSON（含 old_value / new_value）
    ip_address      VARCHAR(45),                -- 来源 IP 地址
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (actor_id) REFERENCES users_ext(id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_actor ON audit_logs(actor_id);
CREATE INDEX ix_audit_action ON audit_logs(action);
CREATE INDEX ix_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX ix_audit_time ON audit_logs(created_at);
```

**字段约束说明：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `id` | VARCHAR(64) | 是 | 主键，UUID | 全局唯一标识 |
| `actor_id` | VARCHAR(64) | 是 | 外键 → users_ext.id，ON DELETE SET NULL | 操作人 |
| `action` | VARCHAR(64) | 是 | 枚举：create/update/delete/visibility_change/role_change/import/export | 操作类型 |
| `resource_type` | VARCHAR(32) | 否 | — | 资源类型 |
| `resource_id` | VARCHAR(255) | 否 | — | 资源标识 |
| `detail` | TEXT | 否 | JSON 格式 | 变更详情 |
| `ip_address` | VARCHAR(45) | 否 | — | 来源 IP |
| `created_at` | TIMESTAMP | 是 | 默认 NOW() | 记录时间 |

**审计埋点清单（第一期实现）：**

| 操作 | 触发位置 | 记录内容 |
|------|---------|---------|
| 资源编辑 | check_resource_modify 通过后的 PUT 端点 | action='update', detail 含 old/new 快照 |
| 资源删除 | DELETE 端点（soft delete） | action='delete', detail 含资源标识 |
| visibility 审批通过 | visibility_applications PUT approve | action='visibility_change', detail 含 old/new visibility |
| 角色变更 | admin.py update_user 中 role 变更 | action='role_change', detail 含 old/new role |
| 用户禁用 | admin.py disable_user | action='update', resource_type='user' |
| 导入 | import 端点 | action='import', detail 含来源信息 |
| 导出 | export 端点 | action='export', detail 含资源标识 |

## 2.2 保留表

| 表名 | 用途 | 变更 |
|------|------|------|
| `users_ext` | 用户 RBAC 信息（role、department_id） | 保留不变 |
| `departments` | 部门信息 | 保留不变 |
| `workflow_runs` | Workflow 运行状态 | 保留不变 |

## 2.3 废弃表

| 表名 | 原用途 | 处置 |
|------|--------|------|
| `skill_applications` | Skill visibility 审批 | 迁移到 `visibility_applications` 后废弃 |
| `skill_default_configs` | Skill 全局/部门默认配置 | 废弃（功能移除） |
| `user_skill_preferences` | 用户个人 skill 偏好 | 废弃（功能移除） |

> 废弃表在迁移完成并验证稳定后删除，保留期不少于 30 天。

## 2.4 数据存储形式

| 资源类型 | 存储位置 | 数据格式 | 可序列化 | 可导出 | 本次变更 |
|---------|---------|---------|---------|--------|---------|
| **Tool** | resource_metadata（统一管理） | Python 代码 + 配置 JSON | ✅ 代码可序列化 | ❌ 代码不可直接导出 | Tool CRUD 已纳入统一管理 |
| **Skill** | 文件系统 → resource_metadata | `SKILL.md`（Markdown + frontmatter） | ✅ 天然可序列化 | ✅ 适合 | CRUD 迁移到 resource_metadata |
| **Workflow** | 数据库（SQLAlchemy） → resource_metadata | YAML 字符串 | ✅ 已经是字符串 | ✅ 适合 | CRUD 迁移到 resource_metadata |
| **Agent** | 文件系统 → resource_metadata | `config.yaml` + `SOUL.md` + `.meta.json` | ✅ 天然可序列化 | ✅ 适合 | CRUD 迁移到 resource_metadata，.meta.json 作为备份保留 |

## 2.5 ER 关系概览

```
users_ext
  ├── departments (department_id)
  │
  ├── resource_metadata (owner_id)
  │     ├── visibility_applications (resource_type + resource_id)
  │     └── audit_logs (操作记录)
  │
  ├── visibility_applications (applicant_id → 申请人)
  ├── visibility_applications (reviewed_by → 审批人)
  └── audit_logs (actor_id)
```

**关键外键关系：**

| 源表 | 源字段 | 目标表 | 目标字段 | ON DELETE | 说明 |
|------|--------|--------|---------|-----------|------|
| `resource_metadata` | `owner_id` | `users_ext` | `id` | RESTRICT | 禁止删除有资源归属的用户 |
| `audit_logs` | `actor_id` | `users_ext` | `id` | SET NULL | 用户删除后审计记录保留，操作人置 NULL |
| `resource_metadata` | `department_id` | `departments` | `id` | SET NULL | 部门删除后 department_id 置 NULL |
| `visibility_applications` | `applicant_id` | `users_ext` | `id` | RESTRICT | 禁止删除有申请记录的用户 |
| `visibility_applications` | `reviewed_by` | `users_ext` | `id` | SET NULL | 用户删除后审批人置 NULL |

---

# 三、API 接口规范

## 3.1 公共约定

### 3.1.1 请求头

| Header | 必填 | 说明 |
|--------|------|------|
| `Authorization` | 是 | Bearer token |
| `Content-Type` | 是 | `application/json`（文件上传为 `multipart/form-data`） |

### 3.1.2 通用响应格式

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

### 3.1.3 分页参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码，从 1 开始 |
| `page_size` | int | 20 | 每页条数，最大 100 |
| `sort_by` | string | `created_at` | 排序字段 |
| `sort_order` | string | `desc` | asc / desc |

### 3.1.4 过滤参数（列表接口通用）

| 参数 | 类型 | 说明 |
|------|------|------|
| `resource_type` | string | 筛选资源类型：tool / skill / workflow / agent |
| `visibility` | string | 筛选 visibility：private / department / public |
| `owner_id` | string | 筛选 owner |
| `keyword` | string | 按名称或描述模糊搜索 |

## 3.2 资源通用接口

### 3.2.1 列表

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/{resource}` |
| 权限 | 所有认证用户，按 visibility 过滤 |
| 请求体 | 无 |
| 响应 | `{ items: [...], total: int, page: int, page_size: int }` |

### 3.2.2 详情

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/{resource}/{id}` |
| 权限 | 按 visibility 过滤 |
| 请求体 | 无 |
| 响应 | 资源完整信息（含 version、owner_id、visibility、created_at、updated_at） |

### 3.2.3 创建

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/{resource}` |
| 权限 | 所有可写角色（user / dept_admin / super_admin） |
| 请求体 | `{ name: string, content: object, visibility?: "private" }` |
| 响应 | 资源完整信息（含 version） |

> name 必须在 resource_type 内全局唯一，visibility 默认 private，仅支持 private。

### 3.2.4 编辑

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/{resource}/{id}` |
| 权限 | 仅 owner |
| 请求体 | `{ name?: string, content?: object, version: int }` |
| 响应 | 资源完整信息（含新 version） |

> 编辑时必须携带当前 version，version 不匹配返回 `VERSION_CONFLICT`。

### 3.2.5 删除

| 项目 | 值 |
|------|-----|
| 方法 | `DELETE` |
| 路径 | `/api/{resource}/{id}` |
| 权限 | 仅 owner |
| 请求体 | 无 |
| 响应 | `{ success: true }` |

> soft delete，设置 deleted_at。有 pending 申请时自动驳回。

### 3.2.6 导出

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/{resource}/{id}/export` |
| 权限 | 按 visibility 过滤 |
| 请求体 | 无 |
| 响应 | 文件流（含完整内容 + 元数据） |

> 导出不改变资源的 visibility 或 owner。

### 3.2.7 导入

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/{resource}/import` |
| 权限 | 所有可写角色 |
| 请求体 | `multipart/form-data`，字段 `file` |
| 响应 | 资源完整信息 |

> 导入等同于"创建"，visibility 默认 private，owner 为当前用户。安全扫描在第二期实现。

## 3.3 Skill 专属接口

### 3.3.1 安装 .skill

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/skills/install` |
| 权限 | 所有可写角色 |
| 请求体 | `{ thread_id: string, path: string }` |
| 响应 | `{ success: bool, skill_name: string, message: string }` |

## 3.4 Tool 专属接口

> Tool 的 CRUD 已纳入统一管理，废弃 MCP 配置直写通道。以下接口统一管理 Tool 的完整生命周期。

### 3.4.1 创建

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/tools` |
| 权限 | 所有可写角色 |
| 请求体 | `{ name: string, description?: string, code?: string, config?: object, visibility?: "private" }` |
| 响应 | `{ id: string, name: string, visibility: string, version: int, created_at: string }` |

### 3.4.2 编辑

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/tools/{name}` |
| 权限 | 仅 owner |
| 请求体 | `{ name?: string, description?: string, code?: string, config?: object, version: int }` |
| 响应 | 工具完整信息 |

### 3.4.3 删除

| 项目 | 值 |
|------|-----|
| 方法 | `DELETE` |
| 路径 | `/api/tools/{name}` |
| 权限 | 仅 owner |
| 请求体 | 无 |
| 响应 | `{ success: true }` |

### 3.4.4 测试

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/tools/{name}/test` |
| 权限 | 按 visibility（所有有浏览权限的用户） |
| 请求体 | `{ params: object }` |
| 响应 | `{ success: bool, result?: any, error?: string }` |

### 3.4.5 更新配置

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/tools/{name}/config` |
| 权限 | 仅 owner |
| 请求体 | `{ config: object, version: int }` |
| 响应 | `{ success: bool, message: string, version: int }` |

## 3.5 Workflow 专属接口

### 3.5.1 执行

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/workflows/{name}/run` |
| 权限 | 所有可写角色（按 visibility） |
| 请求体 | `{ inputs: object }` |
| 响应 | `{ run_id: string, status: string }` |

### 3.5.2 运行状态

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/workflows/{name}/runs/{run_id}` |
| 权限 | 按 visibility 过滤 |
| 请求体 | 无 |
| 响应 | 运行状态详情 |

### 3.5.3 运行历史

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/workflows/{name}/runs` |
| 权限 | 按 visibility 过滤 |
| 请求体 | 无（支持分页） |
| 响应 | `{ runs: [...], total: int, page: int, page_size: int }` |

### 3.5.4 人工审批

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/workflows/{name}/runs/{run_id}/review` |
| 权限 | 审批人 |
| 请求体 | `{ approved: bool, data?: object }` |
| 响应 | `{ success: true }` |

## 3.6 Agent 专属接口

### 3.6.1 名称检查

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/agents/check?name=xxx` |
| 权限 | 所有认证用户 |
| 请求体 | 无 |
| 响应 | `{ available: bool, name: string }` |

### 3.6.2 统计

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/agents/{name}/stats` |
| 权限 | 按 visibility |
| 请求体 | 无 |
| 响应 | 统计信息 |

### 3.6.3 用户配置

| 项目 | 值 |
|------|-----|
| 方法 | `GET / PUT` |
| 路径 | `/api/user-profile` |
| 权限 | 所有可写角色 |
| 请求体（PUT） | `{ content: object }` |
| 响应 | `{ content: object }` |

### 3.6.4 导出

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/agents/{name}/export` |
| 权限 | 按 visibility |
| 请求体 | 无 |
| 响应 | ZIP 文件流（含 config.yaml + SOUL.md + meta.json） |

### 3.6.5 导入

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/agents/import` |
| 权限 | 所有可写角色 |
| 请求体 | `{ name: string, config: object, soul: string, visibility?: "private" }` |
| 响应 | 资源完整信息 |

## 3.7 Visibility 审批接口

### 3.7.1 提交申请

| 项目 | 值 |
|------|-----|
| 方法 | `POST` |
| 路径 | `/api/visibility-applications` |
| 权限 | 所有可写角色 |
| 请求体 | `{ resource_type: string, resource_id: string, target_visibility: "private" | "department" | "public", reason: string }` |
| 响应 | 申请详情 |

### 3.7.2 撤回申请

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/visibility-applications/{id}/withdraw` |
| 权限 | 申请人（且申请状态为 pending） |
| 请求体 | 无 |
| 响应 | `{ success: true }` |

### 3.7.3 审批

| 项目 | 值 |
|------|-----|
| 方法 | `PUT` |
| 路径 | `/api/visibility-applications/{id}` |
| 权限 | dept_admin / super_admin |
| 请求体 | `{ action: "approved" | "rejected", comment: string, version: int }` |
| 响应 | 申请详情（含新 version） |

### 3.7.4 查看待审批

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/visibility-applications` |
| 权限 | dept_admin / super_admin |
| 查询参数 | `?status=pending&resource_type=string&page=1&page_size=20` |
| 响应 | `{ applications: [...], total: int, page: int, page_size: int }` |

> dept_admin 仅看到同部门资源的申请，super_admin 看到所有。

## 3.8 审计日志接口

### 3.8.1 审计日志列表

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/admin/audit-logs` |
| 权限 | super_admin |
| 查询参数 | `?actor_id=&action=&resource_type=&start_date=&end_date=&page=1&page_size=20` |
| 响应 | `{ logs: [...], total: int, page: int, page_size: int }` |

### 3.8.2 审计日志详情

| 项目 | 值 |
|------|-----|
| 方法 | `GET` |
| 路径 | `/api/admin/audit-logs/{id}` |
| 权限 | super_admin |
| 请求体 | 无 |
| 响应 | `{ id, actor_id, action, resource_type, resource_id, detail, ip_address, created_at }` |

## 3.9 错误码汇总

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

---

# 四、前端页面设计

## 4.1 现有页面改造

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

## 4.2 新增页面

| 页面路径 | 功能 | 权限 | 阶段 |
|---------|------|------|------|
| `/workspace/admin/visibility-applications` | 统一审批中心，显示所有待审批的 visibility 变更申请 | dept_admin / super_admin | 第一期 |
| `/workspace/resources` | 统一资源浏览页，按类型筛选（tool/skill/workflow/agent） | 所有认证用户 | 第二期 |

## 4.3 页面交互流程

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
资源详情页 → 点击"导出" → 下载 .zip 文件（包含内容文件 + meta.json 元数据）
```

> 导出格式为 ZIP 包，包含：资源内容文件（Skill: SKILL.md；Workflow: workflow.yaml；Agent: config.yaml + SOUL.md）+ meta.json（元数据：name、owner、visibility、version、created_at 等）。

---

# 五、数据迁移方案

## 5.1 迁移总览

| 阶段 | 内容 | 影响范围 | 预计耗时 | 完成标准 |
|------|------|---------|---------|---------|
| Phase 1 | 创建新表（resource_metadata, visibility_applications, audit_logs）+ 修正索引 + MCP 接口收紧 | 无影响 | 2 天 | 新表创建成功，索引优化生效，MCP 接口增加认证 |
| Phase 2 | 迁移存量数据到 resource_metadata（.meta.json + 存量 Tool + 存量 Workflow） | Skill/Agent/Tool/Workflow | 3 天 | 所有存量资源均有 resource_metadata 记录；抽样校验通过 |
| Phase 3 | 迁移 `skill_applications` 到 `visibility_applications` | Skill 审批 | 1 天 | 旧表记录数 = 新表记录数；状态一致性校验通过 |
| Phase 4 | 废弃 `skill_default_configs` 和 `user_skill_preferences` 表 | Skill 配置 | 1 天 | 代码中无引用旧表；功能回归测试通过 |
| Phase 5 | 后端代码重构（权限函数统一、审批接口迁移、Tool CRUD、审计日志埋点、新增 API） | 后端 | 7 天 | 所有 API 测试通过；审计日志覆盖关键路径 |
| Phase 6 | 前端页面改造（含审计日志页面） | 前端 | 5 天 | 所有页面功能测试通过；审计日志页面可用 |

**总预计耗时：19 天**

### 迁移策略

- **不停服迁移**：所有迁移脚本设计为幂等（可重复执行），支持增量迁移。脚本每次运行时检查已迁移数据，仅处理新增/变更记录。
- **回滚时限**：废弃表（skill_default_configs、user_skill_preferences、skill_applications）数据保留不少于 30 天，回滚必须在此期限内完成。
- **并行写入安全**：迁移脚本运行期间允许正常业务操作，通过幂等设计保证数据一致性。

## 5.2 Phase 1：创建新表

### 5.2.1 操作步骤

```sql
-- 1. resource_metadata 表（含修正后索引）
-- 2. visibility_applications 表
-- 3. audit_logs 表
```

### 5.2.2 索引修正

替换 resource_metadata 表中的低效索引：

```sql
-- 移除低效索引
DROP INDEX IF EXISTS ix_resource_metadata_visibility;
DROP INDEX IF EXISTS ix_resource_metadata_deleted;

-- 新增活性复合索引
CREATE INDEX ix_resource_meta_type_visibility ON resource_metadata(resource_type, visibility, deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_resource_meta_owner_active ON resource_metadata(owner_id, deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_resource_meta_dept_active ON resource_metadata(department_id, deleted_at) WHERE deleted_at IS NULL;
```

### 5.2.3 MCP 接口权限收紧（过渡措施）

在 Tool CRUD 统一端点上线前，先收紧现有 MCP 配置接口：

```
1. GET /api/mcp/config：增加认证要求（Bearer token 必填）
2. PUT /api/mcp/config：角色门控从 USER 提升为 SUPER_ADMIN
3. 完整废弃在 Phase 5 完成（待 Tool CRUD 统一端点上线）
```

### 5.2.4 完成标准

- [ ] 所有新表创建成功（含 audit_logs）
- [ ] 索引优化执行成功
- [ ] MCP 接口认证已收紧
- [ ] 表结构与设计文档一致

### 5.2.5 回滚方案

```sql
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS visibility_applications;
DROP TABLE IF EXISTS resource_metadata;
-- 索引回滚：重新创建被删除的旧索引
CREATE INDEX ix_resource_metadata_visibility ON resource_metadata(visibility);
CREATE INDEX ix_resource_metadata_deleted ON resource_metadata(deleted_at) WHERE deleted_at IS NOT NULL;
```

## 5.3 Phase 2：迁移 .meta.json → resource_metadata

### 5.3.1 前置条件

- Phase 1 完成
- 备份所有 `.meta.json` 文件（复制到备份目录）

### 5.3.2 迁移步骤

```
--- 步骤 A：.meta.json → resource_metadata（Skill/Agent）---
1. 读取所有 skill 目录下的 .meta.json 文件
    - 路径：resources/skills/*/meta.json, skills/private/*/meta.json
2. 读取所有 agent 目录下的 .meta.json 文件
    - 路径：agents/*/meta.json
3. 为每条记录生成 resource_metadata 行：
    - 幂等检查：若 resource_metadata 中已存在相同 resource_type + resource_id 的记录，跳过
    - id = UUID()
    - resource_type = 'skill' 或 'agent'
    - resource_id = meta.json 中的 name 字段
    - owner_id = meta.json 中的 owner 字段（如无则设为 super_admin）
    - department_id = 从 owner 信息中获取（如无则设为 NULL）
    - visibility = meta.json 中的 visibility 字段（如无则默认 'private'）
    - version = 1
4. 批量写入 resource_metadata 表

--- 步骤 B：存量 Tool 数据回填 ---
5. 遍历 MCP 配置中注册的所有 Tool（从 extensions_config.json 或 ToolRegistry 读取）
6. 为每个存量 Tool 生成 resource_metadata 行：
    - 幂等检查：跳过已存在的记录
    - resource_type = 'tool'
    - resource_id = Tool 名称
    - owner_id = 从 MCP 创建记录反向推断（如无法确定则设为 super_admin）
    - department_id = NULL（Tool 为系统级资源）
    - visibility = 'public'（存量 Tool 保持系统公开）
    - version = 1
7. 批量写入 resource_metadata 表

--- 步骤 C：存量 Workflow 数据回填 ---
8. 从 workflow_runs 表中读取所有 run_id 以 'def:' 前缀开头的记录
9. 为每条记录生成 resource_metadata 行：
    - 幂等检查：跳过已存在的记录
    - resource_type = 'workflow'
    - resource_id = run_id 去掉 'def:' 前缀
    - owner_id = 从 workflow_runs 记录的 owner_id 字段读取（如无则设为 super_admin）
    - department_id = 从 owner 信息获取（如无则设为 NULL）
    - visibility = 'private'（存量 Workflow 默认 private）
    - version = 1
10. 批量写入 resource_metadata 表

--- 验证 ---
11. 对比文件数量和表行数
12. 保留 .meta.json 文件作为备份（不删除）
```

### 5.3.3 完成标准

- [ ] 文件数量 = 新表对应 resource_type 的行数
- [ ] 抽样校验 10% 记录，字段值一致
- [ ] owner_id 对应的用户存在于 users_ext 表
- [ ] visibility 值均为有效枚举值

### 5.3.4 回滚方案

```sql
DELETE FROM resource_metadata WHERE resource_type IN ('skill', 'agent');
```

> 回滚后恢复 .meta.json 文件（从未删除的备份中恢复）。

## 5.4 Phase 3：迁移 skill_applications → visibility_applications

### 5.4.1 前置条件

- Phase 2 完成（resource_metadata 已有数据，可用于获取 current_visibility）
- 备份 `skill_applications` 表数据

### 5.4.2 迁移步骤

```
1. 读取 skill_applications 表所有记录
2. 字段映射：
   - id → id（保留原 ID 或生成新 UUID）
   - skill_id → resource_id
   - skill_name → 保留为冗余字段或去掉
   - request_level → target_visibility
   - 新增 current_visibility 字段（从 resource_metadata 表读取）
   - 新增 resource_type 字段（固定为 'skill'）
   - applicant_id → applicant_id
   - status → status
   - approved_by → reviewed_by
   - approved_at → reviewed_at
   - comment → review_comment
3. 批量写入 visibility_applications 表
4. 验证：对比记录数和状态一致性
5. 保留旧表作为备份（不删除）
```

### 5.4.3 完成标准

- [ ] 旧表记录数 = 新表记录数（排除重复提交的情况）
- [ ] 状态一致性：旧表 approved 记录在新表中也为 approved
- [ ] applicant_id 对应的用户存在于 users_ext 表
- [ ] resource_id 在 resource_metadata 表中存在

### 5.4.4 回滚方案

```sql
DELETE FROM visibility_applications WHERE resource_type = 'skill';
```

## 5.5 Phase 4：废弃旧表

### 5.5.1 前置条件

- Phase 3 完成
- 确认代码中不再引用 `skill_default_configs` 和 `user_skill_preferences` 表

### 5.5.2 操作步骤

```
1. 全局搜索代码中对 skill_default_configs 和 user_skill_preferences 的引用
2. 移除所有引用（或标记为废弃）
3. 功能回归测试：确保 Skill 相关功能正常
4. 确认无引用后，标记旧表为废弃状态
```

### 5.5.3 完成标准

- [ ] 代码中无对旧表的活跃引用
- [ ] 功能回归测试通过
- [ ] 旧表数据保留（30 天后可删除）

### 5.5.4 回滚方案

恢复代码中对旧表的引用，重新启用旧表。**注意：回滚必须在旧表数据保留期（30 天）内完成，超期后旧表数据将被清理，无法回滚。**

## 5.6 Phase 5：后端代码重构

### 5.6.1 权限函数统一（authz.py）

```
1. 修改 check_resource_modify()：移除 super_admin 和 department_admin 的直接修改权限
   - 仅保留 owner 检查（resource_owner_id == user.id）
   - 删除 lines 508-519 中的 admin 角色判断
2. 修改 check_resource_access()：移除 department_admin 隐式同部门浏览权限
   - department_admin 与普通用户一样按 visibility 控制
   - 仅审批权限不同（dept_admin 可审批同部门 visibility 变更）
3. 删除 skills.py 中的 _check_resource_modify() 和 _is_visible_to_user()
   - 改用 authz.py 中的 check_resource_modify() 和 check_resource_access()
4. 删除 agents.py 中的 _check_resource_modify()
   - 改用 authz.py 中的 check_resource_modify()
5. 删除 agents.py 中的 _can_set_visibility()
   - visibility 设置改为通过审批流程
```

### 5.6.2 审批接口迁移

```
1. 新增 /api/visibility-applications 端点（POST/PUT/GET）
   - 使用 visibility_applications 表
   - 支持所有资源类型（resource_type 字段）
   - 审批使用乐观锁（version 字段）
   - 撤回使用 PUT /api/visibility-applications/{id}/withdraw
2. 废弃 /api/admin/skill-applications 端点
   - 保留旧端点但标记为 deprecated，返回 410 Gone
   - 前端切换到新端点后移除
3. 删除 skills.py 中的 update_skill_visibility 端点
   - visibility 变更改为通过审批流程
4. 删除 agents.py 中的 _can_set_visibility 函数
   - visibility 设置改为通过审批流程
```

### 5.6.3 资源 CRUD 迁移

```
1. 所有资源 CRUD 接口改为查询 resource_metadata 表获取 visibility/owner
   - 替换所有 _get_skill_meta() / _load_agent_meta() 调用
   - 改为查询 resource_metadata 表
2. 创建资源时同步插入 resource_metadata 记录
   - Skill/Workflow/Agent：创建资源时同步插入
   - Tool：创建 Tool 时同步插入（仅元数据）
3. 编辑资源时同步更新 resource_metadata.version
4. 删除资源时同步设置 resource_metadata.deleted_at
```

### 5.6.4 Tool CRUD 统一管理（由第二期提升至第一期）

```
1. 新增 POST /api/tools 创建 Tool 端点
   - 所有可写角色可用
   - 创建时自动插入 resource_metadata 记录（owner=当前用户，visibility=private）
   - name 在 tool 类型内全局唯一
2. 新增 DELETE /api/tools/{name} 删除 Tool 端点
   - 仅 owner 可删除
   - soft delete，设置 resource_metadata.deleted_at
   - 有 pending 申请时自动驳回
3. 废弃旧 MCP 配置直写通道
   - PUT /api/mcp/config 仅在过渡期保留（已收紧为仅 super_admin）
   - 旧端点返回 410 Gone 或标记为 deprecated
4. 统一 Tool 权限检查路径
   - 所有 Tool 操作强制经过 check_resource_modify（仅 owner）
   - 消除 MCP 接口这一唯一绕过入口
```

### 5.6.5 审计日志埋点

```
1. 定义 record_audit(actor_id, action, resource_type, resource_id, detail, ip_address) 统一工具函数
2. 以下关键操作路径注入审计埋点：
    操作位置                          | 记录内容
    ────────────────────────────────|──────────────────────────
    资源编辑（PUT 端点通过 owner 校验后）| action='update', detail 含 old/new 快照
    资源删除（DELETE 端点）           | action='delete', detail 含资源标识
    visibility 审批通过（PUT approve）| action='visibility_change', detail 含 old/new visibility
    角色变更（admin.py update_user）  | action='role_change', detail 含 old/new role
    用户禁用（admin.py disable_user） | action='update', resource_type='user'
    导入（import 端点）               | action='import', detail 含来源信息
    导出（export 端点）               | action='export', detail 含资源标识
3. 审计日志列表 API（GET /api/admin/audit-logs）
   - super_admin 可查看和筛选审计日志
   - 支持按 actor_id/action/resource_type/date 过滤 + 分页
4. 审计日志详情 API（GET /api/admin/audit-logs/{id}）
```

### 5.6.6 Workflow 运行历史 visibility 校验修复

```
1. get_run_status()（GET /api/workflows/{name}/runs/{run_id}）
   - 增加 check_resource_access 前置校验
   - 无权限时返回 404（而非 403，防止信息泄露）
2. list_runs()（GET /api/workflows/{name}/runs）
   - 增加 check_resource_access 前置校验
   - 无权限时返回空列表或 404
```

### 5.6.7 移除安全扫描占位

```
1. 移除导入流程中的 SECURITY_SCAN_FAILED 错误码引用
2. 移除导入接口中的安全扫描校验逻辑（如有）
3. 安全扫描功能在第二期实现
```

### 5.6.8 完成标准

- [ ] 所有 API 接口测试通过
- [ ] 权限检查正确（viewer 无法创建、非 owner 无法编辑）
- [ ] 并发编辑测试通过（version 冲突返回 VERSION_CONFLICT）
- [ ] 审批流程测试通过（提交/审批/驳回/撤回）
- [ ] Tool CRUD 统一端点创建/删除功能正常
- [ ] 旧 MCP 配置直写通道已废弃
- [ ] 审计日志覆盖所有关键路径
- [ ] Workflow 运行历史 visibility 校验正确
- [ ] 审计日志列表/详情 API 可用

### 5.6.9 回滚方案

回退代码变更，恢复使用旧表和旧端点。注意：
- 审计日志数据保留（不删除）
- 新创建的 Tool 在回滚后仍保留在 resource_metadata 中（静态数据，不阻塞回滚）
- MCP 直写通道恢复为原权限（USER 角色可写）

## 5.7 Phase 6：前端页面改造

### 5.7.1 现有页面改造

| 页面路径 | 改造内容 |
|---------|---------|
| `/workspace/admin/tools` | 增加 tool visibility 管理列 |
| `/workspace/admin/skill-applications` | 重构为统一的 visibility 审批页面，支持所有资源类型 |
| `/workspace/admin/skill-defaults` | 删除（功能移除） |
| `/workspace/admin/users` | 增加管理员人数限制校验、用户禁用/删除时的资源处理 |
| `/workspace/admin/departments` | 增加部门删除前的资源重分配流程 |
| `/workspace/workflows` | 增加收藏/置顶/搜索功能、visibility 标签 |
| `/workspace/workflows/[name]` | 增加 visibility 标签、导出按钮、申请 visibility 变更按钮 |
| `/workspace/workflows/[name]/edit` | 增加 owner 校验（仅 owner 可编辑） |
| `/workspace/agents` | 增加收藏/置顶/搜索功能、visibility 标签 |
| `/workspace/agents/[name]` | 增加 visibility 标签、导出按钮、申请 visibility 变更按钮 |
| `/workspace/agents/[name]/edit` | 增加 owner 校验（仅 owner 可编辑） |
| 设置 → 技能 | 删除（功能移除），改为只读列表 |

### 5.7.2 新增页面

| 页面路径 | 功能 | 权限 |
|---------|------|------|
| `/workspace/admin/visibility-applications` | 统一审批中心 | dept_admin / super_admin |
| `/workspace/admin/audit-logs` | 审计日志查询页面 | super_admin |

### 5.7.3 审计日志页面建设

| 功能 | 说明 |
|------|------|
| 日志列表 | 分页展示审计日志，每行显示时间、操作人、操作类型、资源 |
| 筛选过滤 | 按操作人（actor_id）、操作类型（action）、资源类型（resource_type）、时间范围（start_date/end_date）过滤 |
| 详情弹窗 | 点击单条记录展开 detail JSON（含 old_value / new_value 对比）|
| 操作类型标签 | 用不同颜色标签区分 create/update/delete/visibility_change/role_change/import/export |
| 导出（可选） | CSV 导出按钮，方便审计人员导出日志 |

### 5.7.4 完成标准

- [ ] 所有页面功能测试通过
- [ ] 权限边界测试通过（viewer 无法创建、non owner 无法编辑）
- [ ] 审批流程 UI 测试通过
- [ ] 审计日志页面列表、筛选、详情功能正常
- [ ] Tool 管理页 visibility 管理列和 CRUD 操作 UI 正常

### 5.7.5 回滚方案

回退代码变更，恢复使用旧页面。

## 5.8 数据一致性校验

每个 Phase 完成后执行以下校验：

### 5.8.1 基础校验

| 校验项 | 方法 | 通过标准 |
|--------|------|---------|
| 记录数对比 | COUNT(*) 新旧表 | 数量一致（允许合理差异） |
| 关键字段抽样 | 随机抽取 10% 记录对比 | owner_id、visibility、status 完全一致 |
| 枚举值校验 | 查询所有 distinct 值 | 均为有效枚举值 |
| 审计日志写入验证 | 执行关键操作后查询 audit_logs | 有对应记录且字段正确 |

### 5.8.2 功能校验

| 校验项 | 方法 | 通过标准 |
|--------|------|---------|
| 创建资源 | 通过 API 创建资源 | resource_metadata 新增记录，字段正确 |
| 编辑资源 | 通过 API 编辑资源 | version + 1，updated_at 刷新 |
| 删除资源 | 通过 API 删除资源 | deleted_at 设置，查询不可见 |
| 提交审批 | 通过 API 提交申请 | visibility_applications 新增记录，status = pending |
| 审批操作 | 通过 API 审批通过/驳回 | status 变更，reviewed_by/reviewed_at 填写 |
| 并发编辑 | 同时提交两个编辑请求 | 一个成功（version + 1），一个返回 VERSION_CONFLICT |
| 并发审批 | 同时提交两个审批请求 | 一个成功，一个返回 VERSION_CONFLICT |
| Tool CRUD | 创建/编辑/删除 Tool | resource_metadata 记录对应变更 |
| 审计日志 | 执行编辑/删除/审批后查询 | audit_logs 表有对应记录 |
| Workflow 运行历史 | 无权限用户访问运行历史 | 返回 404 或空列表 |
| 审计日志列表 | 通过 API 查询审计日志 | 分页+筛选正常，detail JSON 可解析 |

### 5.8.3 迁移专项校验

| 校验项 | 方法 | 通过标准 |
|--------|------|---------|
| .meta.json → resource_metadata | 对比文件数量和表行数 | 数量一致 |
| 存量 Tool → resource_metadata | 对比 MCP 配置中 Tool 数量与 resource_metadata 行数 | 数量一致 |
| 存量 Workflow → resource_metadata | 对比 workflow_runs 中 'def:' 记录数与 resource_metadata 行数 | 数量一致 |
| skill_applications → visibility_applications | 对比记录数和状态 | 数量一致，状态映射正确 |
| owner_id 有效性 | 验证所有 owner_id 在 users_ext 中存在 | 无孤儿记录 |
| department_id 有效性 | 验证所有 department_id 在 departments 中存在 | 无孤儿记录 |

## 5.9 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 迁移过程中有新数据写入 | 新旧数据不一致 | 迁移脚本设计为幂等（可重复执行），支持增量迁移，无需停服 |
| .meta.json 中 owner 信息缺失 | owner_id 无法填充 | 迁移前清理数据，缺失的设为 super_admin |
| 存量 Tool 无法确定 owner | owner_id 设为 super_admin | 标记这类 Tool，上线后再通过审批流程转交 |
| 旧表数据量大，迁移耗时超预期 | Phase 超时 | 分批迁移，每批 1000 条，可中断恢复 |
| 废弃表仍被代码引用 | 功能异常 | 迁移前全局搜索引用，逐一清理 |
| 前端页面改造范围大 | 测试不充分 | 分页面逐步改造，每改一个页面立即测试 |
| 废弃表超 30 天保留期后无法回滚 | 回滚失败 | 回滚操作必须在 30 天保留期内完成 |
| MCP 接口权限收紧影响现有用户 | 已习惯通过 MCP 管理 Tool 的用户操作被拒 | 过渡期间文档公告，待 Phase 5 统一端点上线后完全切换 |

### 破坏性变更清单

以下变更会**破坏现有代码行为**，需在 Phase 5/6 中同步处理：

| 变更 | 影响 | 处理方式 |
|------|------|---------|
| `check_resource_modify` 移除 admin 直接修改权限 | super_admin/department_admin 无法直接编辑非自己资源 | 改为仅 owner 可编辑，admin 通过审批流程管理 visibility |
| MCP 配置直写通道废弃 | 现有通过 PUT /api/mcp/config 管理 Tool 的流程需修改 | 切换到新的 POST/DELETE Tool CRUD 端点 |
| Workflow 运行历史新增 visibility 校验 | 之前所有认证用户可见的运行历史可能对部分用户隐藏 | 符合 visibility 设计原则，需在变更公告中说明 |
| `check_resource_access` 移除 department_admin 隐式同部门权限 | department_admin 不再隐式可见同部门 private 资源 | department_admin 与普通用户一样按 visibility 控制 |
| `update_skill_visibility` 端点废弃 | owner 无法直接修改 skill visibility | 改为通过审批流程提交变更申请 |
| `_can_set_visibility` 函数废弃 | department_admin 无法直接设置 department visibility | 改为通过审批流程 |
| `_get_skill_meta` / `_load_agent_meta` 替换为 resource_metadata 查询 | 所有读取 .meta.json 的代码需修改 | 统一改为查询 resource_metadata 表 |
| `_check_resource_modify` / `_is_visible_to_user` 重复函数删除 | skills.py 和 agents.py 中的调用需修改 | 改为使用 authz.py 中的统一函数 |
| `skill_applications` 表废弃 | 使用旧表的代码需修改 | 迁移到 visibility_applications |
| `SECURITY_SCAN_FAILED` 错误码移除 | 导入流程中的安全扫描逻辑移除 | 第一期不做安全扫描，第二期实现 |

## 5.10 迁移检查清单

### Phase 1 检查清单

- [ ] 所有新表创建成功（resource_metadata, visibility_applications, audit_logs）
- [ ] 索引优化执行成功（移除旧索引、新增复合覆盖索引）
- [ ] 表结构与设计文档一致
- [ ] MCP 接口认证已收紧（GET 增加认证，PUT 提升为仅 super_admin）

### Phase 2 检查清单

- [ ] .meta.json 文件已备份
- [ ] 迁移脚本已编写并测试（含 .meta.json + 存量 Tool + 存量 Workflow）
- [ ] 记录数对比通过（三种数据来源分别校验）
- [ ] 抽样校验通过（10% 记录字段一致）
- [ ] owner_id 有效性校验通过（无孤儿记录）
- [ ] 存量 Tool 和 Workflow 均已回填完成

### Phase 3 检查清单

- [ ] skill_applications 表已备份
- [ ] 迁移脚本已编写并测试
- [ ] 记录数对比通过
- [ ] 状态一致性校验通过
- [ ] current_visibility 字段正确填充

### Phase 4 检查清单

- [ ] 代码中无对旧表的活跃引用
- [ ] 功能回归测试通过
- [ ] 旧表数据保留

### Phase 5 检查清单

- [ ] authz.py 权限函数统一完成
- [ ] 重复函数（_check_resource_modify、_is_visible_to_user）已删除
- [ ] 审批接口迁移到 visibility_applications
- [ ] 资源 CRUD 接口改为查询 resource_metadata
- [ ] Tool CRUD 统一端点（POST /api/tools + DELETE /api/tools/{name}）已实现
- [ ] 旧 MCP 配置直写通道已废弃
- [ ] 审计日志埋点覆盖所有关键操作路径
- [ ] 审计日志列表/详情 API 已实现
- [ ] Workflow 运行历史 visibility 校验已修复
- [ ] 所有 API 接口测试通过
- [ ] 权限边界测试通过
- [ ] 并发编辑测试通过
- [ ] 旧端点已废弃（返回 410 Gone）

### Phase 6 检查清单

- [ ] 所有前端页面功能测试通过
- [ ] 审批中心页面功能正常
- [ ] 审计日志页面列表、筛选、详情功能正常
- [ ] Tool 管理页 visibility 管理列和 CRUD 操作 UI 正常
- [ ] 权限边界 UI 测试通过
- [ ] 旧页面已移除或标记为废弃
