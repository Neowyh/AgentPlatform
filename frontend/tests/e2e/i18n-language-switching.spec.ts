import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Open the Settings dialog via the sidebar dropdown menu. */
async function openSettings(page: Page) {
  const trigger = page
    .locator("button")
    .filter({ hasText: /settings and more|设置和更多/i })
    .last();
  await trigger.click({ timeout: 10_000 });
  await page.getByRole("menuitem", { name: /settings|设置/i }).click();
  await expect(page.getByTestId("settings-dialog-content")).toBeVisible({
    timeout: 15_000,
  });
}

/** Wait for the appearance settings page to render the language selector. */
async function waitForLanguageSelector(page: Page) {
  const selector = page.locator(
    '[data-testid="settings-dialog-content"] [role="combobox"]',
  );
  await expect(selector.first()).toBeVisible({ timeout: 15_000 });
  return selector.first();
}

/** Set the locale cookie before navigating so the app boots with that locale. */
async function setLocaleCookie(page: Page, locale: string) {
  await page.context().addCookies([
    {
      name: "locale",
      value: locale,
      domain: "localhost",
      path: "/",
    },
  ]);
}

/** Read the locale cookie value (returns null if absent). */
async function getLocaleCookie(page: Page): Promise<string | null> {
  const cookies = await page.evaluate(() => document.cookie);
  const match = /(?:^|;\s*)locale=([^;]*)/.exec(cookies);
  return match ? match[1] : null;
}

/** Click the language combobox and pick an option by its label text. */
async function selectLanguage(page: Page, label: string) {
  const selector = await waitForLanguageSelector(page);
  await selector.click();
  await page.getByRole("option", { name: label }).click();
}

// ---------------------------------------------------------------------------
// Test data — strings that differ between locales
// ---------------------------------------------------------------------------

const LOCALE_TEXT = {
  "en-US": {
    settingsLabel: "Settings",
    languageTitle: "Language",
    sidebarNewChat: "New chat",
    inputPlaceholder: "How can I assist you today?",
  },
  "zh-CN": {
    settingsLabel: "设置",
    languageTitle: "语言",
    sidebarNewChat: "新对话",
    inputPlaceholder: "今天我能为你做些什么？",
  },
} as const;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("i18n — Language switching", () => {
  test.beforeEach(async ({ page }) => {
    // Clear any leftover locale cookie from previous tests or storageState.
    await page.context().addCookies([
      {
        name: "locale",
        value: "",
        domain: "localhost",
        path: "/",
        expires: 1,
      },
    ]);
    // Disable CSS animations to prevent flaky Select dropdown behavior.
    await page.addInitScript(() => {
      const style = document.createElement("style");
      style.textContent =
        "*, *::before, *::after { animation-duration: 0s !important; transition-duration: 0s !important; }";
      document.addEventListener("DOMContentLoaded", () => {
        document.head?.appendChild(style);
      });
    });
  });

  test.describe("Language selector UI", () => {
    test("language selector is visible in Appearance settings", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      const selector = await waitForLanguageSelector(page);
      await expect(selector).toContainText(/English|中文/);
    });

    test("language selector shows both language options when opened", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      const selector = await waitForLanguageSelector(page);
      await selector.click();

      await expect(page.getByRole("option", { name: "English" })).toBeVisible();
      await expect(page.getByRole("option", { name: "中文" })).toBeVisible();
    });

    test("language selector reflects the currently selected language", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      await selectLanguage(page, "中文");

      // Close and reopen settings, verify combobox shows "中文"
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("settings-dialog-content")).not.toBeVisible(
        {
          timeout: 5_000,
        },
      );

      await openSettings(page);
      const selector = await waitForLanguageSelector(page);
      await expect(selector).toContainText("中文");
    });
  });

  test.describe("Translation updates", () => {
    test("switching to Chinese updates settings dialog text", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      // Before switching — English text should be present.
      await expect(
        page.getByText(LOCALE_TEXT["en-US"].languageTitle, { exact: true }),
      ).toBeVisible();

      // Switch to Chinese.
      await selectLanguage(page, "中文");

      // Settings title should now be in Chinese.
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].settingsLabel, { exact: true }),
      ).toBeVisible({ timeout: 5_000 });

      // Language section title should update.
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].languageTitle, { exact: true }),
      ).toBeVisible({ timeout: 5_000 });
    });

    test("switching to Chinese updates sidebar new-chat label", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      await selectLanguage(page, "中文");

      // Close settings dialog.
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("settings-dialog-content")).not.toBeVisible(
        {
          timeout: 5_000,
        },
      );

      // Sidebar "New chat" should now be "新对话".
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].sidebarNewChat, { exact: true }),
      ).toBeVisible({ timeout: 5_000 });
    });

    test("switching to Chinese updates chat input placeholder", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      await selectLanguage(page, "中文");

      // Close settings dialog.
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("settings-dialog-content")).not.toBeVisible(
        {
          timeout: 5_000,
        },
      );

      // Chat input placeholder should now be in Chinese.
      await expect(
        page.getByPlaceholder(LOCALE_TEXT["zh-CN"].inputPlaceholder),
      ).toBeVisible({ timeout: 5_000 });
    });
  });

  test.describe("Bidirectional switching", () => {
    test("switching to Chinese then back to English restores English text", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      // Switch to Chinese.
      await selectLanguage(page, "中文");
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].languageTitle, { exact: true }),
      ).toBeVisible({ timeout: 5_000 });

      // Switch back to English.
      await selectLanguage(page, "English");
      await expect(
        page.getByText(LOCALE_TEXT["en-US"].languageTitle, { exact: true }),
      ).toBeVisible({ timeout: 5_000 });
    });
  });

  test.describe("Persistence — locale cookie", () => {
    test("locale cookie is set to zh-CN when switching to Chinese", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      await selectLanguage(page, "中文");

      const cookie = await getLocaleCookie(page);
      expect(cookie).toBe("zh-CN");
    });

    test("locale cookie is set to en-US when switching to English", async ({
      page,
    }) => {
      // Start from Chinese so we can switch to English
      await setLocaleCookie(page, "zh-CN");
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      await selectLanguage(page, "English");

      const cookie = await getLocaleCookie(page);
      expect(cookie).toBe("en-US");
    });

    test("language preference persists across page reload", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      await selectLanguage(page, "中文");
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].languageTitle, { exact: true }),
      ).toBeVisible({ timeout: 5_000 });

      // Reload — the client-side useEffect reads the cookie and restores Chinese.
      await page.reload();

      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].sidebarNewChat, { exact: true }),
      ).toBeVisible({ timeout: 15_000 });
    });

    test("pre-set locale cookie is respected on initial load", async ({
      page,
    }) => {
      await setLocaleCookie(page, "zh-CN");
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      // Server renders with default locale; client-side useEffect reads the
      // cookie and switches to Chinese.  toBeVisible polls until the effect
      // has run.
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].sidebarNewChat, { exact: true }),
      ).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe("Edge cases", () => {
    test("no locale cookie falls back to default English", async ({ page }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await expect(
        page.getByText(LOCALE_TEXT["en-US"].sidebarNewChat, { exact: true }),
      ).toBeVisible({ timeout: 15_000 });
    });

    test("invalid locale cookie falls back gracefully to default English", async ({
      page,
    }) => {
      await setLocaleCookie(page, "fr-FR");
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      // normalizeLocale("fr-FR") returns "en-US" — wait for English text.
      await expect(
        page.getByText(LOCALE_TEXT["en-US"].sidebarNewChat, { exact: true }),
      ).toBeVisible({ timeout: 15_000 });
    });

    test("locale cookie zh is normalized to zh-CN", async ({ page }) => {
      await setLocaleCookie(page, "zh");
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      // The useEffect normalizes "zh" -> "zh-CN" when the short code does
      // not match SUPPORTED_LOCALES but starts with "zh".
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].sidebarNewChat, { exact: true }),
      ).toBeVisible({ timeout: 15_000 });

      // Cookie should also be updated to the normalized value.
      const cookie = await getLocaleCookie(page);
      expect(cookie).toBe("zh-CN");
    });

    test("navigator.language is used when no cookie is set", async ({
      page,
    }) => {
      // Override navigator.language before the page loads so the useEffect
      // detects "zh-CN" in the no-cookie path.
      await page.addInitScript(() => {
        Object.defineProperty(Navigator.prototype, "language", {
          get: () => "zh-CN",
          configurable: true,
        });
      });

      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].sidebarNewChat, { exact: true }),
      ).toBeVisible({ timeout: 15_000 });
    });

    test("switching to already-active locale is a no-op", async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          errors.push(msg.text());
        }
      });

      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      // Clear errors accumulated during page load / setup.
      errors.length = 0;

      // Currently in English; select English again.
      await selectLanguage(page, "English");

      // Should not produce any console errors.
      await expect.poll(() => errors.length, { timeout: 5_000 }).toBe(0);

      // Cookie should still be "en-US".
      const cookie = await getLocaleCookie(page);
      expect(cookie).toBe("en-US");
    });
  });

  test.describe("URL behavior", () => {
    test("default English locale does not add /en prefix to URL", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await expect(page).toHaveURL(/\/workspace\/chats\/new/);
      expect(page.url()).not.toContain("/en/workspace");
    });

    test("Chinese locale does not add /zh prefix to URL", async ({ page }) => {
      await setLocaleCookie(page, "zh-CN");
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");

      await expect(page).toHaveURL(/\/workspace\/chats\/new/);
      expect(page.url()).not.toContain("/zh/workspace");
    });
  });

  test.describe("Repeated switching", () => {
    test("sequential repeated language switches work correctly", async ({
      page,
    }) => {
      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      // Perform 6 rapid switches: en -> zh -> en -> zh -> en -> zh
      for (let i = 0; i < 3; i++) {
        await selectLanguage(page, "中文");
        await selectLanguage(page, "English");
      }
      await selectLanguage(page, "中文");

      // Final state should be Chinese.
      await expect(
        page.getByText(LOCALE_TEXT["zh-CN"].languageTitle, { exact: true }),
      ).toBeVisible({ timeout: 5_000 });

      const cookie = await getLocaleCookie(page);
      expect(cookie).toBe("zh-CN");
    });

    test("rapid switches do not cause React state errors", async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          errors.push(msg.text());
        }
      });

      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      // Clear errors accumulated during page load / setup.
      errors.length = 0;

      await selectLanguage(page, "中文");
      await selectLanguage(page, "English");
      await selectLanguage(page, "中文");
      await selectLanguage(page, "English");

      const reactErrors = errors.filter(
        (e) =>
          e.includes("Cannot update a component") ||
          e.includes("setState") ||
          e.includes("unmounted component"),
      );
      await expect.poll(() => reactErrors.length, { timeout: 5_000 }).toBe(0);
    });
  });

  test.describe("Console errors", () => {
    test("single language switch does not produce console errors", async ({
      page,
    }) => {
      const errors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          errors.push(msg.text());
        }
      });

      mockLangGraphAPI(page);
      await page.goto("/workspace/chats/new");
      await openSettings(page);

      // Clear errors accumulated during page load / setup.
      errors.length = 0;

      await selectLanguage(page, "中文");

      await expect.poll(() => errors.length, { timeout: 5_000 }).toBe(0);
    });
  });
});
