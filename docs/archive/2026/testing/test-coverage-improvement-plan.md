# 测试覆盖率提升计划

> status: archived; current testing authority: `docs/testing/coverage-matrix.md`

## 当前进展

### 起始状态 (2026-06-13)

| 维度 | 起始覆盖率 | 测试文件数 | 测试用例数 |
|------|-----------|-----------|-----------|
| 后端 (pytest) | 72% | ~150 | ~3500 |
| 前端 (vitest) | 11.38% | ~20 | ~300 |

### 当前状态 (2026-06-13 20:00)

| 维度 | 当前覆盖率 | 测试文件数 | 测试用例数 | 提升 |
|------|-----------|-----------|-----------|------|
| 后端 | **93.2%** | ~300 | ~7500 | +21.2% |
| 前端 | **36.58%** | 81 | 2423 | +25.2% |

### 目标

| 维度 | 目标覆盖率 | 差距 | 需覆盖语句/行数 |
|------|-----------|------|----------------|
| 后端 | 98% | 4.8% | ~1232 语句 |
| 前端 | 98% | 61.4% | ~4134 行 |

---

## 后端覆盖率分析

### 已完成模块 (93.2%)

| 模块 | 覆盖率 | 测试数 |
|------|--------|--------|
| authz.py | 100% | 102 |
| credential_file.py | 100% | 9 |
| reset_admin.py | 98% | 12 |
| path_utils.py | 100% | 9 |
| thread_runs.py | 92% | 21 |
| artifacts.py | 93% | 26 |
| skills.py | 77% | 34 |
| agents.py | 95.5% | 50 |
| discord.py | 93.6% | 110 |
| aio_sandbox_provider.py | 87.1% | 103 |
| claude_provider.py | 100% | ~50 |
| vllm_provider.py | 100% | ~40 |
| openai_codex_provider.py | 100% | ~30 |
| run_manager.py | 100% | ~50 |
| subagent_executor.py | 100% | ~80 |
| mcp_tools.py | 100% | ~50 |
| workflow_executor.py | 100% | ~60 |
| condition_step.py | 100% | ~40 |
| skill_manage_tool.py | 100% | ~40 |
| infoquest_client.py | 100% | ~40 |
| message_bus.py | 100% | ~30 |
| channel_base.py | 100% | ~20 |
| channel_service.py | 100% | ~30 |
| channel_manager.py | 93.3% | ~70 |
| data_analyzer/tools.py | 100% | ~30 |
| doc_reader/tools.py | 100% | ~40 |
| JSONL store | 100% | 96 |
| admin router | 100% | ~80 |
| models router | 100% | ~80 |
| threads router | 100% | ~60 |
| skills router | 100% | ~50 |
| agents router | 100% | ~50 |
| assistants_compat router | 100% | ~40 |
| 工作流步骤 (5种) | 100% | ~100 |
| persistence 模块 | 100% | ~80 |
| auth repository | 100% | ~30 |
| extensions config | 100% | ~40 |
| 中间件模块 | 100% | ~60 |
| 工具模块 | 100% | ~50 |

### 剩余缺口 (需覆盖 1232 语句)

| 模块 | 未覆盖语句 | 当前覆盖率 | 优先级 |
|------|-----------|-----------|--------|
| wechat.py | 202 | 75.5% | P0 |
| dingtalk.py | 65 | 85.3% | P0 |
| sandbox/tools.py | 63 | 93.6% | P1 |
| aio_sandbox_provider.py | 60 | 87.1% | P1 |
| manager.py | 38 | 93.3% | P1 |
| aio_sandbox.py | 36 | 77.2% | P1 |
| runs/worker.py | 33 | 89.3% | P2 |
| auth.py router | 32 | 85.4% | P2 |
| journal.py | 25 | 91.9% | P2 |
| discord.py | 24 | 93.6% | P2 |
| llm_error_handling_middleware.py | 22 | 90.3% | P2 |
| events/store/db.py | 22 | 87.4% | P2 |
| workflows/parser.py | 22 | 78.2% | P2 |
| utils/network.py | 22 | 40.5% | P2 |
| 其他小模块 | ~600 | 各异 | P3 |

---

## 前端覆盖率分析

### 已完成模块 (36.58%)

| 模块 | 覆盖率 | 测试数 |
|------|--------|--------|
| api/fetcher.ts | 96% | 15 |
| api/errors.ts | 100% | 14 |
| api/stream-mode.ts | 91% | ~10 |
| skills/api.ts | 100% | 5 |
| skills/hooks.ts | 100% | 3 |
| memory/api.ts | 82% | 8 |
| memory/hooks.ts | 83% | 5 |
| mcp/api.ts | ~80% | 4 |
| mcp/hooks.ts | ~80% | 5 |
| models/api.ts | ~80% | 4 |
| models/hooks.ts | ~80% | 3 |
| threads/api.ts | 83% | ~5 |
| threads/export.ts | 73% | ~5 |
| tools/api.ts | 89% | ~5 |
| uploads/prompt-input-files.ts | 100% | ~5 |
| uploads/file-validation.ts | ~80% | ~5 |
| messages/usage.ts | 90% | ~5 |
| messages/utils.ts | 65% | ~10 |
| messages/usage-model.ts | 77% | ~5 |
| artifacts/utils.ts | ~80% | ~5 |
| artifacts/preview.ts | ~80% | ~5 |
| blog/index.ts | ~80% | ~10 |
| config/index.ts | ~80% | ~5 |
| auth/server.ts | ~70% | ~5 |
| auth/types.ts | ~80% | ~5 |
| auth/proxy-policy.ts | 100% | ~3 |
| settings/local.ts | ~80% | ~5 |
| workflows/api.ts | ~70% | ~5 |
| workflows/hooks.ts | ~70% | ~5 |
| i18n/keys.ts | ~80% | ~5 |
| tasks/context.tsx | ~70% | ~5 |
| tasks/subtask-result.ts | ~80% | ~5 |
| hooks/use-mobile.ts | ~80% | ~5 |
| lib/ime.ts | ~80% | ~3 |
| rehype/index.ts | ~80% | ~5 |
| utils/files.tsx | ~80% | ~10 |
| utils/datetime.ts | ~80% | ~3 |
| utils/json.ts | ~80% | ~3 |
| utils/markdown.ts | ~80% | ~3 |
| admin/api.ts | ~80% | ~5 |
| 组件测试 (workspace) | ~30% | ~200 |
| 组件测试 (ai-elements) | ~30% | ~100 |
| 组件测试 (ui) | ~20% | ~30 |
| 页面测试 (admin) | ~20% | ~100 |

### 剩余缺口 (需覆盖 4134 行)

| 模块 | 未覆盖行数 | 当前覆盖率 | 优先级 |
|------|-----------|-----------|--------|
| core/threads/hooks.ts | ~950 | 7.93% | P0 |
| 组件 (workspace/*) | ~1500 | ~30% | P0 |
| 组件 (ai-elements/*) | ~500 | ~30% | P0 |
| 页面 (admin/*) | ~400 | ~20% | P0 |
| core/i18n/* | ~350 | ~15% | P1 |
| core/auth/* | ~300 | ~15% | P1 |
| core/settings/* | ~250 | ~10% | P1 |
| core/notification/* | ~100 | 0% | P1 |
| core/workflows/* | ~100 | ~40% | P2 |
| 其他小模块 | ~500 | 各异 | P2 |

---

## 后续阶段计划

### 阶段 2: 后端 93% → 98%, 前端 37% → 60%

**预计工时**: 4-6 小时 (并行 agent)

#### 后端任务

| 任务 | 目标模块 | 预计新增覆盖 | 方法 |
|------|---------|-------------|------|
| 2-1 | wechat.py (202 missed) | +200 stmts | 修复 hang 测试, 补充 _poll_loop/start/stop |
| 2-2 | dingtalk.py (65 missed) | +60 stmts | 补充 start/stop/message 处理 |
| 2-3 | sandbox/tools.py (63 missed) | +60 stmts | 补充边界用例 |
| 2-4 | aio_sandbox_provider.py (60 missed) | +55 stmts | 补充 warm pool/eviction |
| 2-5 | 小模块 (~600 missed) | +500 stmts | 批量生成 P2/P3 模块测试 |

#### 前端任务

| 任务 | 目标模块 | 预计新增覆盖 | 方法 |
|------|---------|-------------|------|
| 2-6 | core/threads/hooks.ts | +800 lines | 大规模 hook 测试 |
| 2-7 | 组件 (workspace) | +800 lines | 批量组件测试 |
| 2-8 | 组件 (ai-elements) | +300 lines | 批量组件测试 |
| 2-9 | 页面 (admin) | +300 lines | 页面测试 |
| 2-10 | core/i18n/* | +250 lines | i18n 模块测试 |

### 阶段 3: 后端 98% → 99%, 前端 60% → 80%

**预计工时**: 6-8 小时 (并行 agent)

#### 后端任务

| 任务 | 目标模块 | 预计新增覆盖 | 方法 |
|------|---------|-------------|------|
| 3-1 | 剩余 channels/ 模块 | +100 stmts | 补充边界用例 |
| 3-2 | 剩余 runtime/ 模块 | +50 stmts | 补充错误处理 |
| 3-3 | 剩余 routers/ 模块 | +50 stmts | 补充权限/错误处理 |

#### 前端任务

| 任务 | 目标模块 | 预计新增覆盖 | 方法 |
|------|---------|-------------|------|
| 3-4 | 核心 hooks 补充 | +800 lines | 深度 hook 测试 |
| 3-5 | 组件深度测试 | +800 lines | 交互/状态测试 |
| 3-6 | 页面深度测试 | +500 lines | 路由/权限测试 |
| 3-7 | 状态管理测试 | +400 lines | store/context 测试 |

### 阶段 4: 前端 80% → 98%

**预计工时**: 8-10 小时 (并行 agent)

#### 前端任务

| 任务 | 目标模块 | 预计新增覆盖 | 方法 |
|------|---------|-------------|------|
| 4-1 | 剩余组件 | +500 lines | 边界用例 |
| 4-2 | 剩余 hooks | +300 lines | 错误处理 |
| 4-3 | 剩余工具函数 | +200 lines | 边界用例 |
| 4-4 | 集成测试 | +300 lines | 端到端流程 |

---

## 技术要点

### 后端测试模式

```python
# FastAPI 路由测试
from fastapi.testclient import TestClient
from app.gateway.main import app

client = TestClient(app)

def test_endpoint():
    response = client.get("/api/endpoint")
    assert response.status_code == 200
```

```python
# 异步模块测试
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_dependency():
    return AsyncMock()

async def test_async_function(mock_dependency):
    result = await function_under_test(mock_dependency)
    assert result is not None
```

```python
# Channel 测试 (需要 mock 外部 SDK)
def test_channel_send():
    channel = create_channel(config)
    channel._api_client = MagicMock()
    channel._api_client.send = AsyncMock()
    await channel.send(message)
    channel._api_client.send.assert_called_once()
```

### 前端测试模式

```typescript
// Hook 测试
import { renderHook, act } from '@testing-library/react';
import { useMyHook } from './useMyHook';

test('useMyHook returns expected value', () => {
  const { result } = renderHook(() => useMyHook());
  expect(result.current.value).toBe(expected);
});
```

```typescript
// 组件测试
import { render, screen, fireEvent } from '@testing-library/react';
import { MyComponent } from './MyComponent';

test('renders correctly', () => {
  render(<MyComponent />);
  expect(screen.getByText('Hello')).toBeInTheDocument();
});
```

```typescript
// API 测试
import { vi } from 'vitest';
import { fetchApi } from './api';

test('fetchApi calls correct endpoint', async () => {
  const mockFetch = vi.fn().mockResolvedValue({ ok: true, json: () => ({}) });
  global.fetch = mockFetch;
  await fetchApi('/endpoint');
  expect(mockFetch).toHaveBeenCalledWith('/endpoint');
});
```

### 已知问题

1. **WeChat 测试 hang**: `test_wechat_channel.py` 中的 `start/stop/poll` 测试会导致 pytest hang，需要修复 mock
2. **Discord 测试 hang**: `test_discord_channel.py` 中的 `test_stop_joins_thread` 测试失败
3. **前端覆盖率报告**: vitest 在有测试失败时不显示覆盖率报告
4. **Agent 限流**: 并行 agent 过多会导致 429 错误

---

## 执行建议

1. **优先修复 hang 测试**: wechat 和 discord 的 hang 测试是最大瓶颈
2. **并行 agent 控制**: 同时运行不超过 5 个 agent，避免 429 限流
3. **前端优先级**: threads/hooks.ts 是最大缺口，应优先处理
4. **增量验证**: 每完成一批测试后立即运行覆盖率检查
5. **测试质量**: 不仅追求覆盖率数字，确保测试有意义、可维护
