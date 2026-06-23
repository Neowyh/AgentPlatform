# iDeer 用户手册 & 开发运维手册生成计划

> **创建日期**: 2026-06-12
> **目标**: 生成两份完整手册 + UI截图

---

## 一、任务总览

### 1.1 交付物

| 交付物 | 格式 | 位置 |
|--------|------|------|
| 用户使用手册 | Markdown | `docs/user-manual.md` |
| 开发运维手册 | Markdown | `docs/devops-manual.md` |
| UI截图 | PNG | `docs/screenshots/` |

### 1.2 截图生成方案

由于无法直接访问运行中的应用进行截图，提供以下三种解决方案：

#### 方案A：Playwright自动化截图（推荐）

利用项目已有的Playwright E2E测试框架，编写自动化截图脚本。

**优势**：
- 项目已有完整的Playwright配置
- 可复用现有的测试fixtures
- 自动化程度高，可重复执行

**实现步骤**：

1. **创建截图脚本** `frontend/scripts/generate-screenshots.ts`
```typescript
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const SCREENSHOT_DIR = 'docs/screenshots';

// 截图配置
interface ScreenshotConfig {
  name: string;
  path: string;
  waitFor?: string;  // 等待的选择器
  actions?: (page: Page) => Promise<void];  // 额外操作
  viewport?: { width: number; height: number };
}

// 截图列表
const screenshots: ScreenshotConfig[] = [
  {
    name: 'login-page',
    path: '/login',
    waitFor: 'form',
  },
  {
    name: 'setup-page',
    path: '/setup',
    waitFor: 'form',
  },
  {
    name: 'workspace-welcome',
    path: '/workspace/chats/new',
    waitFor: '[data-testid="welcome"]',
  },
  {
    name: 'workspace-chat',
    path: '/workspace/chats/new',
    actions: async (page) => {
      // 发送测试消息
      await page.fill('textarea', '你好，请介绍一下自己');
      await page.press('textarea', 'Enter');
      await page.waitForSelector('[data-testid="message-ai"]', { timeout: 30000 });
    },
  },
  {
    name: 'sidebar-expanded',
    path: '/workspace/chats/new',
    actions: async (page) => {
      // 确保侧边栏展开
      await page.click('[data-testid="sidebar-toggle"]');
    },
  },
  {
    name: 'model-selector',
    path: '/workspace/chats/new',
    actions: async (page) => {
      await page.click('[data-testid="model-selector-trigger"]');
      await page.waitForSelector('[data-testid="model-selector-dialog"]');
    },
  },
  {
    name: 'mode-selector',
    path: '/workspace/chats/new',
    actions: async (page) => {
      await page.click('[data-testid="mode-selector-trigger"]');
    },
  },
  {
    name: 'agents-gallery',
    path: '/workspace/agents',
    waitFor: '[data-testid="agent-gallery"]',
  },
  {
    name: 'workflows-gallery',
    path: '/workspace/workflows',
    waitFor: '[data-testid="workflow-gallery"]',
  },
  {
    name: 'settings-dialog',
    path: '/workspace/chats/new',
    actions: async (page) => {
      await page.click('[data-testid="settings-trigger"]');
      await page.waitForSelector('[data-testid="settings-dialog"]');
    },
  },
  {
    name: 'admin-dashboard',
    path: '/workspace/admin',
    waitFor: '[data-testid="admin-stats"]',
  },
  {
    name: 'admin-users',
    path: '/workspace/admin/users',
    waitFor: '[data-testid="user-list"]',
  },
  {
    name: 'file-upload',
    path: '/workspace/chats/new',
    actions: async (page) => {
      // 模拟文件上传
      const fileInput = await page.locator('input[type="file"]');
      await fileInput.setInputFiles('tests/fixtures/test.pdf');
      await page.waitForSelector('[data-testid="file-preview"]');
    },
  },
  {
    name: 'artifacts-panel',
    path: '/workspace/chats/new',
    actions: async (page) => {
      // 触发生成工件
      await page.fill('textarea', '用Python写一个快速排序算法，保存为文件');
      await page.press('textarea', 'Enter');
      await page.waitForSelector('[data-testid="artifacts-trigger"]', { timeout: 60000 });
      await page.click('[data-testid="artifacts-trigger"]');
    },
  },
  {
    name: 'command-palette',
    path: '/workspace/chats/new',
    actions: async (page) => {
      await page.press('body', 'Meta+k');
      await page.waitForSelector('[data-testid="command-palette"]');
    },
  },
];

// 主函数
async function generateScreenshots() {
  // 创建输出目录
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  for (const config of screenshots) {
    const { test } = await import('@playwright/test');

    test(`screenshot: ${config.name}`, async ({ page }) => {
      // 设置视口
      if (config.viewport) {
        await page.setViewportSize(config.viewport);
      } else {
        await page.setViewportSize({ width: 1440, height: 900 });
      }

      // 导航
      await page.goto(config.path);

      // 等待元素
      if (config.waitFor) {
        await page.waitForSelector(config.waitFor);
      }

      // 执行额外操作
      if (config.actions) {
        await config.actions(page);
      }

      // 截图
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${config.name}.png`),
        fullPage: false,
      });
    });
  }
}

generateScreenshots();
```

2. **运行截图脚本**
```bash
cd frontend
npx playwright test scripts/generate-screenshots.ts --project=chromium
```

3. **输出**
- 截图保存到 `docs/screenshots/`
- 文件名格式：`{功能模块}-{页面/状态}.png`

#### 方案B：手动截图清单

如果无法运行自动化脚本，提供手动截图清单：

| 编号 | 截图名称 | 页面路径 | 操作步骤 |
|------|----------|----------|----------|
| 01 | login-page | `/login` | 直接访问 |
| 02 | setup-page | `/setup` | 首次启动访问 |
| 03 | workspace-welcome | `/workspace/chats/new` | 登录后访问 |
| 04 | workspace-chat | `/workspace/chats/new` | 发送消息后 |
| 05 | sidebar-expanded | 任意workspace页面 | 展开侧边栏 |
| 06 | sidebar-collapsed | 任意workspace页面 | 折叠侧边栏 |
| 07 | model-selector | 聊天页面 | 点击模型名称 |
| 08 | mode-selector | 聊天页面 | 点击模式按钮 |
| 09 | file-upload | 聊天页面 | 上传文件后 |
| 10 | artifacts-panel | 聊天页面 | 生成文件后点击工件按钮 |
| 11 | agents-gallery | `/workspace/agents` | 直接访问 |
| 12 | agent-create | `/workspace/agents/new` | 点击新建Agent |
| 13 | workflows-gallery | `/workspace/workflows` | 直接访问 |
| 14 | workflow-editor | `/workspace/workflows/new` | 点击新建工作流 |
| 15 | settings-dialog | 任意workspace页面 | 点击设置按钮 |
| 16 | settings-memory | 设置对话框 | 点击记忆选项卡 |
| 17 | settings-skills | 设置对话框 | 点击技能选项卡 |
| 18 | admin-dashboard | `/workspace/admin` | 管理员访问 |
| 19 | admin-users | `/workspace/admin/users` | 点击用户管理 |
| 20 | admin-departments | `/workspace/admin/departments` | 点击部门管理 |
| 21 | command-palette | 任意页面 | 按Cmd+K |
| 22 | thinking-process | 聊天页面 | 使用Pro/Ultra模式 |
| 23 | followup-suggestions | 聊天页面 | AI响应后 |
| 24 | export-dialog | 聊天页面 | 点击导出按钮 |

#### 方案C：使用现有E2E测试截图

项目的E2E测试已经覆盖了主要功能流程，可以直接使用或修改现有测试来生成截图：

```bash
# 运行现有测试并生成截图
cd frontend
npx playwright test --project=chromium --update-snapshots

# 截图保存在 test-results/ 目录
```

### 1.3 截图命名规范

```
docs/screenshots/
├── 01-login-page.png
├── 02-setup-admin.png
├── 03-workspace-welcome.png
├── 04-workspace-chat.png
├── 05-sidebar-expanded.png
├── 06-sidebar-collapsed.png
├── 07-model-selector.png
├── 08-mode-flash.png
├── 09-mode-thinking.png
├── 10-mode-pro.png
├── 11-mode-ultra.png
├── 12-file-upload.png
├── 13-file-preview.png
├── 14-artifacts-panel.png
├── 15-artifacts-detail.png
├── 16-thinking-process.png
├── 17-task-decomposition.png
├── 18-tool-call.png
├── 19-sources-citation.png
├── 20-followup-suggestions.png
├── 21-agents-gallery.png
├── 22-agent-create.png
├── 23-agent-edit.png
├── 24-agent-chat.png
├── 25-workflows-gallery.png
├── 26-workflow-create.png
├── 27-workflow-editor.png
├── 28-workflow-run.png
├── 29-workflow-human-review.png
├── 30-settings-account.png
├── 31-settings-appearance.png
├── 32-settings-memory.png
├── 33-settings-skills.png
├── 34-settings-tools.png
├── 35-admin-dashboard.png
├── 36-admin-users.png
├── 37-admin-user-edit.png
├── 38-admin-departments.png
├── 39-admin-tools.png
├── 40-command-palette.png
├── 41-export-markdown.png
├── 42-export-json.png
├── 43-thread-rename.png
├── 44-thread-delete.png
└── 45-error-state.png
```

---

## 二、用户使用手册结构

### 2.1 目录大纲

```markdown
# iDeer 用户使用手册

## 1. 项目简介
   - 1.1 什么是 iDeer
   - 1.2 核心能力概览
   - 1.3 适用场景

## 2. 快速开始
   - 2.1 访问系统
   - 2.2 首次登录
   - 2.3 界面导览

## 3. 智能对话
   - 3.1 发送消息
   - 3.2 查看响应
   - 3.3 思维链展示
   - 3.4 后续建议
   - 3.5 对话历史

## 4. 模型与模式
   - 4.1 选择模型
   - 4.2 Flash模式
   - 4.3 Thinking模式
   - 4.4 Pro模式
   - 4.5 Ultra模式
   - 4.6 推理深度控制

## 5. 文件处理
   - 5.1 上传文件
   - 5.2 文件预览
   - 5.3 支持的格式
   - 5.4 文件分析示例

## 6. 工件管理
   - 6.1 什么是工件
   - 6.2 查看工件
   - 6.3 下载工件
   - 6.4 工件类型

## 7. 技能系统
   - 7.1 内置技能
   - 7.2 启用/禁用技能
   - 7.3 创建自定义技能
   - 7.4 安装技能包

## 8. 智能体（Agent）
   - 8.1 什么是Agent
   - 8.2 浏览Agent画廊
   - 8.3 创建Agent
   - 8.4 使用Agent
   - 8.5 导入/导出Agent

## 9. 工作流（Workflow）
   - 9.1 什么是工作流
   - 9.2 浏览工作流
   - 9.3 创建工作流
   - 9.4 运行工作流
   - 9.5 人工审核

## 10. 系统设置
    - 10.1 账户设置
    - 10.2 外观设置
    - 10.3 通知设置
    - 10.4 记忆管理
    - 10.5 工具配置
    - 10.6 技能管理

## 11. 管理功能（管理员）
    - 11.1 管理后台概览
    - 11.2 用户管理
    - 11.3 部门管理
    - 11.4 工具管理
    - 11.5 角色权限

## 12. 快捷操作
    - 12.1 键盘快捷键
    - 12.2 命令面板
    - 12.3 对话导出
    - 12.4 分享对话

## 13. 常见问题
    - 13.1 登录问题
    - 13.2 对话问题
    - 13.3 文件问题
    - 13.4 性能问题

## 附录
    - A. 快捷键速查表
    - B. 支持的文件格式
    - C. 支持的模型列表
    - D. 术语表
```

### 2.2 内容编写规范

**每个功能模块包含**：
1. **功能说明**：简要介绍功能用途
2. **操作步骤**：分步骤的操作指南
3. **界面截图**：标注关键元素的截图
4. **注意事项**：使用技巧和限制
5. **示例**：实际使用场景

**格式规范**：
- 使用中文，技术术语保留英文
- 截图使用相对路径：`![截图说明](screenshots/xx-name.png)`
- 操作步骤使用有序列表
- 注意事项使用 `> ⚠️` 格式
- 技巧使用 `> 💡` 格式

---

## 三、开发运维手册结构

### 3.1 目录大纲

```markdown
# iDeer 开发运维手册

## 1. 架构概览
   - 1.1 系统架构图
   - 1.2 技术栈详解
   - 1.3 数据流图
   - 1.4 目录结构说明

## 2. 开发环境搭建
   - 2.1 系统要求
   - 2.2 依赖安装
   - 2.3 配置文件
   - 2.4 启动开发服务
   - 2.5 IDE配置

## 3. 前端开发指南
   - 3.1 技术栈
   - 3.2 目录结构
   - 3.3 路由系统
   - 3.4 组件库
   - 3.5 状态管理
   - 3.6 API调用
   - 3.7 国际化
   - 3.8 样式系统

## 4. 后端开发指南
   - 4.1 技术栈
   - 4.2 目录结构
   - 4.3 API路由
   - 4.4 中间件系统
   - 4.5 Agent系统
   - 4.6 工具系统
   - 4.7 技能系统
   - 4.8 工作流引擎
   - 4.9 数据库

## 5. 新功能开发流程
   - 5.1 前端新页面
   - 5.2 前端新组件
   - 5.3 后端新API
   - 5.4 新工具开发
   - 5.5 新技能开发
   - 5.6 新Agent类型
   - 5.7 新工作流步骤

## 6. 问题定位指南
   - 6.1 日志系统
   - 6.2 前端调试
   - 6.3 后端调试
   - 6.4 API调试
   - 6.5 Agent调试
   - 6.6 数据库调试
   - 6.7 性能分析

## 7. 部署运维
   - 7.1 Docker部署
   - 7.2 本地部署
   - 7.3 内网部署
   - 7.4 环境变量
   - 7.5 配置管理
   - 7.6 nginx配置
   - 7.7 SSL/TLS

## 8. 数据库管理
   - 8.1 数据库类型
   - 8.2 迁移管理
   - 8.3 备份恢复
   - 8.4 性能优化

## 9. 监控与日志
   - 9.1 日志配置
   - 9.2 日志级别
   - 9.3 日志分析
   - 9.4 性能监控
   - 9.5 错误追踪

## 10. 安全机制
    - 10.1 认证系统
    - 10.2 CSRF防护
    - 10.3 RBAC权限
    - 10.4 沙盒安全
    - 10.5 API安全

## 11. 测试体系
    - 11.1 单元测试
    - 11.2 集成测试
    - 11.3 E2E测试
    - 11.4 性能测试
    - 11.5 CI/CD

## 12. 扩展开发
    - 12.1 自定义LLM Provider
    - 12.2 自定义工具
    - 12.3 自定义技能
    - 12.4 自定义中间件
    - 12.5 MCP服务器
    - 12.6 IM渠道集成

## 附录
    - A. API参考文档
    - B. 配置文件参考
    - C. 环境变量参考
    - D. 错误代码表
    - E. 术语表
```

### 3.2 核心代码位置速查表

#### 前端关键文件

| 功能 | 文件路径 |
|------|----------|
| 路由定义 | `frontend/src/app/` |
| 根布局 | `frontend/src/app/layout.tsx` |
| 工作空间布局 | `frontend/src/app/workspace/layout.tsx` |
| 聊天页面 | `frontend/src/app/workspace/chats/[thread_id]/page.tsx` |
| 登录页面 | `frontend/src/app/(auth)/login/page.tsx` |
| 设置页面 | `frontend/src/components/workspace/settings/` |
| Agent页面 | `frontend/src/app/workspace/agents/` |
| Workflow页面 | `frontend/src/app/workspace/workflows/` |
| 管理后台 | `frontend/src/app/workspace/admin/` |
| API客户端 | `frontend/src/core/api/` |
| 认证系统 | `frontend/src/core/auth/` |
| 线程管理 | `frontend/src/core/threads/` |
| 模型选择器 | `frontend/src/components/ai-elements/model-selector.tsx` |
| 输入框 | `frontend/src/components/workspace/input-box.tsx` |
| 侧边栏 | `frontend/src/components/workspace/workspace-sidebar.tsx` |
| 消息组件 | `frontend/src/components/workspace/messages/` |
| 工件组件 | `frontend/src/components/workspace/artifacts/` |

#### 后端关键文件

| 功能 | 文件路径 |
|------|----------|
| FastAPI应用 | `backend/app/gateway/app.py` |
| API路由 | `backend/app/gateway/routers/` |
| 认证中间件 | `backend/app/gateway/auth_middleware.py` |
| CSRF中间件 | `backend/app/gateway/csrf_middleware.py` |
| Agent工厂 | `backend/packages/harness/ideer/agents/` |
| 配置系统 | `backend/packages/harness/ideer/config/` |
| LLM适配器 | `backend/packages/harness/ideer/models/` |
| 工具注册 | `backend/packages/harness/ideer/tools/` |
| 技能系统 | `backend/packages/harness/ideer/skills/` |
| 工作流引擎 | `backend/packages/harness/ideer/workflows/` |
| 数据库模型 | `backend/packages/harness/ideer/persistence/models/` |
| 数据库迁移 | `backend/packages/harness/ideer/persistence/alembic/` |
| 沙盒系统 | `backend/packages/harness/ideer/sandbox/` |
| MCP客户端 | `backend/packages/harness/ideer/mcp/` |
| 子代理系统 | `backend/packages/harness/ideer/subagents/` |
| 社区工具 | `backend/packages/harness/ideer/community/` |

#### 配置文件

| 文件 | 用途 |
|------|------|
| `config.yaml` | 运行时配置 |
| `config.example.yaml` | 配置模板 |
| `.env` | 环境变量 |
| `docker/docker-compose.yaml` | Docker生产配置 |
| `docker/nginx/nginx.conf` | nginx配置 |

#### 测试文件

| 类型 | 路径 |
|------|------|
| 后端单元测试 | `backend/tests/` |
| 前端单元测试 | `frontend/tests/unit/` |
| E2E测试 | `frontend/tests/e2e/` |
| Playwright配置 | `frontend/playwright.config.ts` |

### 3.3 问题定位速查

| 问题类型 | 首先检查 | 关键日志/文件 |
|----------|----------|---------------|
| 登录失败 | JWT配置、Cookie | `backend/app/gateway/auth/` |
| API 401 | 认证中间件 | `auth_middleware.py` |
| API 403 | CSRF token | `csrf_middleware.py` |
| 模型调用失败 | API密钥、网络 | `.env`, `config.yaml` |
| 工具执行失败 | 工具配置、沙盒状态 | `ideer/tools/`, `ideer/sandbox/` |
| 技能加载失败 | 技能路径、格式 | `ideer/skills/` |
| 工作流执行失败 | YAML语法、步骤配置 | `ideer/workflows/` |
| 文件上传失败 | 文件大小、格式 | `ideer/uploads/` |
| 数据库错误 | 连接配置、迁移状态 | `ideer/persistence/` |
| 前端白屏 | 浏览器控制台 | `frontend/src/` |
| 流式响应中断 | nginx配置、超时 | `docker/nginx/nginx.conf` |

---

## 四、执行计划

### 4.1 第一阶段：准备截图环境

1. **检查现有E2E测试**
   - 查看 `frontend/tests/e2e/` 中的测试用例
   - 确定可复用的测试fixtures

2. **创建截图脚本**
   - 基于Playwright编写自动化截图脚本
   - 配置测试用户和数据

3. **运行截图脚本**
   - 启动开发服务
   - 执行截图脚本
   - 验证截图质量

### 4.2 第二阶段：生成用户手册

1. **编写内容**
   - 按照目录结构编写各章节
   - 插入截图引用
   - 添加操作步骤和注意事项

2. **审核和完善**
   - 检查截图是否匹配描述
   - 补充遗漏的功能点
   - 优化语言表达

### 4.3 第三阶段：生成开发运维手册

1. **编写内容**
   - 整理技术架构文档
   - 编写开发指南
   - 编写问题定位指南

2. **代码位置映射**
   - 验证所有文件路径
   - 添加行号引用（关键代码）

3. **审核和完善**
   - 技术准确性验证
   - 补充实际案例
   - 添加最佳实践

### 4.4 第四阶段：质量检查

1. **内容完整性检查**
   - 功能覆盖度
   - 截图完整性
   - 链接有效性

2. **技术准确性检查**
   - 代码路径验证
   - 命令可执行性
   - 配置示例正确性

3. **格式规范检查**
   - Markdown语法
   - 截图显示
   - 目录链接

---

## 五、风险和缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 无法自动登录 | 截图脚本失败 | 使用测试数据库预置用户 |
| 页面加载慢 | 截图超时 | 增加等待时间、使用waitForSelector |
| 动态内容不稳定 | 截图不一致 | 固定测试数据、mock API响应 |
| 截图质量差 | 文档不专业 | 设置高分辨率、统一视口大小 |
| 代码路径变化 | 文档过时 | 建立代码-文档映射检查机制 |

---

## 六、成功标准

### 6.1 用户手册

- [ ] 覆盖所有用户可见功能
- [ ] 每个功能有清晰的操作步骤
- [ ] 关键界面有截图说明
- [ ] 常见问题有解答
- [ ] 快捷键速查表完整

### 6.2 开发运维手册

- [ ] 架构图清晰准确
- [ ] 关键代码位置可快速定位
- [ ] 新功能开发流程完整
- [ ] 问题定位指南实用
- [ ] 部署运维步骤可执行

### 6.3 截图

- [ ] 覆盖所有主要界面
- [ ] 截图清晰、分辨率足够
- [ ] 文件命名规范统一
- [ ] 在手册中正确引用

---

## 七、后续维护

### 7.1 文档版本管理

- 文档与代码同步更新
- 重大功能变更时更新文档
- 定期审核文档准确性

### 7.2 截图更新机制

- UI重大变更时重新截图
- 使用Playwright自动化脚本
- 版本化截图文件

### 7.3 反馈收集

- 收集用户使用反馈
- 持续优化文档内容
- 补充缺失的场景

---

**计划制定人**: Claude AI
**审核状态**: 待审核
**预计完成时间**: 根据截图方案确定

---

## 八、用户确认

**截图方案**: 方案A - Playwright自动化截图
**生成范围**: 先生成手册框架
**输出位置**: `docs/manual/` 目录

### 8.1 最终交付物结构

```
docs/manual/
├── README.md                    # 手册目录和说明
├── user-manual.md               # 用户使用手册
├── devops-manual.md             # 开发运维手册
├── screenshots/                 # 截图目录
│   ├── 01-login-page.png
│   ├── 02-setup-admin.png
│   ├── ...
│   └── 45-error-state.png
└── scripts/
    └── generate-screenshots.ts  # 截图生成脚本
```

### 8.2 执行步骤

1. **创建目录结构**
   - `docs/manual/`
   - `docs/manual/screenshots/`
   - `docs/manual/scripts/`

2. **编写截图脚本**
   - `docs/manual/scripts/generate-screenshots.ts`
   - 配置45个截图场景
   - 集成现有Playwright fixtures

3. **生成手册框架**
   - `docs/manual/user-manual.md` - 用户手册框架
   - `docs/manual/devops-manual.md` - 开发运维手册框架
   - `docs/manual/README.md` - 手册目录和使用说明

4. **运行截图脚本**（需要用户执行）
   ```bash
   cd frontend
   npx playwright test ../docs/manual/scripts/generate-screenshots.ts --project=chromium
   ```

5. **补充完整内容**（后续迭代）
   - 根据截图完善手册内容
   - 添加详细的操作步骤
   - 补充代码位置引用
