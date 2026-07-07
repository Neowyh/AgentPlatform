import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

const MOCK_MCP_CONFIG = {
  mcp_servers: {
    "github-mcp": {
      enabled: true,
      type: "stdio" as const,
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-github"],
      env: { GITHUB_TOKEN: "ghp_xxx" },
      headers: {},
      description: "GitHub integration via MCP",
    },
  },
};

const MOCK_SKILLS = [
  {
    name: "deep-research",
    description: "Multi-angle web research methodology",
    category: "public" as const,
    license: "requires_internet",
    enabled: true,
  },
];

/** Helper: open the settings dialog via sidebar dropdown menu */
async function openSettings(page: Page) {
  const trigger = page
    .locator("button")
    .filter({ hasText: /settings and more|settings/i })
    .last();
  await trigger.click({ timeout: 10_000 });
  await page.getByRole("menuitem", { name: /settings/i }).click();
}

test.describe("Settings management", () => {
  test.describe("Settings dialog", () => {
    test("settings dialog opens via sidebar menu", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);

      // Dialog should be visible with title
      await expect(page.getByTestId("settings-dialog")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("settings dialog shows all section tabs", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);

      // All 7 settings tabs should be visible
      const tabs = [
        "settings-tab-account",
        "settings-tab-appearance",
        "settings-tab-notification",
        "settings-tab-memory",
        "settings-tab-tools",
        "settings-tab-skills",
        "settings-tab-about",
      ];
      for (const tabId of tabs) {
        await expect(page.getByTestId(tabId)).toBeVisible({ timeout: 15_000 });
      }
    });

    test("clicking a tab switches the settings page content", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);

      // Click on Account tab
      await page.getByTestId("settings-tab-account").click();

      // Should show account-related content (email, password fields)
      await expect(
        page.getByRole("button", { name: /sign out|退出/i }),
      ).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe("Account settings", () => {
    test("account page shows user email", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-account").click();

      // Should show the mocked user email
      await expect(page.getByText("e2e@test.local")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("account page shows password change form", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-account").click();

      // Should have 3 password inputs (current, new, confirm)
      const passwordInputs = page.locator(
        '[data-testid="settings-dialog-content"] input[type="password"]',
      );
      await expect(passwordInputs).toHaveCount(3, { timeout: 15_000 });
    });

    test("account page shows sign out button", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-account").click();

      await expect(
        page.getByRole("button", { name: /sign out|退出/i }),
      ).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe("Appearance settings", () => {
    test("appearance page shows theme options", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);

      // Appearance is the default tab, should be active
      // Should show 3 theme preview cards (system/light/dark)
      const themeCards = page.locator(
        '[data-testid="settings-dialog-content"] button[class*="rounded-lg"][class*="border"]',
      );
      await expect(themeCards.first()).toBeVisible({ timeout: 15_000 });
      await expect(themeCards).toHaveCount(3);
    });

    test("appearance page shows language selector", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);

      // Should show a Select trigger for language (inside settings-dialog-content)
      const languageSelect = page.locator(
        '[data-testid="settings-dialog-content"] [role="combobox"]',
      );
      await expect(languageSelect.first()).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe("Memory settings", () => {
    test("memory page loads with memory content", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-memory").click();

      // Should show memory-related content
      await expect(page.getByText(/memory|记忆/i).first()).toBeVisible({
        timeout: 15_000,
      });
    });

    test("memory page has export and import buttons", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-memory").click();

      // Should show export/import buttons
      await expect(
        page.getByRole("button", { name: /export|导出/i }),
      ).toBeVisible({ timeout: 15_000 });
      await expect(
        page.getByRole("button", { name: /import|导入/i }),
      ).toBeVisible();
    });

    test("memory page has clear all button", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-memory").click();

      await expect(
        page.getByRole("button", { name: /clear|清除/i }),
      ).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe("Tools (MCP) settings", () => {
    test("tools page loads with MCP server list", async ({ page }) => {
      mockLangGraphAPI(page, { mcpConfig: MOCK_MCP_CONFIG });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-tools").click();

      // Should show the MCP server name
      await expect(page.getByText("github-mcp")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("tools page shows add server button", async ({ page }) => {
      mockLangGraphAPI(page, { mcpConfig: MOCK_MCP_CONFIG });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-tools").click();

      await expect(page.getByRole("button", { name: /add|添加/i })).toBeVisible(
        { timeout: 15_000 },
      );
    });

    test("MCP server cards show enable toggle", async ({ page }) => {
      mockLangGraphAPI(page, { mcpConfig: MOCK_MCP_CONFIG });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-tools").click();

      // Toggle switches should be visible
      const switches = page.getByRole("switch");
      await expect(switches.first()).toBeVisible({ timeout: 15_000 });
    });

    test("empty MCP config shows empty state", async ({ page }) => {
      mockLangGraphAPI(page, { mcpConfig: { mcp_servers: {} } });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-tools").click();

      // Should show empty state message
      await expect(
        page.getByText(/no.*server|empty|没有/i).first(),
      ).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe("Skills settings", () => {
    test("skills page loads with skill tabs", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-skills").click();

      // Should show Public and Custom tabs
      await expect(page.getByRole("tab", { name: /public/i })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByRole("tab", { name: /custom/i })).toBeVisible();
    });

    test("skills page shows public skills", async ({ page }) => {
      mockLangGraphAPI(page, { skills: MOCK_SKILLS });
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-skills").click();

      await expect(page.getByText("deep-research")).toBeVisible({
        timeout: 15_000,
      });
    });
  });

  test.describe("Notification settings", () => {
    test("notification page loads", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-notification").click();

      // Should show notification-related content
      await expect(page.getByText(/notification|通知/i).first()).toBeVisible({
        timeout: 15_000,
      });
    });
  });

  test.describe("About settings", () => {
    test("about page loads with content", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await openSettings(page);
      await page.getByTestId("settings-tab-about").click();

      // About page renders markdown content, should have some visible text
      await expect(
        page.locator('[data-testid="settings-dialog-content"]'),
      ).toBeVisible({ timeout: 15_000 });
    });
  });
});
