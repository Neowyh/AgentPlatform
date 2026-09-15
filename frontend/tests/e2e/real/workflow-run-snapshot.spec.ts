import { expect, test } from "@playwright/test";

import {
  hasRealE2EEnvironment,
  loginAsRealUser,
  requireRealE2EEnvironment,
  seedWorkflowResourceId,
  seedWorkflowRunId,
} from "./real-e2e";

test.skip(
  !hasRealE2EEnvironment(),
  "requires the Real E2E harness (GitHub Actions Real E2E lane), not the mock lane",
);

test.describe("real workflow run snapshot", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  test.beforeAll(requireRealE2EEnvironment);

  test("renders the frozen knowledge revision from the production run API", async ({
    page,
  }) => {
    const workflowResourceId = seedWorkflowResourceId();
    const runId = seedWorkflowRunId(workflowResourceId);
    await loginAsRealUser(page, "user@test.com");
    await page.goto(
      `/workspace/workflows/${encodeURIComponent(workflowResourceId)}/runs/${encodeURIComponent(runId)}`,
    );
    await expect(page.getByTestId("knowledge-snapshot")).toContainText(
      "KB gate-kb · v2 · manifest abcdef123456",
    );
  });
});
