import { expect, test, type Page } from "@playwright/test";

import { DEMO_THREAD_IDS } from "@/core/threads/static-demo";

import { mockLangGraphAPI } from "../utils/mock-api";

const NEW_THREAD_ID = "00000000-0000-0000-0000-000000000001";

async function setupComposerMocks(page: Page) {
  mockLangGraphAPI(page, {
    agents: [
      {
        name: "test-agent",
        description: "Composer readability test agent",
        system_prompt: "You are a test agent.",
      },
    ],
    threads: [
      {
        thread_id: NEW_THREAD_ID,
        title: "Composer readability",
        messages: [],
      },
    ],
    skills: [
      {
        name: "readability-skill",
        description: "A skill for composer readability tests.",
        category: "public",
        license: "MIT",
        enabled: true,
      },
    ],
  });
  await page.route("**/api/threads/*/uploads", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        message: "Uploaded",
        files: [
          {
            filename: "readability.txt",
            size: 20,
            path: "readability.txt",
            virtual_path: "/mnt/user-data/uploads/readability.txt",
            artifact_url: "/api/threads/test/uploads/readability.txt",
            extension: ".txt",
          },
        ],
      }),
    }),
  );
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        models: [
          {
            id: "readability-model",
            name: "readability-model",
            model: "test/readability-model",
            display_name: "Readable model",
          },
          {
            id: "alternate-model",
            name: "alternate-model",
            model: "test/alternate-model",
            display_name: "Alternate model",
          },
        ],
        token_usage: { enabled: false },
      }),
    }),
  );
}

async function expectComposerReadable(
  page: Page,
  options: { selectMode?: boolean; expectModelText?: boolean } = {},
) {
  const input = page.getByTestId("chat-input");
  await expect(input).toBeVisible({ timeout: 15_000 });

  const mode = page.locator('button[aria-label="Mode"]');
  if (options.selectMode) {
    await mode.click();
    await page.getByRole("menuitem", { name: /Flash/ }).click();
    await page.keyboard.press("Escape");
  }

  const bodyFontSize = await input.evaluate((element) =>
    parseFloat(getComputedStyle(element).fontSize),
  );
  const textControls = [
    page.getByTestId("skill-selector-trigger").getByText("Skill", {
      exact: true,
    }),
  ];
  if (options.expectModelText) {
    textControls.push(
      page
        .getByTestId("model-selector-trigger")
        .getByText("Readable model", { exact: true }),
    );
  }
  for (const locator of textControls) {
    await expect(locator).toBeVisible();
    await expect
      .poll(
        () =>
          locator.evaluate((element) =>
            parseFloat(getComputedStyle(element).fontSize),
          ),
        { timeout: 5_000 },
      )
      .toBeGreaterThanOrEqual(bodyFontSize);
  }

  if (options.selectMode) {
    const modeText = await mode.evaluate((button) => {
      const text = Array.from(button.querySelectorAll("*")).find(
        (element) =>
          element.childElementCount === 0 &&
          element.textContent?.trim() === "Flash",
      );
      const typography = text?.closest(".type-compact, .type-body") ?? text;
      return {
        text: text?.textContent?.trim(),
        fontSize: typography
          ? parseFloat(getComputedStyle(typography).fontSize)
          : null,
      };
    });
    expect(modeText.text).toBe("Flash");
    expect(modeText.fontSize).toBeGreaterThanOrEqual(bodyFontSize);
  }

  const attachment = page.getByTestId("add-attachments-button");
  await expect(attachment).toHaveAttribute("aria-label", "Add attachments");
  const iconButtons = [attachment, page.getByTestId("polish-input-button")];
  const voice = page.getByTestId("voice-input-button");
  if (await voice.count()) iconButtons.push(voice);

  for (const button of iconButtons) {
    await expect(button).toHaveAttribute("aria-label", /.+/);
    await expect(button).toBeVisible();
    const box = await button.boundingBox();
    expect(
      box,
      `Expected ${await button.getAttribute("aria-label")} to have a visible hit area`,
    ).not.toBeNull();
    expect(box!.width).toBeGreaterThanOrEqual(40);
    expect(box!.height).toBeGreaterThanOrEqual(40);
  }

  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}

test("new chat composer is readable on desktop and narrow screens", async ({
  page,
}) => {
  await setupComposerMocks(page);

  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 375, height: 812 },
  ]) {
    await page.setViewportSize(viewport);
    if (viewport.width === 1280) {
      await page.goto("/workspace/chats/new", { waitUntil: "commit" });
    }
    await expectComposerReadable(page, {
      selectMode: true,
      expectModelText: true,
    });
  }

  const fileChooser = page.waitForEvent("filechooser");
  await page.getByTestId("add-attachments-button").click();
  const chooser = await fileChooser;
  await chooser.setFiles({
    name: "readability.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("readable attachment"),
  });
  await expect(
    page.getByText("readability.txt", { exact: true }),
  ).toBeVisible();

  await page.getByTestId("model-selector-trigger").click();
  const modelDialog = page.getByRole("dialog");
  await expect(modelDialog).toBeVisible();
  await modelDialog.getByRole("option", { name: /Alternate model/ }).click();
  await expect(modelDialog).toBeHidden();
  await expect(page.getByTestId("model-selector-trigger")).toContainText(
    "Alternate model",
  );

  await page.getByTestId("chat-input").fill("/readability");
  await page.getByTestId("skill-selector-trigger").click();
  const skillSuggestions = page.getByRole("listbox", {
    name: "Skill suggestions",
  });
  await expect(skillSuggestions).toBeVisible();
  await skillSuggestions.getByTestId("slash-option-readability-skill").click();
  await expect(
    page.getByRole("button", { name: "Remove /readability-skill" }),
  ).toBeVisible();
  await expect(page.getByRole("textbox").last()).toBeVisible();
  await expect(skillSuggestions).toBeHidden();
});

test("shared showcase composer remains readable", async ({ page }) => {
  await setupComposerMocks(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/showcase/${DEMO_THREAD_IDS[0]}`, { waitUntil: "commit" });
  await expectComposerReadable(page);
});

test("Custom Agent composer remains readable", async ({ page }) => {
  await setupComposerMocks(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/workspace/capabilities/experts/test-agent/chats/new", {
    waitUntil: "commit",
  });
  await expectComposerReadable(page);
});
