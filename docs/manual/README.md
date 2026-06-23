# iDeer 平台手册

> **版本**: v1.0  
> **更新日期**: 2026-06-12

---

## 手册列表

| 手册 | 说明 | 适用对象 |
|------|------|----------|
| [用户使用手册](user-manual.md) | 平台功能操作指南 | 所有用户、管理员 |
| [开发运维手册](devops-manual.md) | 架构设计、开发指南、部署运维 | 开发人员、运维人员 |

---

## 截图说明

本手册引用的 UI 截图存放在 `screenshots/` 目录下。

### 生成截图

截图通过 Playwright 自动化脚本生成：

```bash
cd frontend
npx playwright test ../docs/manual/scripts/generate-screenshots.ts --project=chromium
```

### 手动截图清单

如果无法运行自动化脚本，请参考下方清单进行手动截图。

### 已生成截图

| 编号 | 文件名 | 页面 | 操作 |
|------|--------|------|------|
| 01 | 01-login-page.png | `/login` | 直接访问 |
| 02 | 02-setup-admin.png | `/setup` | 首次启动 |
| 03 | 03-workspace-welcome.png | `/workspace/chats/new` | 登录后欢迎页 |
| 04 | 04-workspace-chat.png | `/workspace/chats/new` | 发送消息后 |
| 14 | 14-artifacts-panel.png | 聊天页 | 生成工件后点击工件按钮 |
| 15 | 15-artifacts-detail.png | 聊天页 | 工件详情预览 |
| 16 | 16-thinking-process.png | 聊天页 | Pro/Ultra 模式思维链 |
| 17 | 17-task-decomposition.png | 聊天页 | 任务分解展示 |
| 18 | 18-tool-call.png | 聊天页 | 工具调用过程 |
| 19 | 19-sources-citation.png | 聊天页 | 引用来源展示 |
| 20 | 20-followup-suggestions.png | 聊天页 | 后续建议标签 |
| 21 | 21-agents-gallery.png | `/workspace/agents` | Agent 画廊 |
| 22 | 22-agent-create.png | `/workspace/agents/new` | 新建 Agent |
| 23 | 23-agent-edit.png | Agent 编辑页 | 编辑 Agent 配置 |
| 25 | 25-workflows-gallery.png | `/workspace/workflows` | 工作流画廊 |
| 26 | 26-workflow-create.png | `/workspace/workflows/new` | 新建工作流 |
| 27 | 27-workflow-editor.png | 工作流编辑页 | YAML 编辑器 |
| 36 | 36-admin-dashboard.png | `/workspace/admin` | 管理后台 |
| 37 | 37-admin-users.png | `/workspace/admin/users` | 用户管理 |
| 38 | 38-admin-user-edit.png | 用户管理页 | 编辑用户角色 |
| 39 | 39-admin-departments.png | `/workspace/admin/departments` | 部门管理 |
| 40 | 40-admin-tools.png | `/workspace/admin/tools` | 工具管理 |
| 41 | 41-command-palette.png | 任意页面 | Cmd+K 命令面板 |
| 42 | 42-export-json.png | 聊天页 | 导出 JSON |
| 45 | 45-error-state.png | 任意页面 | 错误状态展示 |

### 待生成截图

以下截图需要在应用运行时通过 Playwright 脚本或手动方式补充生成：

| 编号 | 文件名 | 页面 | 操作 |
|------|--------|------|------|
| — | 05-sidebar-expanded.png | 任意页面 | 展开侧边栏 |
| — | 06-sidebar-collapsed.png | 任意页面 | 折叠侧边栏 |
| — | 07-model-selector.png | 聊天页 | 点击模型名 |
| — | 08-mode-flash.png | 聊天页 | 选择 Flash 模式 |
| — | 09-mode-thinking.png | 聊天页 | 选择 Thinking 模式 |
| — | 10-mode-pro.png | 聊天页 | 选择 Pro 模式 |
| — | 11-mode-ultra.png | 聊天页 | 选择 Ultra 模式 |
| — | 12-file-upload.png | 聊天页 | 上传文件 |
| — | 13-file-preview.png | 聊天页 | 文件预览卡片 |
| — | 24-agent-chat.png | Agent 聊天页 | 与 Agent 对话 |
| — | 28-workflow-run.png | 工作流详情页 | 运行工作流 |
| — | 29-workflow-human-review.png | 工作流执行中 | 人工审核步骤 |
| — | 30-settings-account.png | 设置对话框 | 账户选项卡 |
| — | 31-settings-appearance.png | 设置对话框 | 外观选项卡 |
| — | 32-settings-memory.png | 设置对话框 | 记忆选项卡 |
| — | 33-settings-skills.png | 设置对话框 | 技能选项卡 |
| — | 34-settings-tools.png | 设置对话框 | 工具选项卡 |
| — | 35-settings-notification.png | 设置对话框 | 通知选项卡 |
| — | 43-thread-rename.png | 侧边栏 | 重命名对话 |
| — | 44-thread-delete.png | 侧边栏 | 删除对话 |

---

## 完成状态

### 用户使用手册

- [x] 覆盖所有用户可见功能（13章+附录）
- [x] 每个功能有清晰的操作步骤
- [x] 关键界面有截图说明（19个截图已引用）
- [x] 常见问题有解答
- [x] 快捷键速查表完整

### 开发运维手册

- [x] 架构图清晰准确
- [x] 关键代码位置可快速定位
- [x] 新功能开发流程完整
- [x] 问题定位指南实用
- [x] 部署运维步骤可执行

### 截图

- [x] 覆盖主要界面（26个截图已生成）
- [x] 截图清晰、分辨率足够
- [x] 文件命名规范统一
- [x] 在手册中正确引用
- [ ] 补充待生成截图（20个截图待生成）

---

## 问题记录

截图生成过程中遇到的问题及解决方案，请参考 [screenshot-issues.md](screenshot-issues.md)。

---

## 维护说明

- 文档与代码同步更新，重大功能变更时需更新对应手册
- 截图在 UI 重大变更时需重新生成
- 代码路径变更时需同步更新开发运维手册中的路径引用
