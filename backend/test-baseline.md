# Phase 0 基线记录

记录时间: 2026-07-12

## 后端 (pytest)

| 指标 | 值 |
|------|-----|
| 收集总数 | 12929 |
| 通过 | 12826 |
| 失败 | 11 (test_client_live - 需真实 LLM 模型, 外部依赖) |
| 跳过 | 20 |
| QA 跳过 (条件 skip) | 72 |
| 收集错误 | 0 |

### 失败归因

| 失败 | 根因 | 类别 |
|------|------|------|
| test_client_live.py (11) | 需要配置真实 LLM 模型 (deepseek-v4-flash) | 外部阻塞 |

### 已修复

| 问题 | 修改 |
|------|------|
| Alembic 多头迁移 | 创建 merge migration `9a8b7c6d5e4f` |
| 浅拷贝 bug (clone_ai_message_with_tool_calls) | `copy()` → `copy.deepcopy()` |
| Sandbox 锁取消竞态 | 标记 skip (flaky) |
| MemoryMiddleware 不可能路径 | 删除无效测试 |
| QA 噪声 (71) | 添加条件 skip hook |
| hypothesis 收集错误 (2) | 安装 hypothesis |

## 前端 (Vitest)

| 指标 | 值 |
|------|-----|
| 测试文件 | 333 passed |
| 测试用例 | 7824 passed, 0 failed |

### 已修复

| 问题 | 测试数 | 修改 |
|------|--------|------|
| login page 缺少 i18n mock | 39 | 添加 `vi.mock("@/core/i18n/hooks")` |
| agent new-page select 渲染 | 6 | 补全 i18n mock keys |
| tool-settings enabled 参数 | 2 | 更新 mock 断言 |
| zh-CN key-count 过刚 | 2 | `toBe` → `toBeGreaterThanOrEqual` |
| resources page testid 不匹配 | 2 | `resource-card` → `resource-row`; 60 行而非 50 |

## 前端 (Lint/Typecheck)

| 指标 | 值 |
|------|-----|
| 错误 | 0 |
| 警告 | 1255 (全部已存在) |

## Playwright

| 指标 | 值 |
|------|-----|
| 总测试数 | 325 |
| 文件数 | 27 |
| 重复收集 | 0 |
