import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

test.describe("Core workspace — visual regression", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test("agent gallery desktop screenshot", async ({ page }) => {
    await page.goto("/workspace/agents");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot("agent-gallery.png", {
      fullPage: true,
    });
  });

  test("workflow editor desktop screenshot", async ({ page }) => {
    await page.goto("/workspace/workflows/new");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot("workflow-editor.png", {
      fullPage: true,
    });
  });

  test("admin dashboard desktop screenshot", async ({ page }) => {
    await page.goto("/workspace/admin");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot("admin-dashboard.png", {
      fullPage: true,
    });
  });
});
