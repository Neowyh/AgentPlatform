import { expect, test } from "@playwright/test";

import {
  hasRealE2EEnvironment,
  loginAsRealUser,
  requireRealE2EEnvironment,
} from "./real-e2e";

const knowledgeBaseSlug = process.env.E2E_GATE8_KB_SLUG;
const expectedSnippet = process.env.E2E_GATE8_EXPECTED_SNIPPET;
const hasGate8Environment =
  hasRealE2EEnvironment() && Boolean(knowledgeBaseSlug && expectedSnippet);

test.skip(
  !hasGate8Environment,
  "requires an isolated Gate 8 KB with E2E_GATE8_KB_SLUG and E2E_GATE8_EXPECTED_SNIPPET",
);

test.describe("real Knowledge Center Gate 8", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  test.beforeAll(requireRealE2EEnvironment);

  test("reviews retrieval evidence, comparison, and publish-gate feedback", async ({
    page,
  }) => {
    await loginAsRealUser(page, "user@test.com");
    await page.goto("/workspace/library");
    await page.getByRole("button", { name: knowledgeBaseSlug! }).click();

    await page.getByRole("tab", { name: /Retrieval|检索/i }).click();
    await expect(page.locator("body")).toContainText(expectedSnippet!);

    const evaluationTab = page.getByRole("tab", { name: /Evaluation|评估/i });
    await evaluationTab.focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("heading", { name: /Publish evaluation gate/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /A\/B comparison/i }),
    ).toBeVisible();

    const firstControl = page.locator("button, input, select").first();
    await firstControl.focus();
    await expect(firstControl).toBeFocused();
  });
});
