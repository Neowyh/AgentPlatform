import { expect, test, type Page } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

async function selectAgent(page: Page, scenario: RegExp, agent: RegExp) {
  await page.getByRole("tab", { name: scenario }).click();
  await expect(page.getByTestId("agent-pill-bar")).toBeVisible();
  await page.getByRole("tab", { name: agent }).click();
}

test.describe("WorkBuddy cascade bar", () => {
  test("shows three scenario tabs in welcome mode", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await expect(page.getByTestId("scenario-tabs")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("tab", { name: /日常办公/ })).toBeVisible();
    await expect(page.getByRole("tab", { name: /创意设计/ })).toBeVisible();
    await expect(page.getByRole("tab", { name: /专业任务/ })).toBeVisible();
  });

  test("shows the task-first welcome hierarchy", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await expect(page.getByTestId("workbench-home")).toBeVisible();
    await expect(page.getByText("iDeer，落地你的idea")).toBeVisible();
    await expect(page.getByTestId("workbench-quick-entries")).toBeVisible();
    await expect(page.getByText("方向不明？")).toBeVisible();
    await expect(page.getByText("目标明确？")).toBeVisible();
  });

  test("shows pills when scenario tab is selected", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await page.getByRole("tab", { name: /日常办公/ }).click();
    await expect(page.getByTestId("agent-pill-bar")).toBeVisible();
    const pills = page.getByTestId("agent-pill-bar").getByRole("tab");
    await expect(pills).toHaveCount(5);
  });

  test("shows chips when pill is selected", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /日常办公/, /办公文档/);
    await expect(page.getByTestId("task-chip-bar")).toBeVisible();
    const chips = page.getByTestId("task-chip-bar").getByRole("tab");
    await expect(chips).toHaveCount(3);
  });

  test("disables skill invocation while an Agent Pill is selected", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(page, /日常办公/, /办公文档/);

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
    await selectAgent(page, /日常办公/, /办公文档/);

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
    await selectAgent(page, /日常办公/, /办公文档/);
    await page.getByRole("tab", { name: /Word 创建编辑/ }).click();
    const textarea = page.locator("textarea[name='message']");
    await expect(textarea).toBeVisible({ timeout: 15_000 });
    await expect(textarea).toHaveValue(/请帮我处理以下 Word 文档/);
    const selection = await textarea.evaluate((el: HTMLTextAreaElement) => ({
      start: el.selectionStart,
      end: el.selectionEnd,
      text: el.value.substring(el.selectionStart, el.selectionEnd),
    }));
    expect(selection.text).toBe("[描述需求]");
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
    await selectAgent(page, /日常办公/, /智能摘要/);
    await expect(
      page.getByTestId("task-chip-bar").getByRole("tab"),
    ).toHaveCount(3);
    await page.getByRole("tab", { name: /会议纪要/ }).click();

    await expect(page.locator("textarea[name='message']")).toHaveValue(
      /会议记录/,
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
    await selectAgent(page, /日常办公/, /办公文档/);
    await page.getByRole("tab", { name: /Word 创建编辑/ }).click();
    await page.getByRole("tab", { name: /Word 创建编辑/ }).click();
    await expect(
      page.getByRole("tab", { name: /Word 创建编辑/ }),
    ).toHaveAttribute("data-state", "inactive");
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

    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await selectAgent(
      page,
      /专业任务|Professional Tasks/,
      /代码开发|Code Development/,
    );
    await page.getByRole("tab", { name: /按规格实现/ }).click();

    await page.locator("textarea[name='message']").press("Enter");

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
    await page.getByRole("tab", { name: /创意设计/ }).click();
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
    await selectAgent(page, /日常办公/, /办公文档/);
    await page.getByRole("tab", { name: /Word 创建编辑/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("发送建议问题？")).toBeVisible();
  });
});
