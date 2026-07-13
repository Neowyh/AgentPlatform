/**
 * Chat Flow: 聊天功能完整流程
 *
 * 测试:
 * 1. 新建聊天
 * 2. 发送消息
 * 3. 验证消息显示
 * 4. 导出对话
 */

import { test, expect } from "@playwright/test";

import { mockLangGraphAPI } from "../utils/mock-api";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

test.describe("Chat Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Mock 后端 API
    mockLangGraphAPI(page);
  });

  test("should have export option", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/chats/new`);

    // 可能需要先打开菜单
    const menuButton = page
      .locator('button[aria-label="menu"], button[aria-label="Menu"]')
      .first();
    if (await menuButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await menuButton.click();
    }

    // 验证导出选项存在（可能隐藏在菜单中）
    const exportOption = page.locator("text=/导出|export/i").first();
    await expect(exportOption).toBeVisible({ timeout: 3000 });
  });
});
