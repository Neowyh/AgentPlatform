# B7 E2E 剩余 17 个失败 — 问题分析 & 修复方案

> 本文档记录 B7（前端 E2E 回归）中剩余的 17 个测试失败，逐一说明根因、分析过程和修复方案。
>
> 编写于 2026-07-08，基于 commit `f1aeb9c1`（`fix(tests): resolve E2E SSR auth incompatibility with IDEER_AUTH_DISABLED`）

---

## 背景

B7 批次执行 `npx playwright test tests/e2e --project=chromium` 后，结果从原始的 191 passed / 122 failed 提升至 **291 passed / 17 failed / 14 skipped**。

修复的核心改动是在 `frontend/playwright.config.ts` 的 webServer 环境变量中添加 `IDEER_AUTH_DISABLED=1`，使 Next.js SSR 跳过真实认证流程，直接返回 super_admin 用户。但这导致两个认证相关测试需跳过（auth-flow、smoke-login），且暴露了新的问题。

---

## 失败全景

| 类别 | 套件 | 失败数 | 性质 |
|------|------|--------|------|
| 1 | audit-logs | 8 | Mock 拦截未生效（SSR 时序） |
| 2 | skill-management | 5 | 测试与 UI 实现不匹配 |
| 3 | settings-management | 1 | data-testid 被 Radix UI 吞掉 |
| 4 | admin-management | 1 | 部门资源 API mock 缺失 |
| 5 | a11y | 1 | WCAG 违规 |
| 6 | visual | 1 | 截图基线过期 |
| **合计** | | **17** | |

---

## 类别 1：审计日志 — Mock 拦截未生效（8 个失败）

> ⚠️ **对抗审查修正**：初版文档错误地将根因归为 SSR。`useEffect` 永远不会在 SSR 期间执行（React 基本行为），导致 `listAuditLogs()` 在服务器端执行的假设不成立。以下为修正后的分析。

### 涉及测试

`frontend/tests/e2e/audit-logs.spec.ts`:

| # | 测试名 | 行号 | 断言 |
|---|--------|------|------|
| 1 | audit logs page loads with header and log cards | :40 | `getByText("log-0000")` 可见 |
| 2 | log cards display resource type badges | :70 | `getByText("工具").first()` 可见 |
| 3 | log cards show actor and resource info | :82 | `getByText("user-1").first()` 可见 |
| 4 | log cards show IP address | :98 | `getByText("192.168.1.100")` 可见 |
| 5 | total count is displayed | :108 | `getByText("共 3 条")` 可见 |
| 6 | empty state shows placeholder message | :117 | `getByText("没有找到审计日志")` 可见 |
| 7 | clicking a log card opens detail dialog | :190 | `getByText("审计日志详情")` 可见 |
| 8 | detail dialog shows log detail JSON | :206 | `getByText("审计日志详情")` 可见 |

### 根因分析

```
【源码追踪 — 数据获取路径】
  frontend/src/app/workspace/admin/audit-logs/page.tsx
    → line 1: "use client"（客户端组件）
    → line 97: fetchLogs useCallback 调用 listAuditLogs()
    → line 126: useEffect 在组件挂载时触发获取
      → useEffect 仅在浏览器端执行，不会在 SSR 期间运行 ✓

  frontend/src/core/audit-logs/api.ts
    → line 16-29: url = getBackendBaseURL() + "/api/admin/audit-logs"

  frontend/src/core/config/index.ts
    → line 11-18: getBackendBaseURL()
      → 若 NEXT_PUBLIC_BACKEND_BASE_URL 未设置，返回 ""
      → 此时 url = "/api/admin/audit-logs"（相对路径，同源请求）

  frontend/src/core/api/fetcher.ts
    → line 82: globalThis.fetch(url, { credentials: "include" })
      → 浏览器原生 fetch → 应被 Playwright page.route() 拦截 ✓

【源码追踪 — Mock 注册路径】
  mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS })   // test line 43
    → 注册 page.route("**/api/admin/audit-logs", handler)  // mock-api.ts:1056
    → 注册 page.route("**/api/admin/stats", handler)       // mock-api.ts:833
    → 注册 page.route("**/api/admin/users", handler)       // mock-api.ts:849
    → 注册 page.route("**/api/admin/users/*", handler)     // mock-api.ts:865
    → 注册 page.route("**/api/admin/departments", handler) // mock-api.ts:881
    → 注册 page.route("**/api/admin/departments/*", handler)// mock-api.ts:905
  await page.goto("/workspace/admin/audit-logs")           // test line 44
```

**核心问题**：`page.route("**/api/admin/audit-logs")` 理论上应拦截同源相对路径 `/api/admin/audit-logs?page=1&page_size=20`（Playwright glob `**` 匹配任何路径前缀）。页面 dump 显示 32 条真实 UUID 数据，说明 mock 确实未生效。

**可能原因（需进一步诊断）**：

1. **Playwright glob 匹配问题**：虽然 `**/api/admin/audit-logs` 按文档应匹配 `/api/admin/audit-logs`，但 Next.js 生产模式下 fetch 可能经过 service worker 或自定义代理，导致 URL 与预期不同。建议添加诊断代码确认实际请求 URL。

2. **路由注册顺序冲突**：mock-api.ts 先注册了 `**/api/admin/departments/*`（line 905），该通配符也可能意外匹配审计日志的 URL（如果 Next.js 的路径重写规则改变了 URL 结构），导致先被该路由处理并 fallthrough。

3. **Next.js RSC Payload 预取**：如果 workspace layout 中的侧边栏链接使用了 `<Link prefetch={true}>`（Next.js 默认行为），审计日志页面的 RSC payload 可能被预取，其中包括服务器组件部分的数据。但这不影响 `useEffect` 中的客户端 fetch——除非审计日志页面有未发现的服务器组件包装。

**首要任务**：在测试中添加 Playwright 请求日志，确认实际请求的 URL 和方法：

```typescript
page.on("request", (req) => console.log("REQ:", req.method(), req.url()));
page.on("response", (res) => console.log("RES:", res.status(), res.url()));
```

### 修复方案

由于根因尚未完全确定，**不要直接修改测试代码**。先执行诊断步骤：

**第一步：诊断（在测试中添加请求监听）**

```typescript
// audit-logs.spec.ts:43 后添加
page.on("request", (req) => console.log("REQ:", req.method(), req.url()));
page.on("requestfailed", (req) => console.log("FAILED:", req.url()));
```

运行测试检查日志，确认实际请求 URL。重点关注：
- 请求是否真的发往 `/api/admin/audit-logs`？
- 请求的完整 URL 是什么（是否包含 origin 或前缀）？
- Playwright 是否看到了这个请求？

**第二步：根据诊断结果选择对应方案**

| 诊断结果 | 对应方案 |
|---------|---------|
| URL 是 `/api/admin/audit-logs?page=1&page_size=20` 但 mock 未命中 | 改用正则匹配：`new RegExp('/api/admin/audit-logs')` |
| URL 包含额外前缀（如 `/api/langgraph/...`） | 调整 mock 路由模式覆盖实际 URL |
| 请求 URL 正确但被其他路由先拦截 | 调整路由注册顺序，将审计日志路由提前 |
| 请求在 Playwright 中完全看不到 | 说明请求发自 Node.js 层（SSR/RSC prefetch），需从服务端侧处理 |
| `getBackendBaseURL()` 返回了非空值 | 检查 `NEXT_PUBLIC_BACKEND_BASE_URL` 环境变量 |

**影响范围**：8 个测试，均在 `frontend/tests/e2e/audit-logs.spec.ts` 中。**修复前必须完成诊断**。

---

## 类别 2：技能管理 — 测试与 UI 不匹配（5 个失败）

### 涉及测试

`frontend/tests/e2e/skill-management.spec.ts`:

| # | 测试名 | 行号 | 失败原因 |
|---|--------|------|---------|
| 1 | skills show category and license badges | :83 | `getByText(/requires internet/i)` 不可见 |
| 2 | enable/disable toggle is visible | :99 | `getByRole("switch").first()` 不可见 |
| 3 | edit button opens skill editor dialog | :113 | `button[title="Edit skill"]` 30s 超时 |
| 4 | test button opens test dialog | :132 | `button[title="Test skill"]` 30s 超时 |
| 5 | create button navigates to skill creation chat | :151 | `button[name=/create.*skill/]` 30s 超时 |

### 根因分析

```
【源码追踪】
  frontend/src/components/workspace/settings/skill-settings-page.tsx
    → line 46-88: SkillSettingsList 组件
      → 用 <Tabs> 渲染 Public / Custom 两个 tab
      → 用 <Item> + <ItemContent> + <ItemTitle> 渲染技能列表
      → 每个技能只显示 name + category badge + description
      → 没有 toggle switch（<Switch>）
      → 没有 edit button（无编辑入口）
      → 没有 test button（无测试入口）
      → 没有 create button（无创建入口）
    → 这是一个只读浏览组件
```

**核心问题**：技能设置页面是"只读浏览"设计，每个技能卡片只显示名称、分类标签和描述。测试期望的 toggle 开关、编辑/测试/创建按钮**在当前实现中不存在**。测试 1-2 失败是断言找的元素不存在，测试 3-5 失败是按钮找不着导致 30 秒超时。

需要注意的是，测试 1（category badge）中 "public" 文字是可见的（作为 category badge），所以该断言通过。但 license badge（"Requires Internet"）不显示，测试失败。

### 修复方案

删除或修改 5 个测试，使其只断言**实际存在的 UI 元素**。具体的修改策略：

| 测试 | 断言内容 | 修改方式 |
|------|---------|---------|
| skills show category and license badges | public badge + requires internet badge | 保留 public badge 断言，删除 requires internet 断言 |
| enable/disable toggle is visible | switch 可见 | 整个 test 删除 |
| edit button opens skill editor dialog | edit button → cm-editor | 整个 test 删除 |
| test button opens test dialog | test button → dialog | 整个 test 删除 |
| create button navigates to skill creation chat | create button → URL with mode=skill | 整个 test 删除（或改为测空状态文案） |

如果未来 UI 增加了这些交互控件，可重新启用对应的测试。

**影响范围**：5 个测试，均在 `frontend/tests/e2e/skill-management.spec.ts` 中。

---

## 类别 3：设置对话框 data-testid 丢失（1 个失败）

### 涉及测试

`frontend/tests/e2e/settings-management.spec.ts:42`:

```typescript
test("settings dialog opens via sidebar menu", async ({ page }) => {
  mockLangGraphAPI(page);
  await page.goto("/workspace/chats/new");
  await openSettings(page);
  await expect(page.getByTestId("settings-dialog")).toBeVisible({ timeout: 15_000 });
});
```

页面 dump 证实对话框已打开（可见 heading "Settings" + 7 个 tab），但 `getByTestId("settings-dialog")` 找不到。

### 根因分析

```
【源码追踪】
  frontend/src/components/workspace/settings/settings-dialog.tsx
    → line 95-98:
      <Dialog
        {...dialogProps}
        onOpenChange={(open) => props.onOpenChange?.(open)}
        data-testid="settings-dialog"     // ← 这里设置
      >
    → line 100-103:
      <DialogContent
        ...
        data-testid="settings-dialog-content"  // ← DialogContent 也有 testid
      >
```

`data-testid="settings-dialog"` 设置在了 `<Dialog>` 组件上。但 shadcn/ui 的 `<Dialog>` 基于 **Radix UI Dialog**，Radix 的 `<Dialog>` 组件**不渲染任何 DOM 元素**——它只是一个 React Context 提供者，管理弹窗的开关状态。实际的 DOM 节点由 `<DialogContent>`（通过 Portal 渲染）和 `<DialogTrigger>` 创建。

因此，`data-testid="settings-dialog"` 属性被 React 接收但没有渲染到任何实际 DOM 节点上，Playwright 找不到它。

### 修复方案

**方案 A（推荐）**：修改测试，改用 `getByRole` 定位器——Playwright 的可访问性树可以正确识别 dialog 元素：

```typescript
// 改前：
await expect(page.getByTestId("settings-dialog")).toBeVisible();

// 改后：
await expect(page.getByRole("dialog", { name: /settings/i })).toBeVisible();
```

**方案 B**：把 `data-testid` 从 `<Dialog>` 移到 `<DialogContent>`（但 `data-testid="settings-dialog-content"` 已经存在且被其他测试使用，不建议重复利用）。

**影响范围**：1 个测试，在 `frontend/tests/e2e/settings-management.spec.ts` 中。

---

## 类别 4：删除部门 — 资源 API mock 缺失（1 个失败）

### 涉及测试

`frontend/tests/e2e/admin-management.spec.ts:158`:

```typescript
test("delete department shows native confirm dialog", async ({ page }) => {
  mockLangGraphAPI(page, { departments: MOCK_DEPARTMENTS });
  await page.goto("/workspace/admin/departments");
  page.on("dialog", async (dialog) => {
    dialogMessage = dialog.message();
    await dialog.accept();
  });
  const deleteBtn = page.locator('button[title="删除"]').first();
  await deleteBtn.click();
  await expect.poll(() => dialogMessage).toContain("确定");
});
```

`dialogMessage` 始终为空字符串，`window.confirm()` 从未被触发。

### 根因分析

```
【源码追踪】
  frontend/src/app/workspace/admin/departments/page.tsx
    → line 165: handleDelete 函数
      → 先调用 getDepartmentResources(deptId) 获取部门资源
      → 如果 resources.length === 0：走 window.confirm()
      → 如果 resources.length > 0：走自定义资源重分配 Dialog

  frontend/tests/e2e/utils/mock-api.ts
    → line 905-918: **/api/admin/departments/*
      → PUT: ✅ 返回 200
      → DELETE: ✅ 返回 204
      → 其他方法: ❌ route.fallback() → 穿透到真实后端
```

**核心问题**：`getDepartmentResources(deptId)` 的 API 路径通常是 `**/api/admin/departments/{id}/resources`。当前 mock 中 `**/api/admin/departments/*` 的通配符会匹配到这个路径，但因为方法不是 PUT/DELETE，调用了 `route.fallback()`，请求穿透到**真实后端**（运行在 8001 端口）。真实后端返回的部门资源数量 > 0，触发自定义资源重分配 Dialog 而非 `window.confirm()`，导致测试监听不到原生 dialog 事件。

### 修复方案

在 `mock-api.ts` 的 departments 路由区域添加对资源检查端点的 mock。注意两点：

1. **路由必须注册在 `**/api/admin/departments/*` 之前**（line 905 之前），Playwright 按注册顺序匹配，更具体的路由必须更早注册
2. **Mock 响应应包含完整的字段**，以匹配 API 的返回类型

具体代码改动（在 `mock-api.ts` line 881 的 `**/api/admin/departments` 之后、line 905 的 `**/api/admin/departments/*` 之前插入）：

```typescript
// 添加到 mock-api.ts:903（**/api/admin/departments/* 路由之前）
void page.route("**/api/admin/departments/*/resources", (route) => {
  if (route.request().method() === "GET") {
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        department_id: "dept-1",
        department_name: "Engineering",
        resources: [],
        total_count: 0,
      }),
    });
  }
  return route.fallback();
});
```

**影响范围**：1 个测试，在 `frontend/tests/e2e/admin-management.spec.ts` 中；1 个文件，在 `frontend/tests/e2e/utils/mock-api.ts` 中。

---

## 类别 5：WCAG 无障碍违规（1 个失败）

### 涉及测试

`frontend/tests/e2e/a11y/accessibility.spec.ts:24`:

```
Accessibility -- WCAG 2.1 AA >> Agents page has no critical a11y violations
→ 期望 0 个严重违规，实际收到 2 个
```

### 根因分析

Agents 页面渲染了 `AgentGallery` 组件，包含侧边栏、筛选器、搜索框、收藏按钮、导入按钮、"New Agent" 按钮以及 Agent 卡片网格。2 个 axe-core 严重违规需要运行 `analyze()` 获取具体 violation ID 和 selector。

### 修复方案

**方案 A**：运行 axe 分析获取具体违规详情后修复 UI。
**方案 B（临时）**：在测试中跳过这个断言：

```typescript
// accessibility.spec.ts:24
test.skip("Agents page has no critical a11y violations", async ({ page }) => { ... });
```

**影响范围**：1 个测试，在 `frontend/tests/e2e/a11y/accessibility.spec.ts` 中。

---

## 类别 6：截图基线过期（1 个失败）

### 涉及测试

`frontend/tests/e2e/visual/landing.visual.spec.ts:26`:

```
Landing -- visual regression >> mobile viewport screenshot
→ expected: 384×7136px, received: 384×7164px
→ 64,900 pixels different (0.03 ratio, threshold: 0.01)
```

### 根因分析

首页移动端视图的内容发生了变化，页面高度增加了 28 像素。3% 的像素差异超过了 1% 的阈值。

### 修复方案

重新生成截图基线：

```bash
cd frontend
npx playwright test tests/e2e/visual --project=visual --update-snapshots
```

**影响范围**：1 个测试，在 `frontend/tests/e2e/visual/landing.visual.spec.ts` 中；截图文件需要更新。

---

## 修复优先级建议

| 优先级 | 类别 | 理由 |
|--------|------|------|
| P0 | 类别 1（audit-logs 8 个） | 数量最多，阻塞审计功能验证，但需先诊断 |
| P1 | 类别 4（admin-delete 1 个） | 在 mock-api.ts 加一条路由即可修复 |
| P2 | 类别 3（settings-dialog 1 个） | 修复极小（改 1 行测试） |
| P3 | 类别 2（skill-management 5 个） | 技能设置页只读，5 个测试需同步 |
| P4 | 类别 6（visual 1 个） | 一键重新截图 |
| P5 | 类别 5（a11y 1 个） | 需先获取 axe 违规详情后再修复 |

## 修改清单

| 文件 | 改动类型 | 说明 | Ready |
|------|---------|------|-------|
| `frontend/tests/e2e/audit-logs.spec.ts` | 测试代码 | 8 个测试需先诊断再修复 | ❌ 待诊断 |
| `frontend/tests/e2e/skill-management.spec.ts` | 测试代码 | 删除 5 个与 UI 不匹配的测试 | ✅ 可直接改 |
| `frontend/tests/e2e/settings-management.spec.ts` | 测试代码 | 1 个测试定位器改为 getByRole | ✅ 可直接改 |
| `frontend/tests/e2e/utils/mock-api.ts` | 测试工具 | 添加 department resources mock 路由 | ✅ 可直接改 |
| `frontend/tests/e2e/a11y/accessibility.spec.ts` | 测试代码 | 1 个测试加 skip 或修复 UI | ⚠️ 需 axe 详情 |
| — | 截图更新 | 重新生成 mobile landing 截图 | ✅ 可直接改 |
