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
  "requires a real isolated Gate 7 chat and archived citation",
);

test.describe("real Gate 7 evidence loading, error, and restricted states", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  test.beforeAll(requireRealE2EEnvironment);

  test("renders loading, unavailable, and restricted responses in the real chat", async ({
    page,
  }) => {
    await loginAsRealUser(page, "user@test.com");
    await page.goto(`/workspace/chats/${encodeURIComponent(threadId!)}`);
    await expect(page.locator("body")).toContainText(expectedSnippet!, {
      timeout: 120_000,
    });
    const citation = page
      .getByRole("button", { name: /open.*gate7-matrix-marker\.txt/i })
      .last();
    await expect(citation).toBeVisible();

    let releaseFirst!: () => void;
    const firstResponse = new Promise<void>((resolve) => {
      releaseFirst = resolve;
    });
    let calls = 0;
    await page.route(
      `**/api/runs/${encodeURIComponent(runId!)}/evidence**`,
      async (route) => {
        calls += 1;
        if (calls === 1) {
          await firstResponse;
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              receipts: [
                {
                  items: [
                    {
                      evidence_id: new URL(
                        route.request().url(),
                      ).searchParams.get("evidence_id"),
                      display_name: "gate7-matrix-marker.txt",
                      content: expectedSnippet,
                    },
                  ],
                },
              ],
            }),
          });
        } else if (calls === 2) {
          await route.fulfill({
            status: 503,
            contentType: "application/json",
            body: "{}",
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              receipts: [{ result_status: "access_restricted", items: [] }],
            }),
          });
        }
      },
    );

    await citation.click();
    const panel = page.getByTestId("evidence-panel");
    await expect(panel).toContainText("Loading evidence…");
    releaseFirst();
    await expect(panel).toContainText(expectedSnippet!);
    await page.keyboard.press("Escape");

    await citation.click();
    await expect(panel).toContainText(
      "This knowledge evidence is unavailable.",
    );
    await page.keyboard.press("Escape");

    await citation.click();
    await expect(panel).toContainText("This knowledge evidence is restricted.");
    expect(calls).toBe(3);
  });
});
