import { expect, test, type Page } from "@playwright/test";

import {
  expectVisibilityState,
  loginAsRealUser,
  requireRealE2EEnvironment,
  runScopedName,
  seedAgentName,
} from "./real-e2e";

const emptyStorageState = { cookies: [], origins: [] };

async function submitApplication(
  page: Page,
  agentName: string,
  reason: string,
  targetVisibility: "department" | "public" = "department",
) {
  await page.goto(
    `/workspace/capabilities/experts/${encodeURIComponent(agentName)}`,
  );
  await page
    .getByRole("button", { name: /apply.*visibility|申请.*可见性/i })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox").click();
  await dialog.getByRole("option", { name: targetVisibility }).click();
  await dialog.getByLabel(/reason|理由/i).fill(reason);
  await dialog.getByRole("button", { name: /submit|提交/i }).click();
  await expect(
    page.getByText(/application submitted|申请已提交/i),
  ).toBeVisible();
}

async function reviewApplication(
  page: Page,
  reason: string,
  action: "approved" | "rejected",
) {
  await page.goto("/workspace/admin/visibility-applications");
  await expect(page.getByTestId("visibility-applications-page")).toBeVisible();
  const application = page
    .locator('[data-slot="card"]')
    .filter({ hasText: reason });
  await expect(application).toBeVisible();
  await application.getByRole("button", { name: "审核" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: action === "approved" ? "通过" : "驳回" })
    .click();
  await page
    .getByRole("button", { name: action === "approved" ? "已批准" : "已拒绝" })
    .click();
  const reviewedApplication = page
    .locator('[data-slot="card"]')
    .filter({ hasText: reason });
  await expect(reviewedApplication).toBeVisible();
  await expect(
    reviewedApplication.getByText(action === "approved" ? "已批准" : "已拒绝", {
      exact: true,
    }),
  ).toBeVisible();
}

test.describe.serial("real visibility applications", () => {
  test.use({ storageState: emptyStorageState });
  test.beforeAll(requireRealE2EEnvironment);

  for (const [suffix, action, visibility] of [
    ["approve-agent", "approved", "department"],
    ["reject-agent", "rejected", "private"],
  ] as const) {
    test(`user ${action === "approved" ? "approves" : "rejects"} ${suffix}`, async ({
      page,
    }) => {
      const agentName = seedAgentName(suffix);
      const reason = runScopedName(`${action}-reason`);
      await loginAsRealUser(page, "user@test.com");
      await submitApplication(page, agentName, reason);

      await page.context().clearCookies();
      await loginAsRealUser(page, "super_admin@test.com");
      await reviewApplication(page, reason, action);
      expectVisibilityState({ agentName, reason, status: action, visibility });
    });
  }
});
