/**
 * Smoke Test: Login Page
 *
 * 验证登录页面能正常加载，表单元素可用。
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

test.describe("Smoke: Login Page", () => {
  test("should load login page", async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // 验证页面加载
    await expect(page).toHaveTitle(/iDeer|Login|登录/);

    // 验证表单元素
    const emailInput = page
      .locator(
        'input[type="email"], input[name="email"], input[placeholder*="email" i]',
      )
      .first();
    const passwordInput = page.locator('input[type="password"]').first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
      )
      .first();

    await expect(emailInput).toBeVisible({ timeout: 10000 });
    await expect(passwordInput).toBeVisible({ timeout: 10000 });
    await expect(submitButton).toBeVisible({ timeout: 10000 });
  });

  test("should show error for invalid credentials", async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // 输入错误凭据
    const emailInput = page
      .locator('input[type="email"], input[name="email"]')
      .first();
    const passwordInput = page.locator('input[type="password"]').first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
      )
      .first();

    await emailInput.fill("invalid@test.com");
    await passwordInput.fill("wrongpassword");
    await submitButton.click();

    // 验证错误提示
    const errorMessage = page
      .locator("text=/错误|error|invalid|失败/i")
      .first();
    await expect(errorMessage).toBeVisible({ timeout: 10000 });
  });
});
