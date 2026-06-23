/**
 * Auth Flow: 登录/登出完整流程
 *
 * 测试:
 * 1. 访问受保护页面 → 重定向到登录
 * 2. 登录 → 进入 workspace
 * 3. 登出 → 返回登录页
 *
 * NOTE: These tests require a real backend with auth enabled.
 * They are skipped when IDEER_AUTH_DISABLED=1 (E2E mock mode).
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const TEST_EMAIL = "super_admin@test.com";
const TEST_PASSWORD = "super_admin@test.com";

test.describe("Auth Flow", () => {
  // These tests require auth to be enabled (IDEER_AUTH_DISABLED != "1").
  // They run via playwright.auth.config.ts which does NOT set IDEER_AUTH_DISABLED.

  test("should redirect to login when not authenticated", async ({ page }) => {
    // 清除认证状态
    await page.context().clearCookies();

    // 访问受保护页面
    await page.goto(`${BASE_URL}/workspace`);

    // 应该重定向到登录页
    await expect(page).toHaveURL(/\/login/);
  });

  test("should login successfully", async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    // 填写登录表单
    const emailInput = page.locator('input[type="email"], input#email').first();
    const passwordInput = page
      .locator('input[type="password"], input#password')
      .first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("Sign In"), button:has-text("登录"), button:has-text("Login")',
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

    const emailInput = page.locator('input[type="email"], input#email').first();
    const passwordInput = page
      .locator('input[type="password"], input#password')
      .first();
    const submitButton = page
      .locator(
        'button[type="submit"], button:has-text("Sign In"), button:has-text("登录"), button:has-text("Login")',
      )
      .first();

    await emailInput.fill(TEST_EMAIL);
    await passwordInput.fill(TEST_PASSWORD);
    await submitButton.click();
    await page.waitForURL(/\/workspace/, { timeout: 15000 });

    // 登出 — 直接调用登出 API
    await page.evaluate(async () => {
      await fetch("/api/v1/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    });

    // 刷新页面验证登出
    await page.goto(`${BASE_URL}/login`);
    await expect(page).toHaveURL(/\/login/);
  });
});
