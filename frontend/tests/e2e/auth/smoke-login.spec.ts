/**
 * Smoke Test: Login Page
 *
 * Verifies the login page renders correctly and form elements are interactive.
 * These tests run with authentication ENABLED — they override storageState
 * to start unauthenticated so the login page is reachable.
 */

import { test, expect } from "@playwright/test";

// Auth E2E tests need IDEER_AUTH_DISABLED off.  When it's on (required for
// non-auth E2E tests to pass SSR mocks), these tests can't run.
// Run with: npx playwright test --project=auth
test.skip(
  process.env.IDEER_AUTH_DISABLED === "1",
  "IDEER_AUTH_DISABLED — SSR always returns authenticated, login page unreachable",
);

// Start unauthenticated so the login page is accessible (not redirected).
const emptyStorageState = { cookies: [], origins: [] };

test.describe("Smoke: Login Page", () => {
  test.use({ storageState: emptyStorageState });

  test("should load login page", async ({ page }) => {
    await page.goto("/login");

    // Page should load
    await expect(page).toHaveTitle(/iDeer|Login|登录/);

    // Form elements: <input id="email" type="email"> and <input id="password" type="password">
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
    await page.goto("/login");

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

    // The login form reports authentication failures through a Sonner toast.
    const errorMessage = page
      .locator("[data-sonner-toast]")
      .filter({ hasText: /invalid email or password|邮箱或密码错误/i });
    await expect(errorMessage).toBeVisible({ timeout: 10000 });
    await expect(errorMessage).toHaveText(/incorrect|invalid|error|失败/i);
  });
});
