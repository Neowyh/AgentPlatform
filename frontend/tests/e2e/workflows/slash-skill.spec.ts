import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const MOCK_SKILLS = [
  {
    name: "deep-research",
    description: "Multi-angle web research methodology",
    category: "public" as const,
    license: "requires_internet",
    enabled: true,
  },
  {
    name: "web-search",
    description: "Search the web for information",
    category: "public" as const,
    license: "requires_internet",
    enabled: true,
  },
  {
    name: "image-gen",
    description: "Generate images from text prompts",
    category: "public" as const,
    license: null,
    enabled: true,
  },
];

async function gotoChat(page: Page) {
  mockLangGraphAPI(page, { skills: MOCK_SKILLS });
  await page.goto("/workspace/chats/new", { timeout: 60_000 });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 30_000 });
}

test.describe("Slash skill invocation", () => {
  test.describe("Slash overlay", () => {
    test("typing / shows skill suggestions overlay", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.fill("/");
      await textarea.press("Space");
      await textarea.press("Backspace");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 5000,
      });
    });

    test("typing /res filters to matching skills", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.fill("/res");
      await textarea.press("Space");
      await textarea.press("Backspace");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 5000,
      });
      await expect(
        page.getByTestId("slash-option-deep-research"),
      ).toBeVisible();
    });

    test("arrow keys navigate suggestions", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.fill("/");
      await textarea.press("Space");
      await textarea.press("Backspace");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 5000,
      });

      await textarea.press("ArrowDown");
      await textarea.press("ArrowUp");

      await expect(page.getByTestId("slash-overlay")).toBeVisible();
    });

    test("Enter selects skill and inserts prefix", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.fill("/");
      await textarea.press("Space");
      await textarea.press("Backspace");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 5000,
      });

      await textarea.press("Enter");

      await expect(page.getByTestId("slash-overlay")).not.toBeVisible();
      await expect(textarea).toHaveValue(/\/deep-research\s/);
    });

    test("Escape closes overlay without selection", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.fill("/");
      await textarea.press("Space");
      await textarea.press("Backspace");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 5000,
      });

      await textarea.press("Escape");

      await expect(page.getByTestId("slash-overlay")).not.toBeVisible();
    });
  });

  test.describe("Skills toolbar button", () => {
    test("Skills button opens skill selection dialog", async ({ page }) => {
      await gotoChat(page);

      await page.getByTestId("skill-selector-trigger").click();

      await expect(page.getByText("Select Skill")).toBeVisible({
        timeout: 5000,
      });
    });

    test("clicking skill in dialog inserts prefix", async ({ page }) => {
      await gotoChat(page);

      await page.getByTestId("skill-selector-trigger").click();

      await expect(page.getByText("Select Skill")).toBeVisible({
        timeout: 5000,
      });

      await page.getByText("deep-research").click();

      await expect(page.getByTestId("chat-input")).toHaveValue(
        /\/deep-research\s/,
      );
    });
  });
});
