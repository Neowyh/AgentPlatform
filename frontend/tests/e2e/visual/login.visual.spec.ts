import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

test.describe("Login — visual regression", () => {
  test.skip(
    process.env.DEER_FLOW_AUTH_DISABLED === "1" ||
      process.env.IDEER_AUTH_DISABLED === "1",
    "Auth-disabled visual lane cannot reach the login page; run the login visual config with auth enabled.",
  );

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
      // The deer mask is rasterized slightly differently while the page settles
      // in Chromium; tolerate only this small anti-aliasing fluctuation.
      maxDiffPixels: 500,
    });
  });
});
