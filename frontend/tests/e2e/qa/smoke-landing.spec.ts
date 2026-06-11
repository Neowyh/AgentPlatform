/**
 * Smoke Test: Landing Page
 *
 * 验证首页能正常加载，包含关键元素。
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

test.describe("Smoke: Landing Page", () => {
  test("should load landing page", async ({ page }) => {
    await page.goto(BASE_URL);

    // 验证页面加载
    await expect(page).toHaveTitle(/iDeer/);

    // 验证关键元素存在
    const hero = page.locator("text=/AI|Agent|智能/i").first();
    await expect(hero).toBeVisible({ timeout: 10000 });
  });

  test("should have login link", async ({ page }) => {
    await page.goto(BASE_URL);

    // 查找登录链接
    const loginLink = page
      .locator(
        'a[href*="login"], button:has-text("登录"), button:has-text("Login")',
      )
      .first();
    await expect(loginLink).toBeVisible({ timeout: 10000 });
  });
});
