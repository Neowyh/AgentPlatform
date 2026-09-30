import { expect, test, type Locator, type Page } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

async function selectAgent(page: Page, scenario: RegExp, agent: RegExp) {
  await page.getByRole("tab", { name: scenario }).click();
  await expect(page.getByTestId("agent-pill-bar")).toBeVisible();
  await page.getByRole("tab", { name: agent }).click();
}

function mockRecentThreads(page: Page, count: number) {
  mockLangGraphAPI(page, {
    threads: Array.from({ length: count }, (_, index) => ({
      thread_id: `recent-thread-${index + 1}`,
      title: `Recent work ${index + 1}`,
      updated_at: "2026-09-01T00:00:00Z",
    })),
  });
}

// Height of the fixed conversation header, read from the rendered header
// element so the tests track the CSS instead of a hardcoded pixel value.
async function fixedHeaderBand(page: Page): Promise<number> {
  const header = page.locator("header.workbench-conversation-header");
  await expect(header).toBeAttached();
  const box = await header.boundingBox();
  expect(box).not.toBeNull();
  return box!.height;
}

async function expectWithinViewport(
  locator: Locator,
  viewportHeight: number,
  minY = 0,
) {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.y).toBeGreaterThanOrEqual(minY);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewportHeight);
}

async function readWelcomeLayout(page: Page) {
  const selectors = {
    hero: '[data-testid="workbench-home"] .type-page-title',
    quickEntries: '[data-testid="workbench-quick-entry-module"]',
    scenarioTabs: '[data-testid="scenario-tabs"]',
    agentEntries: '[data-testid="agent-pill-bar"]',
    taskEntries: '[data-testid="task-chip-bar"]',
    composer: '[data-testid="input-box"]',
    recentTasks: ".workbench-recent-tasks",
    disclaimer: '[data-testid="workbench-disclaimer"]',
  };
  const layout: Record<string, number[] | null> = {};
  for (const [name, selector] of Object.entries(selectors)) {
    const locator = page.locator(selector);
    if (
      (name === "agentEntries" || name === "taskEntries") &&
      !(await locator.count())
    ) {
      layout[name] = null;
      continue;
    }
    await expect(locator).toBeVisible();
    layout[name] = await locator.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      let x = rect.x + window.scrollX;
      let y = rect.y + window.scrollY;
      let ancestor = element.parentElement;
      while (ancestor) {
        x += ancestor.scrollLeft;
        y += ancestor.scrollTop;
        ancestor = ancestor.parentElement;
      }
      return [x, y, rect.width, rect.height].map(
        (value) => Math.round(value * 10) / 10,
      );
    });
  }
  return layout;
}

async function expectWelcomeLayoutUnchanged(
  page: Page,
  initialLayout: Record<string, number[] | null>,
  state: string,
) {
  const currentLayout = await readWelcomeLayout(page);
  for (const [module, initialBounds] of Object.entries(initialLayout)) {
    const currentBounds = currentLayout[module];
    if (!initialBounds || !currentBounds) continue;
    for (const [index, value] of currentBounds.entries()) {
      expect(
        value,
        `${module} geometry changed after ${state}: initial=${initialBounds.join(",")} current=${currentBounds.join(",")}`,
      ).toBeCloseTo(initialBounds[index]!, 0);
    }
  }
  await expectDisclaimerAtPageBottom(page);
}

async function expectDisclaimerAtPageBottom(page: Page) {
  const bottomGap = await page
    .getByTestId("workbench-disclaimer")
    .evaluate((disclaimer) => {
      const main = disclaimer.closest(".workbench-conversation-main");
      if (!main) throw new Error("Welcome disclaimer is outside the main page");
      const mainRect = main.getBoundingClientRect();
      const disclaimerRect = disclaimer.getBoundingClientRect();
      return (
        main.scrollHeight -
        (disclaimerRect.bottom - mainRect.top + main.scrollTop)
      );
    });
  expect(bottomGap).toBeGreaterThanOrEqual(-1);
  expect(bottomGap).toBeLessThanOrEqual(1);
}

test.describe("@smoke WorkBuddy cascade bar", () => {
  test("shows three scenario tabs in welcome mode", async ({ page }) => {
    // No seeded history: the retirements must hold on a blank account too.
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await expect(page.getByTestId("scenario-tabs")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("tab", { name: /Daily Office/ })).toBeVisible();
    await expect(
      page.getByRole("tab", { name: /Creative Design/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: /Professional Tasks/ }),
    ).toBeVisible();
    await expect(page.getByText(/open source super agent/i)).toHaveCount(0);
    await expect(page.getByTestId("workbench-recent-chats")).toHaveCount(0);
  });

  test("shows the task-first welcome hierarchy", async ({ page }) => {
    mockRecentThreads(page, 1);
    await page.goto("/workspace/chats/new");
    await expect(page.getByTestId("workbench-home")).toBeVisible();
    await expect(
      page.getByText("iDeer, realize your idea").first(),
    ).toBeVisible();
    // History still lands in the left sidebar (this also proves the threads
    // query resolved, so the absence assertions below are not racing it).
    const sidebarThread = page
      .getByTestId("thread-list")
      .getByText("Recent work");
    await expect(sidebarThread.first()).toBeVisible();
    // The long intro and the in-page recent-chats card are retired from the
    // new-conversation home (issue 01); history stays in the left sidebar.
    await expect(page.getByText(/open source super agent/i)).toHaveCount(0);
    await expect(page.getByTestId("workbench-recent-chats")).toHaveCount(0);
    await expect(page.getByText("方向不明？")).toBeVisible();
    await expect(page.getByText("目标明确？")).toBeVisible();
  });

  test("keeps Skill-mode guidance without restoring the ordinary intro", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new?mode=skill");
    await expect(page.getByText("✨ Create Your Own Skill ✨")).toBeVisible();
    await expect(
      page.getByText(/Create your own skill to release the power of iDeer/),
    ).toBeVisible();
    await expect(page.getByText(/open source super agent/i)).toHaveCount(0);
  });

  test("fits the welcome home in the desktop acceptance viewport", async ({
    page,
  }) => {
    const viewport = { width: 1280, height: 720 };
    await page.setViewportSize(viewport);
    // Seed enough history to render the full recent-task strip — the tallest
    // realistic welcome home.
    mockRecentThreads(page, 3);
    await page.goto("/workspace/chats/new");
    const headerBand = await fixedHeaderBand(page);
    const home = page.getByTestId("workbench-home");
    await expect(home).toBeVisible({ timeout: 15_000 });
    const input = page.getByTestId("chat-input");
    await expect(input).toBeVisible();

    // Title, quick entry, and input all sit fully inside the first screen,
    // below the fixed header band — nothing hides under it.
    await expectWithinViewport(home, viewport.height, headerBand);
    await expectWithinViewport(input, viewport.height, headerBand);

    // Nothing overlaps: the home block ends above the input's guide row.
    const homeBox = (await home.boundingBox())!;
    const inputBox = (await input.boundingBox())!;
    expect(homeBox.y + homeBox.height).toBeLessThanOrEqual(inputBox.y);
  });

  test("keeps every welcome entry reachable on short and narrow viewports", async ({
    page,
  }) => {
    mockRecentThreads(page, 3);
    // The welcome home scrolls naturally instead of being clipped: each
    // entry and the input can be brought fully below the fixed header band
    // and inside the viewport, on a short desktop window and a phone.
    for (const viewport of [
      { width: 1280, height: 420 },
      { width: 375, height: 812 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto("/workspace/chats/new");
      const headerBand = await fixedHeaderBand(page);
      const input = page.getByTestId("chat-input");
      await expect(input).toBeVisible({ timeout: 15_000 });
      const voiceInputSupported = await page.evaluate(() => {
        const speechWindow = window as Window & {
          SpeechRecognition?: unknown;
          webkitSpeechRecognition?: unknown;
        };
        return Boolean(
          speechWindow.SpeechRecognition ??
          speechWindow.webkitSpeechRecognition,
        );
      });
      const voiceInput = page.getByTestId("voice-input-button");
      if (!voiceInputSupported) {
        await expect(voiceInput).toHaveCount(0);
      }

      const reachableControls = [
        page.getByTestId("workbench-home").locator(".type-page-title"),
        page.getByRole("tab", { name: /Daily Office/ }),
        page.getByRole("tab", { name: /Creative Design/ }),
        page.getByRole("tab", { name: /Professional Tasks/ }),
        input,
        page.getByTestId("add-attachments-button"),
        page.getByTestId("model-selector-trigger"),
        page.getByTestId("skill-selector-trigger"),
      ];
      if (voiceInputSupported) {
        reachableControls.push(voiceInput);
      }
      for (const locator of reachableControls) {
        await locator.evaluate((element) => {
          element.scrollIntoView({ block: "center" });
        });
        await expectWithinViewport(locator, viewport.height, headerBand);
      }
      await page.getByTestId("chat-input").fill("Reachable draft");
      await expect(page.getByTestId("chat-input")).toHaveValue(
        "Reachable draft",
      );
      await page.getByTestId("model-selector-trigger").click({ trial: true });
      await page.getByTestId("skill-selector-trigger").click({ trial: true });
      await page.getByTestId("add-attachments-button").click({ trial: true });
      await page.getByRole("tab", { name: /Creative Design/ }).click();
      for (const pill of await page
        .getByTestId("agent-pill-bar")
        .getByRole("tab")
        .all()) {
        await pill.scrollIntoViewIfNeeded();
        await expectWithinViewport(pill, viewport.height, headerBand);
      }
    }
  });

  async function verifyComposerChoiceLayout(
    page: Page,
    viewport: { width: number; height: number },
  ) {
    mockRecentThreads(page, 3);
    await page.route("**/api/models", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          models: [
            {
              id: "model-alpha",
              name: "model-alpha",
              model: "alpha",
              display_name: "Model Alpha",
            },
            {
              id: "model-bravo",
              name: "model-bravo",
              model: "bravo",
              display_name: "Model Bravo",
            },
          ],
          token_usage: { enabled: false },
        }),
      }),
    );
    await page.addInitScript(() => {
      class MockSpeechRecognition {
        continuous = false;
        interimResults = false;
        lang = "en-US";
        maxAlternatives = 1;
        onend: (() => void) | null = null;
        onerror: (() => void) | null = null;
        onresult: (() => void) | null = null;
        start() {}
        stop() {
          this.onend?.();
        }
        abort() {
          this.onend?.();
        }
      }
      Object.defineProperty(window, "SpeechRecognition", {
        configurable: true,
        value: MockSpeechRecognition,
      });
    });

    await page.setViewportSize(viewport);
    await page.goto("/workspace/chats/new");
    await expect(page.locator(".workbench-recent-tasks")).toBeVisible();
    const initialLayout = await readWelcomeLayout(page);
    await expectDisclaimerAtPageBottom(page);

    const modelTrigger = page.getByTestId("model-selector-trigger");
    await modelTrigger.focus();
    await modelTrigger.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await expectWelcomeLayoutUnchanged(
      page,
      initialLayout,
      "keyboard model picker",
    );
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expectWelcomeLayoutUnchanged(
      page,
      initialLayout,
      "closing model picker",
    );

    const currentModel = await modelTrigger.innerText();
    const nextModel = currentModel.includes("Model Alpha")
      ? "Model Bravo"
      : "Model Alpha";
    await modelTrigger.click();
    await page.getByRole("option", { name: new RegExp(nextModel) }).click();
    await expect(modelTrigger).toContainText(nextModel);
    await expectWelcomeLayoutUnchanged(page, initialLayout, "model selection");

    const skillTrigger = page.getByTestId("skill-selector-trigger");
    await skillTrigger.click();
    await expect(page.getByTestId("slash-overlay")).toBeVisible();
    await expectWelcomeLayoutUnchanged(
      page,
      initialLayout,
      "skill picker overlay",
    );
    await page
      .getByTestId("slash-overlay")
      .getByTestId("slash-option-frontend-design")
      .click();
    await expect(
      page.getByRole("button", { name: "Remove /frontend-design" }),
    ).toBeVisible();
    await expectWelcomeLayoutUnchanged(
      page,
      initialLayout,
      "mouse skill selection",
    );
    await page.getByRole("button", { name: "Remove /frontend-design" }).click();

    const keyboardInput = page.getByTestId("chat-input");
    await keyboardInput.fill("/data");
    await expect(page.getByTestId("slash-option-data-analysis")).toBeVisible();
    await keyboardInput.press("Enter");
    await expect(
      page.getByRole("button", { name: "Remove /data-analysis" }),
    ).toBeVisible();
    const composerText = page.getByTestId("input-box").getByRole("textbox");
    await expectWelcomeLayoutUnchanged(
      page,
      initialLayout,
      "keyboard skill selection",
    );
    await page.getByRole("button", { name: "Remove /data-analysis" }).click();
    await composerText.fill("");

    await page.getByRole("tab", { name: /Creative Design/ }).click();
    await expect(page.getByTestId("agent-pill-bar")).toBeVisible();
    await expectWelcomeLayoutUnchanged(page, initialLayout, "scenario change");

    const agentPill = page
      .getByTestId("agent-pill-bar")
      .getByRole("tab")
      .first();
    await agentPill.click();
    await expect(page.getByTestId("task-chip-bar")).toBeVisible();
    await expectWelcomeLayoutUnchanged(page, initialLayout, "agent selection");
    const agentSelectedLayout = await readWelcomeLayout(page);

    await page.getByTestId("task-chip-bar").getByRole("tab").first().click();
    await composerText.fill("");
    await expectWelcomeLayoutUnchanged(
      page,
      agentSelectedLayout,
      "task selection",
    );
    const taskSelectedLayout = await readWelcomeLayout(page);

    const voiceInput = page.getByTestId("voice-input-button");
    await expect(voiceInput).toBeVisible();
    await voiceInput.click();
    await expect(voiceInput).toHaveAttribute("aria-pressed", "true");
    await expectWelcomeLayoutUnchanged(page, taskSelectedLayout, "voice input");
    await voiceInput.click();

    await composerText.fill("A focused draft");
    await expectWelcomeLayoutUnchanged(page, taskSelectedLayout, "input focus");
  }

  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 375, height: 812 },
  ]) {
    test(`keeps welcome modules stable at ${viewport.width}px while composer choices change`, async ({
      page,
    }) => {
      await verifyComposerChoiceLayout(page, viewport);
    });
  }

  test("keeps the full conversation list working", async ({ page }) => {
    // Criterion 4: besides the sidebar, the full list page must keep
    // rendering history after the welcome-home retirements.
    mockRecentThreads(page, 3);
    await page.goto("/workspace/chats");
    const listMain = page.locator("main.workbench-body");
    await expect(listMain).toBeVisible({ timeout: 15_000 });
    for (const title of ["Recent work 1", "Recent work 2", "Recent work 3"]) {
      await expect(listMain.getByText(title)).toBeVisible();
    }
  });

  test("shows pills when scenario tab is selected", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await page.getByRole("tab", { name: /Creative Design/ }).click();
    await expect(page.getByTestId("agent-pill-bar")).toBeVisible();
    const pills = page.getByTestId("agent-pill-bar").getByRole("tab");
    await expect(pills).toHaveCount(5);
  });

  test("shows chips when pill is selected", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /Creative Design/, /PPT 制作/);
    await expect(page.getByTestId("task-chip-bar")).toBeVisible();
    const chips = page.getByTestId("task-chip-bar").getByRole("tab");
    await expect(chips).toHaveCount(3);
  });

  test("keeps closure-filtered skill invocation while an Agent Pill is selected", async ({
    page,
  }) => {
    // The pill resolves to the ppt-web canonical agent. Seed its closure
    // (anthropic-pptx) plus an out-of-closure skill to prove the panel only
    // offers what the expert owns (skill_outside_agent_closure otherwise).
    mockLangGraphAPI(page, {
      agents: [
        {
          name: "ppt-web",
          description: "PPT agent",
          skills: ["anthropic-pptx"],
        },
      ],
      skills: [
        {
          name: "anthropic-pptx",
          description: "Create PPT decks.",
          category: "public" as const,
          enabled: true,
        },
        {
          name: "data-analysis",
          description: "Analyze structured data and produce charts.",
          category: "public" as const,
          enabled: true,
        },
      ],
    });
    await page.goto("/workspace/chats/new");
    await page.getByRole("tab", { name: /Creative Design/ }).click();
    await expect(page.getByTestId("agent-pill-bar")).toBeVisible();
    // The published agent detail carries the closure the panel filters by.
    const publishedDetail = page.waitForResponse((response) =>
      /\/api\/resources\/.+\/published/.test(response.url()),
    );
    await page.getByRole("tab", { name: /PPT 制作/ }).click();
    await publishedDetail;

    // The entry stays available inside the expert session...
    await expect(page.getByTestId("skill-selector-trigger")).toBeVisible();
    const textarea = page.getByTestId("chat-input");
    await textarea.click();
    await textarea.pressSequentially("/");

    // ...and the panel opens showing only the Agent closure's skills.
    await expect(page.getByTestId("slash-overlay")).toBeVisible();
    await expect(page.getByTestId("slash-option-anthropic-pptx")).toBeVisible();
    await expect(page.getByTestId("slash-option-data-analysis")).toHaveCount(0);
  });

  test("keeps the caret after newly typed text when an Agent Pill is selected", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /Creative Design/, /PPT 制作/);

    const textarea = page.locator("textarea[name='message']");
    await textarea.click();
    await textarea.pressSequentially("abc");

    await expect(textarea).toHaveValue("abc");
    await expect
      .poll(() =>
        textarea.evaluate((element: HTMLTextAreaElement) => ({
          start: element.selectionStart,
          end: element.selectionEnd,
        })),
      )
      .toEqual({ start: 3, end: 3 });
  });

  test("injects prompt template when chip is clicked", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /Creative Design/, /PPT 制作/);
    await page.getByRole("tab", { name: /网页 PPT/ }).click();
    const textarea = page.locator("textarea[name='message']");
    await expect(textarea).toBeVisible({ timeout: 15_000 });
    await expect(textarea).toHaveValue(/请制作一套网页 PPT/);
    await expect
      .poll(() =>
        textarea.evaluate((el: HTMLTextAreaElement) =>
          el.value.substring(el.selectionStart, el.selectionEnd),
        ),
      )
      .toMatch(/^\[[^\]]+\]$/);
    const selection = await textarea.evaluate((el: HTMLTextAreaElement) => ({
      start: el.selectionStart,
      end: el.selectionEnd,
      text: el.value.substring(el.selectionStart, el.selectionEnd),
    }));
    expect(selection.text).toMatch(/^\[[^\]]+\]$/);
  });

  test("selects the meeting-minutes summary template without duplicate keys", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /Creative Design/, /创意探索/);
    await expect(
      page.getByTestId("task-chip-bar").getByRole("tab"),
    ).toHaveCount(3);
    await page.getByRole("tab", { name: /深度追问/ }).click();

    await expect(page.locator("textarea[name='message']")).toHaveValue(
      /方案进行深度追问/,
    );
    expect(
      consoleErrors.some((error) =>
        error.includes("two children with the same key"),
      ),
    ).toBe(false);
  });

  test("deselects chip when clicked again", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /Creative Design/, /PPT 制作/);
    await page.getByRole("tab", { name: /网页 PPT/ }).click();
    await page.getByRole("tab", { name: /网页 PPT/ }).click();
    await expect(page.getByRole("tab", { name: /网页 PPT/ })).toHaveAttribute(
      "data-state",
      "inactive",
    );
  });

  test("submits the selected Agent and Task runtime context", async ({
    page,
  }) => {
    let submittedContext: Record<string, unknown> | undefined;
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().endsWith("/runs/stream")
      ) {
        submittedContext = request.postDataJSON()?.context;
      }
    });

    // The scenario binding resolves the selected pill to a canonical agent
    // resource and validates the task's skill against the agent closure, so
    // the mock must seed both.
    mockLangGraphAPI(page, {
      agents: [
        {
          name: "code-dev",
          description: "Professional coding agent",
          skills: ["implement"],
        },
      ],
      skills: [
        {
          name: "implement",
          description: "Implement from a specification",
          category: "public" as const,
          license: null,
          enabled: true,
        },
      ],
    });
    await page.goto("/workspace/chats/new?agent=code-dev");
    await expect(page.getByTestId("task-chip-bar")).toBeVisible();
    await page.getByRole("tab", { name: /按规格实现/ }).click();

    await page.locator("textarea[name='message']").fill("implement the spec");
    await page.getByRole("button", { name: "Submit" }).click();

    await expect
      .poll(() => submittedContext)
      .toMatchObject({
        scenario_id: "professional",
        agent_name: "code-dev",
        skill_name: "implement",
        task_id: "spec-implementation",
      });
  });

  test("creative tab shows 5 pills including meta skills", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await page.getByRole("tab", { name: /Creative Design/ }).click();
    const pills = page.getByTestId("agent-pill-bar").getByRole("tab");
    await expect(pills).toHaveCount(5);
    await expect(page.getByRole("tab", { name: /创意探索/ })).toBeVisible();
    await expect(page.getByRole("tab", { name: /技能工坊/ })).toBeVisible();
  });

  test("shows conflict dialog when input is non-empty", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    const textarea = page.locator("textarea[name='message']");
    await textarea.fill("已有内容");
    await selectAgent(page, /Creative Design/, /PPT 制作/);
    await page.getByRole("tab", { name: /网页 PPT/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Send suggestion?")).toBeVisible();
  });
});
