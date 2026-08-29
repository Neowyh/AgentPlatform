import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

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
    await page.getByRole("tab", { name: /日常办公/ }).click();
    await page.getByRole("tab", { name: /办公文档/ }).click();
    await expect(page.getByTestId("task-chip-bar")).toBeVisible();
    const chips = page.getByTestId("task-chip-bar").getByRole("tab");
    await expect(chips).toHaveCount(3);
  });

  test("injects prompt template when chip is clicked", async ({ page }) => {
    mockLangGraphAPI(page);
    await page.goto("/workspace/chats/new");
    await page.getByRole("tab", { name: /日常办公/ }).click();
    await page.getByRole("tab", { name: /办公文档/ }).click();
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
    await page.getByRole("tab", { name: /日常办公/ }).click();
    await page.getByRole("tab", { name: /智能摘要/ }).click();
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
    await page.getByRole("tab", { name: /日常办公/ }).click();
    await page.getByRole("tab", { name: /办公文档/ }).click();
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
    await page
      .getByRole("tab", { name: /专业任务|Professional Tasks/ })
      .click();
    await page.getByRole("tab", { name: /代码开发|Code Development/ }).click();
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
    await page.getByRole("tab", { name: /日常办公/ }).click();
    await page.getByRole("tab", { name: /办公文档/ }).click();
    await page.getByRole("tab", { name: /Word 创建编辑/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("发送建议问题？")).toBeVisible();
  });
});
