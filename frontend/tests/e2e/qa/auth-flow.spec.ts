/**
 * Auth Flow: 登录/登出完整流程
 *
 * 测试:
 * 1. 访问受保护页面 → 重定向到登录
 * 2. 登录 → 进入 workspace
 * 3. 登出 → 返回登录页
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const TEST_EMAIL = "admin@test.com";
const TEST_PASSWORD = "Test1234!";

test.describe("Auth Flow", () => {
  test("should redirect to login when not authenticated", async ({ page }) => {
    // 清除认证状态
    await page.context().clearCookies();

    // 访问受保护页面
    await page.goto(`${BASE_URL}/workspace`);

    // 应该重定向到登录页
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test("should login successfully", async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // 填写登录表单
    const emailInput = page
      .locator('input[type="email"], input[name="email"]')
      .first();
    const passwordInput = page.locator('input[type="password"]').first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
      )
      .first();

    await emailInput.fill(TEST_EMAIL);
    await passwordInput.fill(TEST_PASSWORD);
    await submitButton.click();

    // 验证跳转到 workspace
    await page.waitForURL(/\/workspace/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/workspace/);
  });

  test("should logout successfully", async ({ page }) => {
    // 先登录
    await page.goto(`${BASE_URL}/login`);
    const emailInput = page
      .locator('input[type="email"], input[name="email"]')
      .first();
    const passwordInput = page.locator('input[type="password"]').first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
      )
      .first();

    await emailInput.fill(TEST_EMAIL);
    await passwordInput.fill(TEST_PASSWORD);
    await submitButton.click();
    await page.waitForURL(/\/workspace/, { timeout: 15000 });

    // 登出
    const logoutButton = page
      .locator(
        'button:has-text("登出"), button:has-text("Logout"), a:has-text("登出"), a:has-text("Logout")',
      )
      .first();

    // 可能需要先打开菜单
    const menuButton = page
      .locator('button[aria-label="menu"], button[aria-label="Menu"]')
      .first();
    if (await menuButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await menuButton.click();
    }

    await logoutButton.click();

    // 验证返回登录页
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/login/);
  });
});
