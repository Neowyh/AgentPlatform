import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

test.describe("@smoke Landing page", () => {
  test("renders the header and hero section", async ({ page }) => {
    await page.goto("/");

    // Brand link in the header banner
    await expect(
      page.getByRole("banner").getByRole("link", { name: "iDeer" }),
    ).toBeVisible();

    // Hero call-to-action link
    await expect(
      page.getByRole("link", { name: /start creating|开始创造/i }),
    ).toBeVisible();
  });

  test("Get Started link navigates to workspace", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/");

    const startCreating = page.getByRole("link", {
      name: /start creating|开始创造/i,
    });
    await startCreating.click();

    // Auth is disabled in the mock lane, so the login hop bounces straight
    // into the workspace.
    await page.waitForURL(/\/workspace/, { timeout: 15_000 });
  });
});
