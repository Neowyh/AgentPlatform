/**
 * Smoke Test: Landing Page
 *
 * 验证首页能正常加载，包含关键元素。
 *
 * NOTE: When IDEER_AUTH_DISABLED=1, there is no login link on the landing page.
 * The CTA button is "Get Started with 2.0" linking to /workspace.
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

test.describe("Smoke: Landing Page", () => {
  test("should load landing page", async ({ page }) => {
    await page.goto(BASE_URL);

    // 验证页面加载
    await expect(page).toHaveTitle(/iDeer/);

    // 验证关键元素存在 - Hero section has rotating words like "Deep Research", "Collect Data", etc.
    const hero = page
      .locator("text=/Deep Research|Collect Data|Analyze Data|Get Started/i")
      .first();
    await expect(hero).toBeVisible({ timeout: 10000 });
  });

  test("should have entry point to workspace", async ({ page }) => {
    await page.goto(BASE_URL);

    // Landing page has "Get Started with 2.0" CTA linking to /workspace
    // (no login link when auth is disabled)
    const entryLink = page
      .locator(
        'a[href*="workspace"], button:has-text("Get Started"), button:has-text("登录"), button:has-text("Login"), a[href*="login"]',
      )
      .first();
    await expect(entryLink).toBeVisible({ timeout: 10000 });
  });
});
