import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const MOCK_AUDIT_LOGS = [
  {
    id: "log-00000001-aaaa-bbbb-cccc-dddddddddddd",
    actor_id: "user-1",
    action: "create",
    resource_type: "agent",
    resource_id: "agent-alpha",
    detail: '{"name":"agent-alpha"}',
    ip_address: "192.168.1.100",
    created_at: "2025-06-01T10:00:00Z",
  },
  {
    id: "log-00000002-aaaa-bbbb-cccc-dddddddddddd",
    actor_id: "user-2",
    action: "delete",
    resource_type: "tool",
    resource_id: "tool-beta",
    detail: null,
    ip_address: "10.0.0.50",
    created_at: "2025-06-02T14:30:00Z",
  },
  {
    id: "log-00000003-aaaa-bbbb-cccc-dddddddddddd",
    actor_id: "user-1",
    action: "update",
    resource_type: "skill",
    resource_id: "skill-gamma",
    detail: '{"old":{"enabled":false},"new":{"enabled":true}}',
    ip_address: "192.168.1.100",
    created_at: "2025-06-03T09:15:00Z",
  },
];

test.describe("Audit logs", () => {
  test.describe("Page rendering", () => {
    test("audit logs page loads with header and log cards", async ({
      page,
    }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Should show the page title "审计日志"
      await expect(page.getByText("审计日志")).toBeVisible({
        timeout: 15_000,
      });
      // Should show the subtitle
      await expect(page.getByText("浏览和查询系统操作审计记录")).toBeVisible();

      // Should show log cards with truncated IDs
      const logCards = page.locator(
        '[data-testid="audit-logs-page"] [data-slot="card"]',
      );
      await expect(logCards).toHaveCount(3);
      await expect(logCards.first().getByText("log-0000")).toBeVisible();
      await expect(logCards.nth(1).getByText("log-0000")).toBeVisible();
    });

    test("log cards display action badges", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Action labels: create → 创建, delete → 删除, update → 更新
      await expect(page.getByText("创建").first()).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("删除").first()).toBeVisible();
      await expect(page.getByText("更新").first()).toBeVisible();
    });

    test("log cards display resource type badges", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Resource type labels: agent → 智能体, tool → 工具, skill → Skill
      await expect(page.getByText("智能体").first()).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("工具").first()).toBeVisible();
      await expect(page.getByText("Skill").first()).toBeVisible();
    });

    test("log cards show actor and resource info", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Actor info: "操作者:" followed by actor_id
      await expect(page.getByText("操作者:").first()).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("user-1").first()).toBeVisible();
      await expect(page.getByText("user-2").first()).toBeVisible();

      // Resource info: "资源:" followed by resource_id
      await expect(page.getByText("资源:").first()).toBeVisible();
      await expect(page.getByText("agent-alpha").first()).toBeVisible();
    });

    test("log cards show IP address", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      await expect(page.getByText("IP:").first()).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("192.168.1.100").first()).toBeVisible();
    });

    test("total count is displayed", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      await expect(page.getByText("共 3 条")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("empty state shows placeholder message", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: [] });
      await page.goto("/workspace/admin/audit-logs");

      await expect(page.getByText("没有找到审计日志")).toBeVisible({
        timeout: 15_000,
      });
    });
  });

  test.describe("Filters", () => {
    test("action filter dropdown is visible", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // The action filter select trigger shows "操作类型"
      await expect(
        page.locator('[data-testid="audit-logs-page"]').getByText("操作类型"),
      ).toBeVisible({ timeout: 15_000 });
    });

    test("resource type filter dropdown is visible", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      await expect(
        page.locator('[data-testid="audit-logs-page"]').getByText("资源类型"),
      ).toBeVisible({ timeout: 15_000 });
    });

    test("actor filter input is visible", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // The actor filter input has placeholder "用户 ID"
      await expect(page.getByPlaceholder("用户 ID")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("date filter inputs are visible", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Start and end date inputs
      await expect(
        page.locator('[data-testid="audit-logs-page"]').getByText("开始时间"),
      ).toBeVisible({ timeout: 15_000 });
      await expect(
        page.locator('[data-testid="audit-logs-page"]').getByText("结束时间"),
      ).toBeVisible();
    });

    test("reset button clears filters", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Type into actor filter
      const actorInput = page.getByPlaceholder("用户 ID");
      await actorInput.fill("user-1");
      await expect(actorInput).toHaveValue("user-1");

      // Click reset button
      const resetBtn = page.getByRole("button", { name: /重置/i });
      await expect(resetBtn).toBeVisible({ timeout: 15_000 });
      await resetBtn.click();

      // Input should be cleared
      await expect(actorInput).toHaveValue("");
    });
  });

  test.describe("Detail dialog", () => {
    test("clicking a log card opens detail dialog", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Click the first log card — Cards have cursor-pointer class
      const firstCard = page
        .locator('[data-testid="audit-logs-page"] [data-slot="card"]')
        .first();
      await firstCard.click();

      // Detail dialog should open with title "审计日志详情"
      await expect(page.getByText("审计日志详情")).toBeVisible({
        timeout: 10_000,
      });
    });

    test("detail dialog shows log detail JSON", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // Click the first log card
      const firstCard = page
        .locator('[data-testid="audit-logs-page"] [data-slot="card"]')
        .first();
      await firstCard.click();

      // Detail dialog should show the JSON content
      await expect(page.getByText("审计日志详情")).toBeVisible({
        timeout: 10_000,
      });
      // The first log has detail: '{"name":"agent-alpha"}'
      await expect(
        page.getByRole("dialog").getByText(/"name": "agent-alpha"/),
      ).toBeVisible();
    });
  });

  test.describe("Back navigation", () => {
    test("back arrow navigates to admin page", async ({ page }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin/audit-logs");

      // The back arrow is a Link to /workspace/admin
      const backLink = page.locator('a[href="/workspace/admin"]');
      await expect(backLink).toBeVisible({ timeout: 15_000 });
      await backLink.click();

      await expect(page).toHaveURL(/\/workspace\/admin/, { timeout: 10_000 });
    });
  });

  test.describe("Access from admin sidebar", () => {
    test("audit logs link is accessible from admin navigation", async ({
      page,
    }) => {
      mockLangGraphAPI(page, { auditLogs: MOCK_AUDIT_LOGS });
      await page.goto("/workspace/admin");

      // Should show audit logs link/card on admin dashboard and be clickable
      const auditLogsLink = page.getByRole("link", { name: /审计日志/i });
      await expect(auditLogsLink.first()).toBeVisible({
        timeout: 15_000,
      });
      await auditLogsLink.first().click();
      await expect(page).toHaveURL(/\/workspace\/admin\/audit-logs/, {
        timeout: 10_000,
      });
    });
  });
});
