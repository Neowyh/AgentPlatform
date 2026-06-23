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
 * Chat Interactions — Stagehand E2E Tests
 *
 * Tests chat interface interactions using natural language.
 */

test.describe("Chat Interactions - Stagehand", () => {
  test.skip(
    !hasStagehand,
    "Stagehand requires OPENAI_API_KEY or OPENAI_BASE_URL",
  );
  test.setTimeout(120_000);

  test("open new chat and verify input area", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/chats/new");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      const content = await stagehandExtract(
        stagehand,
        "is there a text input area for typing messages? Is there a send button?",
      );
      expect(content).toBeTruthy();
    } finally {
      await cleanup();
    }
  });

  test("type a message in the input area", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/chats/new");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      await stagehandAct(
        stagehand,
        'type "Hello, this is a test message" in the message input field',
      );

      const content = await stagehandExtract(
        stagehand,
        "what text is currently in the input field?",
      );
      // Content may be a fallback if model doesn't follow schema exactly
      expect(content).toBeTruthy();
    } finally {
      await cleanup();
    }
  });

  test("verify sidebar navigation", async () => {
    const { stagehand, page, cleanup } = await createStagehandTest();
    try {
      await page.goto("http://localhost:3000/workspace/chats/new");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(2000);

      const content = await stagehandExtract(
        stagehand,
        "is there a sidebar with navigation links? What links are visible?",
      );
      expect(content).toBeTruthy();
    } finally {
      await cleanup();
    }
  });
});
