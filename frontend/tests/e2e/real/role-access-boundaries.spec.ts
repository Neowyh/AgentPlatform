import { expect, test } from "@playwright/test";

import {
  assertRbacSeed,
  hasRealE2EEnvironment,
  loginAsRealUser,
  requireRealE2EEnvironment,
} from "./real-e2e";

const emptyStorageState = { cookies: [], origins: [] };

test.skip(
  !hasRealE2EEnvironment(),
  "requires the Real E2E harness (GitHub Actions Real E2E lane), not the mock lane",
);

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
