import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const MOCK_USERS = [
  {
    id: "user-1",
    username: "admin-user",
    email: "admin@test.com",
    department_id: "dept-1",
    department_name: "Engineering",
    role: "super_admin",
    disabled: false,
    created_at: "2025-01-01T00:00:00Z",
    last_login: "2025-06-01T00:00:00Z",
  },
  {
    id: "user-2",
    username: "regular-user",
    email: "user@test.com",
    department_id: "dept-2",
    department_name: "Marketing",
    role: "user",
    disabled: false,
    created_at: "2025-02-01T00:00:00Z",
    last_login: "2025-05-01T00:00:00Z",
  },
];

const MOCK_DEPARTMENTS = [
  {
    id: "dept-1",
    name: "Engineering",
    description: "Software engineering team",
    member_count: 10,
    agent_count: 5,
    skill_count: 8,
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "dept-2",
    name: "Marketing",
    description: "Marketing team",
    member_count: 5,
    agent_count: 2,
    skill_count: 3,
    created_at: "2025-01-15T00:00:00Z",
  },
];

const MOCK_TOOLS = [
  {
    name: "web_search",
    group: "web",
    description: "Search the web",
    requires_network: true,
  },
  {
    name: "read_document",
    group: "enterprise",
    description: "Read PDF/Word documents",
    requires_network: false,
  },
];

/** Helper: open the settings/more dropdown in sidebar */
async function openSidebarMenu(page: Page) {
  const trigger = page
    .locator("button")
    .filter({ hasText: /settings and more|settings/i })
    .last();
  await trigger.click({ timeout: 10_000 });
}

test.describe("Admin management", () => {
  test.describe("Dashboard", () => {
    test("admin dashboard loads with stat cards", async ({ page }) => {
      mockLangGraphAPI(page, {
        users: MOCK_USERS,
        departments: MOCK_DEPARTMENTS,
        tools: MOCK_TOOLS,
      });
      await page.goto("/workspace/admin");

      // Should show stat cards with Chinese labels
      await expect(page.getByText(/用户/i).first()).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText(/部门/i).first()).toBeVisible();
      await expect(page.getByText(/智能体/i).first()).toBeVisible();
    });
  });

  test.describe("User Management", () => {
    test("user list page loads with user cards", async ({ page }) => {
      mockLangGraphAPI(page, { users: MOCK_USERS });
      await page.goto("/workspace/admin/users");

      // Should show user names
      await expect(page.getByText("admin-user")).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("regular-user")).toBeVisible();
    });

    test("user cards show role badges", async ({ page }) => {
      mockLangGraphAPI(page, { users: MOCK_USERS });
      await page.goto("/workspace/admin/users");

      // Role badges use Chinese labels: "超级管理员" for super_admin
      await expect(page.getByText(/超级管理员/i).first()).toBeVisible({
        timeout: 15_000,
      });
    });
  });

  test.describe("Department Management", () => {
    test("department list page loads with department cards", async ({
      page,
    }) => {
      mockLangGraphAPI(page, { departments: MOCK_DEPARTMENTS });
      await page.goto("/workspace/admin/departments");

      // Should show department names (exact match to avoid matching descriptions)
      await expect(page.getByText("Engineering", { exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("Marketing", { exact: true })).toBeVisible();
    });

    test("department cards show member counts", async ({ page }) => {
      mockLangGraphAPI(page, { departments: MOCK_DEPARTMENTS });
      await page.goto("/workspace/admin/departments");

      // Member count renders as "10 成员" - use exact: false
      await expect(page.getByText("10", { exact: false }).first()).toBeVisible({
        timeout: 15_000,
      });
    });

    test("new department dialog opens", async ({ page }) => {
      mockLangGraphAPI(page, { departments: MOCK_DEPARTMENTS });
      await page.goto("/workspace/admin/departments");

      // Click new department button
      const newBtn = page.getByRole("button", {
        name: /新建.*部门|创建.*部门|new.*department/i,
      });
      await newBtn.click();

      // Dialog should open
      await expect(
        page.getByRole("dialog").or(page.locator("[role='dialog']")),
      ).toBeVisible({ timeout: 5_000 });
    });

    test("delete department shows native confirm dialog", async ({ page }) => {
      mockLangGraphAPI(page, { departments: MOCK_DEPARTMENTS });
      await page.goto("/workspace/admin/departments");

      // Delete uses browser native confirm(), handle it with page.on('dialog')
      let dialogMessage = "";
      page.on("dialog", async (dialog) => {
        dialogMessage = dialog.message();
        await dialog.accept();
      });

      // Delete button has title="删除"
      const deleteBtn = page.locator('button[title="删除"]').first();
      await expect(deleteBtn).toBeVisible({ timeout: 15_000 });
      await deleteBtn.click();

      // Verify the native confirm dialog was shown with expected message
      await expect
        .poll(() => dialogMessage, { timeout: 5_000 })
        .toContain("确定");
    });
  });

  test.describe("Tool Management", () => {
    test("tool list page loads with tool cards", async ({ page }) => {
      mockLangGraphAPI(page, { tools: MOCK_TOOLS });
      await page.goto("/workspace/admin/tools");

      // Should show tool names
      await expect(page.getByText("web_search")).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("read_document")).toBeVisible();
    });

    test("tool cards show network requirement badges", async ({ page }) => {
      mockLangGraphAPI(page, { tools: MOCK_TOOLS });
      await page.goto("/workspace/admin/tools");

      // Network badge shows "需联网" in Chinese
      await expect(page.getByText(/联网|需联网/i).first()).toBeVisible({
        timeout: 15_000,
      });
    });
  });

  test.describe("Navigation Access Control", () => {
    test("admin menu items are visible for admin users", async ({ page }) => {
      mockLangGraphAPI(page, {
        users: MOCK_USERS,
        departments: MOCK_DEPARTMENTS,
        tools: MOCK_TOOLS,
      });
      await page.goto("/workspace/chats/new");

      // Open the sidebar dropdown menu
      await openSidebarMenu(page);

      // Should show admin-related menu items
      await expect(page.getByText(/admin panel|管理后台/i).first()).toBeVisible(
        { timeout: 10_000 },
      );
    });
  });
});
