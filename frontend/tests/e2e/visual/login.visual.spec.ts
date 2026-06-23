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
    // When auth is disabled, /login redirects to /workspace. Wait for either form or redirect.
    await page.waitForTimeout(1500); // wait for potential redirect

    await expect(page).toHaveScreenshot("login-default.png", {
      fullPage: true,
    });
  });

  test("mobile viewport screenshot", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    await expect(page).toHaveScreenshot("login-mobile.png", {
      fullPage: true,
    });
  });

  test("dark mode screenshot", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    await expect(page).toHaveScreenshot("login-dark.png", {
      fullPage: true,
    });
  });
});
