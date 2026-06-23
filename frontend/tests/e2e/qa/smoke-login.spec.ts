/**
 * Smoke Test: Login Page
 *
 * 验证登录页面能正常加载，表单元素可用。
 *
 * NOTE: These tests require a real backend with auth enabled.
 * They are skipped when IDEER_AUTH_DISABLED=1 (E2E mock mode)
 * because the auth layout redirects authenticated users away from /login.
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

test.describe("Smoke: Login Page", () => {
  // These tests require auth to be enabled (IDEER_AUTH_DISABLED != "1").
  // They run via playwright.auth.config.ts which does NOT set IDEER_AUTH_DISABLED.

  test("should load login page", async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // 验证页面加载
    await expect(page).toHaveTitle(/iDeer|Login|登录/);

    // 验证表单元素 - actual DOM: <input id="email" type="email"> and <input id="password" type="password">
    const emailInput = page.locator('input[type="email"], input#email').first();
    const passwordInput = page
      .locator('input[type="password"], input#password')
      .first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("Sign In"), button:has-text("登录"), button:has-text("Login")',
      )
      .first();

    await expect(emailInput).toBeVisible({ timeout: 10000 });
    await expect(passwordInput).toBeVisible({ timeout: 10000 });
    await expect(submitButton).toBeVisible({ timeout: 10000 });
  });

  test("should show error for invalid credentials", async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // 输入错误凭据
    const emailInput = page.locator('input[type="email"], input#email').first();
    const passwordInput = page
      .locator('input[type="password"], input#password')
      .first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("Sign In"), button:has-text("登录"), button:has-text("Login")',
      )
      .first();

    await emailInput.fill("invalid@test.com");
    await passwordInput.fill("wrongpassword");
    await submitButton.click();

    // 验证错误提示
    const errorMessage = page
      .locator("text=/错误|error|invalid|失败|incorrect|wrong/i")
      .first();
    await expect(errorMessage).toBeVisible({ timeout: 10000 });
  });
});
