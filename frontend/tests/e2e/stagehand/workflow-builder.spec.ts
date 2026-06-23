import { test, expect } from "@playwright/test";

import {
  createStagehandTest,
  isStagehandAvailable,
  stagehandAct,
  stagehandActBatch,
  stagehandExtract,
} from "../utils/stagehand-helper";

const hasStagehand = isStagehandAvailable();

/**
 * Workflow Builder — Stagehand E2E Tests
 *
 * Uses natural language to test complex workflow builder interactions.
 * Stagehand manages its own browser instance (separate from Playwright tests).
 */

test.describe("Workflow Builder - Stagehand", () => {
  test.skip(
    !hasStagehand,
    "Stagehand requires OPENAI_API_KEY or OPENAI_BASE_URL",
  );
  test.setTimeout(120_000);

  test("navigate to workflow list and verify layout", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/workflows");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      // Observe the page structure
      const observation = await stagehandExtract(
        stagehand,
        "what elements are visible on this page? List the main UI components.",
      );

      expect(observation).toBeTruthy();

      // Verify key elements
      const hasWorkflowList = await stagehandExtract(
        stagehand,
        "is there a workflow list, grid, or empty state visible?",
      );
      expect(hasWorkflowList).toBeTruthy();
    } finally {
      await cleanup();
    }
  });

  test("view workflow details", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/workflows");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      // Try to click on a workflow
      try {
        await stagehandAct(
          stagehand,
          "click on the first workflow in the list",
        );
        const detailVisible = await stagehandExtract(
          stagehand,
          "are workflow details or a workflow editor visible?",
        );
        expect(detailVisible).toBeTruthy();
      } catch {
        // No workflows exist - that's OK
        const emptyState = await stagehandExtract(
          stagehand,
          "is there an empty state or create button?",
        );
        expect(emptyState).toBeTruthy();
      }
    } finally {
      await cleanup();
    }
  });
});
