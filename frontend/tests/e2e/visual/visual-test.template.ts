import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

/**
 * Visual regression test template.
 *
 * Usage:
 *   1. Copy this file → rename to <page>.visual.spec.ts
 *   2. Replace PAGE_PATH, PAGE_NAME, and TEST_ROUTE
 *   3. Run: make test-visual          — compare against baseline
 *   4. Update: make test-visual-update — regenerate baseline screenshots
 *
 * Baseline screenshots live in `__screenshots__/` next to this file
 * and should be committed to git.
 */

const PAGE_NAME = "PAGE_NAME"; // e.g. "landing"
const TEST_ROUTE = "/"; // e.g. "/workspace"

test.describe(`${PAGE_NAME} — visual regression`, () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test("default viewport screenshot", async ({ page }) => {
    await page.goto(TEST_ROUTE);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500); // let animations settle

    await expect(page).toHaveScreenshot(`${PAGE_NAME}-default.png`, {
      fullPage: true,
      // Mask dynamic content that changes between runs:
      // mask: [page.locator('[data-testid="timestamp"]')],
    });
  });

  test("mobile viewport screenshot", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(TEST_ROUTE);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot(`${PAGE_NAME}-mobile.png`, {
      fullPage: true,
    });
  });

  test("dark mode screenshot", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto(TEST_ROUTE);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot(`${PAGE_NAME}-dark.png`, {
      fullPage: true,
    });
  });
});
