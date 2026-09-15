import { expect, test } from "@playwright/test";

import {
  hasRealModelEnvironment,
  loginAsRealUser,
  requireRealE2EEnvironment,
  seedRealModelManifestHash,
  seedRealModelWorkflowResourceId,
} from "./real-e2e";

test.skip(
  !hasRealModelEnvironment(),
  "requires real model and RAGFlow credentials (REAL_E2E_REAL_MODEL=1)",
);

test.describe("real browser model workflow", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  test.beforeAll(requireRealE2EEnvironment);

  test("triggers a real model run and renders its frozen knowledge snapshot", async ({
    page,
  }) => {
    const workflowId = seedRealModelWorkflowResourceId();
    const manifestHash = seedRealModelManifestHash();
    await loginAsRealUser(page, "user@test.com");
    await page.goto(`/workspace/workflows/${encodeURIComponent(workflowId)}`);

    await page.getByRole("button", { name: /^run$/i }).click();
    await page.locator("#run-model").click();
    await page
      .getByRole("option", { name: process.env.REAL_E2E_MODEL_NAME! })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: /^run$/i })
      .click();

    await expect(page).toHaveURL(/\/runs\//, { timeout: 60_000 });
    await expect(page.getByTestId("knowledge-snapshot")).toContainText(
      `v1 · manifest ${manifestHash.slice(0, 12)}`,
      { timeout: 120_000 },
    );
    await expect(page.locator("body")).toContainText(/completed|完成/i, {
      timeout: 180_000,
    });
  });
});
