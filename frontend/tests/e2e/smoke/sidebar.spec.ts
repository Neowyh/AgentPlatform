import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

test.describe("@smoke Sidebar navigation", () => {
  test("sidebar keeps the pre-merge entries and appends Scheduled tasks", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    await expect(sidebar.locator("a[href='/workspace/chats']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      sidebar.locator("a[href='/workspace/scheduled-tasks']"),
    ).toBeVisible();
    // The merged Agents management has no sidebar entry of its own.
    await expect(sidebar.locator("a[href='/workspace/agents']")).toHaveCount(0);
  });
});
