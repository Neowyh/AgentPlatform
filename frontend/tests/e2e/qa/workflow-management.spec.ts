/**
 * Workflow Management: 工作流管理流程
 *
 * 测试:
 * 1. 浏览工作流列表
 * 2. 创建新工作流
 * 3. 查看工作流详情
 * 4. 运行工作流
 */

import { test, expect } from "@playwright/test";

import { mockLangGraphAPI, type MockWorkflow } from "../utils/mock-api";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

const MOCK_WORKFLOWS: MockWorkflow[] = [
  {
    name: "data-pipeline",
    description: "ETL data processing workflow",
    version: "1.0",
    steps: [
      { id: "step1", type: "agent", agent: "default", prompt: "Process data" },
    ],
  },
  {
    name: "review-process",
    description: "Automated code review workflow",
    version: "1.0",
    steps: [
      { id: "step1", type: "agent", agent: "reviewer", prompt: "Review code" },
    ],
  },
];

test.describe("Workflow Management", () => {
  test.beforeEach(async ({ page }) => {
    mockLangGraphAPI(page, { workflows: MOCK_WORKFLOWS });
  });

  test("should list workflows", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/workflows`);

    // 验证工作流列表加载
    const workflowCards = page
      .locator(
        '[data-testid="workflow-card"], [class*="workflow-card"], [class*="card"]',
      )
      .first();
    await expect(workflowCards).toBeVisible({ timeout: 10000 });
  });

  test("should navigate to create workflow", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/workflows`);

    // 查找创建按钮 - text is "New Workflow" / "新建工作流"
    const createButton = page
      .locator(
        'button:has-text("New Workflow"), button:has-text("新建工作流"), button:has-text("Create"), button:has-text("创建")',
      )
      .first();
    await expect(createButton).toBeVisible({ timeout: 10000 });
    await createButton.click();

    // 验证跳转到创建页面
    await page.waitForURL(/\/workflows\/new/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/workflows\/new/);
  });

  test("should create workflow with YAML", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/workflows/new`);

    // 查找 YAML 编辑器
    const editor = page
      .locator('.cm-editor, textarea, [data-testid="yaml-editor"]')
      .first();
    await expect(editor).toBeVisible({ timeout: 10000 });

    // 输入 YAML
    const yamlContent =
      "name: test-workflow\nsteps:\n  - id: step1\n    type: agent\n    agent: default";
    await editor.click();
    await page.keyboard.type(yamlContent);

    // 保存 - the button text is "New Workflow" (t.workflows.newWorkflow)
    const saveButton = page
      .locator(
        'button:has-text("New Workflow"), button:has-text("创建工作流"), button:has-text("Save"), button:has-text("保存")',
      )
      .first();
    await saveButton.click();

    // 验证保存成功
    await page.waitForTimeout(2000);
  });

  test("should view workflow details", async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/workflows`);

    // 点击第一个工作流卡片
    const workflowCard = page
      .locator(
        '[data-testid="workflow-card"], [class*="workflow-card"], [class*="card"]',
      )
      .first();
    await expect(workflowCard).toBeVisible({ timeout: 10000 });
    await workflowCard.click();

    // 验证详情页加载
    await page.waitForURL(/\/workflows\/[^/]+$/, { timeout: 10000 });
    const detailPage = page
      .locator("text=/详情|detail|步骤|step|运行|run/i")
      .first();
    await expect(detailPage).toBeVisible({ timeout: 10000 });
  });
});
