# 截图测试全覆盖计划

> 目标：补齐截图测试在对话框、交互状态、空状态、错误状态、多角色视角、AI 交互、Settings 子页面、Blog/Docs 等维度的覆盖缺口。
>
> 当前状态：22 个截图配置，覆盖 19/23 个路由（83%），但交互状态和异常场景覆盖率为 0%。

---

## 总览

| 维度 | 已覆盖 | 目标 | 新增数 | 优先级 |
|------|--------|------|--------|--------|
| 页面路由 | 19 | 23 | +4 | P1 |
| 对话框/弹窗 | 2 | 17 | +15 | P1 |
| 下拉菜单/交互 | 0 | 11 | +11 | P1 |
| 空状态 | 0 | 9 | +9 | P2 |
| 错误状态 | 0 | 5 | +5 | P2 |
| 用户角色视角 | 1 | 4 | +3 | P2 |
| AI 交互状态 | 0 | 6 | +6 | P1 |
| Settings 子页面 | 1 | 7 | +6 | P1 |
| Blog/Docs | 0 | 4 | +4 | P3 |
| **合计** | **22** | | **+63** | |

预估总截图数（含 mobile + dark 变体）：~150 张 desktop + ~60 张 mobile + ~40 张 dark = **~250 张**。

---

## Phase 1: 核心交互状态（P1）

### 1.1 对话框/弹窗（+15 个截图）

在 `visual-screenshot.spec.ts` 的 SCREENSHOTS 数组中新增以下配置。每个弹窗通过 `actions` 触发打开，截图捕获弹窗展开状态。

| # | name | route | actions 触发方式 | expectedElements |
|---|------|-------|-----------------|------------------|
| 1 | `dialog-rename-thread` | `/workspace/chats/new` | 右键点击侧边栏线程 → 点击"重命名" | `input, [role="dialog"]` |
| 2 | `dialog-delete-agent` | `/workspace/agents` | 点击 Agent 卡片删除按钮 | `[role="dialog"], button:has-text("确定")` |
| 3 | `dialog-delete-workflow` | `/workspace/workflows` | 点击 Workflow 卡片删除按钮 | `[role="dialog"], button:has-text("确定")` |
| 4 | `dialog-create-department` | `/workspace/admin/departments` | 点击"新建部门"按钮 | `input[name="name"], [role="dialog"]` |
| 5 | `dialog-edit-department` | `/workspace/admin/departments` | 点击部门卡片编辑按钮 | `input[name="name"], [role="dialog"]` |
| 6 | `dialog-tool-detail` | `/workspace/admin/tools` | 点击工具卡片 | `[role="dialog"]` |
| 7 | `dialog-add-memory` | `/workspace/chats/new` | Ctrl+, → Memory → "添加事实" | `textarea, [role="dialog"]` |
| 8 | `dialog-edit-memory` | `/workspace/chats/new` | Ctrl+, → Memory → 编辑已有事实 | `textarea, [role="dialog"]` |
| 9 | `dialog-delete-memory` | `/workspace/chats/new` | Ctrl+, → Memory → 删除事实 | `[role="dialog"]` |
| 10 | `dialog-clear-all-memory` | `/workspace/chats/new` | Ctrl+, → Memory → "清除全部" | `[role="dialog"]` |
| 11 | `dialog-import-memory` | `/workspace/chats/new` | Ctrl+, → Memory → 导入 JSON | `[role="dialog"]` |
| 12 | `dialog-skill-editor` | `/workspace/chats/new` | Ctrl+, → Skills → 编辑技能 | `[role="dialog"]` |
| 13 | `dialog-test-skill` | `/workspace/chats/new` | Ctrl+, → Skills → 测试技能 | `[role="dialog"]` |
| 14 | `dialog-keyboard-shortcuts` | `/workspace/chats/new` | Ctrl+K → "Keyboard Shortcuts" | `[role="dialog"], kbd` |
| 15 | `dialog-followup-confirm` | `/workspace/chats/new` | 输入文本 → 点击跟进建议 | `[role="dialog"]` |

**实现要点：**
- 弹窗触发需要等待动画完成（`waitForTimeout(500-1000)`）
- 部分弹窗需要先有数据（如删除需要先有 Agent/Workflow），使用 mock 数据
- 记忆相关弹窗需要先导航到 Settings > Memory 子页面

### 1.2 下拉菜单/交互状态（+11 个截图）

| # | name | route | actions 触发方式 | expectedElements |
|---|------|-------|-----------------|------------------|
| 1 | `dropdown-thread-context` | `/workspace/chats/new` | 悬浮侧边栏线程 → 点击三点菜单 | `[role="menu"]` |
| 2 | `dropdown-mode-selector` | `/workspace/chats/new` | 点击模式按钮（Flash/Thinking 等） | `[role="listbox"], [role="menu"]` |
| 3 | `dropdown-model-selector` | `/workspace/chats/new` | 点击模型名称 | `[role="listbox"], input[type="search"]` |
| 4 | `dropdown-export` | `/workspace/chats/new` | 发送消息 → 点击导出按钮 | `[role="menu"]` |
| 5 | `dropdown-sidebar-nav` | `/workspace/chats/new` | 点击侧边栏底部"设置"按钮 | `[role="menu"]` |
| 6 | `dropdown-admin-role` | `/workspace/admin/users` | 点击用户角色下拉选择 | `[role="listbox"]` |
| 7 | `dropdown-token-usage` | `/workspace/chats/new` | 发送消息 → 点击 token 用量 | `[role="menu"]` |
| 8 | `dropdown-reasoning-effort` | `/workspace/chats/new` | 点击推理努力度选择器 | `[role="listbox"]` |
| 9 | `state-file-upload-preview` | `/workspace/chats/new` | 附加文件到输入框 | `[data-testid="file-preview"], .file-card` |
| 10 | `state-welcome-suggestions` | `/workspace/chats/new` | 首次进入聊天页 | `button:has-text("Create"), [data-testid="suggestion"]` |
| 11 | `state-chat-with-artifacts` | `/workspace/chats/new` | 发送消息 → 打开 artifacts 面板 | `#artifacts, [data-testid="artifact-panel"]` |

**实现要点：**
- 下拉菜单通常有动画延迟，需要 `waitForTimeout(300-500)`
- 模型选择器可能需要 mock `/api/models` 返回数据
- 文件上传预览需要模拟文件选择（`page.setInputFiles`）

### 1.3 AI 交互状态（+6 个截图）

| # | name | route | actions 触发方式 | expectedElements |
|---|------|-------|-----------------|------------------|
| 1 | `ai-streaming-response` | `/workspace/chats/new` | 发送消息 → 在流式响应过程中截图 | `.streaming-indicator, [data-testid="streaming"]` |
| 2 | `ai-reasoning-expanded` | `/workspace/chats/new` | 发送消息 → 展开思考过程 | `[data-testid="reasoning"], .reasoning-block` |
| 3 | `ai-feedback-buttons` | `/workspace/chats/new` | 悬浮在 AI 消息上 | `button[aria-label*="thumb"], [data-testid="feedback"]` |
| 4 | `ai-citation-hovercard` | `/workspace/chats/new` | 悬浮在引用标记上 | `[data-testid="citation"], .citation-hover` |
| 5 | `ai-followup-suggestions` | `/workspace/chats/new` | 等待 AI 回复完成 → 出现建议 | `[data-testid="suggestion"], .followup` |
| 6 | `ai-message-with-code` | `/workspace/chats/new` | 发送要求代码的消息 → 代码块渲染 | `pre code, .code-block` |

**实现要点：**
- 流式响应截图需要精确时机控制，可在 mock SSE 的 `values` 事件后延迟截图
- 思考过程展开需要 mock 返回 reasoning 内容
- 引用悬浮卡片需要 mock 返回带 citations 的消息

### 1.4 Settings 子页面（+6 个截图）

| # | name | route | actions 触发方式 | expectedElements |
|---|------|-------|-----------------|------------------|
| 1 | `settings-appearance` | `/workspace/chats/new` | Ctrl+, → 点击"外观"标签 | `[data-testid="theme-card"], .theme-preview` |
| 2 | `settings-notification` | `/workspace/chats/new` | Ctrl+, → 点击"通知"标签 | `button:has-text("Request"), [data-testid="notification"]` |
| 3 | `settings-memory` | `/workspace/chats/new` | Ctrl+, → 点击"记忆"标签 | `[data-testid="memory-list"], .fact-item` |
| 4 | `settings-tools` | `/workspace/chats/new` | Ctrl+, → 点击"工具"标签 | `[data-testid="tool-list"], .tool-item` |
| 5 | `settings-skills` | `/workspace/chats/new` | Ctrl+, → 点击"技能"标签 | `[data-testid="skill-list"], .skill-item` |
| 6 | `settings-about` | `/workspace/chats/new` | Ctrl+, → 点击"关于"标签 | `[data-testid="about"]` |

**实现要点：**
- Settings 弹窗使用 Tab 切换子页面，通过 `page.click` 点击对应标签
- Memory/Tools/Skills 页面需要 mock API 返回数据
- Notification 页面需要 mock 浏览器通知权限状态

---

## Phase 2: 状态变体（P2）

### 2.1 空状态（+9 个截图）

通过 mock 返回空数组触发空状态引导页。

| # | name | route | mock 配置 | expectedTexts |
|---|------|-------|-----------|---------------|
| 1 | `empty-agents` | `/workspace/agents` | agents: [] | "No agents", "无智能体" |
| 2 | `empty-workflows` | `/workspace/workflows` | workflows: [] | "No workflows", "无工作流" |
| 3 | `empty-chats` | `/workspace/chats` | threads: [] | "No chats", "无对话" |
| 4 | `empty-memory` | `/workspace/chats/new` | Ctrl+, → Memory → 无数据 | "No saved facts", "无记忆" |
| 5 | `empty-skills` | `/workspace/chats/new` | Ctrl+, → Skills → 无数据 | "No skills", "无技能" |
| 6 | `empty-admin-users` | `/workspace/admin/users` | users: [] | "No users", "无用户" |
| 7 | `empty-admin-departments` | `/workspace/admin/departments` | departments: [] | "No departments", "无部门" |
| 8 | `empty-admin-tools` | `/workspace/admin/tools` | tools: [] | "No tools", "无工具" |
| 9 | `empty-command-palette` | `/workspace/chats/new` | Ctrl+K → 输入无匹配内容 | "No results", "无结果" |

**实现要点：**
- 空状态需要独立的 mock 配置，覆盖默认的 mock 数据
- `mockLangGraphAPI(page, { agents: [], workflows: [], ... })`
- Settings 子页面的空状态需要在 Settings 弹窗内触发

### 2.2 错误状态（+5 个截图）

| # | name | route | 触发方式 | expectedTexts |
|---|------|-------|----------|---------------|
| 1 | `error-login-wrong-password` | `/login` | 输入错误密码 → 提交 | "错误", "invalid", "incorrect" |
| 2 | `error-login-empty-form` | `/login` | 不填任何字段 → 提交 | "required", "必填" |
| 3 | `error-setup-weak-password` | `/setup` | 输入弱密码 → 提交 | "too short", "too weak", "密码" |
| 4 | `error-workflow-invalid-yaml` | `/workspace/workflows/new` | 输入无效 YAML → 保存 | "error", "invalid", "错误" |
| 5 | `error-admin-promote-confirm` | `/workspace/admin/users` | 将用户提升为超级管理员 → 确认弹窗 | "确定", "confirm", "超级管理员" |

**实现要点：**
- 错误状态需要模拟用户输入错误数据
- 登录错误需要后端返回错误响应（mock 401）
- YAML 验证错误可以在前端触发（输入非法字符）

### 2.3 多角色视角（+3 个截图配置组）

为不同角色创建独立的截图配置，使用不同的登录凭据。

| # | name | role | route | 说明 |
|---|------|------|-------|------|
| 1 | `role-user-workspace` | user | `/workspace/chats/new` | 普通用户视角：无管理入口 |
| 2 | `role-user-sidebar` | user | `/workspace/chats/new` | 普通用户侧边栏：无管理员菜单 |
| 3 | `role-viewer-workspace` | viewer | `/workspace/chats/new` | 只读用户视角：无编辑按钮 |

**实现要点：**
- 需要在 `ScreenshotConfig` 中增加 `role` 字段
- `loginViaUI` 函数需要支持按角色选择不同凭据
- 或通过 mock API 返回不同角色的用户信息
- 每个角色的截图独立于 admin 角色的截图

---

## Phase 3: 补充覆盖（P3）

### 3.1 缺失的路由页面（+4 个截图）

| # | name | route | 说明 |
|---|------|-------|------|
| 1 | `blog-list` | `/blog` | Blog 文章列表 |
| 2 | `blog-post` | `/blog/posts` | Blog 文章详情 |
| 3 | `blog-tags` | `/blog/tags/test` | Blog 标签筛选 |
| 4 | `docs-home` | `/zh/docs` | 文档首页 |

**实现要点：**
- Blog/Docs 页面是公开页面，不需要 mock 和 auth
- 需要确认这些页面在测试环境中是否可访问
- 如果是静态生成页面，可能需要先 build

### 3.2 视口变体扩展

对 Phase 1 和 Phase 2 中的关键交互截图，补充 mobile 和 dark mode 变体。

**必须有 mobile 变体的页面：**
- 所有对话框截图（dialog-*）
- 空状态截图（empty-*）
- Settings 子页面（settings-appearance, settings-memory）

**必须有 dark mode 变体的页面：**
- settings-appearance（主题预览在暗色模式下效果不同）
- ai-message-with-code（代码块暗色模式高亮）
- 所有对话框截图

---

## 实施步骤

### Step 1: 扩展 ScreenshotConfig 接口

```typescript
interface ScreenshotConfig {
  name: string;
  route: string;
  waitFor?: string;
  actions?: (page: Page) => Promise<void>;
  needsMock?: boolean;
  needsAuth?: boolean;
  expectedElements?: string[];
  expectedTexts?: string[];
  // 新增
  role?: "admin" | "user" | "viewer";  // 登录角色
  skipMobile?: boolean;                 // 跳过 mobile 变体
  skipDark?: boolean;                   // 跳过 dark mode 变体
  mockOverrides?: Record<string, any>;  // 自定义 mock 数据覆盖
}
```

### Step 2: 扩展 loginViaUI 函数

```typescript
async function loginViaUI(page: Page, role: "admin" | "user" | "viewer" = "admin"): Promise<void> {
  const credentials = {
    admin: { email: "admin@test.com", password: process.env.QA_ADMIN_PASSWORD ?? "Test1234!" },
    user: { email: "user@test.com", password: process.env.QA_USER_PASSWORD ?? "Test1234!" },
    viewer: { email: "viewer@test.com", password: process.env.QA_VIEWER_PASSWORD ?? "Test1234!" },
  };
  // ... 登录逻辑
}
```

### Step 3: 扩展 mockLangGraphAPI 支持自定义覆盖

```typescript
// 在 mock-api.ts 中增加 options 参数支持
function mockLangGraphAPI(page: Page, overrides?: Record<string, any>) {
  // 默认 mock 数据
  const agents = overrides?.agents ?? [MOCK_AGENT];
  const workflows = overrides?.workflows ?? [MOCK_WORKFLOW];
  // ...
}
```

### Step 4: 逐 Phase 添加截图配置

按 Phase 1 → 2 → 3 顺序，在 SCREENSHOTS 数组中添加新配置。

### Step 5: 更新 Mobile 和 Dark Mode 过滤器

将新增截图中需要 mobile/dark 变体的页面名添加到 `MOBILE_SCREENSHOTS` 和 `DARK_SCREENSHOTS` 过滤列表中。

### Step 6: 更新 qa-tester SKILL.md

更新截图覆盖页面列表，反映新增的对话框、交互状态、空状态等截图。

---

## 验证清单

每个 Phase 完成后：

- [ ] 运行 `npx playwright test tests/e2e/qa/visual-screenshot.spec.ts --project=qa`
- [ ] 检查 `frontend/test-results/qa/screenshots/` 目录下截图文件数量
- [ ] 检查每个 `-health.json` 文件的 `status` 字段
- [ ] 人工抽查 5 张截图，确认截到了预期的 UI 状态
- [ ] 确认 mobile 变体的视口正确（375px 宽度）
- [ ] 确认 dark mode 变体的配色正确

---

## 文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/tests/e2e/qa/visual-screenshot.spec.ts` | 编辑 | 新增 63 个截图配置 |
| `frontend/tests/e2e/utils/mock-api.ts` | 编辑 | 支持自定义 mock 覆盖 |
| `.claude/skills/qa-tester/SKILL.md` | 编辑 | 更新截图覆盖页面列表 |
| `docs/screenshot-test-coverage-plan.md` | 本文件 | 计划文档 |
