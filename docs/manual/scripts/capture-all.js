/**
 * 完整截图生成脚本
 *
 * 使用方法:
 *   cd frontend
 *   node ../docs/manual/scripts/capture-all.js
 *
 * 环境变量:
 *   BASE_URL      - 目标地址 (默认 http://localhost:3000)
 *   TEST_EMAIL    - 测试用户邮箱 (默认 admin@example.com)
 *   TEST_PASSWORD - 测试用户密码 (默认 password123)
 */

const { chromium } = require(require.resolve('playwright', { paths: [process.cwd() + '/node_modules'] }));
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = path.resolve(__dirname, '../screenshots');
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const TEST_EMAIL = process.env.TEST_EMAIL || 'screenshot@test.com';
const TEST_PASSWORD = process.env.TEST_PASSWORD || 'Test@2026!';

// 确保输出目录存在
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// ─── Helper Functions ─────────────────────────────────────────

/**
 * 通过 API 登录并设置 cookie
 * 比表单填写更可靠
 */
async function loginViaAPI(page) {
  try {
    // 使用 page.request 发送登录请求（自动共享 cookie jar）
    const response = await page.request.post(`${BASE_URL}/api/v1/auth/login/local`, {
      form: {
        username: TEST_EMAIL,
        password: TEST_PASSWORD,
      },
    });

    if (response.ok()) {
      console.log('  ✅ API 登录成功');
      return true;
    } else {
      const body = await response.json().catch(() => ({}));
      console.warn(`  ⚠️ API 登录失败: ${response.status()} ${body?.detail?.message || ''}`);
      return false;
    }
  } catch (e) {
    console.warn(`  ⚠️ API 登录异常: ${e.message}`);
    return false;
  }
}

/**
 * 检查是否在登录页面，如果是则自动登录
 */
async function loginIfNeeded(page) {
  const url = page.url();
  if (url.includes('/login') || url.includes('/setup')) {
    console.log('  🔐 检测到登录页面，通过 API 登录...');
    const success = await loginViaAPI(page);
    if (success) {
      // 登录后重新导航到目标页面
      const targetUrl = page.url();
      await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 30000 });
      // 检查是否还在登录页
      if (page.url().includes('/login')) {
        console.warn('  ⚠️ 登录后仍在登录页面');
        return false;
      }
    }
    return success;
  }
  return true;
}

/**
 * 确保侧边栏展开
 */
async function ensureSidebarExpanded(page) {
  try {
    // 检查侧边栏状态
    const sidebar = page.locator('[data-sidebar="sidebar"]').first();
    const state = await sidebar.getAttribute('data-state').catch(() => null);

    if (state === 'collapsed') {
      console.log('  📂 侧边栏已折叠，正在展开...');

      // 侧边栏折叠时，trigger 是 hidden 的，需要先 hover header 区域
      const header = page.locator('.group\\/workspace-header').first();
      if (await header.isVisible({ timeout: 3000 }).catch(() => false)) {
        await header.hover();
        await page.waitForTimeout(300);
      }

      // 点击 trigger 展开
      const trigger = page.locator('[data-sidebar="trigger"]').first();
      if (await trigger.isVisible({ timeout: 3000 }).catch(() => false)) {
        await trigger.click();
        await page.waitForTimeout(500);
        console.log('  ✅ 侧边栏已展开');
      }
    }
  } catch (e) {
    console.warn(`  ⚠️ 侧边栏操作失败: ${e.message}`);
  }
}

/**
 * 确保侧边栏折叠
 */
async function ensureSidebarCollapsed(page) {
  try {
    const sidebar = page.locator('[data-sidebar="sidebar"]').first();
    const state = await sidebar.getAttribute('data-state').catch(() => null);

    if (state !== 'collapsed') {
      console.log('  📁 侧边栏已展开，正在折叠...');
      const trigger = page.locator('[data-sidebar="trigger"]').first();
      if (await trigger.isVisible({ timeout: 3000 }).catch(() => false)) {
        await trigger.click();
        await page.waitForTimeout(500);
        console.log('  ✅ 侧边栏已折叠');
      }
    }
  } catch (e) {
    console.warn(`  ⚠️ 侧边栏操作失败: ${e.message}`);
  }
}

/**
 * 等待聊天输入框就绪
 * 先等待 input-box wrapper，再等待 textarea 可交互
 */
async function waitForChatReady(page) {
  try {
    // 等待 wrapper
    await page.waitForSelector('[data-testid="input-box"]', { timeout: 15000 });
    // 等待 textarea 可见且可交互
    const textarea = page.locator('textarea[data-testid="chat-input"]');
    await textarea.waitFor({ state: 'visible', timeout: 10000 });
    // 确保 textarea 已启用
    await page.waitForFunction(
      () => {
        const el = document.querySelector('textarea[data-testid="chat-input"]');
        return el && !el.disabled;
      },
      { timeout: 5000 },
    );
    return textarea;
  } catch (e) {
    console.warn(`  ⚠️ 聊天输入框等待超时: ${e.message}`);
    // 返回 fallback locator
    return page.locator('textarea[data-testid="chat-input"]');
  }
}

/**
 * 打开设置对话框并切换到指定 tab
 */
async function openSettings(page, tabId) {
  // 确保侧边栏展开
  await ensureSidebarExpanded(page);

  // 点击导航菜单触发器
  const navMenuTrigger = page.locator('[data-testid="nav-menu-trigger"]');
  await navMenuTrigger.waitFor({ state: 'visible', timeout: 5000 });
  await navMenuTrigger.click();
  await page.waitForTimeout(500);

  // 点击设置菜单项
  const settingsMenuItem = page.locator('[data-testid="settings-menu-item"]');
  await settingsMenuItem.waitFor({ state: 'visible', timeout: 5000 });
  await settingsMenuItem.click();

  // 等待设置对话框打开
  await page.waitForSelector('[data-testid="settings-dialog"]', { timeout: 5000 });
  await page.waitForTimeout(300);

  // 切换到指定 tab
  if (tabId) {
    const tab = page.locator(`[data-testid="settings-tab-${tabId}"]`);
    if (await tab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await tab.click();
      await page.waitForTimeout(500);
    }
  }
}

/**
 * 创建测试对话（用于线程操作截图）
 * 先发送一条消息，然后返回到对话列表
 */
async function createTestConversation(page) {
  try {
    const textarea = await waitForChatReady(page);
    await textarea.fill('测试对话');
    await textarea.press('Enter');
    // 等待 AI 回复或超时
    await page.waitForSelector('[data-testid="ai-message"]', { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1000);
    // 导航回新对话页面以刷新线程列表
    await page.goto(`${BASE_URL}/workspace/chats/new`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
  } catch (e) {
    console.warn(`  ⚠️ 创建测试对话失败: ${e.message}`);
  }
}

// ─── 截图配置 ─────────────────────────────────────────────────

const screenshots = [
  // ─── 认证 ───────────────────────────────────────────────
  {
    name: '01-login-page',
    url: '/login',
    waitFor: 'input[name="email"]',
  },
  {
    name: '02-setup-admin',
    url: '/setup',
    waitFor: 'input[name="email"]',
  },

  // ─── 工作空间 - 聊天 ─────────────────────────────────────
  {
    name: '03-workspace-welcome',
    url: '/workspace/chats/new',
    waitFor: '[data-testid="input-box"]',
  },
  {
    name: '04-workspace-chat',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = await waitForChatReady(page);
      await textarea.fill('你好，请介绍一下 iDeer 平台的核心功能');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="ai-message"]', {
        timeout: 60000,
      });
      await page.waitForTimeout(3000);
    },
  },
  {
    name: '05-sidebar-expanded',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await ensureSidebarExpanded(page);
      await page.waitForTimeout(500);
    },
  },
  {
    name: '06-sidebar-collapsed',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await ensureSidebarCollapsed(page);
      await page.waitForTimeout(500);
    },
  },

  // ─── 模型与模式选择 ─────────────────────────────────────
  {
    name: '07-model-selector',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      const trigger = page.locator('[data-testid="model-selector-trigger"]');
      if (await trigger.isVisible({ timeout: 5000 }).catch(() => false)) {
        await trigger.click();
        await page.waitForTimeout(500);
        // 等待对话框或下拉菜单出现
        await page.waitForSelector('[data-slot="dialog"], [role="dialog"], [role="listbox"]', {
          timeout: 5000,
        }).catch(() => {});
      }
    },
  },
  {
    name: '08-mode-flash',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await modeBtn.click();
        await page.waitForTimeout(500);
        const flash = page.locator('[role="menuitem"], [role="option"]').filter({ hasText: 'Flash' }).first();
        if (await flash.isVisible({ timeout: 3000 }).catch(() => false)) await flash.click();
      }
    },
  },
  {
    name: '09-mode-thinking',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await modeBtn.click();
        await page.waitForTimeout(500);
        const thinking = page.locator('[role="menuitem"], [role="option"]').filter({ hasText: /Reasoning|Thinking/ }).first();
        if (await thinking.isVisible({ timeout: 3000 }).catch(() => false)) await thinking.click();
      }
    },
  },
  {
    name: '10-mode-pro',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await modeBtn.click();
        await page.waitForTimeout(500);
        const pro = page.locator('[role="menuitem"], [role="option"]').filter({ hasText: 'Pro' }).first();
        if (await pro.isVisible({ timeout: 3000 }).catch(() => false)) await pro.click();
      }
    },
  },
  {
    name: '11-mode-ultra',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await modeBtn.click();
        await page.waitForTimeout(500);
        const ultra = page.locator('[role="menuitem"], [role="option"]').filter({ hasText: 'Ultra' }).first();
        if (await ultra.isVisible({ timeout: 3000 }).catch(() => false)) await ultra.click();
      }
    },
  },

  // ─── 文件处理 ──────────────────────────────────────────
  {
    name: '12-file-upload',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      // 使用 input[type="file"] 作为备选选择器
      const fileInput = page.locator('[data-testid="file-input"], input[type="file"]').first();
      const testFile = path.join(SCREENSHOT_DIR, 'test-upload.txt');
      fs.writeFileSync(testFile, 'This is a test file for screenshot.');
      await fileInput.setInputFiles(testFile);
      await page.waitForTimeout(1000);
      fs.unlinkSync(testFile);
    },
  },
  {
    name: '13-file-preview',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      const fileInput = page.locator('[data-testid="file-input"], input[type="file"]').first();
      const testFile = path.join(SCREENSHOT_DIR, 'test-preview.txt');
      fs.writeFileSync(testFile, 'This is a test file for preview screenshot.');
      await fileInput.setInputFiles(testFile);
      await page.waitForTimeout(2000);
      fs.unlinkSync(testFile);
    },
  },

  // ─── 工件 ─────────────────────────────────────────────
  {
    name: '14-artifacts-panel',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = await waitForChatReady(page);
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
      const textarea = await waitForChatReady(page);
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
      await waitForChatReady(page);
      // 先切换到 Pro 模式以触发思维链
      const modeBtn = page.locator('[data-testid="mode-selector-trigger"]');
      if (await modeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await modeBtn.click();
        await page.waitForTimeout(300);
        const pro = page.locator('[role="menuitem"], [role="option"]').filter({ hasText: 'Pro' }).first();
        if (await pro.isVisible({ timeout: 3000 }).catch(() => false)) await pro.click();
      }
      const textarea = await waitForChatReady(page);
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
      const textarea = await waitForChatReady(page);
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
      const textarea = await waitForChatReady(page);
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
      const textarea = await waitForChatReady(page);
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
      const textarea = await waitForChatReady(page);
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
    name: '21-agents-gallery',
    url: '/workspace/agents',
    waitFor: '[data-testid="agent-card"]',
  },
  {
    name: '22-agent-create',
    url: '/workspace/agents/new',
    waitFor: 'input[name="name"]',
  },
  {
    name: '23-agent-edit',
    url: '/workspace/agents/new',
    actions: async (page) => {
      await page.waitForTimeout(1000);
    },
  },
  {
    name: '24-agent-chat',
    url: '/workspace/agents',
    actions: async (page) => {
      // 先等待 agent card 加载
      await page.waitForSelector('[data-testid="agent-card"]', { timeout: 10000 }).catch(() => {});
      const chatBtn = page.locator('[data-testid="agent-chat-button"]').first();
      if (await chatBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await chatBtn.click();
        await page.waitForTimeout(1000);
      }
    },
  },

  // ─── 工作流 ───────────────────────────────────────────
  {
    name: '25-workflows-gallery',
    url: '/workspace/workflows',
    waitFor: '[data-testid="workflow-card"]',
  },
  {
    name: '26-workflow-create',
    url: '/workspace/workflows/new',
    actions: async (page) => {
      await page.waitForTimeout(1000);
    },
  },
  {
    name: '27-workflow-editor',
    url: '/workspace/workflows/new',
    actions: async (page) => {
      await page.waitForTimeout(1000);
    },
  },
  {
    name: '28-workflow-run',
    url: '/workspace/workflows',
    actions: async (page) => {
      await page.waitForSelector('[data-testid="workflow-card"]', { timeout: 10000 }).catch(() => {});
      const runBtn = page.locator('[data-testid="workflow-run-button"]').first();
      if (await runBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await runBtn.click();
        await page.waitForTimeout(2000);
      }
    },
  },
  {
    name: '29-workflow-human-review',
    url: '/workspace/workflows',
    actions: async (page) => {
      await page.waitForSelector('[data-testid="workflow-card"]', { timeout: 10000 }).catch(() => {});
      const workflowCard = page.locator('[data-testid="workflow-card"]').first();
      if (await workflowCard.isVisible({ timeout: 5000 }).catch(() => false)) {
        await workflowCard.click();
        await page.waitForTimeout(1000);
      }
    },
  },

  // ─── 设置 ─────────────────────────────────────────────
  {
    name: '30-settings-account',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await openSettings(page, null);
    },
  },
  {
    name: '31-settings-appearance',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await openSettings(page, 'appearance');
    },
  },
  {
    name: '32-settings-memory',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await openSettings(page, 'memory');
    },
  },
  {
    name: '33-settings-skills',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await openSettings(page, 'skills');
    },
  },
  {
    name: '34-settings-tools',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await openSettings(page, 'tools');
    },
  },
  {
    name: '35-settings-notification',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await openSettings(page, 'notification');
    },
  },

  // ─── 管理后台 ──────────────────────────────────────────
  {
    name: '36-admin-dashboard',
    url: '/workspace/admin',
    waitFor: '[data-testid="admin-dashboard"]',
  },
  {
    name: '37-admin-users',
    url: '/workspace/admin/users',
    waitFor: '[data-testid="user-list"]',
  },
  {
    name: '38-admin-user-edit',
    url: '/workspace/admin/users',
    actions: async (page) => {
      await page.waitForTimeout(1000);
    },
  },
  {
    name: '39-admin-departments',
    url: '/workspace/admin/departments',
    waitFor: '[data-testid="department-list"]',
  },
  {
    name: '40-admin-tools',
    url: '/workspace/admin/tools',
    waitFor: '[data-testid="tool-list"]',
  },

  // ─── 快捷操作 ──────────────────────────────────────────
  {
    name: '41-command-palette',
    url: '/workspace/chats/new',
    actions: async (page) => {
      await waitForChatReady(page);
      // 使用 Ctrl+K 作为备选（Meta+K 在非 Mac 上不工作）
      await page.keyboard.press('Control+k');
      await page.waitForTimeout(500);
    },
  },
  {
    name: '42-export-json',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = await waitForChatReady(page);
      await textarea.fill('你好');
      await textarea.press('Enter');
      await page.waitForSelector('[data-testid="ai-message"]', {
        timeout: 60000,
      }).catch(() => {});
      await page.waitForTimeout(1000);
      const exportBtn = page.locator('[data-testid="export-trigger-button"]');
      if (await exportBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await exportBtn.click();
        await page.waitForTimeout(500);
        const jsonOption = page.locator('[role="menuitem"]').filter({ hasText: /JSON|json/ }).first();
        if (await jsonOption.isVisible({ timeout: 3000 }).catch(() => false)) await jsonOption.click();
      }
    },
  },
  {
    name: '43-thread-rename',
    url: '/workspace/chats/new',
    actions: async (page) => {
      // 先创建测试对话
      await createTestConversation(page);

      // hover 触发操作按钮
      const threadItem = page.locator('[data-testid="thread-item"]').first();
      if (await threadItem.isVisible({ timeout: 5000 }).catch(() => false)) {
        await threadItem.hover();
        await page.waitForTimeout(300);
        const threadActionsTrigger = page.locator('[data-testid="thread-actions-trigger"]').first();
        if (await threadActionsTrigger.isVisible({ timeout: 3000 }).catch(() => false)) {
          await threadActionsTrigger.click();
          await page.waitForTimeout(300);
          const renameBtn = page.locator('[data-testid="thread-rename-action"]');
          if (await renameBtn.isVisible({ timeout: 3000 }).catch(() => false)) await renameBtn.click();
          await page.waitForTimeout(500);
        }
      }
    },
  },
  {
    name: '44-thread-delete',
    url: '/workspace/chats/new',
    actions: async (page) => {
      // 先创建测试对话
      await createTestConversation(page);

      // hover 触发操作按钮
      const threadItem = page.locator('[data-testid="thread-item"]').first();
      if (await threadItem.isVisible({ timeout: 5000 }).catch(() => false)) {
        await threadItem.hover();
        await page.waitForTimeout(300);
        const threadActionsTrigger = page.locator('[data-testid="thread-actions-trigger"]').first();
        if (await threadActionsTrigger.isVisible({ timeout: 3000 }).catch(() => false)) {
          await threadActionsTrigger.click();
          await page.waitForTimeout(300);
          const deleteBtn = page.locator('[data-testid="thread-delete-action"]');
          if (await deleteBtn.isVisible({ timeout: 3000 }).catch(() => false)) await deleteBtn.click();
          await page.waitForTimeout(500);
        }
      }
    },
  },
  {
    name: '45-error-state',
    url: '/workspace/chats/new',
    actions: async (page) => {
      const textarea = await waitForChatReady(page);
      await textarea.fill('/invalid-command');
      await textarea.press('Enter');
      await page.waitForTimeout(2000);
    },
  },
];

// ─── Main Capture Function ────────────────────────────────────

async function captureScreenshots() {
  console.log('🚀 开始生成截图...');
  console.log(`📁 输出目录: ${SCREENSHOT_DIR}`);
  console.log(`🌐 目标地址: ${BASE_URL}`);
  console.log(`👤 测试用户: ${TEST_EMAIL}`);
  console.log('');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  let successCount = 0;
  let failCount = 0;
  let loginDone = false;

  // 预先通过 API 登录，将 cookie 注入到 browser context
  console.log('🔐 正在通过 API 预登录...');
  const setupPage = await context.newPage();
  loginDone = await loginViaAPI(setupPage);
  await setupPage.close();
  if (!loginDone) {
    console.error('❌ 预登录失败，请检查 TEST_EMAIL 和 TEST_PASSWORD 环境变量');
    await browser.close();
    process.exit(1);
  }

  for (const config of screenshots) {
    const page = await context.newPage();
    try {
      console.log(`📸 正在生成: ${config.name}`);

      // 带重试的导航
      let navigated = false;
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          await page.goto(`${BASE_URL}${config.url}`, {
            waitUntil: 'networkidle',
            timeout: 30000,
          });
          navigated = true;
          break;
        } catch (navErr) {
          if (attempt < 3) {
            console.warn(`  ⚠️ 导航失败 (尝试 ${attempt}/3)，等待重试...`);
            await new Promise(r => setTimeout(r, 3000));
          } else {
            throw navErr;
          }
        }
      }

      if (!navigated) {
        throw new Error('导航失败，已重试 3 次');
      }

      // 如果被重定向到登录页，尝试重新登录
      if (page.url().includes('/login') || page.url().includes('/setup')) {
        console.log('  🔐 重新登录...');
        await loginViaAPI(page);
        await page.goto(`${BASE_URL}${config.url}`, {
          waitUntil: 'networkidle',
          timeout: 30000,
        });
      }

      if (config.waitFor) {
        try {
          await page.waitForSelector(config.waitFor, { timeout: 15000 });
        } catch {
          console.warn(`  ⚠️ 等待 "${config.waitFor}" 超时`);
        }
      }

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

    // 截图间隔，防止服务器过载
    await new Promise(r => setTimeout(r, 1000));
  }

  await browser.close();

  console.log('');
  console.log('📊 生成完成!');
  console.log(`  ✅ 成功: ${successCount}`);
  console.log(`  ❌ 失败: ${failCount}`);
  console.log(`  📁 总计: ${screenshots.length}`);
}

captureScreenshots().catch(console.error);
