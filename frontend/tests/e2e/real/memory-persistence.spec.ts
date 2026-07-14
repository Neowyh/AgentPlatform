import { expect, test, type Page } from "@playwright/test";

import {
  expectMemoryStorageToContain,
  loginAsRealUser,
  requireRealE2EEnvironment,
  runScopedName,
} from "./real-e2e";

const emptyStorageState = { cookies: [], origins: [] };

async function openMemory(page: Page) {
  await page.getByTestId("nav-menu-trigger").click();
  await page.getByTestId("settings-menu-item").click();
  await expect(page.getByTestId("settings-dialog-content")).toBeVisible();
  await page.getByTestId("settings-tab-memory").click();
}

test.describe("real memory persistence", () => {
  test.use({ storageState: emptyStorageState });
  test.beforeAll(requireRealE2EEnvironment);

  test("creates, reloads, and deletes a fact in isolated filesystem storage", async ({
    page,
  }) => {
    const fact = runScopedName("memory-fact");
    await loginAsRealUser(page, "super_admin@test.com");
    await openMemory(page);

    await page.getByRole("button", { name: /add fact|添加事实/i }).click();
    const editor = page.getByRole("dialog");
    await editor.getByRole("textbox").nth(0).fill(fact);
    await editor.getByRole("button", { name: /save|保存/i }).click();
    await expect(page.getByText(fact)).toBeVisible();
    await expectMemoryStorageToContain(fact);

    await page.reload();
    await openMemory(page);
    await expect(page.getByText(fact)).toBeVisible();

    const factRow = page
      .getByText(fact)
      .locator(
        "xpath=ancestor::div[contains(@class, 'rounded-md') and (.//button[@aria-label='Delete' or @aria-label='删除'] or .//button[@title='Delete' or @title='删除'])]",
      );
    await factRow.getByRole("button", { name: /delete|删除/i }).click();
    const confirmation = page.getByRole("dialog");
    await confirmation.getByRole("button", { name: /delete|删除/i }).click();
    await expect(page.getByText(fact)).not.toBeVisible();
    await expectMemoryStorageToContain(fact, false);
  });
});
