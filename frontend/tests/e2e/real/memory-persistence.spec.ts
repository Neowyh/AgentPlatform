import { expect, test, type Page } from "@playwright/test";

import {
  expectMemoryStorageToContain,
  requireRealE2EEnvironment,
  runScopedName,
} from "./real-e2e";

const emptyStorageState = { cookies: [], origins: [] };

async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("super_admin@test.com");
  await page.getByLabel(/password/i).fill("super_admin@test.com");
  await page.getByRole("button", { name: /sign in|登录/i }).click();
  await expect
    .poll(async () =>
      (await page.context().cookies()).some(
        (cookie) => cookie.name === "access_token",
      ),
    )
    .toBe(true);
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/workspace/, { timeout: 15_000 });
}

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
    await loginAsAdmin(page);
    await openMemory(page);

    await page.getByRole("button", { name: /add fact|添加事实/i }).click();
    const editor = page.getByRole("dialog");
    await editor.getByRole("textbox").nth(0).fill(fact);
    await editor.getByRole("button", { name: /save|保存/i }).click();
    await expect(page.getByText(fact, { exact: true })).toBeVisible();
    expectMemoryStorageToContain(fact);

    await page.reload();
    await openMemory(page);
    await expect(page.getByText(fact, { exact: true })).toBeVisible();

    const factRow = page
      .getByText(fact, { exact: true })
      .locator(
        "xpath=ancestor::div[contains(@class, 'rounded-md') and .//button[@aria-label='Delete' or @aria-label='删除']]",
      );
    await factRow.getByRole("button", { name: /delete|删除/i }).click();
    const confirmation = page.getByRole("dialog");
    await confirmation.getByRole("button", { name: /delete|删除/i }).click();
    await expect(page.getByText(fact, { exact: true })).not.toBeVisible();
    expectMemoryStorageToContain(fact, false);
  });
});
