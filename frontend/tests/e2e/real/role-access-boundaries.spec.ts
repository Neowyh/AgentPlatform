import { expect, test } from "@playwright/test";

import {
  assertRbacSeed,
  loginAsRealUser,
  requireRealE2EEnvironment,
} from "./real-e2e";

const emptyStorageState = { cookies: [], origins: [] };

test.describe("real RBAC boundaries", () => {
  test.use({ storageState: emptyStorageState });
  test.beforeAll(() => {
    requireRealE2EEnvironment();
    assertRbacSeed();
  });

  test("super admin can open the admin dashboard", async ({ page }) => {
    await loginAsRealUser(page, "super_admin@test.com");
    await page.goto("/workspace/admin");
    await expect(page.getByTestId("admin-dashboard")).toBeVisible();
    await expect(page.getByTestId("admin-stat-card").nth(0)).toBeVisible();
  });

  test("normal user is redirected away from admin dashboard", async ({
    page,
  }) => {
    await loginAsRealUser(page, "user@test.com");
    await page.goto("/workspace/admin");
    await expect(page).toHaveURL(/\/workspace(?:\/|$)(?!admin)/);
  });
});
