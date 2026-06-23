import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

/**
 * File upload E2E tests.
 *
 * Verifies the upload → attachment list → send-with-attachment flow
 * through the real UI (with a mocked backend).
 */

test.describe("File Upload", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
  });

  test("upload button is visible on workspace page", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // The upload trigger may be a button, icon, or hidden input.
    // Look for common patterns.
    const uploadTrigger = page
      .locator(
        '[data-testid="upload-button"], [data-testid="file-upload"], button:has-text("upload"), button:has-text("上传")',
      )
      .first();

    // At least one upload entry-point should exist
    const fileInput = page.locator('input[type="file"]');
    const hasTrigger = (await uploadTrigger.count()) > 0;
    const hasInput = (await fileInput.count()) > 0;

    expect(
      hasTrigger || hasInput,
      "Expected an upload button or file input on the workspace page",
    ).toBeTruthy();
  });

  test("file can be selected via file input", async ({ page }) => {
    // Navigate directly to the new-chat page where the input box (with file
    // input) is mounted.  Going through /workspace triggers a redirect and
    // may race with the conditional mount of the InputBox component.
    await page.goto("/workspace/chats/new");
    await page.waitForLoadState("networkidle");

    // The PromptInput component renders a hidden <input type="file"> with
    // data-testid="file-input".
    const fileInput = page.locator('[data-testid="file-input"]').first();
    await expect(fileInput).toBeAttached({ timeout: 10000 });

    // Upload a small text file
    await fileInput.setInputFiles({
      name: "test-upload.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Hello from a11y / upload E2E test"),
    });

    // After selecting a file the UI should reflect the pending attachment.
    // Look for the filename appearing somewhere in the page.
    await expect(page.locator("text=test-upload.txt").first()).toBeVisible({
      timeout: 5000,
    });
  });
});
