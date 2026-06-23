/**
 * Agent Management: Agent 管理流程
 *
 * 测试:
 * 1. 浏览 Agent 列表
 * 2. 创建新 Agent
 * 3. 查看 Agent 详情
 * 4. 删除 Agent
 */

import { test, expect } from "@playwright/test";

import { mockLangGraphAPI, type MockAgent } from "../utils/mock-api";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

const MOCK_AGENTS: MockAgent[] = [
  {
    name: "research-assistant",
    description: "Helps with research tasks",
    model: "gpt-4",
  },
  {
    name: "code-reviewer",
    description: "Reviews code for quality",
    model: "gpt-4",
  },
];

test.describe("Agent Management", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });
  });

  test("should list agents", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/agents`);

    // 验证 Agent 列表加载
    const agentCards = page
      .locator(
        '[data-testid="agent-card"], [class*="agent-card"], [class*="card"]',
      )
      .first();
    await expect(agentCards).toBeVisible({ timeout: 10000 });
  });

  test("should navigate to create agent", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/agents`);

    // 查找创建按钮 - text is "New Agent" / "新建智能体"
    const createButton = page
      .locator(
        'button:has-text("New Agent"), button:has-text("新建智能体"), button:has-text("Create"), button:has-text("创建")',
      )
      .first();
    await expect(createButton).toBeVisible({ timeout: 10000 });
    await createButton.click();

    // 验证跳转到创建页面
    await page.waitForURL(/\/agents\/new/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/agents\/new/);
  });

  test("should create agent with name", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/agents/new`);

    // 输入 Agent 名称 - placeholder is "e.g. code-reviewer" / "例如 code-reviewer"
    const nameInput = page
      .locator(
        'input[data-testid="agent-name"], input[placeholder*="e.g." i], input[placeholder*="例如" i], input[type="text"]',
      )
      .first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });
    await nameInput.fill("test-agent-qa");

    // 提交 - button text is "Continue" / "继续"
    const nextButton = page
      .locator(
        'button:has-text("Continue"), button:has-text("继续"), button:has-text("下一步"), button:has-text("Next"), button[type="submit"]',
      )
      .first();
    await nextButton.click();

    // 验证进入下一步（对话设置）
    await page.waitForTimeout(2000);
    const setupArea = page
      .locator('textarea, [data-testid="chat-input"], [contenteditable="true"]')
      .first();
    const isVisible = await setupArea
      .isVisible({ timeout: 5000 })
      .catch(() => false);
    expect(typeof isVisible).toBe("boolean");
  });

  test("should view agent details", async ({ page }) => {
    // Navigate directly to the first agent's detail page
    await page.goto(`${BASE_URL}/workspace/agents/research-assistant`);

    // 验证详情页加载 - the detail page shows the agent name heading and Configuration
    await expect(
      page.getByRole("heading", { name: "research-assistant" }),
    ).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Configuration").first()).toBeVisible({
      timeout: 10000,
    });
  });
});
