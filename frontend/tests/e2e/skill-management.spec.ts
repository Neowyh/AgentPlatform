import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

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

    test("skills show category and license badges", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Should show category badge
      await expect(page.getByText("public").first()).toBeVisible({
        timeout: 15_000,
      });

      // Should show "Requires Internet" badge for skills with that license
      await expect(page.getByText(/requires internet/i)).toBeVisible();
    });

    test("enable/disable toggle is visible", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Toggle switches should be visible
      const switches = page.getByRole("switch");
      await expect(switches.first()).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe("Skill Editor", () => {
    test("edit button opens skill editor dialog", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Click edit button (icon-only with title="Edit skill")
      const editBtn = page.locator('button[title="Edit skill"]').first();
      await editBtn.click();

      // Should open editor dialog with CodeMirror
      await expect(page.locator(".cm-editor")).toBeVisible({
        timeout: 15_000,
      });
    });
  });

  test.describe("Test Skill", () => {
    test("test button opens test dialog", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Click test button (icon-only with title="Test skill")
      const testBtn = page.locator('button[title="Test skill"]').first();
      await testBtn.click();

      // Should open test dialog with instructions
      await expect(page.getByText(/new chat|start new/i).first()).toBeVisible({
        timeout: 15_000,
      });
    });
  });

  test.describe("Create Skill", () => {
    test("create button navigates to skill creation chat", async ({ page }) => {
      mockLangGraphAPI(page, { skills: [] });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByText(/^skills$/i).click();

      // Click create button (may match multiple, use first)
      const createBtn = page
        .getByRole("button", {
          name: /create.*skill|create your first/i,
        })
        .first();
      await createBtn.click();

      // Should navigate to chat with mode=skill
      await expect(page).toHaveURL(/mode=skill/, { timeout: 10_000 });
    });
  });
});
