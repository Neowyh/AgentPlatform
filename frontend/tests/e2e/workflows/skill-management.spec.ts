import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const MOCK_SKILLS = [
  {
    name: "deep-research",
    description: "Multi-angle web research methodology",
    category: "public" as const,
    license: "requires_internet",
    enabled: true,
  },
  {
    name: "my-custom-skill",
    description: "A custom skill created by the user",
    category: "custom" as const,
    license: null,
    enabled: false,
  },
];

/** Helper: open the settings dialog via sidebar dropdown menu */
async function openSettings(page: Page) {
  // Click the sidebar footer dropdown trigger ("Settings and more")
  const trigger = page
    .locator("button")
    .filter({ hasText: /settings and more|settings/i })
    .last();
  await trigger.click({ timeout: 10_000 });

  // Click the "Settings" menu item in the dropdown
  await page.getByRole("menuitem", { name: /settings/i }).click();
}

test.describe("Skill management", () => {
  test.describe("Settings Page", () => {
    test("skills settings page loads with tabs", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);

      // Navigate to Skills section
      await page.getByText(/^skills$/i).click();

      // Should show Public and Custom tabs
      await expect(page.getByRole("tab", { name: /public/i })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByRole("tab", { name: /custom/i })).toBeVisible();
    });

    test("public tab shows public skills", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Public tab should be active by default, showing deep-research
      await expect(page.getByText("deep-research")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("custom tab shows custom skills", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Switch to Custom tab
      await page.getByRole("tab", { name: /custom/i }).click();

      // Should show custom skill
      await expect(page.getByText("my-custom-skill")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("skills show category and visibility application action", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Should show category badge
      await expect(page.getByText("public").first()).toBeVisible({
        timeout: 15_000,
      });

      await expect(page.getByRole("button", { name: /apply visibility/i }).first()).toBeVisible();
    });
  });
});
