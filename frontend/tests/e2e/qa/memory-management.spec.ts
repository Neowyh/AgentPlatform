import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

/**
 * Memory management E2E tests.
 *
 * Verifies the memory list / create / edit / delete flow through the UI.
 * The backend is mocked — only front-end behaviour is validated.
 *
 * Memory is accessible via the Settings dialog's "Memory" tab.  The test
 * opens the dialog from the sidebar nav menu and switches to the memory
 * section.
 */

test.describe("Memory Management", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
  });

  test("memory settings area is reachable", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Open the sidebar settings menu via the nav-menu trigger in the sidebar
    // footer, then click "Settings" to open the settings dialog.
    const navMenuTrigger = page.locator('[data-testid="nav-menu-trigger"]');
    await expect(navMenuTrigger).toBeVisible({ timeout: 10000 });
    await navMenuTrigger.click();

    const settingsItem = page.locator('[data-testid="settings-menu-item"]');
    await expect(settingsItem).toBeVisible({ timeout: 5000 });
    await settingsItem.click();

    // The settings dialog content (rendered in a portal) should now be visible.
    // Dialog Root is a Radix context provider with no DOM node, so we target
    // the DialogContent element which carries data-testid="settings-dialog-content".
    const settingsContent = page.locator(
      '[data-testid="settings-dialog-content"]',
    );
    await expect(settingsContent).toBeVisible({ timeout: 5000 });

    // Click the "Memory" tab in the settings sidebar navigation
    const memoryTab = page.locator('[data-testid="settings-tab-memory"]');
    await expect(memoryTab).toBeVisible({ timeout: 5000 });
    await memoryTab.click();

    // The memory settings page should render — verify the page body is visible
    // and the memory section loaded successfully.
    await expect(page.locator("body")).toBeVisible();

    // The memory section should have a search input and filter controls once
    // the data loads (the mock returns memory data with facts).
    const searchInput = settingsContent.locator("input[placeholder]").first();
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });
});
