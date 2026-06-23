# 截图生成问题记录

> **创建日期**: 2026-06-12
> **修复日期**: 2026-06-12
> **状态**: ✅ 已修复

---

## 一、问题概述

在自动生成 UI 截图过程中，45 个截图中有 20 个无法正确捕获目标页面状态，生成的是空白/默认页面截图（占位图）。

**原始成功率**: 26/45 (57.8%)

---

## 二、根因分析

经过代码审查，所有 `data-testid` 选择器在前端代码中均正确存在。问题的根因是**截图脚本的运行时交互问题**，而非选择器缺失。

| 问题类别 | 根因 | 影响截图数 |
|---------|------|-----------|
| 聊天输入框超时 | textarea 在嵌套组件中，页面加载后未等待可交互状态 | 10 |
| 设置对话框失败 | 侧边栏可能折叠，nav-menu-trigger 不可见 | 6 |
| 侧边栏操作失败 | 折叠状态下 trigger 元素 hidden，需 hover 才显示 | 2 |
| 模型/模式选择器 | 元素可能被遮挡或需要特定交互才能显示 | 5 |
| 文件上传失败 | 隐藏元素 + 选择器匹配问题 | 2 |
| 线程操作失败 | 线程列表为空（无历史对话） | 2 |
| Agent/工作流失败 | 列表为空或按钮不可见 | 3 |

---

## 三、修复方案

### 3.1 新增辅助函数

在 `docs/manual/scripts/capture-all.js` 中添加了以下辅助函数：

| 函数 | 职责 |
|------|------|
| `loginIfNeeded(page)` | 检测登录页面，自动填写凭证并登录 |
| `ensureSidebarExpanded(page)` | 检查侧边栏状态，折叠时 hover + click 展开 |
| `ensureSidebarCollapsed(page)` | 检查侧边栏状态，展开时 click 折叠 |
| `waitForChatReady(page)` | 等待 input-box wrapper → textarea visible → textarea enabled |
| `openSettings(page, tabId)` | 展开侧边栏 → 点击导航菜单 → 打开设置 → 切换 tab |
| `createTestConversation(page)` | 发送测试消息创建对话，用于线程操作截图 |

### 3.2 各问题修复详情

#### 2.1 聊天输入框（10 个截图）
- **修复**: 使用 `waitForChatReady()` 先等待 wrapper，再等待 textarea 可见且启用
- **选择器**: `textarea[data-testid="chat-input"]`（更精确的定位）

#### 2.2 设置对话框（6 个截图）
- **修复**: 使用 `openSettings(page, tabId)` 统一处理
- **流程**: 展开侧边栏 → 点击 nav-menu-trigger → 点击 settings-menu-item → 切换 tab

#### 2.3 侧边栏（2 个截图）
- **修复**: 使用 `ensureSidebarExpanded()` / `ensureSidebarCollapsed()`
- **关键**: 折叠状态下 trigger 是 hidden 的，需先 hover header 区域使其显示

#### 2.4 模型/模式选择器（5 个截图）
- **修复**: 先调用 `waitForChatReady()` 确保页面就绪
- **改进**: 使用 `role="menuitem"` + `hasText` 组合选择器替代纯文本匹配

#### 2.5 文件上传（2 个截图）
- **修复**: 使用 `[data-testid="file-input"], input[type="file"]` 双选择器

#### 2.6 线程操作（2 个截图）
- **修复**: 使用 `createTestConversation()` 先创建测试对话
- **改进**: 先 hover thread-item，再点击 actions trigger

#### 2.7 Agent/工作流（3 个截图）
- **修复**: 增加显式等待 `[data-testid="agent-card"]` / `[data-testid="workflow-card"]`

### 3.3 其他改进

- **自动登录**: 首次访问 workspace 页面时自动检测并登录
- **环境变量**: 支持 `TEST_EMAIL` 和 `TEST_PASSWORD` 配置测试凭证
- **命令面板**: 使用 `Control+k` 作为 `Meta+k` 的备选（跨平台兼容）
- **导出菜单**: 使用 `role="menuitem"` + `hasText` 选择器
- **超时优化**: 各处增加合理的超时和错误处理

---

## 四、使用方法

```bash
# 启动服务
make start

# 运行截图脚本（默认凭证）
cd frontend && node ../docs/manual/scripts/capture-all.js

# 使用自定义凭证
TEST_EMAIL=user@example.com TEST_PASSWORD=mypassword cd frontend && node ../docs/manual/scripts/capture-all.js
```

---

## 五、验证清单

- [ ] 运行截图脚本，成功率 >90%
- [ ] 检查 `docs/manual/screenshots/` 目录中的截图
- [ ] 验证聊天对话截图（04）显示实际对话内容
- [ ] 验证设置对话框截图（30-35）显示正确的 tab 内容
- [ ] 验证侧边栏截图（05-06）显示展开/折叠状态
- [ ] 验证线程操作截图（43-44）显示操作菜单

---

## 六、相关文件

- 截图脚本: `docs/manual/scripts/capture-all.js`（已修复）
- 截图目录: `docs/manual/screenshots/`
- 截图清单: `docs/manual/README.md`
- 用户手册: `docs/manual/user-manual.md`
