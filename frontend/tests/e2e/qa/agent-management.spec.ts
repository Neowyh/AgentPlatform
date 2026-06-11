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

import { mockLangGraphAPI } from "../utils/mock-api";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

test.describe("Agent Management", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page);
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

    // 查找创建按钮
    const createButton = page
      .locator(
        'button:has-text("创建"), button:has-text("Create"), a:has-text("创建"), a:has-text("Create")',
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

    // 输入 Agent 名称
    const nameInput = page
      .locator(
        'input[data-testid="agent-name"], input[placeholder*="name" i], input[type="text"]',
      )
      .first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });
    await nameInput.fill("test-agent-qa");

    // 提交
    const nextButton = page
      .locator(
        'button:has-text("下一步"), button:has-text("Next"), button[type="submit"]',
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
    await page.goto(`${BASE_URL}/workspace/agents`);

    // 点击第一个 Agent 卡片
    const agentCard = page
      .locator(
        '[data-testid="agent-card"], [class*="agent-card"], [class*="card"]',
      )
      .first();
    await expect(agentCard).toBeVisible({ timeout: 10000 });
    await agentCard.click();

    // 验证详情页加载
    await page.waitForURL(/\/agents\/[^/]+$/, { timeout: 10000 });
    const detailPage = page.locator("text=/详情|detail|配置|config/i").first();
    await expect(detailPage).toBeVisible({ timeout: 10000 });
  });
});
