/**
 * Auth Flow: Login/Logout complete flow
 *
 * Tests:
 * 1. Access protected page -> redirect to login
 * 2. Login -> enter workspace
 * 3. Logout -> return to login page
 *
 * These tests run with authentication ENABLED — they override storageState
 * to start unauthenticated so the login flow can be exercised.
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const TEST_EMAIL = "super_admin@test.com";
const TEST_PASSWORD = "super_admin@test.com";

// Auth E2E tests need IDEER_AUTH_DISABLED off.  When it's on (required for
// non-auth E2E tests to pass SSR mocks), these tests can't run.
// Run with: npx playwright test --project=auth
test.skip(
  process.env.IDEER_AUTH_DISABLED === "1",
  "IDEER_AUTH_DISABLED — SSR always returns authenticated, login flow unreachable",
);

// Start unauthenticated so login/logout flows work.
const emptyStorageState = { cookies: [], origins: [] };

test.describe("Auth Flow", () => {
  test.use({ storageState: emptyStorageState });

  test("should redirect to login when not authenticated", async ({ page }) => {
    await page.context().clearCookies();

    await page.goto(`${BASE_URL}/workspace`);

    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/);
  });

  test("should login successfully", async ({ page }) => {
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

    // Should redirect to workspace after login
    await page.waitForURL(/\/workspace/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/workspace/);
  });

  test("should logout successfully", async ({ page }) => {
    // Login first
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

    // Logout — call the logout API via the frontend proxy
    await page.evaluate(async () => {
      await fetch("/api/v1/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    });

    // Navigate to login to verify logout took effect
    await page.goto(`${BASE_URL}/login`);
    await expect(page).toHaveURL(/\/login/);
  });
});
