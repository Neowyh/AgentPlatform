import { expect, test } from "@playwright/test";

import {
  hasRealE2EEnvironment,
  loginAsRealUser,
  requireRealE2EEnvironment,
} from "./real-e2e";

const threadId = process.env.E2E_GATE7_THREAD_ID;
const runId = process.env.E2E_GATE7_RUN_ID;
const expectedSnippet = process.env.E2E_GATE7_EXPECTED_SNIPPET;
const hasGate7Environment =
  hasRealE2EEnvironment() && Boolean(threadId && runId && expectedSnippet);

test.skip(
  !hasGate7Environment,
  "requires a real isolated Gate 7 chat with E2E_GATE7_THREAD_ID, E2E_GATE7_RUN_ID, and E2E_GATE7_EXPECTED_SNIPPET",
);

test.describe("real retrieval evidence Gate 7", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  test.beforeAll(requireRealE2EEnvironment);

  test("opens the archived item delivered by the real run", async ({
    page,
  }) => {
    await loginAsRealUser(page, "user@test.com");
    await page.goto(`/workspace/chats/${encodeURIComponent(threadId!)}`);
    await expect(page.locator("body")).toContainText(expectedSnippet!, {
      timeout: 120_000,
    });

    const evidenceLink = page.getByRole("button", { name: /open/i }).first();
    await expect(evidenceLink).toBeVisible();
    await evidenceLink.focus();
    const expectedEvidenceUrl = new URL(
      `/api/runs/${encodeURIComponent(runId!)}/evidence`,
      process.env.IDEER_INTERNAL_GATEWAY_BASE_URL,
    ).toString();
    const evidenceRequest = page.waitForRequest(
      (request) => request.url() === expectedEvidenceUrl,
    );
    await evidenceLink.press("Enter");
    await evidenceRequest;
    await expect(page.getByTestId("evidence-panel")).toBeVisible();
    await expect(page.getByTestId("evidence-panel")).toContainText(
      expectedSnippet!,
    );

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("evidence-panel")).not.toBeVisible();
    await expect(evidenceLink).toBeFocused();
  });
});
