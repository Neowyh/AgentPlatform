# 功能规划与开发跟踪

本文档分为两部分：
- **第一部分：未开发功能** — 已明确需求但尚未实现的特性，每个条目包含背景、接口就绪状态、前端缺口和实现要点。
- **第二部分：已完成功能** — 已实现完成的功能，保留记录供参考。

> **追加规则：** 新增未开发功能请追加至第一部分的末尾，保持编号连续。

---

# 第一部分：未开发功能

## 1. 文档体系建设（基于文档梳理与差距分析）

> 来源：`docs/文档体系梳理与差距分析.md` 全量分析结果。以下按优先级分组列出待完成工作。

### 1.1 高优先级（立即补充）

#### 1.1.1 生产部署标准指南

- **现状**：仅有内网离线部署指南（`scripts/README-intranet.md`）和离线部署专题文档（`docs/deployment/`），缺少标准在线生产部署文档。
- **待完成**：
  - 编写 Docker Compose 生产模式部署指南（区别于开发模式的 docker-start）
  - 编写 Kubernetes 部署参考架构文档
  - 明确生产环境与开发环境的配置差异（安全、性能、日志）
  - 提供部署验证清单（健康检查、功能验证、性能基线）
- **建议位置**：`docs/deployment/production-deployment.md` + `docs/deployment/production-deployment-zh.md`

#### 1.1.2 备份与恢复策略

- **现状**：完全缺失。数据库备份、对话历史恢复、配置备份均无文档。
- **待完成**：
  - 数据库（SQLite/PostgreSQL）备份策略与操作步骤
  - 对话历史和用户数据恢复流程
  - 配置文件版本管理与回滚方案
  - 灾难恢复预案（RTO/RPO 目标定义）
- **建议位置**：`docs/deployment/backup-and-recovery.md`

#### 1.1.3 高可用/扩容方案

- **现状**：完全缺失。无水平扩展、负载均衡、多实例部署文档。
- **待完成**：
  - 水平扩展架构设计（多 Gateway 实例、共享数据库）
  - 负载均衡配置参考（Nginx/HAProxy）
  - 会话亲和性与状态管理策略
  - 沙箱资源池化与弹性伸缩方案
- **建议位置**：`docs/deployment/high-availability.md`

#### 1.1.4 CI/CD 流水线文档

- **现状**：完全缺失。无 CI/CD 流水线、自动发布流程文档。
- **待完成**：
  - CI 流水线配置说明（lint、test、build 步骤）
  - CD 发布流程（镜像构建、推送、部署触发）
  - 分支策略与发布版本管理
  - 自动化测试在 CI 中的集成方式
- **建议位置**：`docs/deployment/ci-cd-pipeline.md`

### 1.2 中优先级（短期优化）

#### 1.2.1 版本迁移指南

- **现状**：无版本间迁移指南（v1→v2、版本升级路径）。
- **待完成**：
  - v1 → v2 迁移路径与数据转换说明
  - 配置文件格式变更对照表
  - API 兼容性说明与废弃接口清单
  - 回滚方案
- **建议位置**：`docs/migration/v1-to-v2.md`

#### 1.2.2 前端组件开发规范

- **现状**：`frontend/AGENTS.md` 有架构描述，但缺少组件开发模式文档。无 Shadcn UI 使用模式、组件设计规范。
- **待完成**：
  - Shadcn UI 组件封装规范（何时用原生、何时封装）
  - 组件目录结构与命名约定
  - 状态管理模式（TanStack Query vs React Hook vs Context）
  - 样式规范（Tailwind 类名组织、响应式断点使用）
- **建议位置**：`frontend/docs/component-development-guide.md`

#### 1.2.3 数据模型/类型系统集中文档

- **现状**：backend 和 frontend 类型散落在代码中，缺少集中文档。
- **待完成**：
  - 核心数据模型概览（Thread、Message、Agent、Skill、Tool、Config）
  - 前后端类型映射关系
  - 枚举值与状态机说明
  - API 响应数据结构速查表
- **建议位置**：`docs/data-models.md`（或 `backend/docs/DATA_MODELS.md` + `frontend/docs/type-system.md`）

#### 1.2.4 测试 Step-by-Step 教程

- **现状**：`docs/testing-guidelines.md` 存在但与实际测试框架脱节，缺少可操作的教程。
- **待完成**：
  - "如何编写一个新的 backend pytest 测试"——从 mock 到集成的完整示例
  - "如何编写一个新的 frontend E2E 测试"——Playwright 完整示例
  - "如何编写一个新的 frontend 单元测试"——Vitest 完整示例
  - 测试数据工厂使用教程（`backend/tests/factories/` 的实操指南）
- **建议位置**：`docs/testing/backend-test-tutorial.md`、`docs/testing/frontend-e2e-tutorial.md`、`docs/testing/frontend-unit-tutorial.md`

#### 1.2.5 生产环境安全检查清单

- **现状**：`backend/docs/GUARDRAILS.md` 和 `SECURITY.md` 存在，但缺少面向运维的安全检查清单。
- **待完成**：
  - SSL/TLS 证书配置
  - CORS 策略配置
  - API Key 轮换与管理
  - 审计日志启用与配置
  - 速率限制配置
  - 输入验证与 SQL 注入防护检查
  - 容器安全基线（非 root 运行、只读文件系统等）
- **建议位置**：`docs/deployment/security-checklist.md`

#### 1.2.6 通用运维排障手册

- **现状**：`docs/deployment/` 有离线场景排查，缺少通用运维排障文档。
- **待完成**：
  - 端口冲突排查
  - 数据库连接失败排查
  - LLM API 超时/限流排查
  - 沙箱启动失败排查
  - MCP 服务器连接失败排查
  - 前端构建失败排查
  - 日志级别配置与日志分析方法
- **建议位置**：`docs/deployment/troubleshooting.md`

#### 1.2.7 健康检查/监控集成文档

- **现状**：LangSmith/Langfuse 追踪有文档，但缺少基础设施级监控文档。
- **待完成**：
  - 健康检查端点文档（`/api/health` 或类似）
  - Prometheus 指标导出配置
  - Grafana Dashboard 模板
  - 日志聚合配置（stdout → ELK/Loki）
  - 告警规则建议
- **建议位置**：`docs/deployment/monitoring.md`

#### 1.2.8 config.example.yaml 逐字段注释

- **现状**：config.example.yaml 有 1161 行，但字段缺少注释说明。
- **待完成**：
  - 为每个配置字段添加行内注释（类型、默认值、是否必填、说明）
  - 提供最小可用配置示例（仅 LLM + 搜索）
  - 常见配置组合示例（单用户开发、小团队、企业部署）
- **建议位置**：原地更新 `config.example.yaml`，新增 `docs/config-annotated-example.yaml`

#### 1.2.9 常见错误码对照表

- **现状**：缺失。开发者遇到错误时只能查看源码。
- **待完成**：
  - HTTP 错误码与业务错误码汇总
  - 每个错误码的触发条件、可能原因、解决方法
  - 前端错误提示文案与后端错误码的映射
- **建议位置**：`docs/error-codes.md`（或 `backend/docs/ERROR_CODES.md`）

### 1.3 已有文档改进项

#### 1.3.1 docs/ 目录统一索引

- **现状**：`backend/docs/README.md` 做了索引，但 `docs/` 根目录无索引。50+ 文件缺少导航。
- **待完成**：
  - 创建 `docs/README.md` 作为文档导航入口
  - 按类别组织（部署、测试、验证、架构、规划、智能体、手册）
  - 标注文档状态（活跃/归档/内部）
- **建议位置**：`docs/README.md`

#### 1.3.2 内部过程文档归档

- **现状**：`docs/bug-list.md`、`progress.md`、`task_plan.md`、`findings.md` 等为内部开发过程记录，不适合外部开发者阅读。
- **待完成**：
  - 将内部过程文档移至 `docs/internal/` 或添加内部标记
  - 保留有价值的结论性内容，移除临时性记录
- **建议位置**：`docs/internal/`

#### 1.3.3 中英文统一

- **现状**：部分文档仅中文，部分仅英文，不利于国际化协作。
- **待完成**：
  - 核心文档（架构、部署、API）提供中英双语版本
  - 建立翻译对照表或使用统一文档模板
  - 优先统一：`docs/deployment/`、`docs/architecture/overview.md`、`docs/development/learning-roadmap.md`

#### 1.3.4 后端/前端架构全景图统一

- **现状**：backend 和 frontend 架构图分散在不同文件，缺少统一视图。
- **待完成**：
  - 创建端到端架构全景图（前端 → Gateway → Agent → 工具/沙箱 → 外部服务）
  - 标注各组件间的数据流和依赖关系
  - 提供交互式或可缩放的架构图（Mermaid/Diagrams）
- **建议位置**：`docs/architecture/overview.md`



## 2. 资源可见性变更申请前端入口（智能体 / 技能）

### 背景

后端已提供统一的 VisibilityApplication 体系，支持 agent、skill、workflow 三种资源类型的可见性变更申请与审批。当前前端实现不完整：

| 资源类型 | 申请入口 | 审批入口 |
|---------|---------|---------|
| workflow | ✅ `/workspace/workflows/{name}` 页面有"申请可见性"按钮 | ✅ `/workspace/admin/visibility-applications` |
| skill | ❌ 无前端入口 | ✅ `/workspace/admin/visibility-applications` |
| agent | ❌ 无前端入口，编辑页 visibility 为 `disabled`，备注"由管理员管理" | ✅ `/workspace/admin/visibility-applications` |

此外，agent 编辑页（`frontend/src/app/workspace/agents/[agent_name]/edit/page.tsx:200`）的 visibility 下拉框为 `disabled`，普通用户无法申请可见性变更，只能依赖管理员直接修改数据库。

### 后端就绪状态

**API**: `POST /api/visibility-applications` ✅ 已实现

支持所有 `resource_type`（agent / skill / workflow），请求体：

```json
{
  "resource_type": "agent",
  "resource_id": "my-agent",
  "target_visibility": "public",
  "reason": "需要公开给团队使用"
}
```

**类型定义**: `frontend/src/core/visibility-applications/types.ts` ✅ 已定义

```typescript
interface CreateVisibilityApplicationRequest {
  resource_type: "tool" | "skill" | "workflow" | "agent";
  resource_id: string;
  target_visibility: "private" | "department" | "public";
  reason: string;
}
```

**API 函数**: `frontend/src/core/visibility-applications/api.ts` ✅ `createVisibilityApplication()`
**审批模块**: `/workspace/admin/visibility-applications` ✅ 已支持所有资源类型

### 前端缺口

#### 2.1 智能体详情页添加"申请可见性"按钮

**目标文件**: `frontend/src/app/workspace/agents/[agent_name]/page.tsx`（或 `detail/page.tsx`，需确认文件是否存在）

参照 workflow 详情页（`frontend/src/app/workspace/workflows/[workflow_name]/page.tsx:219-224`）的模式：

```tsx
<Button variant="outline" onClick={() => setVisibilityDialogOpen(true)}>
  {t.agents.applyVisibility}
</Button>
```

- 点击后弹出对话框，用户选择目标可见性（department / public）并填写理由
- 提交 `createVisibilityApplication({ resource_type: "agent", resource_id, target_visibility, reason })`

若 agent 详情页不存在，需先创建。

#### 2.2 智能体编辑页解除 visibility 禁用

**目标文件**: `frontend/src/app/workspace/agents/[agent_name]/edit/page.tsx:200`

当前行为：visibility 下拉框 `disabled`，提示"由管理员管理"。

改为：visibility 下拉框可选，当用户选择不同于当前值时弹出确认对话框（或提示提交流程），调用申请接口而非直接修改。

#### 2.3 技能申请入口

需在技能管理页面（位置待确认，`src/app/workspace/` 下目前无 skills 目录）添加申请入口，或与技能浏览页面整合。

`frontend/src/core/skills/api.ts:61` 已导出 `submitSkillApplication()` 函数但未被任何 UI 组件调用。

#### 2.4 i18n 补充

需补充以下国际化键值（中英文）：

| Key | en-US | zh-CN |
|-----|-------|-------|
| `agents.applyVisibility` | Apply for Visibility | 申请可见性变更 |
| `agents.visibilityReason` | Reason for visibility change | 变更理由 |
| `agents.visibilityReasonRequired` | Please provide a reason | 请填写变更理由 |
| `agents.visibilityTarget` | Target visibility | 目标可见性 |
| `agents.applicationSubmitted` | Application submitted successfully | 申请已提交 |
| `skills.applyVisibility` | Apply for Visibility | 申请可见性变更 |
| `skills.applicationSubmitted` | Application submitted successfully | 申请已提交 |

### 相关文件

| 文件 | 说明 |
|------|------|
| `frontend/src/app/workspace/workflows/[workflow_name]/page.tsx` | 参照实现（workflow 申请按钮 + 对话框） |
| `frontend/src/app/workspace/agents/[agent_name]/edit/page.tsx` | 编辑页 visibility 禁用，需改造 |
| `frontend/src/core/visibility-applications/api.ts` | 统一的 API 调用函数 |
| `frontend/src/core/visibility-applications/types.ts` | 类型定义 |
| `frontend/src/core/skills/api.ts` | `submitSkillApplication()` 函数，待接入 UI |
| `backend/app/gateway/routers/visibility_applications.py` | 后端 API 实现 |

### 实现优先级建议

1. **P0** 智能体详情页 + 申请入口（第 2.1 节）
2. **P1** 智能体编辑页 visibility 改进（第 2.2 节）
3. **P2** 技能申请入口（第 2.3 节）
4. **P3** i18n 补充（第 2.4 节）

---

## 3. 可见性申请重复提交的 UX 优化

### 背景

用户在工作流详情页提交可见性变更申请时，若该资源已有 PENDING 状态的申请，后端返回 409 Conflict，前端展示 "Failed to submit visibility application: A pending application already exists for this resource"。问题在于：

1. **状态不透明**：用户无法知道自己的资源已有待审核申请
2. **无前置检查**：可见性弹窗中直接展示提交表单，用户填完所有内容后提交才被拒绝
3. **无恢复路径**：报错后用户不知道可以撤回旧申请或等待审核

### 当前已知边界场景（已处理）

| 场景 | 处理方式 | 位置 |
|------|---------|------|
| 工作流被删除后 PENDING 申请 | 自动标记为 `rejected`，附注"资源已删除，申请自动关闭" | `backend/app/gateway/routers/workflows.py:377-397` |

### 修复方案

#### 3.1 后端：新增查询接口

**目标文件**: `backend/app/gateway/routers/visibility_applications.py`

新增 `GET /api/visibility-applications/check`，用户可查询指定资源的 pending 申请状态（无需 admin 角色）：

```python
# 请求参数
resource_type: str  # tool | skill | workflow | agent
resource_id: str

# 响应
{
  "has_pending": bool,
  "application": ApplicationResponse | null  # 存在 pending 申请时返回详情
}
```

设计原则：
- 该接口是只读的，仅查询自己资源的申请状态（资源已存在于当前上下文中）
- 不需要 admin 权限，任何认证用户均可调用
- 不与现有 `GET /api/visibility-applications`（require_role 管理端）冲突

#### 3.2 前端：弹窗状态感知

**目标文件**: `frontend/src/app/workspace/workflows/[workflow_name]/page.tsx`

打开可见性弹窗时先调用查询接口，按状态展示不同 UI：

| 状态 | UI |
|------|-----|
| 无 pending 申请 | 正常提交表单（现有行为不变） |
| 有 pending 申请 | 展示"已有待审核申请"提示（提交时间、目标可见性），提供"撤回并重新申请"按钮 |

交互流程：

```
用户点击"申请可见性变更"
  → 检查该资源是否有 pending 申请
  → 无 → 显示正常提交表单
  → 有 → 显示状态卡片：
         "你于 2026-07-09 14:30 提交了 private → public 的申请，等待管理员审核。"
         [撤回并重新申请] [关闭]
           ↓ 点击撤回
           调用 withdraw API
           成功后关闭状态卡片，刷新为提交表单
```

**新增 API 函数**: `frontend/src/core/visibility-applications/api.ts`
```typescript
export async function checkVisibilityApplicationStatus(
  resourceType: string,
  resourceId: string,
): Promise<{ has_pending: boolean; application: VisibilityApplication | null }>
```

#### 3.3 错误兜底

若用户仍因竞态条件在提交时收到 409，保持现有错误提示，但确保响应体中包含已有申请的 ID 和 version，方便用户直接执行撤回。

#### 3.4 i18n 补充

| Key | en-US | zh-CN |
|-----|-------|-------|
| `workflows.pendingApplicationExists` | You have a pending application submitted at {time} | 你于 {time} 已提交待审核申请 |
| `workflows.withdrawAndResubmit` | Withdraw and Re-apply | 撤回并重新申请 |
| `workflows.withdrawSuccess` | Application withdrawn, you can now submit a new one | 申请已撤回，可以重新提交 |
| `workflows.checkingApplication` | Checking application status... | 正在检查申请状态... |

#### 3.5 相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/gateway/routers/visibility_applications.py` | 新增 check 查询接口 |
| `frontend/src/core/visibility-applications/api.ts` | 新增 check 和 withdraw API 函数 |
| `frontend/src/core/visibility-applications/types.ts` | 类型定义（无需改动） |
| `frontend/src/app/workspace/workflows/[workflow_name]/page.tsx` | 弹窗状态感知改造 |
| `frontend/src/core/i18n/locales/en-US.ts` | 英文国际化 |
| `frontend/src/core/i18n/locales/zh-CN.ts` | 中文国际化 |
| `frontend/src/core/i18n/locales/types.ts` | i18n 类型定义 |

### 实现优先级建议

1. **P0** 后端 check 接口（第 3.1 节）
2. **P1** 前端弹窗状态感知（第 3.2 节）— 依赖 P0
3. **P1** 撤回流程集成（第 3.2 节撤回分支）
4. **P2** i18n 补充（第 3.4 节）
5. **P3** 错误兜底优化（第 3.3 节）





## 4. Skill Category 统一：移除 public/custom 划分

### 背景

当前 Skill 有 `SkillCategory.PUBLIC` 和 `SkillCategory.CUSTOM` 两个类别，分别存储于 `skills/public/` 和 `skills/custom/` 目录。在"用户拥有资源 + `resource_metadata` 管控可见性"的 RBAC 模型下，这一划分是冗余的：

| 要表达的含义 | 当前用 category 表达 | 可用 resource_metadata 替代 |
|------------|-------------------|---------------------------|
| 平台内置、只读 | `PUBLIC` | `owner_id="builtin"` + 编辑接口禁止非 owner 修改 |
| 所有人可见 | PUBLIC 类别跳过 RBAC | `visibility="public"` |
| 用户创建、可编辑 | `CUSTOM` | `owner_id=<user_id>` |

### 收益

- **消除特殊判断路径**：`list_skills()` 不再需要 `if skill.category == SkillCategory.PUBLIC: continue` 这条旁路，所有资源走同一套 RBAC 逻辑
- **简化安装/导入流程**：不再关心目标目录是 `custom/` 还是 `public/`
- **平台内置技能也可做可见性管理**：超级管理员可以"公开"或"部门内开放"一个内置技能
- **资源类型间行为一致**：Agent、Tool、Workflow 都没有 public/custom 之分，Skill 是唯一的例外

### 方案

#### 5.1 引入 builtin 用户

在 `_ensure_admin_user()` 同一 startup hook 中，确保一个 `UserModel(id="builtin", username="builtin", role="user", disabled=True)` 存在。所有平台内置 skill 的 `owner_id = "builtin"`。

编辑接口检查 `if owner_id == "builtin": raise 403`（只读保护）。
前端可将 `builtin` 用户的资源标记为"系统内置"（`disabled=True` 做标识）。

#### 5.2 存储目录合并

将 `skills/public/{name}/` 和 `skills/custom/{name}/` 统一到 `skills/{name}/`。

需要 migration 脚本：
1. 扫描 `skills/public/` 和 `skills/custom/` 下所有 skill
2. 平铺到 `skills/{name}/`（同名冲突时 custom 优先）
3. 为所有原 public skill 创建 `resource_metadata` 记录（`owner_id="builtin"`, `visibility="public"`）
4. 为所有原 custom skill 创建 `resource_metadata` 记录（`owner_id` 按已有数据或 super_admin, `visibility` 按已有数据或 private）

#### 5.3 移除 `SkillCategory` 枚举

删除 `SkillCategory.PUBLIC` 和 `SkillCategory.CUSTOM`，以及在以下位置的分支判断：

| 文件 | 删除内容 |
|------|---------|
| `ideer/skills/types.py` | `SkillCategory` 枚举定义 |
| `skills/storage/local_skill_storage.py` | `_iter_skill_files()` 中按 category 遍历的逻辑 |
| `skills/storage/skill_storage.py` | 所有 category 相关方法 |
| `app/gateway/routers/skills.py` | `list_skills()` 中 `skill.category == SkillCategory.PUBLIC` 的跳过逻辑 |
| `ideer/skills/loader.py` | category 相关的过滤/分组逻辑 |

#### 5.4 前端调整

- 技能管理页面不再区分"系统技能"和"自定义技能"标签页
- 在技能列表中增加 owner 标识（builtin / user name）代替原来的分类标签

### 依赖关系

| 前置条件 | 说明 |
|---------|------|
| 第 6 项（懒注册机制） | 确保统一后新增的 skill 自动有 resource_metadata |
| 第 2 项（可见性申请前端入口） | 确保用户对"系统内置"skill 的可见性变更能走申请流程 |

### 风险与回退

| 风险 | 缓解措施 |
|------|---------|
| 目录合并后文件路径改变，旧路径引用失效 | 添加软链接或缓存层兼容 |
| 迁移过程可能丢数据 | 先备份再迁移，迁移脚本幂等可重入 |
| builtin 用户被误删 | `_ensure_admin_user` 级 startup 自动重建 |
| 前端未同步导致分类标签错误 | 前端先发 PR 适配，后端后发 PR 合并 |

### 实现优先级建议

1. **P0** builtin 用户 seed（6.1）— 轻量，可独立上线
2. **P1** 目录合并 migration 脚本（6.2）
3. **P1** 代码中移除 category 分支（6.3）
4. **P2** 前端适配（6.4）
5. **P3** 旧路径兼容层（可选）

---

## 5. QA 测试资源残留清理机制缺失

### 背景

`backend/tests/qa/test_api_qa.py` 中的 CRUD 测试（`test_agent_crud`、`test_workflow_crud`）会通过 API 创建 agent 和 workflow 资源，并在测试结束时删除。但如果测试进程被外部因素（系统休眠、OOM、手动中断等）异常终止，资源会被永久残留：

| 资源 | 创建时间 | 残留原因 |
|------|---------|---------|
| `qa-test-agent-03691324` | 2026-07-11 00:50:13 | 测试进程在创建后、删除前被中断 |
| `qa-test-workflow` | 2026-07-11 00:50:13 | 同上，仅隔 235ms |

### 具体问题

#### 5.1 无资源清理兜底机制

- Agent 和 Workflow 的测试 CRUD 均无 setup/teardown 兜底清理（例如 `pytest.fixture(autouse=True)` 或 `yield` 删除）
- 系统无定期清理任务或启动时 reconciliation 来清除残留的测试资源
- 手动清理只能靠直接操作数据库，无 API 或脚本支持

#### 5.2 Agent 创建未记录审计日志

对比：

| 操作 | 是否调用 `record_audit()` |
|-----|-------------------------|
| workflow 创建 | ✅ 是（`workflows.py:267`） |
| workflow 更新 | ✅ 是（`workflows.py:338`） |
| workflow 删除 | ✅ 是（`workflows.py:403`） |
| agent 创建 | ❌ **否**（`agents.py:502-581` 无 audit 调用） |
| agent 更新 | ✅ 是（`agents.py:690`） |
| agent 删除 | ✅ 是（`agents.py:865`） |

Agent 创建缺少 audit log 意味着无法通过审计追踪定位残留资源的创建来源（actor、IP、时间）。

#### 5.3 Agent 与 Workflow 审计覆盖不一致

同一测试套件触发的操作，workflow 有完整审计链路而 agent 缺失，给残留排查带来额外困难。

### 修复方案

#### 5.4 测试层：fixture 兜底清理

**目标文件**: `backend/tests/qa/test_api_qa.py`

参照以下模式在 `TestAgentsQA` 和 `TestWorkflowsQA` 中添加 `autouse` fixture：

```python
@pytest.fixture(autouse=True)
def cleanup_agent(request, auth_cookies):
    yield
    # 在 teardown 时清理残留的测试 agent
    name = getattr(request.node, "_test_agent_name", None)
    if name:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.delete(f"{BASE_URL}/api/agents/{name}", cookies=auth_cookies)
```

给 `test_agent_crud` 和 `test_workflow_crud` 的测试 request 绑定资源名：

```python
request.node._test_agent_name = agent_name  # 创建资源后立即注册
```

#### 5.5 Agent 创建补充 audit log

**目标文件**: `backend/app/gateway/routers/agents.py` — `create_agent_endpoint()`（第 566 行）

在 `logger.info(f"Created agent ...")` 之后补充：

```python
await record_audit(
    actor_id=current_user.id,
    action="create",
    resource_type="agent",
    resource_id=normalized_name,
    ip_address=http_request.client.host if http_request.client else None,
)
```

#### 5.6 启动时/定期清理机制

**可选方案**（二选一或同时实现）：

1. **启动时 reconciliation**：参照 `_ensure_admin_user()` 模式，在 `app.py:lifespan()` 中扫描 `resource_metadata` 表中 `resource_id` 以 `qa-test-` 开头的记录并清理
2. **定期清理脚本**：提供 CLI 命令 `make clean-test-resources` 或 `python -m ideer.scripts.clean_qa_test_data`

#### 边界情况

| 场景 | 处理 |
|------|------|
| 测试正运行中被清理 | fixture teardown 与清理脚本可能竞争 — 清理脚本应检查资源的 `created_at`（> 1 小时前才清理） |
| agent 文件已写入磁盘但 metadata 残留 | 先删除磁盘文件，再删除 metadata 记录 |
| workflow 磁盘文件已写入 | 删除 metadata + 调用 `_workflow_store.delete_workflow()` |

### 相关文件

| 文件 | 改动量 |
|------|--------|
| `backend/tests/qa/test_api_qa.py` | +40 行（autouse fixture + 资源名注册） |
| `backend/app/gateway/routers/agents.py` | +7 行（create_agent_endpoint 补充 audit） |
| `backend/app/gateway/app.py` | +20 行（启动时 reconciliation，可选） |

### 实现优先级建议

1. **P0** Agent 创建补充 audit log（5.5）— 轻量，可独立上线
2. **P1** 测试 fixture 兜底清理（5.4）— 阻止新残留产生
3. **P2** 清理脚本（5.6 方案 2）— 清理已残留资源

---

## 6. 前端 i18n 硬编码字符串迁移

### 背景

当前前端使用自建 i18n 系统（`frontend/src/core/i18n/`），核心工作区（chats、workflows、messages、settings 等）已正确使用 `useI18n()` hook。但存在大量硬编码字符串未接入 i18n 系统，总计约 23 个文件、385+ 个硬编码字符串。

### 问题分布

| 级别 | 模块 | 文件数 | 硬编码字符串数 |
|------|------|--------|--------------|
| CRITICAL | 管理后台 (admin/) | 8 | ~260+ |
| HIGH | 登录/注册页 | 2 | ~35 |
| HIGH | Landing 页面 (hero, footer, 各 section) | 7 | ~71 |
| MEDIUM | skill-editor, about-content 等 | 5 | ~15 |
| LOW | agents/new/page.tsx (部分迁移) | 1 | 5 |

**总计约 23 个文件、385+ 个硬编码字符串。**

### 6.1 管理后台 (CRITICAL)

**目标文件**: `frontend/src/app/workspace/admin/` 下 8 个文件

所有管理后台页面完全未使用 `useI18n()`，约 260+ 个中文硬编码字符串：

| 文件 | 硬编码字符串数 |
|------|--------------|
| `admin/page.tsx` | ~10 |
| `admin/users/page.tsx` | ~77 |
| `admin/departments/page.tsx` | ~50 |
| `admin/resources/page.tsx` | ~18 |
| `admin/tools/page.tsx` | ~11 |
| `admin/visibility-applications/page.tsx` | ~53 |
| `admin/audit-logs/page.tsx` | ~60 |
| `admin/skill-applications/page.tsx` | ~1 |

**注意：** 部分翻译 key 已存在于 `en-US.ts` / `zh-CN.ts` 中（如 `common.delete/save/cancel/edit/create`、`workflows.visibilityPrivate/Department/Public`、`agents.visibilityPrivate/Department/Public`），可直接复用。

### 6.2 登录/注册页 (HIGH)

**目标文件**:
- `frontend/src/app/(auth)/login/page.tsx` — ~14 个硬编码字符串
- `frontend/src/app/(auth)/setup/page.tsx` — ~21 个硬编码字符串

登录页混合了中文错误消息和英文 UI 标签，setup 页全部为英文。建议新增 `auth.*` 命名空间或复用现有 `common.*` 翻译。

### 6.3 Landing 页面 (HIGH)

**目标文件**: `frontend/src/components/landing/` 下 7 个文件

| 文件 | 硬编码字符串数 |
|------|--------------|
| `hero.tsx` | ~18 |
| `footer.tsx` | ~3 |
| `sections/whats-new-section.tsx` | ~20 |
| `sections/skills-section.tsx` | ~3 |
| `sections/sandbox-section.tsx` | ~10 |
| `sections/case-study-section.tsx` | ~14 |
| `sections/community-section.tsx` | ~3 |

建议在翻译文件中新增 `landing.*` 命名空间。

### 6.4 其他文件 (MEDIUM)

| 文件 | 硬编码字符串数 | 说明 |
|------|--------------|------|
| `skill-editor.tsx` | ~11 | 编辑面板标题、按钮、验证错误 |
| `about-content.ts` | ~47 行中文 | 关于页面的 markdown 内容 |
| `citation-link.tsx` | 1 | 中文 "来源" 字符串 |
| `post-list.tsx` | 2 | "Language:"、"Tags:" |
| `prompt-input.tsx` | 1 | aria-label="Submit" |

### 6.5 部分迁移文件 (LOW)

**目标文件**: `frontend/src/app/workspace/agents/new/page.tsx`

已使用 `useI18n()` 和 `t.agents.*`，但可见性标签仍硬编码：
- `可见性`、`私有`、`部门共享`、`公开`、`部门共享和公开选项仅管理员可用`

翻译 key 已存在于 `en-US.ts` / `zh-CN.ts` 中（`agents.visibilityPrivate/Department/Public`），直接替换即可。

### 实现优先级建议

1. **P0** agents/new/page.tsx 可见性标签替换（5 个 key 已存在，改动最小）
2. **P1** 管理后台整体接入 i18n（最大收益，~260 个字符串）
3. **P2** 登录/注册页接入 i18n
4. **P3** Landing 页面接入 i18n（需新增 `landing.*` 命名空间）
5. **P4** 其他零散文件迁移

---

# 第二部分：已完成功能

## ✅ 1. MCP 配置管理页面（增删改）

**状态：✅ 已完成**（由 2026-07 实现完整 CRUD + mock PUT handler）

**实现内容：**
- `ToolSettingsPage`（`frontend/src/components/workspace/settings/tool-settings-page.tsx`）已支持添加/编辑/删除服务器
  - 页面顶部"添加服务器"按钮 → 弹出表单弹窗
  - 每个 item 右侧"编辑"按钮 → 弹出表单弹窗（预填当前值）
  - 每个 item 右侧"删除"按钮 → 二次确认弹窗
- 表单字段：服务器名称、type（stdio/sse/http）、command、args、url、env、headers、description、enabled
- `KeyValueEditor` 组件支持 env/headers 的键值对动态增删
- Hooks（`frontend/src/core/mcp/hooks.ts`）：`useAddMCPServer`、`useUpdateMCPServer`、`useDeleteMCPServer`、`useEnableMCPServer`
- i18n 键值已补充（中英文）
- Mock PUT handler 已补充（`frontend/src/app/mock/api/mcp/config/route.ts`）

**相关文件：**
- `frontend/src/components/workspace/settings/tool-settings-page.tsx`
- `frontend/src/core/mcp/hooks.ts`
- `frontend/src/core/mcp/api.ts`
- `frontend/src/core/mcp/types.ts`
- `frontend/src/app/mock/api/mcp/config/route.ts`
- `frontend/src/core/i18n/locales/en-US.ts`、`zh-CN.ts`、`types.ts`
- `backend/app/gateway/routers/mcp.py`

## ✅ 2. 智能体元数据统一为 ResourceMetadata（移除 .meta.json）

**状态：✅ 已完成**（由 2026-07-10 的清理工作完成）

所有业务代码中的 `.meta.json` 读写逻辑已移除：
- `setup_agent_tool.py` → 写 `ResourceMetadata` 表
- `agents.py` → 仅 DB，无 `.meta.json` fallback
- `skills.py` → 仅 DB，无 `.meta.json` fallback
- `skill_manage_tool.py` → 创建 skill 时写入 `ResourceMetadata`

迁移脚本 `migrate_meta_json.py` 已实现，供存量部署使用。

代码中现有 `.meta.json` 引用仅存于：
- 迁移脚本本身（合法输入）
- 迁移脚本测试 fixture（合法输入）
- 过时的文档（历史参考）

**注意事项：**
- **`database.backend: memory` 模式**：`get_session_factory()` 返回 `None`，metadata 返回空字典，默认 `private` 兜底。
- **迁移时机**：存量部署先在代码变更前执行 `python -m ideer.scripts.migrate_meta_json`。

## ✅ 3. 用户删除功能

**状态：✅ 已完成**（由 2026-07 实现，含 `DELETE /api/admin/users/{user_id}` 端点 + 三种资源策略）

**实现内容：**
- `backend/app/gateway/routers/admin.py` 新增 `DELETE /api/admin/users/{user_id}` 端点（需 super_admin 角色）
- `backend/app/gateway/user_deletion.py` 新增完整业务逻辑层，支持三种 `resource_strategy`：
  - `transfer` — 资源转移至目标用户（更新 `owner_id` + 移动磁盘目录）
  - `delete` — 软删除 metadata + 删除磁盘文件
  - `soft_delete` — 仅软删除 metadata，保留磁盘文件
- 历史数据硬删除（threads / runs / run_events / feedback）
- 磁盘文件清理（agents / agent-memory / threads / memory.json）
- `visibility_applications` 自动撤回 + `audit_logs.actor_id` SET NULL
- `token_version` 递增使 JWT 立即失效
- 前置校验：最后一名 super_admin 禁止删除、转移目标校验

**相关文件：**
- `backend/app/gateway/routers/admin.py` — `DELETE /api/admin/users/{user_id}` 端点
- `backend/app/gateway/user_deletion.py` — 用户删除业务逻辑
- `backend/tests/test_admin_router.py` — 12 个测试用例覆盖三种策略 + 边界场景

## ✅ 4. Agent 同名冲突修复：metadata 按 (name, owner_id) 隔离

**状态：✅ 已完成**（由 2026-07 实现 7 处改动 + 后续补充懒迁移兜底）

**实现内容（`backend/app/gateway/routers/agents.py` 的 7 处改动）：**

1. `_load_agent_meta` 增加 `for_owner` 参数，按 owner 过滤查询
2. `_save_agent_meta` 查重加入 `owner_id = user_id` 过滤
3. `toggle_agent_favorite` 内联查询加入 `owner_id` 过滤
4. `list_agents` 批量加载从 `dict` 改为 `defaultdict(list)` 按 name 分组
5. `list_agents` 懒迁移和可见性改为按 `(name, owner_id)` 判断
6. `delete_agent` 软删加入 `owner_id = user_id` 过滤
7. 调用方传参：写路径传 `for_owner=user_id`，读路径不传

**后续补充（2026-07-10）：**

- 新增 `_ensure_agent_meta` 函数：为磁盘存在但 DB 缺 metadata 记录的 agent 执行懒迁移
- 在 `delete_agent`、`update_agent`、`get_agent_stats` 三个路径的 RBAC 检查前调用该函数
- 修复场景：修复前已存在的 agent（如超级管理员的 `test`）缺少 metadata 记录导致 403 的问题

**相关文件：**
- `backend/app/gateway/routers/agents.py` — 所有改动

## ✅ 5. fault-zeroing 智能体恢复

**状态：✅ 已完成**（由 2026-07-10 的清理恢复工作完成）

### 背景

`fault-zeroing` 智能体（Agent）原属旧库用户 `test@123.com`，因清理旧库 `backend/.deer-flow/` 时被删除。其关联的 Custom Skill `skills/custom/fault-zeroing/` 未被删除。`config.yaml` 和 `SOUL.md` 原始文件仍保存在 `docs/fault-zeroing-agent/agent/`。

### 执行内容

- Agent 文件已创建：`backend/.ideer/users/{super_admin_id}/agents/fault-zeroing/config.yaml` + `SOUL.md`（57 行）
- `resource_metadata` 记录已注册（agent, owner=super_admin, visibility=private）

### 验证

- `GET /api/agents` 返回列表中包含 `fault-zeroing`
- `GET /api/agents/fault-zeroing` 返回完整配置

### 相关文件

| 文件 | 说明 |
|------|------|
| `docs/fault-zeroing-agent/agent/config.yaml` | Agent 配置文件原文 |
| `docs/fault-zeroing-agent/agent/SOUL.md` | SOUL.md 原文 |
| `skills/custom/fault-zeroing/SKILL.md` | 关联的自定义 Skill |

## ✅ 6. Skill ResourceMetadata 懒注册机制

### 背景

当前 Skill 缺少与 Agent 对等的"文件系统发现即自动补录 `resource_metadata`"机制。Agent 在 `list_agents()`、`get_agent()`、`update_agent()` 等 5 个入口有懒迁移代码，而 Skill 的 `list_skills()` 发现磁盘有文件但 DB 缺记录时直接跳过，不会自动补齐。

### 具体问题

| 资源类型 | 磁盘发现自动创建 resource_metadata | 创建时级联注册子资源 |
|---------|:-------------------------------:|:------------------:|
| Agent | ✅ 是 | N/A |
| Skill | ❌ 否（缺失） | ❌ 否（创建 Agent 不会注册其引用的 Skill） |

`skills/custom/srs-writer/` 和 `skills/custom/fault-zeroing/` 两个预置 Skill 文件存在于磁盘，但在 `resource_metadata` 表中无对应记录，导致 RBAC 管控层面这些 Skill 是"透明"的。

### 实现方案（三步）

#### 4.1 `list_skills()` 添加懒注册

**目标文件**: `backend/app/gateway/routers/skills.py` — `list_skills()` 函数（约第 160-175 行）

参照 `agents.py:296-302` 的 Agent 懒迁移模式，在遍历 custom skill 时，如果 `_load_skill_meta()` 返回空且 `current_user` 已认证，自动调用 `_save_skill_meta()` 创建记录。

**逻辑**：
- 仅对 `SkillCategory.CUSTOM` 生效
- 仅当 DB 查无记录
- 仅当有已认证用户
- 用当前用户作为 owner

#### 4.2 启动时全量 reconciliation

**目标文件**: `backend/app/gateway/app.py` — `lifespan()` 函数（约第 190 行）

新增 `_reconcile_resource_metadata()` 函数，在 `_ensure_admin_user()` 之后调用：
- 扫描 `skills/custom/` 目录
- 对每个缺少 `resource_metadata` 记录的 skill，自动创建（owner=super_admin, visibility=private）
- 幂等：已有记录的不动

#### 4.3 `setup_agent` 级联注册引用的 Skill

**目标文件**: `backend/packages/harness/ideer/tools/builtins/setup_agent_tool.py`（约第 106 行）

在 `_upsert_agent_metadata(agent_name, user_id)` 之后，遍历 `skills` 参数列表，调用 `custom_skill_exists()` 校验文件存在性后，为每个引用且文件存在的 skill 创建 `resource_metadata` 记录。

#### 边界情况

| 场景 | 处理 |
|------|------|
| 无 `current_user`（匿名列表） | 跳过懒注册 |
| `setup_agent` 引用不存在的 skill | `custom_skill_exists()` 返回 False，跳过 |
| 已有 `resource_metadata` 记录 | upsert 幂等，不重复创建 |

#### 相关文件

| 文件 | 改动量 |
|------|--------|
| `backend/app/gateway/routers/skills.py` | +15 行 |
| `backend/app/gateway/app.py` | +45 行（新增函数 + 调用） |
| `backend/packages/harness/ideer/tools/builtins/setup_agent_tool.py` | +20 行 |
