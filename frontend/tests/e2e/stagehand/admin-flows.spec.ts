import { test, expect } from "@playwright/test";

import {
  createStagehandTest,
  isStagehandAvailable,
  stagehandExtract,
} from "../utils/stagehand-helper";

const hasStagehand = isStagehandAvailable();

/**
 * Admin Flows — Stagehand E2E Tests
 *
 * Tests admin panel interactions using natural language.
 */

test.describe("Admin Panel - Stagehand", () => {
  test.skip(
    !hasStagehand,
    "Stagehand requires OPENAI_API_KEY or OPENAI_BASE_URL",
  );
  test.setTimeout(120_000); // Stagehand needs time for Chrome launch + LLM API calls

  test("navigate to admin panel", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/admin");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      const content = await stagehandExtract(
        stagehand,
        "what is shown on this admin page? Describe the main sections.",
      );
      expect(content).toBeTruthy();
    } finally {
      await cleanup();
    }
  });

  test("view user management", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/admin/users");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      const content = await stagehandExtract(
        stagehand,
        "is there a list or table of users? Or an empty state?",
      );
      expect(content).toBeTruthy();
    } finally {
      await cleanup();
    }
  });

  test("view department management", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/admin/departments");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      const content = await stagehandExtract(
        stagehand,
        "is there a list or table of departments? Or an empty state?",
      );
      expect(content).toBeTruthy();
    } finally {
      await cleanup();
    }
  });

  test("view tool management", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/admin/tools");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      const content = await stagehandExtract(
        stagehand,
        "is there a list or table of tools? Or an empty state?",
      );
      expect(content).toBeTruthy();
    } finally {
      await cleanup();
    }
  });
});
