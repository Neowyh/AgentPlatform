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

  // SSR auth guard must stay on /workspace/chats/new. If IDEER_AUTH_DISABLED
  // is missing, Next will redirect to /login or render "Service temporarily
  // unavailable" (gateway_unavailable). Fail fast with an actionable message
  // instead of timing out 30 s on chat-input and being misreported as a loop.
  try {
    await expect(page).toHaveURL(/\/workspace\/chats\/new/, {
      timeout: 10_000,
    });
  } catch {
    const url = page.url();
    const unavailableVisible = await page
      .getByText("Service temporarily unavailable")
      .isVisible()
      .catch(() => false);
    if (unavailableVisible) {
      throw new Error(
        `[E2E] SSR gateway_unavailable at ${url} — gateway unreachable and IDEER_AUTH_DISABLED bypass not active. ` +
          `Ensure webServer.env.IDEER_AUTH_DISABLED=1 reaches both build and runtime (see frontend/src/core/auth/server.ts).`,
      );
    }
    if (url.includes("/login") || url.includes("/setup")) {
      throw new Error(
        `[E2E] SSR auth redirect to ${url} — IDEER_AUTH_DISABLED=1 not active on Next server. ` +
          `Ensure webServer.env.IDEER_AUTH_DISABLED=1 reaches both build and runtime.`,
      );
    }
    throw new Error(
      `[E2E] Expected /workspace/chats/new but landed on ${url}. Check SSR auth (IDEER_AUTH_DISABLED) or webServer.`,
    );
  }

  // Also surface gateway_unavailable even when URL is correct (edge case where
  // layout renders error without redirect)
  const unavailable = page.getByText("Service temporarily unavailable");
  if (await unavailable.isVisible().catch(() => false)) {
    throw new Error(
      `[E2E] SSR gateway_unavailable on ${page.url()} — gateway unreachable and IDEER_AUTH_DISABLED bypass not active.`,
    );
  }

  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
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
    test("Skills button opens skill selection dialog", async ({ page }) => {
      await gotoChat(page);

      await page.getByTestId("skill-selector-trigger").click();

      await expect(page.getByText("Select Skill")).toBeVisible({
        timeout: 8000,
      });
    });

    test("clicking skill in dialog inserts prefix", async ({ page }) => {
      await gotoChat(page);

      await page.getByTestId("skill-selector-trigger").click();

      await expect(page.getByText("Select Skill")).toBeVisible({
        timeout: 8000,
      });

      await page.getByRole("dialog").getByText("deep-research").first().click();

      await expect(page.getByTestId("chat-input")).toHaveValue(
        /\/deep-research\s/,
      );
    });
  });
});
