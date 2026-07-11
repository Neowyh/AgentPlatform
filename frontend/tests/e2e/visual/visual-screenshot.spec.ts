/**
 * Visual Screenshot: 主动截图核心页面供 AI 视觉分析
 *
 * 不做像素级回归对比（那是 visual/ 目录的事），
 * 专门捕获关键页面截图供 qa-tester Phase 2.5 AI 视觉分析使用。
 *
 * 截图保存到: frontend/playwright-artifacts/qa/screenshots/
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

import { test, type Page } from "@playwright/test";

import { mockLangGraphAPI, type MockAPIOptions } from "../utils/mock-api";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const SCREENSHOT_DIR =
  process.env.SCREENSHOT_DIR ??
  path.resolve(__dirname, "../../../playwright-artifacts/qa/screenshots");

// 确保截图目录存在
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

/** 截图配置 */
interface ScreenshotConfig {
  name: string;
  route: string;
  waitFor?: string;
  actions?: (page: Page) => Promise<void>;
  needsMock?: boolean;
  needsAuth?: boolean;
  /** 该页面必须存在的 CSS 选择器（关键组件） */
  expectedElements?: string[];
  /** 该页面必须包含的文本内容（页面标识） */
  expectedTexts?: string[];
  /** 登录角色，默认 admin */
  role?: "admin" | "user" | "viewer";
  /** 跳过 mobile 变体 */
  skipMobile?: boolean;
  /** 跳过 dark mode 变体 */
  skipDark?: boolean;
  /** 自定义 mock 数据覆盖（空数组触发空状态等） */
  mockOverrides?: MockAPIOptions;
}

/** 健康检查结果 */
interface HealthCheckResult {
  page: string;
  route: string;
  timestamp: string;
  viewport: string;
  status: "ok" | "warn" | "fail";
  checks: {
    consoleErrors: string[];
    failedRequests: string[];
    pageEmpty: boolean;
    horizontalOverflow: boolean;
    reactError: boolean;
    urlDrift: boolean;
    wrongPage: string | null;
    missingElements: string[];
  };
}

/**
 * 运行通用健康检查
 * 在截图之后调用，捕获页面运行时状态
 */
async function runHealthChecks(
  page: Page,
  config: ScreenshotConfig,
  viewport: string,
  consoleErrors: string[],
  failedRequests: string[],
): Promise<HealthCheckResult> {
  const checks: HealthCheckResult["checks"] = {
    consoleErrors: [...consoleErrors],
    failedRequests: [...failedRequests],
    pageEmpty: false,
    horizontalOverflow: false,
    reactError: false,
    urlDrift: false,
    wrongPage: null,
    missingElements: [],
  };

  // URL 偏移检测 — 当前 URL 是否偏离预期路由
  try {
    const currentUrl = new URL(page.url());
    const actualPath = currentUrl.pathname;
    // 将动态路由段 [xxx] 替换为空，只比较静态前缀
    const routePrefix = config.route
      .replace(/\[.*?\]/g, "")
      .replace(/\/+$/, "");
    if (routePrefix && !actualPath.startsWith(routePrefix)) {
      checks.urlDrift = true;
    }
  } catch {
    // 忽略
  }

  // 错误页面检测 — 是否被重定向到登录/404/403/错误页
  try {
    const bodyText = await page.locator("body").innerText({ timeout: 3000 });
    const currentPath = new URL(page.url()).pathname;

    // 登录页重定向（非 login 页面却出现了登录表单）
    if (config.route !== "/login" && config.route !== "/setup") {
      const hasLoginForm = await page
        .locator('input[type="password"]')
        .isVisible({ timeout: 1000 })
        .catch(() => false);
      if (hasLoginForm || currentPath === "/login") {
        checks.wrongPage = "被重定向到登录页";
      }
    }

    // 404 / 403 / 错误页面文本检测
    if (!checks.wrongPage) {
      const wrongPagePatterns = [
        { pattern: /404|not found|页面不存在/i, meaning: "页面不存在 (404)" },
        {
          pattern: /403|forbidden|权限不足|access denied/i,
          meaning: "权限不足 (403)",
        },
        {
          pattern: /500|internal server error|服务器错误/i,
          meaning: "服务器错误 (500)",
        },
        {
          pattern: /something went wrong|应用错误|发生错误/i,
          meaning: "应用错误",
        },
      ];
      for (const { pattern, meaning } of wrongPagePatterns) {
        if (pattern.test(bodyText)) {
          checks.wrongPage = meaning;
          break;
        }
      }
    }

    // 页面空白检测
    checks.pageEmpty = bodyText.trim().length < 10;
  } catch {
    checks.pageEmpty = true;
  }

  // 水平溢出检测
  try {
    const overflow = await page.evaluate(() => {
      return document.body.scrollWidth > document.body.clientWidth + 5;
    });
    checks.horizontalOverflow = overflow;
  } catch {
    // dialog 类页面可能无法检测，忽略
  }

  // React Error Boundary 检测
  try {
    const errorTexts = [
      "Something went wrong",
      "应用错误",
      "Error Boundary",
      "发生错误",
    ];
    const bodyHtml = await page.locator("body").innerHTML({ timeout: 3000 });
    checks.reactError = errorTexts.some((t) => bodyHtml.includes(t));
  } catch {
    // 忽略
  }

  // 关键元素存在性检测
  if (config.expectedElements?.length) {
    for (const selector of config.expectedElements) {
      try {
        const visible = await page
          .locator(selector)
          .first()
          .isVisible({ timeout: 2000 })
          .catch(() => false);
        if (!visible) {
          checks.missingElements.push(selector);
        }
      } catch {
        checks.missingElements.push(selector);
      }
    }
  }

  // 判断总体状态
  let status: HealthCheckResult["status"] = "ok";
  if (
    checks.pageEmpty ||
    checks.reactError ||
    checks.wrongPage ||
    checks.missingElements.length > 0
  ) {
    status = "fail";
  } else if (
    checks.consoleErrors.length > 0 ||
    checks.horizontalOverflow ||
    checks.urlDrift
  ) {
    status = "warn";
  }

  return {
    page: config.name,
    route: config.route,
    timestamp: new Date().toISOString(),
    viewport,
    status,
    checks,
  };
}

/** 核心页面截图列表 */
const SCREENSHOTS: ScreenshotConfig[] = [
  // ─── 公开页面 ──────────────────────────────────────────
  {
    name: "landing",
    route: "/",
    waitFor: "body",
    needsMock: false,
    needsAuth: false,
    expectedTexts: ["iDeer"],
  },
  {
    name: "login",
    route: "/login",
    waitFor: "form",
    needsMock: false,
    needsAuth: false,
    expectedElements: [
      'input[type="email"], input[name="email"]',
      'input[type="password"]',
    ],
  },
  {
    name: "setup",
    route: "/setup",
    waitFor: "form",
    needsMock: false,
    needsAuth: false,
    expectedElements: ['input[type="password"]'],
  },

  // ─── Workspace 页面（需要 mock + auth） ────────────────
  {
    name: "workspace-new-chat",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    expectedElements: [
      'textarea, [data-testid="chat-input"], [contenteditable="true"]',
    ],
  },
  {
    name: "workspace-chat-with-message",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("测试消息：请介绍一下 iDeer 平台");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000); // 等待 mock 响应
        }
      }
    },
  },
  {
    name: "chat-list",
    route: "/workspace/chats",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["Thread", "thread", "聊天", "对话"],
  },
  {
    name: "agents-gallery",
    route: "/workspace/agents",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["Agent", "agent", "智能体"],
  },
  {
    name: "agent-create",
    route: "/workspace/agents/new",
    needsMock: true,
    needsAuth: true,
    expectedElements: [
      'input[name="name"], input[placeholder*="name"], textarea',
    ],
  },
  {
    name: "agent-detail",
    route: "/workspace/agents/research-assistant",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["research-assistant", "Agent", "智能体"],
  },
  {
    name: "agent-edit",
    route: "/workspace/agents/research-assistant/edit",
    needsMock: true,
    needsAuth: true,
    expectedElements: [
      'input[name="name"], input[name="description"], textarea',
    ],
  },
  {
    name: "agent-chat",
    route: "/workspace/agents/research-assistant/chats/new",
    needsMock: true,
    needsAuth: true,
    expectedElements: [
      'textarea, [data-testid="chat-input"], [contenteditable="true"]',
    ],
  },
  {
    name: "workflows-gallery",
    route: "/workspace/workflows",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["Workflow", "workflow", "工作流"],
  },
  {
    name: "workflow-create",
    route: "/workspace/workflows/new",
    needsMock: true,
    needsAuth: true,
    expectedElements: [".cm-editor", "textarea"],
  },
  {
    name: "workflow-detail",
    route: "/workspace/workflows/research-workflow",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["research-workflow", "Workflow", "工作流"],
  },
  {
    name: "workflow-edit",
    route: "/workspace/workflows/research-workflow/edit",
    needsMock: true,
    needsAuth: true,
    expectedElements: [".cm-editor", "textarea"],
  },
  {
    name: "admin-dashboard",
    route: "/workspace/admin",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["用户", "部门", "智能体", "User", "Department", "Agent"],
  },
  {
    name: "admin-users",
    route: "/workspace/admin/users",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["用户", "User", "角色", "Role"],
  },
  {
    name: "admin-departments",
    route: "/workspace/admin/departments",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["部门", "Department"],
  },
  {
    name: "admin-tools",
    route: "/workspace/admin/tools",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["工具", "Tool"],
  },
  {
    name: "sidebar-expanded",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    expectedElements: ['[data-testid="sidebar"], nav, aside'],
    actions: async (page) => {
      // 确保侧边栏展开
      const sidebar = page
        .locator('[data-testid="sidebar"], nav, aside')
        .first();
      if (await sidebar.isVisible({ timeout: 3000 }).catch(() => false)) {
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "settings-account",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    expectedTexts: ["设置", "Settings", "外观", "Appearance"],
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
    },
  },
  {
    name: "command-palette",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    expectedElements: [
      '[cmdk-root], [role="dialog"], [data-testid="command-palette"]',
    ],
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+k");
      await page.waitForTimeout(1000);
    },
  },

  // ─── Phase 1.1: 对话框/弹窗 ────────────────────────────────
  {
    name: "dialog-rename-thread",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      // 先发送消息创建一个线程
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("测试消息");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      // 右键点击侧边栏线程触发重命名
      const threadItem = page
        .locator('[data-testid="thread-item"], .thread-item, nav a')
        .first();
      if (await threadItem.isVisible({ timeout: 3000 }).catch(() => false)) {
        await threadItem.click({ button: "right" });
        await page.waitForTimeout(500);
        const renameBtn = page
          .locator(
            'button:has-text("Rename"), button:has-text("重命名"), [data-testid="rename-thread"]',
          )
          .first();
        if (await renameBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await renameBtn.click();
          await page.waitForTimeout(500);
        }
      }
    },
    expectedElements: ['input, [role="dialog"]'],
  },
  {
    name: "dialog-delete-agent",
    route: "/workspace/agents",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      const deleteBtn = page
        .locator(
          'button:has-text("Delete"), button:has-text("删除"), button[aria-label*="delete"], button[aria-label*="Delete"]',
        )
        .first();
      if (await deleteBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await deleteBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: [
      '[role="dialog"], button:has-text("确定"), button:has-text("Confirm")',
    ],
  },
  {
    name: "dialog-delete-workflow",
    route: "/workspace/workflows",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      const deleteBtn = page
        .locator(
          'button:has-text("Delete"), button:has-text("删除"), button[aria-label*="delete"], button[aria-label*="Delete"]',
        )
        .first();
      if (await deleteBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await deleteBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: [
      '[role="dialog"], button:has-text("确定"), button:has-text("Confirm")',
    ],
  },
  {
    name: "dialog-create-department",
    route: "/workspace/admin/departments",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      const createBtn = page
        .locator(
          'button:has-text("新建"), button:has-text("Create"), button:has-text("添加"), button:has-text("Add")',
        )
        .first();
      if (await createBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await createBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['input[name="name"], input, [role="dialog"]'],
  },
  {
    name: "dialog-edit-department",
    route: "/workspace/admin/departments",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      const editBtn = page
        .locator(
          'button:has-text("Edit"), button:has-text("编辑"), button[aria-label*="edit"], button[aria-label*="Edit"]',
        )
        .first();
      if (await editBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await editBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['input[name="name"], input, [role="dialog"]'],
  },
  {
    name: "dialog-tool-detail",
    route: "/workspace/admin/tools",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      const toolCard = page
        .locator('[data-testid="tool-card"], .tool-card, tr, .card')
        .first();
      if (await toolCard.isVisible({ timeout: 5000 }).catch(() => false)) {
        await toolCard.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"]'],
  },
  {
    name: "dialog-add-memory",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      // 点击记忆/Memory 标签
      const memoryTab = page
        .locator(
          'button:has-text("Memory"), button:has-text("记忆"), [role="tab"]:has-text("Memory"), [role="tab"]:has-text("记忆")',
        )
        .first();
      if (await memoryTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await memoryTab.click();
        await page.waitForTimeout(500);
      }
      const addBtn = page
        .locator(
          'button:has-text("添加"), button:has-text("Add"), button:has-text("新建"), button:has-text("Create")',
        )
        .first();
      if (await addBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await addBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['textarea, input, [role="dialog"]'],
  },
  {
    name: "dialog-edit-memory",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true, // 复用 add-memory 的 mobile 变体
    skipDark: false,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const memoryTab = page
        .locator(
          'button:has-text("Memory"), button:has-text("记忆"), [role="tab"]:has-text("Memory"), [role="tab"]:has-text("记忆")',
        )
        .first();
      if (await memoryTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await memoryTab.click();
        await page.waitForTimeout(500);
      }
      const editBtn = page
        .locator(
          'button:has-text("Edit"), button:has-text("编辑"), button[aria-label*="edit"]',
        )
        .first();
      if (await editBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await editBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['textarea, input, [role="dialog"]'],
  },
  {
    name: "dialog-delete-memory",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: false,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const memoryTab = page
        .locator(
          'button:has-text("Memory"), button:has-text("记忆"), [role="tab"]:has-text("Memory"), [role="tab"]:has-text("记忆")',
        )
        .first();
      if (await memoryTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await memoryTab.click();
        await page.waitForTimeout(500);
      }
      const deleteBtn = page
        .locator(
          'button:has-text("Delete"), button:has-text("删除"), button[aria-label*="delete"]',
        )
        .first();
      if (await deleteBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await deleteBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"]'],
  },
  {
    name: "dialog-clear-all-memory",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const memoryTab = page
        .locator(
          'button:has-text("Memory"), button:has-text("记忆"), [role="tab"]:has-text("Memory"), [role="tab"]:has-text("记忆")',
        )
        .first();
      if (await memoryTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await memoryTab.click();
        await page.waitForTimeout(500);
      }
      const clearBtn = page
        .locator(
          'button:has-text("Clear"), button:has-text("清除"), button:has-text("全部清除")',
        )
        .first();
      if (await clearBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await clearBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"]'],
  },
  {
    name: "dialog-import-memory",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const memoryTab = page
        .locator(
          'button:has-text("Memory"), button:has-text("记忆"), [role="tab"]:has-text("Memory"), [role="tab"]:has-text("记忆")',
        )
        .first();
      if (await memoryTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await memoryTab.click();
        await page.waitForTimeout(500);
      }
      const importBtn = page
        .locator('button:has-text("Import"), button:has-text("导入")')
        .first();
      if (await importBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await importBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"]'],
  },
  {
    name: "dialog-skill-editor",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const skillsTab = page
        .locator(
          'button:has-text("Skills"), button:has-text("技能"), [role="tab"]:has-text("Skills"), [role="tab"]:has-text("技能")',
        )
        .first();
      if (await skillsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await skillsTab.click();
        await page.waitForTimeout(500);
      }
      const editBtn = page
        .locator(
          'button:has-text("Edit"), button:has-text("编辑"), button[aria-label*="edit"]',
        )
        .first();
      if (await editBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await editBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"], textarea, .cm-editor'],
  },
  {
    name: "dialog-test-skill",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const skillsTab = page
        .locator(
          'button:has-text("Skills"), button:has-text("技能"), [role="tab"]:has-text("Skills"), [role="tab"]:has-text("技能")',
        )
        .first();
      if (await skillsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await skillsTab.click();
        await page.waitForTimeout(500);
      }
      const testBtn = page
        .locator(
          'button:has-text("Test"), button:has-text("测试"), button[aria-label*="test"]',
        )
        .first();
      if (await testBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await testBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"]'],
  },
  {
    name: "dialog-keyboard-shortcuts",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+k");
      await page.waitForTimeout(1000);
      const shortcutsItem = page
        .locator(
          '[cmdk-item]:has-text("Keyboard"), [cmdk-item]:has-text("快捷键"), [cmdk-item]:has-text("Shortcut")',
        )
        .first();
      if (await shortcutsItem.isVisible({ timeout: 3000 }).catch(() => false)) {
        await shortcutsItem.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"], kbd'],
  },
  {
    name: "dialog-followup-confirm",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("请帮我创建一个项目");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      // 点击跟进建议
      const suggestion = page
        .locator(
          '[data-testid="suggestion"], .followup, button:has-text("Follow"), button:has-text("继续")',
        )
        .first();
      if (await suggestion.isVisible({ timeout: 3000 }).catch(() => false)) {
        await suggestion.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="dialog"]'],
  },

  // ─── Phase 1.2: 下拉菜单/交互状态 ──────────────────────────
  {
    name: "dropdown-thread-context",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      // 先创建线程
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("测试消息");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      // 悬浮侧边栏线程项，点击三点菜单
      const moreBtn = page
        .locator(
          '[data-testid="thread-menu"], button[aria-label="More"], button[aria-label*="menu"], .thread-item button',
        )
        .last();
      if (await moreBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await moreBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="menu"]'],
  },
  {
    name: "dropdown-mode-selector",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const modeBtn = page
        .locator(
          'button:has-text("Flash"), button:has-text("Thinking"), button:has-text("Mode"), [data-testid="mode-selector"]',
        )
        .first();
      if (await modeBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await modeBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="listbox"], [role="menu"]'],
  },
  {
    name: "dropdown-model-selector",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const modelBtn = page
        .locator(
          '[data-testid="model-selector"], button:has-text("Model"), button:has-text("模型")',
        )
        .first();
      if (await modelBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await modelBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="listbox"], input[type="search"]'],
  },
  {
    name: "dropdown-export",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("测试消息");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      const exportBtn = page
        .locator(
          'button:has-text("Export"), button:has-text("导出"), button[aria-label*="export"], button[aria-label*="Export"]',
        )
        .first();
      if (await exportBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await exportBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="menu"]'],
  },
  {
    name: "dropdown-sidebar-nav",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const settingsBtn = page
        .locator(
          '[data-testid="sidebar-settings"], nav button:has-text("Settings"), nav button:has-text("设置"), aside button:has-text("Settings"), aside button:has-text("设置")',
        )
        .first();
      if (await settingsBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await settingsBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="menu"]'],
  },
  {
    name: "dropdown-admin-role",
    route: "/workspace/admin/users",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const roleSelect = page
        .locator('select, [role="combobox"], [data-testid="role-select"]')
        .first();
      if (await roleSelect.isVisible({ timeout: 5000 }).catch(() => false)) {
        await roleSelect.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="listbox"], [role="option"], option'],
  },
  {
    name: "dropdown-token-usage",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("测试消息");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      const tokenBtn = page
        .locator(
          '[data-testid="token-usage"], button:has-text("token"), button:has-text("Token")',
        )
        .first();
      if (await tokenBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await tokenBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="menu"]'],
  },
  {
    name: "dropdown-reasoning-effort",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const effortBtn = page
        .locator(
          '[data-testid="reasoning-effort"], button:has-text("Effort"), button:has-text("推理")',
        )
        .first();
      if (await effortBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await effortBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[role="listbox"]'],
  },
  {
    name: "state-file-upload-preview",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      // 模拟文件上传
      const fileInput = page.locator('input[type="file"]').first();
      if ((await fileInput.count()) > 0) {
        await fileInput.setInputFiles({
          name: "test-file.txt",
          mimeType: "text/plain",
          buffer: Buffer.from("Hello, this is a test file content."),
        });
        await page.waitForTimeout(1000);
      }
    },
    expectedElements: [
      '[data-testid="file-preview"], .file-card, .file-preview',
    ],
  },
  {
    name: "state-welcome-suggestions",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    expectedElements: ['button, [data-testid="suggestion"]'],
  },
  {
    name: "state-chat-with-artifacts",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("请生成一个 SVG 图标");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      // 尝试打开 artifacts 面板
      const artifactBtn = page
        .locator(
          '[data-testid="artifact-panel"], #artifacts, button:has-text("Artifact"), button:has-text("作品")',
        )
        .first();
      if (await artifactBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await artifactBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['#artifacts, [data-testid="artifact-panel"]'],
  },

  // ─── Phase 1.3: AI 交互状态 ────────────────────────────────
  {
    name: "ai-streaming-response",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: false,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("请详细介绍一下 iDeer 平台的功能");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          // 在流式响应过程中截图 — 短暂等待
          await page.waitForTimeout(800);
        }
      }
    },
    expectedElements: [
      '.streaming-indicator, [data-testid="streaming"], .animate-pulse',
    ],
  },
  {
    name: "ai-reasoning-expanded",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: false,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("分析一下这个项目的架构");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      // 展开思考过程
      const reasoningBtn = page
        .locator(
          '[data-testid="reasoning"], .reasoning-block, button:has-text("Reasoning"), button:has-text("思考"), button:has-text("Thinking")',
        )
        .first();
      if (await reasoningBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await reasoningBtn.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[data-testid="reasoning"], .reasoning-block'],
  },
  {
    name: "ai-feedback-buttons",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("你好");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      // 悬浮在 AI 消息上显示反馈按钮
      const aiMessage = page
        .locator('[data-testid="ai-message"], .message-ai, .assistant-message')
        .first();
      if (await aiMessage.isVisible({ timeout: 3000 }).catch(() => false)) {
        await aiMessage.hover();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: [
      'button[aria-label*="thumb"], [data-testid="feedback"], button:has-text("👍"), button:has-text("👎")',
    ],
  },
  {
    name: "ai-citation-hovercard",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("搜索一下最新的技术文档");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
      // 悬浮在引用标记上
      const citation = page
        .locator(
          '[data-testid="citation"], .citation-hover, sup, a[href*="source"]',
        )
        .first();
      if (await citation.isVisible({ timeout: 3000 }).catch(() => false)) {
        await citation.hover();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[data-testid="citation"], .citation-hover'],
  },
  {
    name: "ai-followup-suggestions",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("介绍一下 iDeer 的工作流功能");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(4000); // 等待回复完成 + 建议生成
        }
      }
    },
    expectedElements: ['[data-testid="suggestion"], .followup, button'],
  },
  {
    name: "ai-message-with-code",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      const input = page
        .locator(
          'textarea, [data-testid="chat-input"], [contenteditable="true"]',
        )
        .first();
      if (await input.isVisible({ timeout: 5000 }).catch(() => false)) {
        await input.fill("写一个 Python 快速排序算法");
        const sendBtn = page
          .locator(
            'button[data-testid="send-button"], button[aria-label="Send"]',
          )
          .first();
        if (await sendBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await sendBtn.click();
          await page.waitForTimeout(3000);
        }
      }
    },
    expectedElements: ["pre, code, .code-block"],
  },

  // ─── Phase 1.4: Settings 子页面 ─────────────────────────────
  {
    name: "settings-appearance",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: false,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const appearanceTab = page
        .locator(
          'button:has-text("Appearance"), button:has-text("外观"), [role="tab"]:has-text("Appearance"), [role="tab"]:has-text("外观")',
        )
        .first();
      if (await appearanceTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await appearanceTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: [
      '[data-testid="theme-card"], .theme-preview, [role="tablist"]',
    ],
  },
  {
    name: "settings-notification",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const notifTab = page
        .locator(
          'button:has-text("Notification"), button:has-text("通知"), [role="tab"]:has-text("Notification"), [role="tab"]:has-text("通知")',
        )
        .first();
      if (await notifTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await notifTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: [
      'button:has-text("Request"), [data-testid="notification"]',
    ],
  },
  {
    name: "settings-memory",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const memoryTab = page
        .locator(
          'button:has-text("Memory"), button:has-text("记忆"), [role="tab"]:has-text("Memory"), [role="tab"]:has-text("记忆")',
        )
        .first();
      if (await memoryTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await memoryTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[data-testid="memory-list"], .fact-item'],
  },
  {
    name: "settings-tools",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const toolsTab = page
        .locator(
          'button:has-text("Tools"), button:has-text("工具"), [role="tab"]:has-text("Tools"), [role="tab"]:has-text("工具")',
        )
        .first();
      if (await toolsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await toolsTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[data-testid="tool-list"], .tool-item'],
  },
  {
    name: "settings-skills",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const skillsTab = page
        .locator(
          'button:has-text("Skills"), button:has-text("技能"), [role="tab"]:has-text("Skills"), [role="tab"]:has-text("技能")',
        )
        .first();
      if (await skillsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await skillsTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[data-testid="skill-list"], .skill-item'],
  },
  {
    name: "settings-about",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const aboutTab = page
        .locator(
          'button:has-text("About"), button:has-text("关于"), [role="tab"]:has-text("About"), [role="tab"]:has-text("关于")',
        )
        .first();
      if (await aboutTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await aboutTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedElements: ['[data-testid="about"]'],
  },

  // ─── Phase 2.1: 空状态 ─────────────────────────────────────
  {
    name: "empty-agents",
    route: "/workspace/agents",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    mockOverrides: { agents: [] },
    expectedTexts: ["No agents", "无智能体", "暂无"],
  },
  {
    name: "empty-workflows",
    route: "/workspace/workflows",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    mockOverrides: { workflows: [] },
    expectedTexts: ["No workflows", "无工作流", "暂无"],
  },
  {
    name: "empty-chats",
    route: "/workspace/chats",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    mockOverrides: { threads: [] },
    expectedTexts: ["No chats", "无对话", "暂无"],
  },
  {
    name: "empty-memory",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const memoryTab = page
        .locator(
          'button:has-text("Memory"), button:has-text("记忆"), [role="tab"]:has-text("Memory"), [role="tab"]:has-text("记忆")',
        )
        .first();
      if (await memoryTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await memoryTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedTexts: ["No saved facts", "无记忆", "暂无"],
  },
  {
    name: "empty-skills",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    mockOverrides: { skills: [] },
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+,");
      await page.waitForTimeout(1500);
      const skillsTab = page
        .locator(
          'button:has-text("Skills"), button:has-text("技能"), [role="tab"]:has-text("Skills"), [role="tab"]:has-text("技能")',
        )
        .first();
      if (await skillsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await skillsTab.click();
        await page.waitForTimeout(500);
      }
    },
    expectedTexts: ["No skills", "无技能", "暂无"],
  },
  {
    name: "empty-admin-users",
    route: "/workspace/admin/users",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    mockOverrides: { users: [] },
    expectedTexts: ["No users", "无用户", "暂无"],
  },
  {
    name: "empty-admin-departments",
    route: "/workspace/admin/departments",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    mockOverrides: { departments: [] },
    expectedTexts: ["No departments", "无部门", "暂无"],
  },
  {
    name: "empty-admin-tools",
    route: "/workspace/admin/tools",
    needsMock: true,
    needsAuth: true,
    skipMobile: false,
    skipDark: true,
    mockOverrides: { tools: [] },
    expectedTexts: ["No tools", "无工具", "暂无"],
  },
  {
    name: "empty-command-palette",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      await page.waitForTimeout(1000);
      await page.keyboard.press("Control+k");
      await page.waitForTimeout(1000);
      // 输入无匹配内容
      const cmdInput = page
        .locator(
          '[cmdk-input], input[placeholder*="Search"], input[placeholder*="搜索"]',
        )
        .first();
      if (await cmdInput.isVisible({ timeout: 3000 }).catch(() => false)) {
        await cmdInput.fill("zzzznonexistent12345");
        await page.waitForTimeout(500);
      }
    },
    expectedTexts: ["No results", "无结果", "没有找到"],
  },

  // ─── Phase 2.2: 错误状态 ───────────────────────────────────
  {
    name: "error-login-wrong-password",
    route: "/login",
    needsMock: false,
    needsAuth: false,
    skipMobile: false,
    skipDark: true,
    actions: async (page) => {
      const emailInput = page
        .locator('input[type="email"], input[name="email"]')
        .first();
      const passwordInput = page.locator('input[type="password"]').first();
      const submitButton = page
        .locator(
          'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
        )
        .first();
      if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
        await emailInput.fill("admin@test.com");
        await passwordInput.fill("WrongPassword123!");
        await submitButton.click();
        await page.waitForTimeout(2000);
      }
    },
    expectedTexts: ["错误", "invalid", "incorrect", "Error", "失败"],
  },
  {
    name: "error-login-empty-form",
    route: "/login",
    needsMock: false,
    needsAuth: false,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const submitButton = page
        .locator(
          'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
        )
        .first();
      if (await submitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
        await submitButton.click();
        await page.waitForTimeout(1000);
      }
    },
    expectedTexts: ["required", "必填", "Please"],
  },
  {
    name: "error-setup-weak-password",
    route: "/setup",
    needsMock: false,
    needsAuth: false,
    skipMobile: false,
    skipDark: true,
    actions: async (page) => {
      const passwordInput = page.locator('input[type="password"]').first();
      const submitButton = page
        .locator(
          'button[type="submit"], button:has-text("Setup"), button:has-text("设置")',
        )
        .first();
      if (await passwordInput.isVisible({ timeout: 5000 }).catch(() => false)) {
        await passwordInput.fill("123");
        await submitButton.click();
        await page.waitForTimeout(1000);
      }
    },
    expectedTexts: ["too short", "too weak", "密码", "short", "weak"],
  },
  {
    name: "error-workflow-invalid-yaml",
    route: "/workspace/workflows/new",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      const editor = page
        .locator('.cm-editor, textarea, [contenteditable="true"]')
        .first();
      if (await editor.isVisible({ timeout: 5000 }).catch(() => false)) {
        await editor.click();
        await page.keyboard.type("invalid: yaml: content: [[[");
        await page.waitForTimeout(500);
        // 尝试保存
        const saveBtn = page
          .locator('button:has-text("Save"), button:has-text("保存")')
          .first();
        if (await saveBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await saveBtn.click();
          await page.waitForTimeout(1000);
        }
      }
    },
    expectedTexts: ["error", "invalid", "错误", "Error"],
  },
  {
    name: "error-admin-promote-confirm",
    route: "/workspace/admin/users",
    needsMock: true,
    needsAuth: true,
    skipMobile: true,
    skipDark: true,
    actions: async (page) => {
      // 尝试修改用户角色
      const roleSelect = page
        .locator('select, [role="combobox"], [data-testid="role-select"]')
        .first();
      if (await roleSelect.isVisible({ timeout: 5000 }).catch(() => false)) {
        await roleSelect.click();
        await page.waitForTimeout(500);
        const superAdminOption = page
          .locator(
            'option:has-text("super_admin"), [role="option"]:has-text("super_admin"), [role="option"]:has-text("超级管理员")',
          )
          .first();
        if (
          await superAdminOption.isVisible({ timeout: 2000 }).catch(() => false)
        ) {
          await superAdminOption.click();
          await page.waitForTimeout(500);
        }
      }
    },
    expectedElements: [
      '[role="dialog"], button:has-text("确定"), button:has-text("Confirm")',
    ],
  },

  // ─── Phase 2.3: 多角色视角 ─────────────────────────────────
  {
    name: "role-user-workspace",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    role: "user",
    skipMobile: true,
    skipDark: true,
    expectedElements: [
      'textarea, [data-testid="chat-input"], [contenteditable="true"]',
    ],
  },
  {
    name: "role-user-sidebar",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    role: "user",
    skipMobile: true,
    skipDark: true,
    expectedElements: ['[data-testid="sidebar"], nav, aside'],
    actions: async (page) => {
      const sidebar = page
        .locator('[data-testid="sidebar"], nav, aside')
        .first();
      if (await sidebar.isVisible({ timeout: 3000 }).catch(() => false)) {
        await page.waitForTimeout(500);
      }
    },
  },
  {
    name: "role-viewer-workspace",
    route: "/workspace/chats/new",
    needsMock: true,
    needsAuth: true,
    role: "viewer",
    skipMobile: true,
    skipDark: true,
    expectedElements: [
      'textarea, [data-testid="chat-input"], [contenteditable="true"]',
    ],
  },

  // ─── Phase 3.1: 缺失的路由页面 ─────────────────────────────
  {
    name: "blog-list",
    route: "/blog",
    needsMock: false,
    needsAuth: false,
    skipMobile: false,
    skipDark: true,
    expectedElements: ["main, article, .posts, .blog-list"],
  },
  {
    name: "blog-post",
    route: "/blog/posts",
    needsMock: false,
    needsAuth: false,
    skipMobile: false,
    skipDark: true,
    expectedElements: ["main, article, .post-content"],
  },
  {
    name: "blog-tags",
    route: "/blog/tags/test",
    needsMock: false,
    needsAuth: false,
    skipMobile: true,
    skipDark: true,
    expectedElements: ["main, article, .tag, .posts"],
  },
  {
    name: "docs-home",
    route: "/zh/docs",
    needsMock: false,
    needsAuth: false,
    skipMobile: false,
    skipDark: true,
    expectedElements: ["main, article, .docs, .documentation"],
  },
];

/** 辅助：登录并获取 cookie */
async function loginViaUI(
  page: Page,
  role: "admin" | "user" | "viewer" = "admin",
): Promise<void> {
  const credentials = {
    admin: {
      email: process.env.QA_ADMIN_EMAIL ?? "admin@test.com",
      password: process.env.QA_ADMIN_PASSWORD ?? "Test1234!",
    },
    user: {
      email: process.env.QA_USER_EMAIL ?? "user@test.com",
      password: process.env.QA_USER_PASSWORD ?? "Test1234!",
    },
    viewer: {
      email: process.env.QA_VIEWER_EMAIL ?? "viewer@test.com",
      password: process.env.QA_VIEWER_PASSWORD ?? "Test1234!",
    },
  };

  const { email, password } = credentials[role];
  await page.goto(`${BASE_URL}/login`);
  const emailInput = page
    .locator('input[type="email"], input[name="email"]')
    .first();
  const passwordInput = page.locator('input[type="password"]').first();
  const submitButton = page
    .locator(
      'button[type="submit"], button:has-text("登录"), button:has-text("Login")',
    )
    .first();

  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill(email);
    await passwordInput.fill(password);
    await submitButton.click();
    await page.waitForURL(/\/workspace/, { timeout: 15000 }).catch(() => {});
  }
}

// ─── Desktop 截图 ────────────────────────────────────────
test.describe("Visual Screenshots — Desktop (1280x720)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  for (const config of SCREENSHOTS) {
    test(`screenshot: ${config.name} (desktop)`, async ({ page }) => {
      // 注册健康检查监听器
      const consoleErrors: string[] = [];
      const failedRequests: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      page.on("response", (resp) => {
        if (resp.status() >= 400)
          failedRequests.push(`${resp.status()} ${resp.url()}`);
      });

      // Mock API（如果需要）
      if (config.needsMock) {
        mockLangGraphAPI(page, config.mockOverrides);
      }

      // 登录（如果需要）
      if (config.needsAuth) {
        await loginViaUI(page, config.role);
      }

      // 导航到目标页面
      await page.goto(`${BASE_URL}${config.route}`, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });

      // 等待指定元素
      if (config.waitFor) {
        await page
          .waitForSelector(config.waitFor, { timeout: 10000 })
          .catch(() => {});
      }

      // 等待网络空闲
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(500); // 动画稳定

      // 执行自定义操作
      if (config.actions) {
        await config.actions(page).catch(() => {});
      }

      // 截图
      const filePath = path.join(SCREENSHOT_DIR, `${config.name}-desktop.png`);
      await page.screenshot({ path: filePath, fullPage: true });
      console.log(`📸 Desktop screenshot saved: ${filePath}`);

      // 健康检查并输出 JSON
      const health = await runHealthChecks(
        page,
        config,
        "desktop",
        consoleErrors,
        failedRequests,
      );
      const healthPath = path.join(
        SCREENSHOT_DIR,
        `${config.name}-desktop-health.json`,
      );
      fs.writeFileSync(healthPath, JSON.stringify(health, null, 2));
      console.log(`📋 Health check: ${health.status} → ${healthPath}`);
    });
  }
});

// ─── Mobile 截图 ─────────────────────────────────────────
test.describe("Visual Screenshots — Mobile (375x812)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
  });

  // 关键页面的 mobile 截图 — 旧配置白名单 + 新配置 skipMobile 控制
  const MOBILE_NAMES = new Set([
    "landing",
    "login",
    "setup",
    "workspace-new-chat",
    "workspace-chat-with-message",
    "chat-list",
    "agents-gallery",
    "agent-detail",
    "workflows-gallery",
    "workflow-detail",
    "admin-dashboard",
    "admin-users",
    "settings-account",
  ]);
  const MOBILE_SCREENSHOTS = SCREENSHOTS.filter(
    (s) => MOBILE_NAMES.has(s.name) || s.skipMobile !== true,
  );

  for (const config of MOBILE_SCREENSHOTS) {
    test(`screenshot: ${config.name} (mobile)`, async ({ page }) => {
      const consoleErrors: string[] = [];
      const failedRequests: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      page.on("response", (resp) => {
        if (resp.status() >= 400)
          failedRequests.push(`${resp.status()} ${resp.url()}`);
      });

      if (config.needsMock) {
        mockLangGraphAPI(page, config.mockOverrides);
      }
      if (config.needsAuth) {
        await loginViaUI(page, config.role);
      }

      await page.goto(`${BASE_URL}${config.route}`, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });

      if (config.waitFor) {
        await page
          .waitForSelector(config.waitFor, { timeout: 10000 })
          .catch(() => {});
      }

      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(500);

      if (config.actions) {
        await config.actions(page).catch(() => {});
      }

      const filePath = path.join(SCREENSHOT_DIR, `${config.name}-mobile.png`);
      await page.screenshot({ path: filePath, fullPage: true });
      console.log(`📱 Mobile screenshot saved: ${filePath}`);

      const health = await runHealthChecks(
        page,
        config,
        "mobile",
        consoleErrors,
        failedRequests,
      );
      const healthPath = path.join(
        SCREENSHOT_DIR,
        `${config.name}-mobile-health.json`,
      );
      fs.writeFileSync(healthPath, JSON.stringify(health, null, 2));
      console.log(`📋 Health check: ${health.status} → ${healthPath}`);
    });
  }
});

// ─── Dark Mode 截图 ──────────────────────────────────────
test.describe("Visual Screenshots — Dark Mode", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ colorScheme: "dark" });
  });

  // Dark mode 截图 — 旧配置白名单 + 新配置 skipDark 控制
  const DARK_NAMES = new Set([
    "workspace-new-chat",
    "workspace-chat-with-message",
    "chat-list",
    "agents-gallery",
    "agent-detail",
    "workflows-gallery",
    "workflow-detail",
    "admin-dashboard",
    "admin-users",
    "settings-account",
    "command-palette",
  ]);
  const DARK_SCREENSHOTS = SCREENSHOTS.filter(
    (s) => DARK_NAMES.has(s.name) || s.skipDark !== true,
  );

  for (const config of DARK_SCREENSHOTS) {
    test(`screenshot: ${config.name} (dark)`, async ({ page }) => {
      const consoleErrors: string[] = [];
      const failedRequests: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      page.on("response", (resp) => {
        if (resp.status() >= 400)
          failedRequests.push(`${resp.status()} ${resp.url()}`);
      });

      if (config.needsMock) {
        mockLangGraphAPI(page, config.mockOverrides);
      }
      if (config.needsAuth) {
        await loginViaUI(page, config.role);
      }

      await page.goto(`${BASE_URL}${config.route}`, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });

      if (config.waitFor) {
        await page
          .waitForSelector(config.waitFor, { timeout: 10000 })
          .catch(() => {});
      }

      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(500);

      if (config.actions) {
        await config.actions(page).catch(() => {});
      }

      const filePath = path.join(SCREENSHOT_DIR, `${config.name}-dark.png`);
      await page.screenshot({ path: filePath, fullPage: true });
      console.log(`🌙 Dark mode screenshot saved: ${filePath}`);

      const health = await runHealthChecks(
        page,
        config,
        "dark",
        consoleErrors,
        failedRequests,
      );
      const healthPath = path.join(
        SCREENSHOT_DIR,
        `${config.name}-dark-health.json`,
      );
      fs.writeFileSync(healthPath, JSON.stringify(health, null, 2));
      console.log(`📋 Health check: ${health.status} → ${healthPath}`);
    });
  }
});
