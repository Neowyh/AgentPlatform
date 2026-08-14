import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const MOCK_WORKFLOWS = [
  {
    name: "test-workflow",
    description: "A test workflow",
    version: "1.0",
    steps: [
      { id: "step1", type: "agent", agent: "test-agent", prompt: "Hello" },
    ],
    inputs: {
      query: { type: "string", required: true, description: "The query" },
    },
    yaml_content:
      'name: test-workflow\ndescription: "A test workflow"\nversion: "1.0"\ninputs:\n  query:\n    type: string\n    required: true\nsteps:\n  - id: step1\n    type: agent\n    agent: test-agent\n    prompt: Hello',
  },
];

test.describe("Workflow management", () => {
  test.describe("Gallery", () => {
    test("gallery page loads and shows workflow cards", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows");

      await expect(page.getByText("test-workflow")).toBeVisible({
        timeout: 15_000,
      });
    });

    test("gallery shows New Workflow button", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows");

      await expect(
        page.getByRole("button", { name: /new workflow/i }),
      ).toBeVisible({ timeout: 15_000 });
    });

    test("New Workflow button navigates to create page", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows");

      await page.getByRole("button", { name: /new workflow/i }).click();

      await expect(page).toHaveURL(/\/workspace\/workflows\/new/);
    });

    test("workflow card navigates to detail page", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows");

      await page.getByText("test-workflow").first().click();

      await expect(page).toHaveURL(/\/workspace\/workflows\/test-workflow/);
      await expect(page.getByText("step1").first()).toBeVisible({
        timeout: 10_000,
      });
    });

    test("gallery shows empty state when no workflows", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: [] });
      await page.goto("/workspace/workflows");

      await expect(page.getByText("test-workflow")).toBeHidden({
        timeout: 15_000,
      });
    });
  });

  test.describe("Create Workflow", () => {
    test("create page loads with YAML editor", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: [] });
      await page.goto("/workspace/workflows/new");

      // CodeMirror editor should be visible
      await expect(page.locator(".cm-editor")).toBeVisible({
        timeout: 15_000,
      });

      // Should have pre-filled template content
      await expect(page.getByText("name: my-workflow")).toBeVisible();
    });

    test("create page shows validation error for invalid YAML", async ({
      page,
    }) => {
      mockLangGraphAPI(page, { workflows: [] });
      await page.goto("/workspace/workflows/new");

      const editor = page.locator(".cm-content");
      await expect(editor).toBeVisible({ timeout: 15_000 });

      // Clear the editor and type invalid content (missing name)
      await editor.click();
      await page.keyboard.press("Control+a");
      await page.keyboard.type("steps: []");

      // Should show validation error
      await expect(page.getByText(/name/i).first()).toBeVisible({
        timeout: 5_000,
      });
    });

    test("editor accepts workflow YAML and keeps validation surface visible", async ({
      page,
    }) => {
      mockLangGraphAPI(page, { workflows: [] });
      await page.goto("/workspace/workflows/new");

      const editor = page.locator(".cm-content");
      await expect(editor).toBeVisible({ timeout: 15_000 });

      await editor.click();
      await page.keyboard.press("Control+a");
      await page.keyboard.type(
        "name: qa-workflow\nsteps:\n  - id: step1\n    type: agent\n    agent: default",
      );

      await expect(page.locator(".cm-editor")).toBeVisible({
        timeout: 5_000,
      });
      await expect(page.getByText("qa-workflow").first()).toBeVisible();
    });
  });

  test.describe("Workflow Detail", () => {
    test("detail page shows steps, inputs, and YAML", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows/test-workflow");

      // Should show workflow name
      await expect(page.getByText("test-workflow").first()).toBeVisible({
        timeout: 15_000,
      });

      // Should show steps
      await expect(page.getByText("step1").first()).toBeVisible();

      // Should show inputs (use first to avoid strict mode)
      await expect(page.getByText("query").first()).toBeVisible();

      // Should show Run button
      await expect(page.getByRole("button", { name: /run/i })).toBeVisible();

      // Should show Edit link
      await expect(page.getByRole("link", { name: /edit/i })).toBeVisible();
    });

    test("run dialog opens with input fields", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows/test-workflow");

      // Click Run button
      await page.getByRole("button", { name: /run/i }).click();

      // Run dialog should appear with input field for "query"
      await expect(page.getByText("query").first()).toBeVisible({
        timeout: 5_000,
      });
    });
  });

  test.describe("Edit Workflow", () => {
    test("edit page loads with existing YAML", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows/test-workflow/edit");

      // CodeMirror editor should be visible with existing content
      await expect(page.locator(".cm-editor")).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("test-workflow").first()).toBeVisible();
    });

    test("save sends version in PUT request body", async ({ page }) => {
      // Empty workflows list falls back to the mock's valid v2 detail YAML
      mockLangGraphAPI(page, { workflows: [] });
      let putBody: Record<string, unknown> | null = null;
      // Registered after mockLangGraphAPI so it takes precedence for PUT
      await page.route("**/api/workflows/test-workflow", async (route) => {
        if (route.request().method() === "PUT") {
          putBody = route.request().postDataJSON();
          return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              name: "test-workflow",
              description: "Updated",
              version: "2",
              steps_count: 1,
              inputs: {},
            }),
          });
        }
        return route.fallback();
      });
      await page.goto("/workspace/workflows/test-workflow/edit");

      await expect(page.locator(".cm-editor")).toBeVisible({
        timeout: 15_000,
      });
      await page.getByRole("button", { name: /save changes/i }).click();

      await expect(page).toHaveURL(/\/workspace\/workflows\/test-workflow$/);
      expect(putBody).toMatchObject({
        version: 1,
        yaml_content: expect.any(String),
      });
    });
  });

  test.describe("Delete Workflow", () => {
    test("delete button opens confirmation dialog", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/workflows");

      // Delete button is icon-only with text-destructive class
      const deleteBtn = page.locator("button.text-destructive").first();
      await expect(deleteBtn).toBeVisible({ timeout: 15_000 });
      await deleteBtn.click();

      await expect(page.getByText(/are you sure|confirm/i)).toBeVisible({
        timeout: 5_000,
      });
    });
  });

  test.describe("Sidebar Navigation", () => {
    test("sidebar shows Workflows link", async ({ page }) => {
      mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
      await page.goto("/workspace/chats/new");

      await expect(page.getByRole("link", { name: /workflows/i })).toBeVisible({
        timeout: 15_000,
      });
    });
  });
});
