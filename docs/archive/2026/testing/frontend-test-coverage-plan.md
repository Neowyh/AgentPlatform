# 前端测试覆盖分析与补全计划

> status: archived; current testing authority: `docs/testing/coverage-matrix.md`

> 分支: `offline_feature` vs `main`
> 生成日期: 2026-06-10
> 目标: 覆盖本分支 **全部 63 个前端源文件改动** 的测试

---

## 一、改动分类总览

本分支前端改动可分为 **7 个功能域**，共计 25 个新增文件 + 38 个修改文件：

| 功能域 | 新增 | 修改 | 当前 E2E 覆盖 | 当前单元覆盖 |
|--------|------|------|--------------|-------------|
| ① 品牌重命名 (deer-flow → iDeer) | 0 | 20 | ✅ 已适配 | ✅ 已适配 |
| ② 内网离线适配 | 0 | 4 | ❌ | ❌ |
| ③ Agent 管理扩展 | 2 | 5 | ⚠️ 部分 | ❌ |
| ④ Workflow 引擎 | 11 | 0 | ❌ | ❌ |
| ⑤ Skill 管理增强 | 1 | 1 | ❌ | ❌ |
| ⑥ Admin 管理后台 | 6 | 0 | ❌ | ❌ |
| ⑦ 导航与设置调整 | 5 | 8 | ❌ | ❌ |

---

## 二、逐文件改动分析与测试需求

### ① 品牌重命名（20 个修改文件）

| 文件 | 改动内容 | 测试需求 |
|------|---------|---------|
| `app/layout.tsx` | 标题 → iDeer | E2E: 页面标题显示 iDeer |
| `components/landing/header.tsx` | 品牌名 + 移除 GitHub Star 按钮 + 移除外部链接 | E2E: 落地页头部无 GitHub 按钮、品牌为 iDeer |
| `components/landing/hero.tsx` | 文案 → iDeer | E2E: 落地页 Hero 渲染 |
| `components/landing/footer.tsx` | 移除外部链接 | E2E: Footer 无 GitHub/deerflow.tech 链接 |
| `components/landing/sections/case-study-section.tsx` | 文案 → iDeer | — 品牌文字，E2E 落地页已覆盖 |
| `components/landing/sections/community-section.tsx` | 文案 → iDeer | — 同上 |
| `components/landing/sections/sandbox-section.tsx` | 文案 → iDeer | — 同上 |
| `components/landing/sections/skills-section.tsx` | 文案 → iDeer | — 同上 |
| `components/landing/sections/whats-new-section.tsx` | 文案 → iDeer | — 同上 |
| `components/landing/progressive-skills-animation.tsx` | 文案 → iDeer | — 同上 |
| `(auth)/login/page.tsx` | 标题 DeerFlow → iDeer | E2E: 登录页标题显示 iDeer |
| `(auth)/setup/page.tsx` | 标题 DeerFlow → iDeer | E2E: 设置页标题显示 iDeer |
| `components/workspace/workspace-header.tsx` | 品牌 → iDeer | — 侧边栏头部，E2E 间接覆盖 |
| `components/workspace/settings/about-content.ts` | About 内容全面改写：移除 GitHub 链接、Star History、作者致谢、外部网站链接 | E2E: 设置 → About 内容无 GitHub/deerflow.tech 链接 |
| `core/agents/api.ts` | 错误信息 → iDeer | — 文案，无需单独测试 |
| `core/i18n/locales/en-US.ts` | 翻译键值 → iDeer | — i18n，间接覆盖 |
| `core/i18n/locales/zh-CN.ts` | 翻译键值 → iDeer + 新增 admin/workflow 相关键 | 单元: 翻译键完整性 |
| `core/i18n/locales/types.ts` | 新增翻译键类型 | — 类型检查覆盖 |
| `core/settings/local.ts` | localStorage key → ideer + 旧键迁移逻辑 | 单元: 旧键迁移读写 |
| `core/auth/gateway-config.ts` | 品牌适配 | 单元: 已有测试已适配 |

### ② 内网离线适配（4 个修改文件）

| 文件 | 改动内容 | 测试需求 |
|------|---------|---------|
| `components/ai-elements/model-selector.tsx` | 模型 Logo 增加 fallback：CDN 加载失败时显示首字母圆圈（内网无外网访问） | E2E: 模型选择器在 Logo 加载失败时显示 fallback |
| `components/workspace/recent-chat-list.tsx` | 分享链接移除 Vercel URL 硬编码，改用 `window.location.origin` | E2E: 分享对话复制的链接不含 vercel.app |
| `components/workspace/workspace-container.tsx` | 移除 GitHub 图标链接 | E2E: 工作区容器无 GitHub 图标 |
| `core/api/stream-mode.ts` | 流模式适配 | — 内部逻辑，间接覆盖 |

### ③ Agent 管理扩展（2 新增 + 5 修改）

| 文件 | 改动内容 | 测试需求 |
|------|---------|---------|
| **新增** `agents/[agent_name]/page.tsx` | Agent 详情页：统计卡片、配置概览、快捷操作 | E2E: 详情页显示模型/工具组/技能/SOUL.md |
| **新增** `agents/[agent_name]/edit/page.tsx` | Agent 编辑页：表单（描述、模型、工具组、技能、SOUL.md） | E2E: 编辑表单加载、修改、保存 |
| 修改 `agents/new/page.tsx` | 新增可见性选择器（private/department/public），管理员权限控制 | E2E: 可见性选择器显示、非管理员禁用 department/public |
| 修改 `agents/agent-card.tsx` | 新增导出按钮（ZIP 下载） | E2E: 导出触发下载 |
| 修改 `agents/agent-gallery.tsx` | 新增导入按钮（ZIP 上传） | E2E: 导入 ZIP 成功 |
| 修改 `core/agents/api.ts` | 新增 `exportAgent()`、`importAgent()` 函数 | 单元: API 函数调用 |
| 修改 `core/agents/hooks.ts` | `useAgents()` 暴露 `refetch` | — 已被 E2E 间接覆盖 |

### ④ Workflow 引擎（11 个新增文件）

| 文件 | 改动内容 | 测试需求 |
|------|---------|---------|
| **新增** `workflows/page.tsx` | Workflow 画廊页 | E2E: 画廊加载、卡片展示 |
| **新增** `workflows/new/page.tsx` | 新建 Workflow（CodeMirror YAML 编辑器） | E2E: 编辑器加载、预填模板、校验、保存 |
| **新增** `workflows/[workflow_name]/page.tsx` | Workflow 详情+运行 | E2E: Steps/Inputs/YAML 展示、运行对话框、状态轮询 |
| **新增** `workflows/[workflow_name]/edit/page.tsx` | 编辑 Workflow | E2E: 加载现有 YAML、修改、保存 |
| **新增** `workflows/workflow-gallery.tsx` | 画廊组件 | — 被页面测试覆盖 |
| **新增** `workflows/workflow-card.tsx` | 卡片组件+删除确认 | E2E: 卡片信息展示、删除确认弹窗 |
| **新增** `core/workflows/api.ts` | 8 个 API 函数 | 单元: API 函数调用、错误处理 |
| **新增** `core/workflows/hooks.ts` | 7 个 React Query hooks | 单元: hooks 缓存/失效逻辑 |
| **新增** `core/workflows/types.ts` | 类型定义 | 单元: 类型结构验证 |
| **新增** `core/workflows/validate.ts` | YAML 校验 | 单元: validateYaml 各种输入 |
| **新增** `core/workflows/index.ts` | barrel export | — 无需测试 |

### ⑤ Skill 管理增强（1 新增 + 1 修改）

| 文件 | 改动内容 | 测试需求 |
|------|---------|---------|
| **新增** `settings/skill-editor.tsx` | 分屏 CodeMirror 编辑器：左侧 Markdown 编辑、右侧实时预览、YAML frontmatter 校验 | E2E: 编辑器打开、frontmatter 校验、预览渲染 |
| 修改 `settings/skill-settings-page.tsx` | 新增编辑/测试按钮、分屏编辑器集成、分组徽章、"需要互联网"徽章 | E2E: 编辑/测试按钮点击、徽章显示 |

### ⑥ Admin 管理后台（6 个新增文件）

| 文件 | 改动内容 | 测试需求 |
|------|---------|---------|
| **新增** `admin/page.tsx` | 仪表盘：4 张统计卡片 | E2E: 统计数据展示、卡片跳转 |
| **新增** `admin/users/page.tsx` | 用户管理：列表、角色变更、禁用 | E2E: 用户列表、角色下拉变更、禁用按钮 |
| **新增** `admin/departments/page.tsx` | 部门管理：CRUD 弹窗 | E2E: 新建/编辑/删除部门 |
| **新增** `admin/tools/page.tsx` | 工具管理：卡片网格、分组筛选、详情弹窗、JSON 测试 | E2E: 工具列表、筛选、测试执行 |
| **新增** `core/admin/api.ts` | Admin API 层（stats/users/departments） | 单元: API 函数调用 |
| **新增** `core/admin/types.ts` | Admin 类型定义 | — 类型检查覆盖 |

### ⑦ 导航与设置调整（5 新增 + 8 修改）

| 文件 | 改动内容 | 测试需求 |
|------|---------|---------|
| **新增** `workspace/workspace-breadcrumb.tsx` | 面包屑导航（支持 admin/workflow/agent 路径） | E2E: 各页面面包屑正确显示 |
| **新增** `core/tools/api.ts` | Tools API（list/detail/test） | 单元: API 函数调用 |
| **新增** `core/tools/types.ts` | Tool/ToolTestResult 类型 | — 类型检查覆盖 |
| **新增** `core/tools/index.ts` | barrel export | — 无需测试 |
| **新增** `ui/label.tsx` | Label UI 组件 | — 被其他测试间接覆盖 |
| 修改 `workspace-nav-menu.tsx` | 移除外部链接（GitHub/官网/报告问题/联系我们），新增管理后台入口（仅管理员可见） | E2E: 管理员看到 Admin 入口、非管理员看不到 |
| 修改 `workspace-nav-chat-list.tsx` | 新增 Workflows 导航链接 | E2E: 侧边栏显示 Workflows 链接、点击跳转 |
| 修改 `workspace-header.tsx` | 品牌 → iDeer | — 被品牌测试覆盖 |
| 修改 `recent-chat-list.tsx` | 分享链接逻辑简化 | E2E: 分享链接使用当前 origin |
| 修改 `workspace-container.tsx` | 移除 GitHub 图标 | E2E: 无 GitHub 图标 |
| 修改 `settings/memory-settings-page.tsx` | 记忆设置页调整 | E2E: 设置页加载 |
| 修改 `core/messages/usage-model.ts` | Token 用量模型 | — 内部逻辑 |
| 修改 `core/tasks/subtask-result.ts` | 子任务结果 | — 内部逻辑，单元测试已适配 |
| 修改 `core/threads/export.ts` | 导出功能 | — 内部逻辑，单元测试已适配 |
| 修改 `core/artifacts/preview.ts` | 产物预览 | — 内部逻辑，单元测试已适配 |
| 修改 `ai-elements/model-selector.tsx` | Logo fallback（归入②内网适配） | — 同② |
| 修改 `[lang]/docs/layout.tsx` | 文档布局 | — 文档页，非核心功能 |
| 修改 `blog/layout.tsx` | 博客布局 | — 博客页，非核心功能 |

---

## 三、现有测试基线

### E2E 测试（8 spec，22 测试）

| spec | 测试数 | 覆盖范围 |
|------|--------|---------|
| `landing.spec.ts` | 2 | 落地页渲染 + Get Started 跳转 |
| `chat.spec.ts` | 4 | 新对话、输入、发送消息、文件上传 |
| `agent-chat.spec.ts` | 3 | Agent 画廊加载、Agent 对话页、Agent 徽章 |
| `sidebar.spec.ts` | 2 | 侧边栏导航链接 |
| `thread-history.spec.ts` | 4 | 线程列表、跳转、历史消息 |
| `chat-thread-init-ordering.spec.ts` | 1 | API 调用顺序回归 |
| `artifact-preview.spec.ts` | 4 | HTML/MD/JSON/SVG 产物预览 |
| `artifact-visualization.spec.ts` | 2 | 故障树/SVG 可视化 |

### 单元测试（20 文件）

| 测试文件 | 覆盖范围 |
|---------|---------|
| `auth/server.test.ts` | getServerSideUser 静态模式 |
| `auth/gateway-config.test.ts` | 网关配置 |
| `threads/api.test.ts` | fetchThreadTokenUsage |
| `threads/export.test.ts` | 格式化导出 |
| `artifacts/preview.test.ts` | 产物预览 |
| `tasks/subtask-result.test.ts` | 子任务结果 |
| 其他 14 文件 | 各工具函数 |

---

## 四、测试补全计划

### Phase 1: Mock 基础设施扩展

**修改文件**: `tests/e2e/utils/mock-api.ts`

在现有 `mockLangGraphAPI()` 中新增以下 mock：

```typescript
// ── Agent CRUD ──────────────────────────────────────────────────
// POST /api/agents → 创建 Agent
// PUT /api/agents/{name} → 更新 Agent
// DELETE /api/agents/{name} → 204
// GET /api/agents/check?name={name} → { available: true, name }
// GET /api/agents/{name}/export → Blob
// POST /api/agents/import → 创建的 Agent

// ── Workflow CRUD + Run ──────────────────────────────────────────
// GET /api/workflows → { workflows: [], total: 0 }
// POST /api/workflows → 创建的 Workflow
// GET /api/workflows/{name} → WorkflowDetail (含 yaml_content, steps)
// PUT /api/workflows/{name} → 更新的 Workflow
// DELETE /api/workflows/{name} → 204
// POST /api/workflows/{name}/run → { run_id, status, workflow }
// GET /api/workflows/{name}/runs/{runId} → RunStatus (含 steps 状态)

// ── Skill ────────────────────────────────────────────────────────
// GET /api/skills → { skills: MockSkill[] }
// PUT /api/skills/{name} → 更新的 Skill
// POST /api/skills/install → { success, skill_name, message }

// ── Admin ────────────────────────────────────────────────────────
// GET /api/admin/stats → { users, departments, agents, skills }
// GET /api/admin/users → 用户列表
// PUT /api/admin/users/{id} → 更新的用户
// GET /api/admin/departments → 部门列表
// POST /api/admin/departments → 创建的部门
// PUT /api/admin/departments/{id} → 更新的部门
// DELETE /api/admin/departments/{id} → 204
// GET /api/admin/tools → 工具列表
// GET /api/tools → 工具列表（非 admin 路径）
// GET /api/tools/{name} → 工具详情
// POST /api/tools/{name}/test → 测试结果
```

新增 Mock 数据类型：

```typescript
export type MockWorkflow = {
  name: string;
  description?: string;
  version?: string;
  yaml_content?: string;
  steps?: StepDef[];
  inputs?: Record<string, InputParam>;
};

export type MockSkill = {
  name: string;
  description?: string;
  category: "public" | "custom";
  license?: string;
  enabled: boolean;
};

export type MockUser = {
  id: string;
  username: string;
  department?: string;
  system_role: string;
  disabled: boolean;
};

export type MockDepartment = {
  id: string;
  name: string;
  description?: string;
  member_count: number;
};
```

### Phase 2: Agent E2E 测试

**新文件**: `tests/e2e/agent-management.spec.ts`

| # | 测试用例 | 操作步骤 | 验证点 |
|---|---------|---------|--------|
| 1 | Agent 画廊加载 | 导航 `/workspace/agents` | 显示 Agent 卡片网格 |
| 2 | Agent 画廊空状态 | mock 空 agents 列表 | 显示创建 CTA |
| 3 | 新建 Agent — 可见性选择器 | 点击 New Agent | 显示可见性下拉、非管理员 department/public 禁用 |
| 4 | 新建 Agent — 名称校验 | 输入无效名称（含空格） | 显示格式错误 |
| 5 | 新建 Agent — 名称查重 | 输入已存在的名称 | 显示名称已存在错误 |
| 6 | 新建 Agent — 进入对话步骤 | 输入有效新名称 → 提交 | 跳转到对话步骤、自动发送引导消息 |
| 7 | Agent 详情页 | 点击卡片进入详情 | 显示模型、工具组徽章、技能徽章、SOUL.md |
| 8 | 编辑 Agent — 加载 | 点击 Edit Agent | 表单预填现有配置 |
| 9 | 编辑 Agent — 保存 | 修改描述 → Save | Toast 成功、跳转回详情页 |
| 10 | 删除 Agent | 卡片垃圾桶 → 确认 | Toast 成功、卡片从列表消失 |
| 11 | 导出 Agent | 卡片下载图标 | 触发 .zip 文件下载 |
| 12 | 导入 Agent | Import 按钮 → 选择 .zip | Toast 成功、画廊刷新 |

**新文件**: `tests/e2e/agent-chat.spec.ts`（扩展现有 agent-chat.spec.ts 或新建）

| # | 测试用例 | 验证点 |
|---|---------|--------|
| 13 | Agent 对话 — Agent 徽章 | 对话页头部显示 Agent 名称徽章 |
| 14 | Agent 对话 — 专属欢迎页 | 显示 Agent 名称+描述+图标 |

### Phase 3: Workflow E2E 测试

**新文件**: `tests/e2e/workflow-management.spec.ts`

| # | 测试用例 | 操作步骤 | 验证点 |
|---|---------|---------|--------|
| 1 | Workflow 画廊加载 | 导航 `/workspace/workflows` | 显示卡片网格 |
| 2 | Workflow 画廊空状态 | mock 空列表 | 显示创建 CTA |
| 3 | 侧边栏 Workflows 链接 | 查看侧边栏 | 显示 Workflows 导航项、点击跳转 |
| 4 | 新建 Workflow — 编辑器加载 | 点击 New Workflow | CodeMirror 编辑器显示、预填模板 YAML |
| 5 | 新建 Workflow — 校验报错 | 删除 `name:` 行 → 看到红色 Alert | 校验错误提示 |
| 6 | 新建 Workflow — 保存 | 保持有效 YAML → Save | Toast 成功、跳转回列表页 |
| 7 | Workflow 详情页 | 点击卡片 | 显示 Steps 列表、Inputs 定义、YAML 预览 |
| 8 | 编辑 Workflow — 加载 | 点击 Edit | 编辑器加载现有 yaml_content |
| 9 | 编辑 Workflow — 保存 | 修改 YAML → Save | Toast 成功、跳转回详情页 |
| 10 | 删除 Workflow | 卡片垃圾桶 → 确认 | Toast 成功、卡片消失 |
| 11 | 运行 Workflow — 参数表单 | 点击 Run | 弹出对话框、显示输入字段、必填标红星 |
| 12 | 运行 Workflow — 必填校验 | 不填必填项 → Run | 显示校验错误 |
| 13 | 运行 Workflow — 执行 | 填写参数 → Run | Run Status 卡片出现、步骤状态更新 |
| 14 | 运行 Workflow — 轮询停止 | 等待终态 | 轮询自动停止 |

### Phase 4: Skill E2E 测试

**新文件**: `tests/e2e/skill-management.spec.ts`

| # | 测试用例 | 操作步骤 | 验证点 |
|---|---------|---------|--------|
| 1 | Skill 设置页加载 | Settings → Skills | 显示 Public/Custom 标签页 |
| 2 | 标签页切换 | 点击 Custom | 列表按 category 过滤 |
| 3 | 技能徽章显示 | 查看技能列表 | 分类徽章、"需要互联网"徽章（如有） |
| 4 | 启用/禁用 Skill | 切换开关 | 调用 PUT API、状态更新 |
| 5 | Skill 编辑器 — 打开 | 点击编辑图标 | 打开分屏编辑器 |
| 6 | Skill 编辑器 — frontmatter 校验 | 删除 `name:` 字段 | 显示红色校验错误 |
| 7 | Skill 编辑器 — 预览 | 输入 Markdown 内容 | 右侧实时预览渲染 |
| 8 | 测试 Skill — 对话框 | 点击测试图标 | 显示指引对话框、有"Start New Chat"按钮 |
| 9 | 创建 Skill — 跳转 | 点击 Create | 关闭设置弹窗、跳转到 `?mode=skill` 对话 |

### Phase 5: Admin E2E 测试

**新文件**: `tests/e2e/admin-management.spec.ts`

| # | 测试用例 | 操作步骤 | 验证点 |
|---|---------|---------|--------|
| 1 | 管理员 — 导航入口可见 | 管理员登录 → 打开 Settings & More | 显示管理后台、用户管理、部门管理、工具管理 |
| 2 | 非管理员 — 导航入口隐藏 | 普通用户登录 → 打开菜单 | 不显示管理入口 |
| 3 | Admin 仪表盘 | 导航 `/workspace/admin` | 显示 4 张统计卡片 |
| 4 | 仪表盘卡片跳转 | 点击用户卡片 | 跳转到用户管理页 |
| 5 | 用户管理 — 列表 | 导航用户管理 | 显示用户卡片、角色徽章 |
| 6 | 用户管理 — 角色变更 | 下拉选择新角色 | 调用 PUT API、Toast 成功 |
| 7 | 用户管理 — 禁用 | 点击禁用按钮 | 状态更新 |
| 8 | 部门管理 — 列表 | 导航部门管理 | 显示部门卡片网格 |
| 9 | 部门管理 — 新建 | 点击新建 → 填写 → 保存 | 弹窗表单、Toast 成功、新卡片出现 |
| 10 | 部门管理 — 编辑 | 点击编辑 → 修改 → 保存 | 加载现有数据、保存成功 |
| 11 | 部门管理 — 删除 | 删除 → 确认 | Toast 成功、卡片消失 |
| 12 | 工具管理 — 列表 | 导航工具管理 | 显示工具卡片 |
| 13 | 工具管理 — 分组筛选 | 选择分组 | 列表按分组过滤 |
| 14 | 工具管理 — 测试执行 | 点击详情 → 填 JSON → 测试 | 弹窗显示结果 |

### Phase 6: 品牌与离线适配 E2E 测试

**新文件**: `tests/e2e/brand-and-offline.spec.ts`

| # | 测试用例 | 操作步骤 | 验证点 |
|---|---------|---------|--------|
| 1 | 落地页 — 无外部链接 | 检查 Header | 无 GitHub Star 按钮、无 deerflow.tech 链接 |
| 2 | 落地页 — 品牌名 | 检查 Header | 显示 "iDeer" |
| 3 | 登录页 — 品牌名 | 导航 `/login` | 标题显示 "iDeer" |
| 4 | 设置页 — About 内容 | Settings → About | 无 GitHub 链接、无 deerflow.tech、无作者致谢 |
| 5 | 分享链接 — 使用当前 origin | 分享对话 → 复制链接 | 链接不含 vercel.app、使用 `window.location.origin` |
| 6 | 工作区 — 无 GitHub 图标 | 检查 workspace header | 无 GitHub 图标链接 |
| 7 | 模型选择器 — Logo fallback | 打开模型选择器 | CDN 失败时显示首字母 fallback |

### Phase 7: 单元测试补全

| 新文件 | 测试目标 | 测试用例 |
|--------|---------|---------|
| `tests/unit/core/workflows/validate.test.ts` | `validateYaml()` | 空字符串→错误、缺 name→错误、缺 steps→错误、有效→无错误 |
| `tests/unit/core/workflows/api.test.ts` | Workflow API 函数 | listWorkflows 调用正确 URL、createWorkflow 发送 yaml_content、runWorkflow 发送 inputs、错误处理 |
| `tests/unit/core/admin/api.test.ts` | Admin API 函数 | getAdminStats 返回数据、listUsers 调用、updateUserRole 发送正确 body、错误处理 |
| `tests/unit/core/tools/api.test.ts` | Tools API 函数 | listTools 带筛选参数、getToolDetail、testTool 发送 params |
| `tests/unit/core/settings/local.test.ts` | localStorage 迁移 | 新键读取、旧键迁移到新键、QuotaExceededError 容错 |
| `tests/unit/core/i18n/keys.test.ts` | i18n 键完整性 | en-US 和 zh-CN 包含所有必需键（adminPanel、workflows 等新增键） |

---

## 五、测试文件清单汇总

### 新增 E2E spec 文件（6 个）

| 文件 | 测试数 | 对应功能域 |
|------|--------|-----------|
| `tests/e2e/agent-management.spec.ts` | 12 | ③ Agent 管理扩展 |
| `tests/e2e/workflow-management.spec.ts` | 14 | ④ Workflow 引擎 |
| `tests/e2e/skill-management.spec.ts` | 9 | ⑤ Skill 管理增强 |
| `tests/e2e/admin-management.spec.ts` | 14 | ⑥ Admin 管理后台 |
| `tests/e2e/brand-and-offline.spec.ts` | 7 | ①② 品牌+离线 |
| 扩展 `tests/e2e/agent-chat.spec.ts` | +2 | ③ Agent 对话 |

### 新增单元测试文件（6 个）

| 文件 | 测试数 | 对应功能域 |
|------|--------|-----------|
| `tests/unit/core/workflows/validate.test.ts` | 4 | ④ Workflow |
| `tests/unit/core/workflows/api.test.ts` | 6 | ④ Workflow |
| `tests/unit/core/admin/api.test.ts` | 5 | ⑥ Admin |
| `tests/unit/core/tools/api.test.ts` | 4 | ⑦ 工具 API |
| `tests/unit/core/settings/local.test.ts` | 4 | ① 品牌迁移 |
| `tests/unit/core/i18n/keys.test.ts` | 2 | ① i18n 键 |

### 修改文件（1 个）

| 文件 | 改动 |
|------|------|
| `tests/e2e/utils/mock-api.ts` | 新增 ~25 个 mock 端点 + Mock 数据类型 |

---

## 六、实施优先级与依赖

```
Phase 1: Mock 基础设施扩展 (必须最先完成)
    │
    ├──► Phase 2: Agent E2E (12 测试)
    ├──► Phase 3: Workflow E2E (14 测试)
    ├──► Phase 4: Skill E2E (9 测试)
    ├──► Phase 5: Admin E2E (14 测试)
    └──► Phase 6: 品牌+离线 E2E (7 测试)
    │
    └──► Phase 7: 单元测试 (25 测试，可并行)
```

### 预估工作量

| 阶段 | 改动文件数 | 新增测试数 | 预估工时 |
|------|-----------|-----------|---------|
| Phase 1: Mock 扩展 | 1 | — | 3h |
| Phase 2: Agent E2E | 1 | 12 | 3h |
| Phase 3: Workflow E2E | 1 | 14 | 4h |
| Phase 4: Skill E2E | 1 | 9 | 2h |
| Phase 5: Admin E2E | 1 | 14 | 4h |
| Phase 6: 品牌+离线 E2E | 1 | 7 | 2h |
| Phase 7: 单元测试 | 6 | 25 | 3h |
| **合计** | **12 文件** | **81 测试** | **~21h** |

---

## 七、改动覆盖对照表

以下确保每个改动文件都有对应测试：

| 改动文件 | 对应测试 |
|---------|---------|
| `app/layout.tsx` | brand-and-offline #2 |
| `landing/header.tsx` | brand-and-offline #1 #2 |
| `landing/hero.tsx` | brand-and-offline #2 |
| `landing/footer.tsx` | brand-and-offline #1 |
| `landing/sections/*.tsx` (5) | brand-and-offline #2 (间接) |
| `landing/progressive-skills-animation.tsx` | brand-and-offline #2 (间接) |
| `(auth)/login/page.tsx` | brand-and-offline #3 |
| `(auth)/setup/page.tsx` | brand-and-offline #3 |
| `workspace-header.tsx` | brand-and-offline #6 |
| `settings/about-content.ts` | brand-and-offline #4 |
| `core/agents/api.ts` | agent-management #11 #12 + 单元测试 |
| `core/agents/hooks.ts` | agent-management (间接) |
| `core/i18n/locales/*.ts` (3) | i18n/keys.test.ts |
| `core/settings/local.ts` | settings/local.test.ts |
| `core/auth/gateway-config.ts` | 已有单元测试 |
| `ai-elements/model-selector.tsx` | brand-and-offline #7 |
| `recent-chat-list.tsx` | brand-and-offline #5 |
| `workspace-container.tsx` | brand-and-offline #6 |
| `workspace-nav-menu.tsx` | admin-management #1 #2 |
| `workspace-nav-chat-list.tsx` | workflow-management #3 |
| `settings/memory-settings-page.tsx` | skill-management (设置页入口) |
| `settings/skill-settings-page.tsx` | skill-management #1-9 |
| `settings/skill-editor.tsx` | skill-management #5-7 |
| `agents/new/page.tsx` | agent-management #3-6 |
| `agents/agent-card.tsx` | agent-management #10 #11 |
| `agents/agent-gallery.tsx` | agent-management #1 #2 #12 |
| `agents/[name]/page.tsx` | agent-management #7 |
| `agents/[name]/edit/page.tsx` | agent-management #8 #9 |
| `workflows/page.tsx` | workflow-management #1 #2 |
| `workflows/new/page.tsx` | workflow-management #4-6 |
| `workflows/[name]/page.tsx` | workflow-management #7 #11-14 |
| `workflows/[name]/edit/page.tsx` | workflow-management #8 #9 |
| `workflows/workflow-gallery.tsx` | workflow-management (间接) |
| `workflows/workflow-card.tsx` | workflow-management #10 |
| `core/workflows/*.ts` (5) | workflows/validate.test.ts + api.test.ts |
| `admin/page.tsx` | admin-management #3 #4 |
| `admin/users/page.tsx` | admin-management #5-7 |
| `admin/departments/page.tsx` | admin-management #8-11 |
| `admin/tools/page.tsx` | admin-management #12-14 |
| `core/admin/*.ts` (2) | admin/api.test.ts |
| `core/tools/*.ts` (3) | tools/api.test.ts |
| `workspace-breadcrumb.tsx` | 各 E2E 间接覆盖面包屑 |
| `ui/label.tsx` | 被 agent-management 间接覆盖 |
| `core/api/stream-mode.ts` | chat.spec.ts 间接覆盖 |
| `core/artifacts/preview.ts` | 已有单元测试 |
| `core/messages/usage-model.ts` | chat.spec.ts 间接覆盖 |
| `core/tasks/subtask-result.ts` | 已有单元测试 |
| `core/threads/export.ts` | 已有单元测试 |
| `[lang]/docs/layout.tsx` | 非核心，不覆盖 |
| `blog/layout.tsx` | 非核心，不覆盖 |

---

## 八、验证标准

完成后运行 `pnpm test:e2e` 和 `pnpm test` 应全部通过：

1. **现有 22 个 E2E 测试** 继续通过（回归验证）
2. **新增 56 个 E2E 测试** 通过（Agent 12 + Workflow 14 + Skill 9 + Admin 14 + 品牌离线 7）
3. **新增 25 个单元测试** 通过
4. **`pnpm build`** 构建成功
5. **`tsc --noEmit`** 类型检查通过

总测试数：22（现有）+ 56（新增 E2E）+ 25（新增单元）= **103 个测试**
