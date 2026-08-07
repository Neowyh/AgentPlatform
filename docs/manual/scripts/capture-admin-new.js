/**
 * 新增管理功能截图生成脚本
 *
 * 针对 2026-08 新增/重构的管理页面（审批管理、审计日志、资源管理）。
 * 通过 browser route 注入示例数据，配合 IDEER_AUTH_DISABLED 的独立前端实例使用。
 *
 * 使用方法:
 *   cd frontend
 *   node ../docs/manual/scripts/capture-admin-new.js
 */

const { chromium } = require(require.resolve('@playwright/test', { paths: [process.cwd() + '/node_modules'] }));
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = path.resolve(__dirname, '../screenshots');
// 截图专用实例：带 IDEER_AUTH_DISABLED=1 启动，避免真实登录态
const BASE_URL = process.env.SCREENSHOT_BASE_URL || 'http://localhost:3003';

// 确保输出目录存在
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const mockVisibleApps = {
  applications: [
    {
      id: 'app-1',
      resource_type: 'workflow',
      resource_id: 'wf:data-analysis',
      applicant_id: 'user-1',
      current_visibility: 'private',
      target_visibility: 'department',
      department_id: 'dept-1',
      reason: '部门内协作需要（数据分析流程）',
      status: 'pending',
      submitted_at: '2026-08-06T09:30:00Z',
      reviewed_by: null,
      reviewed_at: null,
      review_comment: null,
      version: 1,
    },
    {
      id: 'app-2',
      resource_type: 'agent',
      resource_id: 'agent:sales-assistant',
      applicant_id: 'user-2',
      current_visibility: 'department',
      target_visibility: 'public',
      department_id: 'dept-1',
      reason: '沉淀为本组公共销售助手',
      status: 'pending',
      submitted_at: '2026-08-06T10:12:00Z',
      reviewed_by: null,
      reviewed_at: null,
      review_comment: null,
      version: 1,
    },
    {
      id: 'app-3',
      resource_type: 'skill',
      resource_id: 'skill:data-viz',
      applicant_id: 'user-3',
      current_visibility: 'private',
      target_visibility: 'public',
      department_id: null,
      reason: '数据可视化技能，全公司共用',
      status: 'approved',
      submitted_at: '2026-08-05T14:00:00Z',
      reviewed_by: 'admin-1',
      reviewed_at: '2026-08-05T15:20:00Z',
      review_comment: '同意公开',
      version: 2,
    },
  ],
  total: 3,
  page: 1,
  page_size: 20,
};

const mockAuditLogs = {
  items: [
    {
      id: 'log-1',
      actor_id: 'user-1',
      action: 'apply',
      resource_type: 'workflow',
      resource_id: 'wf:data-analysis',
      detail: '{"from":"private","to":"department"}',
      ip_address: '10.0.0.5',
      created_at: '2026-08-06T09:30:00Z',
    },
    {
      id: 'log-2',
      actor_id: 'admin-1',
      action: 'approve',
      resource_type: 'skill',
      resource_id: 'skill:data-viz',
      detail: '{"application_id":"app-3","visibility":"public"}',
      ip_address: '10.0.0.1',
      created_at: '2026-08-05T15:20:00Z',
    },
    {
      id: 'log-3',
      actor_id: 'user-2',
      action: 'create',
      resource_type: 'agent',
      resource_id: 'agent:sales-assistant',
      detail: '{}',
      ip_address: '10.0.0.7',
      created_at: '2026-08-05T11:00:00Z',
    },
    {
      id: 'log-4',
      actor_id: 'system',
      action: 'revoke',
      resource_type: 'user',
      resource_id: 'user-9',
      detail: '{"reason":"用户离职"}',
      ip_address: null,
      created_at: '2026-08-04T16:45:00Z',
    },
    {
      id: 'log-5',
      actor_id: 'user-3',
      action: 'update',
      resource_type: 'workflow',
      resource_id: 'wf:report-gen',
      detail: '{"change":"增加 interrupt 审批节点"}',
      ip_address: '10.0.0.9',
      created_at: '2026-08-04T10:05:00Z',
    },
  ],
  total: 5,
  page: 1,
  page_size: 20,
};

const mockResources = {
  resources: [
    {
      id: 'agent:sales-assistant',
      resource_type: 'agent',
      resource_type_label: 'Agent',
      resource_id: 'agent:sales-assistant',
      visibility: 'department',
      owner_id: 'user-2',
      department_id: 'dept-1',
      created_at: '2026-08-05T11:00:00Z',
    },
    {
      id: 'wf:data-analysis',
      resource_type: 'workflow',
      resource_type_label: 'Workflow',
      resource_id: 'wf:data-analysis',
      visibility: 'private',
      owner_id: 'user-1',
      department_id: 'dept-1',
      created_at: '2026-08-06T09:15:00Z',
    },
    {
      id: 'skill:data-viz',
      resource_type: 'skill',
      resource_type_label: 'Skill',
      resource_id: 'skill:data-viz',
      visibility: 'public',
      owner_id: 'user-3',
      department_id: null,
      created_at: '2026-08-05T15:20:00Z',
    },
    {
      id: 'tool:web_search',
      resource_type: 'tool',
      resource_type_label: 'Tool',
      resource_id: 'tool:web_search',
      visibility: 'public',
      owner_id: null,
      department_id: null,
      created_at: '2026-07-30T08:00:00Z',
    },
  ],
  total: 4,
  page: 1,
  page_size: 20,
};

// 需要生成的截图：路径 + 要 mock 的接口（url 部分匹配） + 等待的 data-testid
const screenshots = [
  {
    name: '47-admin-visibility-applications',
    url: '/workspace/admin/visibility-applications',
    waitFor: '[data-testid="visibility-applications-page"]',
    mocks: [
      { url: '**/api/visibility-applications*', payload: mockVisibleApps, contentType: 'application/json' },
    ],
    timeout: 15000,
  },
  {
    name: '48-admin-audit-logs',
    url: '/workspace/admin/audit-logs',
    waitFor: '[data-testid="audit-logs-page"]',
    mocks: [
      { url: '**/api/admin/audit-logs*', payload: mockAuditLogs, contentType: 'application/json' },
    ],
    timeout: 15000,
  },
  {
    name: '49-admin-resources',
    url: '/workspace/admin/resources',
    waitFor: '[data-testid="resource-table"]',
    mocks: [
      { url: '**/api/admin/resources*', payload: mockResources, contentType: 'application/json' },
    ],
    timeout: 15000,
  },
];

async function captureScreenshots() {
  console.log('🚀 开始生成新增管理页面截图...');
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

    // 先注册 route mock：页面内 client 组件渲染时会请求这些 API
    for (const mock of config.mocks) {
      await page.route(mock.url, (route) => {
        route.fulfill({
          status: 200,
          contentType: mock.contentType || 'application/json',
          body: JSON.stringify(mock.payload),
        });
      });
    }

    try {
      console.log(`📸 正在生成: ${config.name}`);

      await page.goto(`${BASE_URL}${config.url}`, { waitUntil: 'networkidle', timeout: 30000 });

      if (config.waitFor) {
        await page.waitForSelector(config.waitFor, { timeout: config.timeout || 15000 });
      }

      await page.waitForTimeout(1500);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${config.name}.png`),
        fullPage: false,
      });

      console.log(`  ✅ 截图已保存`);
      successCount++;
    } catch (e) {
      console.error(`  ❌ 失败: ${e.message}`);
      // 失败也尝试截图，便于排查
      try {
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${config.name}-error.png`) });
      } catch {}
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