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
  ...[
    "officecli",
    "data-analysis",
    "code-documentation",
    "summarize",
    "ppt-generation",
  ].map((name) => ({
    name,
    description: `${name} skill`,
    category: "public" as const,
    license: null,
    enabled: true,
  })),
];

async function gotoChat(page: Page) {
  mockLangGraphAPI(page, { skills: MOCK_SKILLS });
  // Retry goto up to 3 times to tolerate transient SSR redirect race
  // (RSC prefetch may race with mock setup). Retries are cheap vs
  // misreporting as slash-overlay failure.
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    await page.goto("/workspace/chats/new", { timeout: 60_000 });
    try {
      await expect(page).toHaveURL(/\/workspace\/chats\/new/, {
        timeout: 10_000,
      });
      const unavailable = page.getByText("Service temporarily unavailable");
      if (await unavailable.isVisible().catch(() => false)) {
        throw new Error(
          `[E2E] SSR gateway_unavailable on ${page.url()} — gateway unreachable and IDEER_AUTH_DISABLED bypass not active.`,
        );
      }
      await expect(page.getByTestId("chat-input")).toBeVisible({
        timeout: 15_000,
      });
      return;
    } catch (e) {
      lastError = e;
      const url = page.url();
      const msg = e instanceof Error ? e.message : String(e);
      // Only retry on known transient SSR states
      if (
        msg.includes("SSR gateway_unavailable") ||
        msg.includes("SSR auth redirect") ||
        url.includes("/login") ||
        url.includes("/setup")
      ) {
        if (attempt < 2) {
          await page.waitForTimeout(800);
          continue;
        }
      }
      throw e;
    }
  }
  throw lastError;
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
        timeout: 8000,
      });
      await expect(
        page.getByTestId("slash-overlay").getByRole("button"),
      ).toHaveCount(8);
    });

    test("typing /res filters to matching skills", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.fill("/res");
      await textarea.press("Space");
      await textarea.press("Backspace");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 8000,
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
        timeout: 8000,
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
        timeout: 8000,
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
        timeout: 8000,
      });

      await textarea.press("Escape");

      await expect(page.getByTestId("slash-overlay")).not.toBeVisible();
    });
  });

  test.describe("Skills toolbar button", () => {
    test("Skills button opens the anchored skill picker", async ({ page }) => {
      await gotoChat(page);

      await page.getByTestId("skill-selector-trigger").click();

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 8000,
      });
    });

    test("clicking skill in the picker inserts prefix", async ({ page }) => {
      await gotoChat(page);

      await page.getByTestId("skill-selector-trigger").click();

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 8000,
      });

      await page.getByTestId("slash-option-deep-research").click();

      await expect(page.getByTestId("chat-input")).toHaveValue(
        /\/deep-research\s/,
      );
    });
  });
});
