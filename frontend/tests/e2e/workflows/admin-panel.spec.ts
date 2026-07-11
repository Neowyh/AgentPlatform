/**
 * Admin Panel: 管理面板流程
 *
 * 测试:
 * 1. 访问管理面板
 * 2. 查看统计数据
 * 3. 用户管理
 * 4. 部门管理
 */

import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

test.describe("Admin Panel", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
  });

  test("should access admin dashboard", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/admin`);

    // 验证管理面板加载
    const dashboard = page.locator("text=/管理|admin|dashboard|统计/i").first();
    await expect(dashboard).toBeVisible({ timeout: 10000 });
  });

  test("should show stats cards", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/admin`);

    // 验证统计卡片
    const statsCards = page
      .locator('[data-testid="stat-card"], [class*="stat"], [class*="card"]')
      .first();
    await expect(statsCards).toBeVisible({ timeout: 10000 });
  });

  test("should navigate to user management", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/admin`);

    // 查找用户管理链接
    const userLink = page
      .locator(
        'a:has-text("用户"), a:has-text("Users"), button:has-text("用户"), button:has-text("Users")',
      )
      .first();
    await expect(userLink).toBeVisible({ timeout: 10000 });
    await userLink.click();

    // 验证用户列表
    await page.waitForURL(/\/admin\/users/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/admin\/users/);
  });

  test("should navigate to department management", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/admin`);

    // 查找部门管理链接
    const deptLink = page
      .locator(
        'a:has-text("部门"), a:has-text("Departments"), button:has-text("部门"), button:has-text("Departments")',
      )
      .first();
    await expect(deptLink).toBeVisible({ timeout: 10000 });
    await deptLink.click();

    // 验证部门列表
    await page.waitForURL(/\/admin\/departments/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/admin\/departments/);
  });
});
