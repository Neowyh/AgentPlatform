/**
 * 剩余截图生成脚本
 *
 * 使用方法:
 *   cd frontend
 *   node ../docs/manual/scripts/capture-remaining.js
 */

const { chromium } = require(require.resolve('playwright', { paths: [process.cwd() + '/node_modules'] }));
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = path.resolve(__dirname, '../screenshots');
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

// 确保输出目录存在
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// 需要生成的截图列表
const screenshots = [
  // ─── 模型与模式选择 ─────────────────────────────────────
  {
    name: '07-model-selector',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const trigger = page.locator('[data-testid="model-selector-trigger"]');
      if (await trigger.isVisible()) {
        await trigger.click();
        await page.waitForSelector('[data-slot="dialog"]', {
          timeout: 5000,
        }).catch(() => {});
      }
    },
  },
  {
    name: '08-mode-flash',
    url: '/workspace/chats/new',
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
    name: '09-mode-thinking',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible()) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const thinking = page.locator('text="Reasoning"').first();
        if (await thinking.isVisible()) await thinking.click();
      }
    },
  },
  {
    name: '10-mode-pro',
    url: '/workspace/chats/new',
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
    name: '11-mode-ultra',
    url: '/workspace/chats/new',
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
    name: '12-file-upload',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const fileInput = page.locator('[data-testid="file-input"]');
      if ((await fileInput.count()) > 0) {
        const testFile = path.join(SCREENSHOT_DIR, 'test-upload.txt');
        fs.writeFileSync(testFile, 'This is a test file for screenshot.');
        await fileInput.setInputFiles(testFile);
        await page.waitForTimeout(1000);
        fs.unlinkSync(testFile);
      }
    },
  },
  {
    name: '13-file-preview',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const fileInput = page.locator('[data-testid="file-input"]');
      if ((await fileInput.count()) > 0) {
        const testFile = path.join(SCREENSHOT_DIR, 'test-preview.txt');
        fs.writeFileSync(testFile, 'This is a test file for preview screenshot.');
        await fileInput.setInputFiles(testFile);
        await page.waitForTimeout(2000);
        fs.unlinkSync(testFile);
      }
    },
  },

  // ─── 工件 ─────────────────────────────────────────────
  {
    name: '14-artifacts-panel',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('用 Python 写一个快速排序算法，保存为文件');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="artifact-trigger-button"]', {
        timeout: 120000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: '15-artifacts-detail',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('用 Python 写一个Hello World程序');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="artifact-trigger-button"]', {
        timeout: 120000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },

  // ─── 思维链与引用 ────────────────────────────────────────
  {
    name: '16-thinking-process',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible()) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const pro = page.locator('text="Pro"').first();
        if (await pro.isVisible()) await pro.click();
      }
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('分析一下微服务架构的优缺点');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="chain-of-thought"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: '17-task-decomposition',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('帮我创建一个React项目，包含用户登录功能');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="chain-of-thought-step"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: '18-tool-call',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('搜索一下最新的AI技术趋势');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="chain-of-thought-step"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: '19-sources-citation',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('什么是微服务架构？');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="sources-container"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(2000);
    },
  },
  {
    name: '20-followup-suggestions',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('什么是 RESTful API？');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="suggestions-container"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(1000);
    },
  },

  // ─── Agent ────────────────────────────────────────────
  {
    name: '23-agent-edit',
    url: '/workspace/agents',
    actions: async (page) => {
      // Agent 编辑是通过单独的路由，不是按钮
      // 直接导航到编辑页面
      const agentCard = page.locator('[data-testid="agent-card"]').first();
      if (await agentCard.isVisible()) {
        // 获取 agent 名称并导航到编辑页面
        await page.goto('/workspace/agents/new');
        await page.waitForTimeout(1000);
      }
    },
  },
  {
    name: '24-agent-chat',
    url: '/workspace/agents',
    actions: async (page) => {
      const chatBtn = page.locator('[data-testid="agent-chat-button"]').first();
      if (await chatBtn.isVisible()) {
        await chatBtn.click();
        await page.waitForTimeout(1000);
      }
    },
  },

  // ─── 工作流 ───────────────────────────────────────────
  {
    name: '27-workflow-editor',
    url: '/workspace/workflows/new',
    actions: async (page) => {
      // 工作流编辑器使用 CodeMirror，没有 name input
      // 直接截图编辑器界面
      await page.waitForTimeout(1000);
    },
  },
  {
    name: '28-workflow-run',
    url: '/workspace/workflows',
    actions: async (page) => {
      const runBtn = page.locator('[data-testid="workflow-run-button"]').first();
      if (await runBtn.isVisible()) {
        await runBtn.click();
        await page.waitForTimeout(2000);
      }
    },
  },
  {
    name: '29-workflow-human-review',
    url: '/workspace/workflows',
    actions: async (page) => {
      const workflowCard = page.locator('[data-testid="workflow-card"]').first();
      if (await workflowCard.isVisible()) {
        await workflowCard.click();
        await page.waitForTimeout(1000);
      }
    },
  },

  // ─── 设置 ─────────────────────────────────────────────
  {
    name: '35-settings-notification',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const navMenuTrigger = page.locator('[data-testid="nav-menu-trigger"]');
      if (await navMenuTrigger.isVisible()) {
        await navMenuTrigger.click();
        await page.waitForTimeout(300);
        const settingsMenuItem = page.locator('[data-testid="settings-menu-item"]');
        if (await settingsMenuItem.isVisible()) {
          await settingsMenuItem.click();
          await page.waitForSelector('[data-testid="settings-dialog"]', {
            timeout: 5000,
          }).catch(() => {});
          const tab = page.locator('[data-testid="settings-tab-notification"]');
          if (await tab.isVisible()) await tab.click();
          await page.waitForTimeout(500);
        }
      }
    },
  },

  // ─── 管理后台 ──────────────────────────────────────────
  {
    name: '37-admin-user-edit',
    url: '/workspace/admin/users',
    actions: async (page) => {
      // 用户管理使用角色选择器，不是编辑按钮
      // 直接截图用户列表
      await page.waitForTimeout(1000);
    },
  },

  // ─── 快捷操作 ──────────────────────────────────────────
  {
    name: '42-export-json',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('你好');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="ai-message"]', {
        timeout: 60000,
      }).catch(() => {});
      const exportBtn = page.locator('[data-testid="export-trigger-button"]');
      if (await exportBtn.isVisible()) {
        await exportBtn.click();
        await page.waitForTimeout(500);
        const jsonOption = page.locator('text="Export as JSON"').first();
        if (await jsonOption.isVisible()) await jsonOption.click();
      }
    },
  },
  {
    name: '43-thread-rename',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const threadActionsTrigger = page.locator('[data-testid="thread-actions-trigger"]').first();
      if (await threadActionsTrigger.isVisible()) {
        await threadActionsTrigger.hover();
        await page.waitForTimeout(300);
        await threadActionsTrigger.click();
        await page.waitForTimeout(300);
        const renameBtn = page.locator('[data-testid="thread-rename-action"]');
        if (await renameBtn.isVisible()) await renameBtn.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: '44-thread-delete',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const threadActionsTrigger = page.locator('[data-testid="thread-actions-trigger"]').first();
      if (await threadActionsTrigger.isVisible()) {
        await threadActionsTrigger.hover();
        await page.waitForTimeout(300);
        await threadActionsTrigger.click();
        await page.waitForTimeout(300);
        const deleteBtn = page.locator('[data-testid="thread-delete-action"]');
        if (await deleteBtn.isVisible()) await deleteBtn.click();
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: '45-error-state',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = page.locator('[data-testid="chat-input"]');
      await textarea.fill('/invalid-command');
      await textarea.press('Enter');
      await page.waitForTimeout(2000);
    },
  },
];

async function captureScreenshots() {
  console.log('🚀 开始生成截图...');
  console.log(`📁 输出目录: ${SCREENSHOT_DIR}`);
  console.log(`🌐 目标地址: ${BASE_URL}`);
  console.log('');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  let successCount = 0;
  let failCount = 0;

  for (const config of screenshots) {
    const page = await context.newPage();
    try {
      console.log(`📸 正在生成: ${config.name}`);

      await page.goto(`${BASE_URL}${config.url}`, {
        waitUntil: 'networkidle',
        timeout: 30000,
      });

      if (config.actions) {
        try {
          await config.actions(page);
        } catch (e) {
          console.warn(`  ⚠️ 操作执行失败: ${e.message}`);
        }
      }

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${config.name}.png`),
        fullPage: false,
      });

      console.log(`  ✅ 截图已保存`);
      successCount++;
    } catch (e) {
      console.error(`  ❌ 失败: ${e.message}`);
      failCount++;
    } finally {
      await page.close();
    }
  }

  await browser.close();

  console.log('');
  console.log('📊 生成完成!');
  console.log(`  ✅ 成功: ${successCount}`);
  console.log(`  ❌ 失败: ${failCount}`);
  console.log(`  📁 总计: ${screenshots.length}`);
}

captureScreenshots().catch(console.error);
