import { expect, test, type Page } from "@playwright/test";

import {
  assertRbacSeed,
  queryDatabase,
  requireRealE2EEnvironment,
  runScopedName,
  seedAgentName,
} from "./real-e2e";

const emptyStorageState = { cookies: [], origins: [] };

async function loginAs(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(email);
  await page.getByRole("button", { name: /sign in|登录/i }).click();
  await expect(page).toHaveURL(/\/workspace/, { timeout: 15_000 });
}

test.describe("real RBAC boundaries", () => {
  test.use({ storageState: emptyStorageState });
  test.beforeAll(() => {
    requireRealE2EEnvironment();
    assertRbacSeed();
  });

  test("super admin and department admin can open the admin dashboard", async ({
    page,
  }) => {
    await loginAs(page, "super_admin@test.com");
    await page.goto("/workspace/admin");
    await expect(page.getByTestId("admin-dashboard")).toBeVisible();
    await expect(page.getByTestId("admin-stat-card").nth(0)).toBeVisible();

    await page.context().clearCookies();
    await loginAs(page, "department_admin@test.com");
    await page.goto("/workspace/admin");
    await expect(page.getByTestId("admin-dashboard")).toBeVisible();
  });

  test("normal user is redirected away from admin dashboard", async ({
    page,
  }) => {
    await loginAs(page, "user@test.com");
    await page.goto("/workspace/admin");
    await expect(page).toHaveURL(/\/workspace(?:\/|$)(?!admin)/);
  });

  test("viewer can see its deterministically seeded agent", async ({
    page,
  }) => {
    const agentName = seedAgentName("viewer-agent");
    await loginAs(page, "viewer@test.com");
    await page.goto("/workspace/agents");
    const agentCard = page
      .getByTestId("agent-card")
      .filter({ has: page.getByText(agentName, { exact: true }) });
    await expect(agentCard).toBeVisible();
  });

  test("department admin cannot review a cross-department application", async ({
    page,
  }) => {
    const agentName = seedAgentName("cross-department-agent");
    const reason = runScopedName("cross-department-pending");
    const application = queryDatabase(
      "SELECT id, version, status FROM visibility_applications WHERE resource_type = 'agent' AND resource_id = ? AND reason = ?",
      [agentName, reason],
    );
    if (application?.[2] !== "pending") {
      throw new Error(
        `Missing pending cross-department application: ${JSON.stringify(application)}`,
      );
    }

    await loginAs(page, "department_admin@test.com");
    const response = await page.evaluate(
      async ({ id, version }) => {
        const result = await fetch(`/api/visibility-applications/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "approved",
            comment: "E2E denied",
            version,
          }),
        });
        return { status: result.status, body: await result.text() };
      },
      { id: String(application[0]), version: Number(application[1]) },
    );
    expect(response.status, response.body).toBe(403);
    const unchanged = queryDatabase(
      "SELECT status, reviewed_by FROM visibility_applications WHERE id = ?",
      [String(application[0])],
    );
    expect(unchanged).toEqual(["pending", null]);
  });
});
