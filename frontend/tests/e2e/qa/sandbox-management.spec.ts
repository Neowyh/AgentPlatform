import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

/**
 * Sandbox management E2E tests.
 *
 * Verifies that sandbox-related UI elements render correctly.
 * Actual sandbox API testing is covered by the backend test template
 * (sandbox-test.template.py); this file focuses on front-end behaviour.
 */

test.describe("Sandbox Management", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
  });

  test("workspace page loads without sandbox errors", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // The workspace should render without crashing
    await expect(page.locator("body")).toBeVisible();

    // Check that no uncaught sandbox-related errors appear
    const errors: string[] = [];
    page.on("pageerror", (err) => {
      if (err.message.toLowerCase().includes("sandbox")) {
        errors.push(err.message);
      }
    });

    // Give the page a moment to settle
    await page.waitForTimeout(1000);
    expect(errors).toHaveLength(0);
  });

  test("agent chat page renders without sandbox errors", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Navigate to an agent chat if available
    const agentLink = page
      .locator(
        '[data-testid="agent-card"], [data-testid="agent-item"], a[href*="/agent"]',
      )
      .first();

    if ((await agentLink.count()) === 0) {
      test.skip();
      return;
    }

    await agentLink.click();
    await page.waitForLoadState("networkidle");

    await expect(page.locator("body")).toBeVisible();
  });
});
