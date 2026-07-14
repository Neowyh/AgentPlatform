import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

test.describe("Login — visual regression", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test("default viewport screenshot", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();

    await expect(page).toHaveScreenshot("login-default.png", {
      fullPage: true,
    });
  });
});
