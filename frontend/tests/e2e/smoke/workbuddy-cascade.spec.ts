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

      for (const locator of [
        input,
        page.getByTestId("scenario-tabs"),
        page.getByRole("tab", { name: /Daily Office/ }),
      ]) {
        await locator.evaluate((element) => {
          element.scrollIntoView({ block: "center" });
        });
        await expectWithinViewport(locator, viewport.height, headerBand);
      }
    }
  });

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

  test("disables skill invocation while an Agent Pill is selected", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /Creative Design/, /PPT 制作/);

    await expect(page.getByTestId("skill-selector-trigger")).not.toBeVisible();
    const textarea = page.getByTestId("chat-input");
    await textarea.fill("/");
    await textarea.press("Space");
    await textarea.press("Backspace");
    await expect(page.getByTestId("slash-overlay")).not.toBeVisible();
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
