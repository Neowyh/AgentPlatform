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

/**
 * Read the box only after two consecutive measurements agree: the overlays
 * animate in, and a box captured mid-transition (likely when the machine is
 * loaded) would report shifted x/width.
 */
async function readSettledBox(locator: import("@playwright/test").Locator) {
  let previous = await locator.boundingBox();
  await expect
    .poll(
      async () => {
        const current = await locator.boundingBox();
        const stable =
          previous !== null &&
          current !== null &&
          Math.abs(current.x - previous.x) <= 1 &&
          Math.abs(current.width - previous.width) <= 1;
        previous = current;
        return stable;
      },
      { timeout: 5_000 },
    )
    .toBe(true);
  return previous;
}

test.describe("Slash skill invocation", () => {
  test("typing slash and clicking Skill anchor skill pickers to the composer", async ({
    page,
  }) => {
    await gotoChat(page);

    const textarea = page.getByTestId("chat-input");
    const picker = page.getByTestId("slash-overlay");

    // Typing "/" surfaces the inline suggestions listbox. Disable transitions
    // so box measurements below cannot race a mid-flight animation.
    await page.addStyleTag({
      content:
        "*, *::before, *::after { transition: none !important; animation: none !important; }",
    });
    await textarea.pressSequentially("/");
    await expect(picker).toBeVisible({ timeout: 8000 });

    await expect(
      picker.getByRole("option").filter({ hasText: "deep-research" }).first(),
    ).toBeVisible();
    const slashBox = await readSettledBox(picker);

    await textarea.press("Escape");
    await expect(picker).not.toBeVisible();

    // The Skill toolbar button surfaces the catalog picker.
    await page.getByTestId("skill-selector-trigger").click();
    await expect(picker).toBeVisible({ timeout: 8000 });

    await expect(page.getByTestId("slash-option-deep-research")).toBeVisible();
    const buttonBox = await readSettledBox(picker);
    const inputBox = await readSettledBox(textarea);

    expect(slashBox).not.toBeNull();
    expect(buttonBox).not.toBeNull();
    // Both entry points anchor to the composer's edges (the converged
    // widgets are two surfaces with slightly different padding, so compare
    // with a small tolerance (the overlays inset by their wrapper padding)).
    for (const box of [slashBox, buttonBox]) {
      expect(Math.abs(box!.x - inputBox!.x)).toBeLessThanOrEqual(16);
      expect(Math.abs(box!.width - inputBox!.width)).toBeLessThanOrEqual(24);
    }
  });

  test.describe("Slash overlay", () => {
    test("typing / shows skill suggestions overlay", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.pressSequentially("/");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 8000,
      });
      // The converged composer caps the typing-flow list at
      // MAX_SKILL_SUGGESTIONS (6) even with more seeded skills.
      await expect(
        page.getByTestId("slash-overlay").getByRole("option"),
      ).toHaveCount(6);
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
      await textarea.pressSequentially("/");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 8000,
      });

      await textarea.press("ArrowDown");
      await textarea.press("ArrowUp");

      await expect(page.getByTestId("slash-overlay")).toBeVisible();
    });

    test("Enter selects skill and activates the chip", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.pressSequentially("/");

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 8000,
      });

      await textarea.press("Enter");

      // Selecting a skill activates it as a removable chip; the plain
      // textarea is swapped for the inline skill input (converged contract).
      await expect(
        page.getByRole("button", { name: "Remove /deep-research" }),
      ).toBeVisible();
      await expect(page.getByTestId("slash-overlay")).not.toBeVisible();
    });

    test("Escape closes overlay without selection", async ({ page }) => {
      await gotoChat(page);

      const textarea = page.getByTestId("chat-input");
      await textarea.pressSequentially("/");

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

    test("clicking skill in the picker activates the skill chip", async ({
      page,
    }) => {
      await gotoChat(page);

      await page.getByTestId("skill-selector-trigger").click();

      await expect(page.getByTestId("slash-overlay")).toBeVisible({
        timeout: 8000,
      });

      await page.getByTestId("slash-option-deep-research").click();

      await expect(
        page.getByRole("button", { name: "Remove /deep-research" }),
      ).toBeVisible();
      await expect(page.getByTestId("chat-input")).not.toBeVisible();
      await expect(page.getByTestId("slash-overlay")).not.toBeVisible();
    });

    test("keyboard and mouse selection use the same invocation and submit text", async ({
      page,
    }) => {
      const submittedMessages: string[] = [];
      page.on("request", (request) => {
        if (
          request.method() !== "POST" ||
          !request.url().endsWith("/runs/stream")
        ) {
          return;
        }
        const body = request.postDataJSON() as {
          input?: { messages?: Array<{ content?: unknown }> };
        };
        const content = body.input?.messages?.[0]?.content;
        submittedMessages.push(
          typeof content === "string"
            ? content
            : Array.isArray(content)
              ? content
                  .map((part) =>
                    typeof part === "object" &&
                    part !== null &&
                    "text" in part &&
                    typeof part.text === "string"
                      ? part.text
                      : "",
                  )
                  .join("")
              : "",
        );
      });

      await gotoChat(page);
      const textarea = page.getByTestId("chat-input");
      await textarea.pressSequentially("/");
      await expect(page.getByTestId("slash-overlay")).toBeVisible();
      await textarea.press("Enter");

      const skillChip = page.getByRole("button", {
        name: "Remove /deep-research",
      });
      await expect(skillChip).toBeVisible();
      const keyboardInput = page.locator(
        '[data-slot="input-group-control"][contenteditable="true"]',
      );
      await keyboardInput.pressSequentially("compare available sources");
      const keyboardText = await keyboardInput.textContent();
      const keyboardCaret = await keyboardInput.evaluate((element) => {
        const selection = window.getSelection();
        return selection?.anchorNode === element.firstChild
          ? selection.anchorOffset
          : null;
      });
      await keyboardInput.press("Enter");
      await expect
        .poll(() => submittedMessages.length, { timeout: 10_000 })
        .toBe(1);

      await gotoChat(page);
      await page.getByTestId("skill-selector-trigger").click();
      await expect(page.getByTestId("slash-overlay")).toBeVisible();
      await page.getByTestId("slash-option-deep-research").click();
      await expect(skillChip).toBeVisible();

      const mouseInput = page.locator(
        '[data-slot="input-group-control"][contenteditable="true"]',
      );
      await mouseInput.pressSequentially("compare available sources");
      expect(await mouseInput.textContent()).toBe(keyboardText);
      expect(
        await mouseInput.evaluate((element) => {
          const selection = window.getSelection();
          return selection?.anchorNode === element.firstChild
            ? selection.anchorOffset
            : null;
        }),
      ).toBe(keyboardCaret);
      await mouseInput.press("Enter");
      await expect
        .poll(() => submittedMessages.length, { timeout: 10_000 })
        .toBe(2);

      expect(submittedMessages[1]).toBe(submittedMessages[0]);
      expect(submittedMessages[0]).toBe(
        "/deep-research compare available sources",
      );
    });

    test("skill changes keep the new-chat composer dimensions stable", async ({
      page,
    }) => {
      await gotoChat(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { transition: none !important; animation: none !important; }",
      });
      const form = page.getByTestId("input-box").locator("form");
      const initial = await form.boundingBox();
      expect(initial).not.toBeNull();

      const expectStableDimensions = async () => {
        const current = await form.boundingBox();
        expect(current).not.toBeNull();
        expect(Math.abs(current!.width - initial!.width)).toBeLessThanOrEqual(
          1,
        );
        expect(Math.abs(current!.height - initial!.height)).toBeLessThanOrEqual(
          1,
        );
      };

      const textarea = page.getByTestId("chat-input");

      await textarea.fill(
        Array.from({ length: 10 }, (_, index) => `Line ${index + 1}`).join(
          "\n",
        ),
      );
      const multiline = await form.boundingBox();
      expect(multiline).not.toBeNull();
      expect(multiline!.height).toBeGreaterThan(initial!.height + 20);
      await textarea.fill("");

      await textarea.pressSequentially("/");
      await textarea.press("Enter");
      await expect(
        page.getByRole("button", { name: "Remove /deep-research" }),
      ).toBeVisible();
      await expectStableDimensions();

      const skillInput = page.locator(
        '[data-slot="input-group-control"][contenteditable="true"]',
      );
      await skillInput.pressSequentially("/");
      await expect(page.getByTestId("slash-option-web-search")).toBeVisible();
      await page.getByTestId("slash-option-web-search").click();
      await expect(
        page.getByRole("button", { name: "Remove /web-search" }),
      ).toBeVisible();
      await expectStableDimensions();

      await page.getByRole("button", { name: "Remove /web-search" }).click();
      await expect(page.getByTestId("chat-input")).toBeVisible();
      await expectStableDimensions();

      await page.getByTestId("skill-selector-trigger").click();
      await page.getByTestId("slash-option-deep-research").click();
      await expect(
        page.getByRole("button", { name: "Remove /deep-research" }),
      ).toBeVisible();
      await expectStableDimensions();
    });
  });
});
