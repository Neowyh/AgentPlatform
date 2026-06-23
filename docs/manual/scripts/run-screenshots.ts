/**
 * 独立截图生成脚本
 *
 * 使用方法:
 *   cd docs/manual/scripts
 *   npx playwright test run-screenshots.ts --config=playwright-standalone.config.ts
 */

import { test, type Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const SCREENSHOT_DIR = path.resolve(__dirname, "../screenshots");
const BASE_URL = process.env.BASE_URL || "http://localhost:3000";

// 确保输出目录存在
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

interface ScreenshotConfig {
  name: string;
  url: string;
  waitFor?: string;
  actions?: (page: Page) => Promise<void>;
  viewport?: { width: number; height: number };
}

const screenshots: ScreenshotConfig[] = [
  // ─── 认证 ───────────────────────────────────────────────
  {
    name: "01-login-page",
    url: "/login",
    waitFor: 'input[name="email"]',
  },
  {
    name: "02-setup-admin",
    url: "/setup",
    waitFor: 'input[name="email"]',
  },

  // ─── 工作空间 - 聊天 ─────────────────────────────────────
  {
    name: "03-workspace-welcome",
    url: "/workspace/chats/new",
    waitFor: '[data-testid="welcome"]',
  },
  {
    name: "04-workspace-chat",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("你好，请介绍一下 iDeer 平台的核心功能");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="message-ai"]', {
        timeout: 60000,
      });
      await page.waitForTimeout(3000);
    },
  },
  {
    name: "05-sidebar-expanded",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const toggle = page.locator('[data-testid="sidebar-toggle"]');
      if (await toggle.isVisible()) {
        await toggle.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "06-sidebar-collapsed",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const toggle = page.locator('[data-testid="sidebar-toggle"]');
      if (await toggle.isVisible()) {
        await toggle.click();
        await page.waitForTimeout(500);
      }
    },
  },

  // ─── 模型与模式选择 ─────────────────────────────────────
  {
    name: "07-model-selector",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const trigger = page.locator('[data-testid="model-selector-trigger"]');
      if (await trigger.isVisible()) {
        await trigger.click();
        await page.waitForSelector('[data-testid="model-selector-dialog"]', {
          timeout: 5000,
        });
      }
    },
  },
  {
    name: "08-mode-flash",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible()) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const flash = page.locator('text="Flash"').first();
        if (await flash.isVisible()) await flash.click();
      }
    },
  },
  {
    name: "09-mode-thinking",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible()) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const thinking = page.locator('text="Thinking"').first();
        if (await thinking.isVisible()) await thinking.click();
      }
    },
  },
  {
    name: "10-mode-pro",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible()) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const pro = page.locator('text="Pro"').first();
        if (await pro.isVisible()) await pro.click();
      }
    },
  },
  {
    name: "11-mode-ultra",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible()) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const ultra = page.locator('text="Ultra"').first();
        if (await ultra.isVisible()) await ultra.click();
      }
    },
  },

  // ─── 文件处理 ──────────────────────────────────────────
  {
    name: "12-file-upload",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const fileInput = page.locator('input[type="file"]');
      if ((await fileInput.count()) > 0) {
        const testFile = path.join(SCREENSHOT_DIR, "test-upload.txt");
        fs.writeFileSync(testFile, "This is a test file for screenshot.");
        await fileInput.setInputFiles(testFile);
        await page.waitForTimeout(1000);
        fs.unlinkSync(testFile);
      }
    },
  },
  {
    name: "13-file-preview",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const fileInput = page.locator('input[type="file"]');
      if ((await fileInput.count()) > 0) {
        const testFile = path.join(SCREENSHOT_DIR, "test-preview.txt");
        fs.writeFileSync(testFile, "This is a test file for preview screenshot.");
        await fileInput.setInputFiles(testFile);
        await page.waitForSelector('[data-testid="file-preview"]', {
          timeout: 5000,
        }).catch(() => {});
        await page.waitForTimeout(1000);
        fs.unlinkSync(testFile);
      }
    },
  },

  // ─── 工件 ─────────────────────────────────────────────
  {
    name: "14-artifacts-panel",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("用 Python 写一个快速排序算法，保存为文件");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="artifacts-trigger"]', {
        timeout: 120000,
      });
      await page.click('[data-testid="artifacts-trigger"]');
      await page.waitForTimeout(1000);
    },
  },
  {
    name: "15-artifacts-detail",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("用 Python 写一个Hello World程序");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="artifacts-trigger"]', {
        timeout: 120000,
      });
      await page.click('[data-testid="artifacts-trigger"]');
      await page.waitForTimeout(2000);
    },
  },

  // ─── 思维链与引用 ────────────────────────────────────────
  {
    name: "16-thinking-process",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible()) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const pro = page.locator('text="Pro"').first();
        if (await pro.isVisible()) await pro.click();
      }
      const textarea = page.locator("textarea").first();
      await textarea.fill("分析一下微服务架构的优缺点");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="chain-of-thought"]', {
        timeout: 60000,
      });
      await page.waitForTimeout(2000);
    },
  },
  {
    name: "17-task-decomposition",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("帮我创建一个React项目，包含用户登录功能");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="task-decomposition"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: "18-tool-call",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("搜索一下最新的AI技术趋势");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="tool-call"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: "19-sources-citation",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("什么是微服务架构？");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="sources"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: "20-followup-suggestions",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("什么是 RESTful API？");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="suggestion"]', {
        timeout: 60000,
      });
      await page.waitForTimeout(1000);
    },
  },

  // ─── Agent ────────────────────────────────────────────
  {
    name: "21-agents-gallery",
    url: "/workspace/agents",
    waitFor: '[data-testid="agent-gallery"]',
  },
  {
    name: "22-agent-create",
    url: "/workspace/agents/new",
    waitFor: 'input[name="name"]',
  },
  {
    name: "23-agent-edit",
    url: "/workspace/agents",
    actions: async (page) => {
      // 点击第一个 Agent 的编辑按钮
      const editBtn = page.locator('[data-testid="agent-edit"]').first();
      if (await editBtn.isVisible()) {
        await editBtn.click();
        await page.waitForTimeout(1000);
      }
    },
  },
  {
    name: "24-agent-chat",
    url: "/workspace/agents",
    actions: async (page) => {
      // 点击第一个 Agent 的聊天按钮
      const chatBtn = page.locator('[data-testid="agent-chat"]').first();
      if (await chatBtn.isVisible()) {
        await chatBtn.click();
        await page.waitForTimeout(1000);
      }
    },
  },

  // ─── 工作流 ───────────────────────────────────────────
  {
    name: "25-workflows-gallery",
    url: "/workspace/workflows",
    waitFor: '[data-testid="workflow-gallery"]',
  },
  {
    name: "26-workflow-create",
    url: "/workspace/workflows/new",
    waitFor: 'input[name="name"]',
  },
  {
    name: "27-workflow-editor",
    url: "/workspace/workflows/new",
    actions: async (page) => {
      // 填写工作流名称
      const nameInput = page.locator('input[name="name"]');
      if (await nameInput.isVisible()) {
        await nameInput.fill("测试工作流");
      }
      await page.waitForTimeout(1000);
    },
  },
  {
    name: "28-workflow-run",
    url: "/workspace/workflows",
    actions: async (page) => {
      // 点击第一个工作流的运行按钮
      const runBtn = page.locator('[data-testid="workflow-run"]').first();
      if (await runBtn.isVisible()) {
        await runBtn.click();
        await page.waitForTimeout(2000);
      }
    },
  },
  {
    name: "29-workflow-human-review",
    url: "/workspace/workflows",
    actions: async (page) => {
      // 点击第一个工作流查看详情
      const workflowItem = page.locator('[data-testid="workflow-item"]').first();
      if (await workflowItem.isVisible()) {
        await workflowItem.click();
        await page.waitForTimeout(1000);
      }
    },
  },

  // ─── 设置 ─────────────────────────────────────────────
  {
    name: "30-settings-account",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const settingsBtn = page.locator('[data-testid="settings-trigger"]');
      if (await settingsBtn.isVisible()) {
        await settingsBtn.click();
        await page.waitForSelector('[data-testid="settings-dialog"]', {
          timeout: 5000,
        });
      }
    },
  },
  {
    name: "31-settings-appearance",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const settingsBtn = page.locator('[data-testid="settings-trigger"]');
      if (await settingsBtn.isVisible()) {
        await settingsBtn.click();
        await page.waitForSelector('[data-testid="settings-dialog"]', {
          timeout: 5000,
        });
        const tab = page.locator('text="Appearance"').first();
        if (await tab.isVisible()) await tab.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "32-settings-memory",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const settingsBtn = page.locator('[data-testid="settings-trigger"]');
      if (await settingsBtn.isVisible()) {
        await settingsBtn.click();
        await page.waitForSelector('[data-testid="settings-dialog"]', {
          timeout: 5000,
        });
        const tab = page.locator('text="Memory"').first();
        if (await tab.isVisible()) await tab.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "33-settings-skills",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const settingsBtn = page.locator('[data-testid="settings-trigger"]');
      if (await settingsBtn.isVisible()) {
        await settingsBtn.click();
        await page.waitForSelector('[data-testid="settings-dialog"]', {
          timeout: 5000,
        });
        const tab = page.locator('text="Skills"').first();
        if (await tab.isVisible()) await tab.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "34-settings-tools",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const settingsBtn = page.locator('[data-testid="settings-trigger"]');
      if (await settingsBtn.isVisible()) {
        await settingsBtn.click();
        await page.waitForSelector('[data-testid="settings-dialog"]', {
          timeout: 5000,
        });
        const tab = page.locator('text="Tools"').first();
        if (await tab.isVisible()) await tab.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "35-settings-notification",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const settingsBtn = page.locator('[data-testid="settings-trigger"]');
      if (await settingsBtn.isVisible()) {
        await settingsBtn.click();
        await page.waitForSelector('[data-testid="settings-dialog"]', {
          timeout: 5000,
        });
        const tab = page.locator('text="Notifications"').first();
        if (await tab.isVisible()) await tab.click();
        await page.waitForTimeout(500);
      }
    },
  },

  // ─── 管理后台 ──────────────────────────────────────────
  {
    name: "35-admin-dashboard",
    url: "/workspace/admin",
    waitFor: '[data-testid="admin-stats"]',
  },
  {
    name: "36-admin-users",
    url: "/workspace/admin/users",
    waitFor: '[data-testid="user-list"]',
  },
  {
    name: "37-admin-user-edit",
    url: "/workspace/admin/users",
    actions: async (page) => {
      // 点击第一个用户的编辑按钮
      const editBtn = page.locator('[data-testid="user-edit"]').first();
      if (await editBtn.isVisible()) {
        await editBtn.click();
        await page.waitForTimeout(1000);
      }
    },
  },
  {
    name: "38-admin-departments",
    url: "/workspace/admin/departments",
    waitFor: '[data-testid="department-list"]',
  },
  {
    name: "39-admin-tools",
    url: "/workspace/admin/tools",
    waitFor: '[data-testid="tool-list"]',
  },

  // ─── 快捷操作 ──────────────────────────────────────────
  {
    name: "40-command-palette",
    url: "/workspace/chats/new",
    actions: async (page) => {
      await page.keyboard.press("Meta+k");
      await page.waitForSelector('[data-testid="command-palette"]', {
        timeout: 5000,
      });
    },
  },
  {
    name: "41-export-markdown",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("你好");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="message-ai"]', {
        timeout: 60000,
      });
      const exportBtn = page.locator('[data-testid="export-trigger"]');
      if (await exportBtn.isVisible()) {
        await exportBtn.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "42-export-json",
    url: "/workspace/chats/new",
    actions: async (page) => {
      const textarea = page.locator("textarea").first();
      await textarea.fill("你好");
      await textarea.press("Enter");
      await page.waitForSelector('[data-testid="message-ai"]', {
        timeout: 60000,
      });
      const exportBtn = page.locator('[data-testid="export-trigger"]');
      if (await exportBtn.isVisible()) {
        await exportBtn.click();
        await page.waitForTimeout(500);
        // 选择 JSON 导出
        const jsonOption = page.locator('text="JSON"').first();
        if (await jsonOption.isVisible()) await jsonOption.click();
      }
    },
  },
  {
    name: "43-thread-rename",
    url: "/workspace/chats/new",
    actions: async (page) => {
      // 点击侧边栏中的对话
      const threadItem = page.locator('[data-testid="thread-item"]').first();
      if (await threadItem.isVisible()) {
        await threadItem.click({ button: "right" });
        await page.waitForTimeout(500);
        const renameBtn = page.locator('text="Rename"').first();
        if (await renameBtn.isVisible()) await renameBtn.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "44-thread-delete",
    url: "/workspace/chats/new",
    actions: async (page) => {
      // 点击侧边栏中的对话
      const threadItem = page.locator('[data-testid="thread-item"]').first();
      if (await threadItem.isVisible()) {
        await threadItem.click({ button: "right" });
        await page.waitForTimeout(500);
        const deleteBtn = page.locator('text="Delete"').first();
        if (await deleteBtn.isVisible()) await deleteBtn.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "45-error-state",
    url: "/workspace/chats/new",
    actions: async (page) => {
      // 触发一个错误状态
      const textarea = page.locator("textarea").first();
      await textarea.fill("/invalid-command");
      await textarea.press("Enter");
      await page.waitForTimeout(2000);
    },
  },
];

// ─── 测试生成 ─────────────────────────────────────────────
for (const config of screenshots) {
  test(`screenshot: ${config.name}`, async ({ page }) => {
    const viewport = config.viewport || { width: 1440, height: 900 };
    await page.setViewportSize(viewport);

    await page.goto(`${BASE_URL}${config.url}`, {
      waitUntil: "networkidle",
      timeout: 30000,
    });

    if (config.waitFor) {
      try {
        await page.waitForSelector(config.waitFor, { timeout: 15000 });
      } catch {
        console.warn(
          `⚠️  [${config.name}] 等待 "${config.waitFor}" 超时，继续截图`
        );
      }
    }

    if (config.actions) {
      try {
        await config.actions(page);
      } catch (e) {
        console.warn(`⚠️  [${config.name}] 操作执行失败: ${e}`);
      }
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, `${config.name}.png`),
      fullPage: false,
    });

    console.log(`✅ [${config.name}] 截图已保存`);
  });
}
