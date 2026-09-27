import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

test.describe("Core workspace — visual regression", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test("agent gallery desktop screenshot", async ({ page }) => {
    await page.goto("/workspace/capabilities/experts");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot("agent-gallery.png", {
      fullPage: true,
    });
  });

  test("library desktop screenshot", async ({ page }) => {
    await page.route(/\/api\/resources\?type=knowledge_base/, (route) =>
      route.fulfill({
        json: {
          items: [
            {
              id: "kb-1",
              type: "knowledge_base",
              slug: "team-docs",
              display_name: "Team docs",
              visibility: "public",
              can_modify: true,
              knowledge_document_count: 2,
            },
          ],
          total: 1,
        },
      }),
    );
    await page.route(/\/api\/resources\/[^/?]+\/documents$/, (route) =>
      route.fulfill({
        json: {
          items: [
            {
              id: "doc-1",
              resource_id: "kb-1",
              name: "Platform overview",
              size: 1024,
              mime_type: "text/plain",
              content_hash: "hash-doc-1",
              source: "upload",
              status: "ready",
              can_modify: true,
              metadata: {},
              created_at: "2026-09-01T00:00:00Z",
              updated_at: null,
            },
          ],
        },
      }),
    );
    await page.goto("/workspace/library");
    await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();
    await expect(page.getByText("Platform overview")).toBeVisible();
    await expect(page).toHaveScreenshot("library.png", {
      fullPage: true,
    });
  });

  test("workflow editor desktop screenshot", async ({ page }) => {
    await page.goto("/workspace/workflows/new");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot("workflow-editor.png", {
      fullPage: true,
    });
  });

  test("existing workflow editor desktop screenshot", async ({ page }) => {
    test.setTimeout(120_000);
    mockLangGraphAPI(page, {
      workflows: [
        { name: "research-workflow", description: "Research workflow" },
      ],
    });
    await page.route(/\/api\/resources\?type=knowledge_base/, (route) =>
      route.fulfill({
        json: {
          items: [{ id: "kb-1", slug: "docs", display_name: "Docs" }],
          total: 1,
        },
      }),
    );
    await page.route(/\/api\/resources\/kb-1\/knowledge-revisions/, (route) =>
      route.fulfill({ json: { items: [] } }),
    );

    await page.goto("/workspace/workflows/new");
    const baselineEditor = page.locator(".cm-editor");
    await expect(baselineEditor).toBeVisible();
    const baselineEditorBounds = await baselineEditor.boundingBox();
    if (!baselineEditorBounds) {
      throw new Error("The baseline workflow editor should be visible");
    }

    await page.goto("/workspace/workflows/research-workflow/edit", {
      waitUntil: "domcontentloaded",
      timeout: 90_000,
    });
    const existingWorkflowEditor = page.locator(".cm-editor");
    await expect(existingWorkflowEditor).toBeVisible();
    expect(await existingWorkflowEditor.boundingBox()).toEqual(
      baselineEditorBounds,
    );
    await expect(
      page.getByRole("button", { name: "Knowledge bases" }),
    ).toBeVisible();
    await expect(page).toHaveScreenshot("workflow-existing-editor.png", {
      fullPage: true,
    });
    await page.getByRole("button", { name: "Knowledge bases" }).click();
    await expect(page.getByRole("dialog")).toHaveScreenshot(
      "workflow-knowledge-dependencies.png",
    );
  });

  test("existing chat desktop screenshot", async ({ page }) => {
    // Match the pre-merge manual's 04-workspace-chat.png canvas.
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: "00000000-0000-0000-0000-000000004100",
          title: "Quarterly report review",
          messages: [
            {
              type: "human",
              id: "msg-human-existing-chat",
              content: [
                { type: "text", text: "Summarize the quarterly report" },
              ],
            },
            {
              type: "ai",
              id: "msg-ai-existing-chat",
              content:
                "Here is the quarterly summary. Revenue grew steadily and the top three accounts drove most of the increase.",
            },
          ],
        },
      ],
    });
    await page.goto("/workspace/chats/00000000-0000-0000-0000-000000004100");
    await expect(page.getByTestId("main-message-list")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page).toHaveScreenshot("existing-chat.png", {
      fullPage: true,
    });
  });

  test("admin dashboard desktop screenshot", async ({ page }) => {
    await page.goto("/workspace/admin");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot("admin-dashboard.png", {
      fullPage: true,
    });
  });
});
