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

  test("admin dashboard desktop screenshot", async ({ page }) => {
    await page.goto("/workspace/admin");
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page).toHaveScreenshot("admin-dashboard.png", {
      fullPage: true,
    });
  });
});
