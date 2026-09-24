import { expect, test } from "@playwright/test";

import {
  hasRealE2EEnvironment,
  loginAsRealUser,
  requireRealE2EEnvironment,
} from "./real-e2e";

const knowledgeBaseSlug = process.env.E2E_GATE8_KB_SLUG;
const expectedSnippet = process.env.E2E_GATE8_EXPECTED_SNIPPET;
const expectedEvidence = process.env.E2E_GATE8_EXPECTED_EVIDENCE;
const expectedComparison = process.env.E2E_GATE8_EXPECTED_COMPARISON;
const expectedGateFeedback = process.env.E2E_GATE8_EXPECTED_GATE_FEEDBACK;
const hasGate8Environment =
  hasRealE2EEnvironment() &&
  Boolean(
    knowledgeBaseSlug &&
    expectedSnippet &&
    expectedEvidence &&
    expectedComparison &&
    expectedGateFeedback,
  );

test.skip(
  !hasGate8Environment,
  "requires isolated Gate 8 data and evidence/comparison/gate markers",
);

test.describe("real Knowledge Center Gate 8", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  test.beforeAll(requireRealE2EEnvironment);

  test("reviews retrieval evidence, comparison, and publish-gate feedback", async ({
    page,
  }) => {
    await loginAsRealUser(page, "user@test.com");
    await page.goto("/workspace/library");
    await page.getByRole("tab", { name: /Knowledge Bases|知识库/i }).click();
    await page.getByRole("button", { name: knowledgeBaseSlug! }).click();

    await page.getByRole("tab", { name: /Retrieval|检索/i }).click();
    const matchingRecord = page
      .getByRole("listitem")
      .filter({ hasText: expectedSnippet! })
      .first();
    await matchingRecord
      .getByRole("button", { name: /View record|查看记录/i })
      .click();
    await expect(page.locator("body")).toContainText(expectedSnippet!);
    await expect(page.locator("body")).toContainText(expectedEvidence!);

    const evaluationTab = page.getByRole("tab", { name: /Evaluation|评估/i });
    await evaluationTab.focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("heading", { name: /Publish evaluation gate/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /A\/B comparison/i }),
    ).toBeVisible();
    await page.getByLabel("Side A revision").selectOption({ index: 1 });
    await page.getByLabel("Side B revision").selectOption({ index: 1 });
    await page.getByRole("button", { name: "Compare" }).click();
    await expect(page.locator("body")).toContainText(expectedComparison!);
    await expect(page.locator("body")).toContainText(expectedGateFeedback!);

    const firstControl = page.locator("button, input, select").first();
    await firstControl.focus();
    await expect(firstControl).toBeFocused();
  });
});
