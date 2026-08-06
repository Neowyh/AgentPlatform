# 第二批测试工具接入实现计划

> status: archived; current testing authority: `docs/testing/coverage-matrix.md`

> 目标：将 pytest-xdist、factory_boy（已有依赖）、Lighthouse CI、dependency-cruiser 四个工具接入现有测试框架，提升 CI 效率、测试数据质量、前端性能守护和架构边界强制。

## 现状摘要

| 维度 | 当前状态 | 问题 |
|------|---------|------|
| 后端测试并行 | 串行执行，CI 用 pytest-split 4 分片 | 本地开发无并行，CI 分片仅做分组不做并发 |
| 测试数据工厂 | factory_boy 已在 dev 依赖但未使用，20+ 个 ad-hoc `_make_*` builder 散落各处 | 数据不一致、维护成本高 |
| 前端性能 | 零监控，无 Lighthouse CI、无 bundle 预算 | 无法发现性能退化 |
| 架构边界 | 无 dependency-cruiser / import-linter，仅有 import/order 排序规则 | 任何模块可随意跨层导入 |

---

## 一、pytest-xdist：后端测试并行化

### 1.1 目标

- 本地 `make test` 自动利用多核并行执行
- CI 4 分片改为 xdist 内置并行（或保留分片 + xdist 双重加速）
- 确保现有 fixture（特别是 autouse 单例重置、conftest 模块级副作用）在并行下安全

### 1.2 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| conftest.py 中 `sys.modules` 注入 | 并行 worker 可能互相污染 | xdist 每个 worker 独立进程，天然隔离 |
| `_auto_user_context` contextvar | 每个 worker 独立进程，contextvar 天然隔离 | 无需改动 |
| 共享文件/端口冲突 | tests/qa/ 启动 uvicorn 会端口冲突 | qa 测试排除在并行之外 |
| SQLite 数据库并发写入 | 并行写入可能死锁 | 项目用 SQLAlchemy + 连接池，需验证 |

### 1.3 实现步骤

#### Step 1：添加依赖

**文件：`backend/pyproject.toml`**

```toml
[dependency-groups]
dev = [
    # ... existing ...
    "pytest-xdist>=3.8.0",   # 新增
]
```

然后执行：
```bash
cd backend && uv lock && uv sync --group dev
```

#### Step 2：配置 pytest.ini_options

**文件：`backend/pyproject.toml`**

```toml
[tool.pytest.ini_options]
markers = [
    # ... existing markers ...
    "serial: marks tests that must run serially (not parallel-safe)",
]
addopts = "--tb=short"
```

#### Step 3：标记不可并行的测试

需要排查并标记的测试类别：

```bash
# 找出所有使用固定端口的测试
grep -rn "localhost:8001\|127.0.0.1:8001\|port.*8001" backend/tests/ --include="*.py"

# 找出所有写入共享文件的测试
grep -rn "open(\|Path(\|tmp_path\|tempfile" backend/tests/ --include="*.py" | grep -v conftest

# 找出所有使用全局单例状态的测试
grep -rn "singleton\|_instance\|global\|CLASS_VARIABLE" backend/tests/ --include="*.py"
```

标记方式：
```python
import pytest

@pytest.mark.serial
class TestQAEndpoints:
    """这些测试使用固定端口，不能并行。"""
    ...
```

#### Step 4：新增 Makefile targets

**文件：`backend/Makefile`**

```makefile
# 并行测试（本地开发，排除 qa 和 serial）
test-parallel:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
		uv run pytest tests/ -v -n auto \
		--ignore=tests/qa \
		--ignore=tests/blocking_io \
		-m "not serial and not requires_llm"

# 保持原有 test 不变（向后兼容）
test:
	PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/ -v
```

#### Step 5：CI 工作流调整

**文件：`.github/workflows/backend-unit-tests.yml`**

方案 A（推荐）：保留 pytest-split 分片 + 每片内 xdist 并行

```yaml
strategy:
  matrix:
    shard: [1, 2, 3, 4]
  fail-fast: false

steps:
  - name: Run tests
    run: |
      uv run pytest tests/ \
        --splits 4 --group $SHARD --splitting-algorithm least_duration \
        -n auto \
        --cov=app --cov=packages \
        --cov-report=xml --cov-report=json:coverage.json --cov-report=term-missing
```

方案 B：去掉 pytest-split，纯 xdist 8 workers

```yaml
steps:
  - name: Run tests
    run: |
      uv run pytest tests/ -n 8 \
        --cov=app --cov=packages \
        --cov-report=xml --cov-report=json:coverage.json --cov-report=term-missing
```

**建议采用方案 A**：pytest-split 保证分片均匀（基于历史耗时），xdist 在每片内并行，两者叠加效果最佳。

#### Step 6：验证

```bash
# 本地验证并行执行
cd backend && make test-parallel

# 对比耗时
time make test           # 串行基准
time make test-parallel  # 并行对比

# 验证 qa 测试被正确排除
uv run pytest tests/ -n auto --collect-only -q | grep -c "qa/"
```

### 1.4 预期收益

| 指标 | 当前 | 预期 |
|------|------|------|
| 本地测试耗时 | ~3-5 min | ~1-2 min |
| CI 每分片耗时 | ~3-4 min | ~1.5-2 min |
| CI 总耗时（4 分片） | ~4 min（并行分片） | ~2-2.5 min |

---

## 二、factory_boy：统一测试数据工厂

### 2.1 目标

- 将散落的 20+ 个 ad-hoc `_make_*` builder 替换为声明式 Factory 类
- 新测试直接使用 Factory，不再手写 builder
- 与现有 `conftest.py` fixture 共存，不破坏现有测试

### 2.2 现状分析

当前 ad-hoc builder 分布：

| 文件 | Builder 函数 | 构建对象 |
|------|-------------|---------|
| `_agent_e2e_helpers.py` | `FakeToolCallingModel`, `build_single_tool_call_model()` | 假 LLM 模型 |
| `_router_auth_helpers.py` | `make_authed_test_app()`, `call_unwrapped()` | 认证测试应用 |
| `test_model_factory.py` | `_make_model()`, `_make_app_config()` | 模型配置 |
| `test_workflow_executor.py` | `_make_state()` | 工作流状态 |
| `test_workflow_store.py` | `_mock_session_factory()` | 数据库会话 |
| `test_lead_agent_prompt.py` | `make_skill()` | 技能对象 |
| `test_subagent_token_collector.py` | `_make_llm_response()`, `_make_llm_response_from_usages()` | LLM 响应 |

### 2.3 实现步骤

#### Step 1：创建 Factory 模块

**新建文件：`backend/tests/factories/`**

```
backend/tests/factories/
├── __init__.py          # 统一导出
├── models.py            # SQLAlchemy model factories
├── llm.py               # LLM 相关 factories
├── workflow.py            # 工作流相关 factories
└── auth.py              # 认证相关 factories
```

**`backend/tests/factories/__init__.py`**：
```python
"""测试数据工厂 — 基于 factory_boy 的声明式数据构建。"""

from .models import AppConfigFactory, UserFactory, ThreadFactory
from .llm import LLMResponseFactory, ToolCallModelFactory
from .workflow import WorkflowStateFactory, WorkflowStepFactory
from .auth import AuthedAppFactory

__all__ = [
    "AppConfigFactory",
    "UserFactory",
    "ThreadFactory",
    "LLMResponseFactory",
    "ToolCallModelFactory",
    "WorkflowStateFactory",
    "WorkflowStepFactory",
    "AuthedAppFactory",
]
```

**`backend/tests/factories/models.py`**（示例）：
```python
"""SQLAlchemy model factories。"""

import factory
from factory import fuzzy

from app.models import User, Thread, AppConfig  # 需确认实际模型路径


class UserFactory(factory.Factory):
    class Meta:
        model = User  # 或 dict，取决于是否用 ORM

    id = factory.Sequence(lambda n: f"user-{n}")
    username = factory.Sequence(lambda n: f"testuser-{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    role = fuzzy.FuzzyChoice(["user", "admin", "department_admin", "viewer"])


class ThreadFactory(factory.Factory):
    class Meta:
        model = dict  # 如果是 Pydantic 模型，用 dict 中转

    id = factory.Sequence(lambda n: f"thread-{n}")
    title = factory.Sequence(lambda n: f"Test Thread {n}")
    user_id = factory.LazyFunction(lambda: UserFactory().id)
    status = "active"


class AppConfigFactory(factory.Factory):
    class Meta:
        model = dict

    llm = factory.LazyAttribute(lambda _: {
        "provider": fuzzy.FuzzyChoice(["openai", "anthropic", "deepseek"]).fuzz(),
        "model": "gpt-4o-mini",
    })
    sandbox = factory.LazyAttribute(lambda _: {"enabled": False})
```

**`backend/tests/factories/llm.py`**（示例）：
```python
"""LLM 响应 factories — 替代 _make_llm_response 等 ad-hoc builder。"""

import factory
from unittest.mock import MagicMock


class LLMResponseFactory(factory.Factory):
    """构建模拟的 LLM 响应对象。"""

    class Meta:
        model = dict

    content = factory.Faker("sentence")
    usage_metadata = factory.LazyAttribute(lambda _: {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    })
    tool_calls = []
    finish_reason = "stop"


class ToolCallModelFactory(factory.Factory):
    """构建模拟的 ToolCallingModel。"""

    class Meta:
        model = MagicMock

    invoke = factory.LazyAttribute(lambda _: MagicMock(
        content="Test response",
        tool_calls=[],
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    ))
```

#### Step 2：注册 fixtures

**文件：`backend/tests/conftest.py`**（新增 fixture，不删除旧 builder）

```python
# 在文件末尾追加
from tests.factories import (
    UserFactory,
    ThreadFactory,
    AppConfigFactory,
    LLMResponseFactory,
    WorkflowStateFactory,
)


@pytest.fixture
def user_factory():
    """返回 UserFactory，测试中可 user_factory(role='admin') 覆盖默认值。"""
    return UserFactory


@pytest.fixture
def thread_factory():
    return ThreadFactory


@pytest.fixture
def app_config_factory():
    return AppConfigFactory


@pytest.fixture
def llm_response_factory():
    return LLMResponseFactory


@pytest.fixture
def workflow_state_factory():
    return WorkflowStateFactory
```

#### Step 3：渐进迁移（不删旧代码）

**迁移策略**：新测试使用 Factory，旧测试保持不动。标记旧 builder 为 `@deprecated`。

示例——新测试写法：
```python
def test_user_permissions(user_factory):
    admin = user_factory(role="admin")
    viewer = user_factory(role="viewer")
    assert admin.role == "admin"
    assert viewer.role == "viewer"
```

旧 builder 标记：
```python
import warnings

def _make_llm_response(**kwargs):
    """@deprecated: 使用 llm_response_factory fixture 替代。"""
    warnings.warn(
        "_make_llm_response is deprecated, use llm_response_factory fixture",
        DeprecationWarning,
        stacklevel=2,
    )
    # ... existing code ...
```

#### Step 4：添加 Factory Boy 使用规范

**文件：`backend/tests/factories/README.md`**（新建）

```markdown
# 测试数据工厂使用规范

## 原则
1. 新测试**必须**使用 Factory，不再手写 `_make_*` builder
2. Factory 定义放在 `tests/factories/` 对应模块中
3. 通过 fixture 注入：`def test_xxx(user_factory): ...`
4. 需要特殊数据时用 `factory.build(dict, field=value)` 覆盖默认值

## 添加新 Factory
1. 在对应模块中定义 Factory 类
2. 在 `__init__.py` 中导出
3. 在 `conftest.py` 中注册 fixture
4. 编写至少一个使用该 Factory 的测试

## 禁止
- 禁止在测试文件中定义 Factory（必须放 factories/ 模块）
- 禁止 Factory 依赖其他 Factory 的运行时状态（用 LazyFunction 而非直接调用）
```

### 2.4 预期收益

| 指标 | 当前 | 预期 |
|------|------|------|
| 新测试编写时间 | 15-30 min（手写 builder） | 5-10 min（声明式 Factory） |
| 测试数据一致性 | 不同文件 builder 字段不统一 | Factory 统一默认值 |
| 代码可维护性 | 20+ 个散落 builder | 集中管理、类型安全 |

---

## 三、Lighthouse CI：前端性能守护

### 3.1 目标

- 每次 PR 自动跑 Lighthouse，阻止性能退化
- 设置 Performance / Accessibility / Best Practices 分数阈值
- 输出性能报告作为 PR artifact

### 3.2 阈值设定

基于 Next.js 15 + Tailwind 典型项目的合理基线：

| 维度 | 阈值 | 说明 |
|------|------|------|
| Performance | ≥ 80 | 内网应用，不要求 90+ |
| Accessibility | ≥ 90 | 已有 axe-core 集成，应保持高分 |
| Best Practices | ≥ 90 | 基本 web 标准 |
| SEO | ≥ 80 | 内网应用 SEO 不是重点 |

### 3.3 实现步骤

#### Step 1：安装依赖

**文件：`frontend/package.json`**

```json
{
  "devDependencies": {
    "@lhci/cli": "^0.14.0"
  }
}
```

```bash
cd frontend && pnpm add -D @lhci/cli
```

#### Step 2：创建 Lighthouse CI 配置

**新建文件：`frontend/lighthouserc.json`**

```json
{
  "ci": {
    "collect": {
      "url": ["http://localhost:3000/", "http://localhost:3000/workspace"],
      "startServerCommand": "pnpm build && pnpm start",
      "startServerReadyPattern": "Ready on",
      "startServerReadyTimeout": 60000,
      "numberOfRuns": 1,
      "settings": {
        "preset": "desktop",
        "chromeFlags": "--no-sandbox --headless --disable-gpu"
      }
    },
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.80 }],
        "categories:accessibility": ["error", { "minScore": 0.90 }],
        "categories:best-practices": ["error", { "minScore": 0.90 }],
        "categories:seo": ["warn", { "minScore": 0.80 }],
        "first-contentful-paint": ["warn", { "maxNumericValue": 2000 }],
        "largest-contentful-paint": ["warn", { "maxNumericValue": 2500 }],
        "cumulative-layout-shift": ["warn", { "maxNumericValue": 0.1 }],
        "total-blocking-time": ["warn", { "maxNumericValue": 300 }]
      }
    },
    "upload": {
      "target": "temporary-public-storage"
    }
  }
}
```

#### Step 3：新增 Makefile target

**文件：`frontend/Makefile`**

```makefile
# Lighthouse CI 性能测试
lighthouse:
	pnpm lhci autorun

# 仅收集报告（不 assert）
lighthouse-collect:
	pnpm lhci collect
```

#### Step 4：新建 GitHub Actions 工作流

**新建文件：`.github/workflows/lighthouse-ci.yml`**

```yaml
name: Lighthouse CI

on:
  pull_request:
    paths:
      - "frontend/**"
      - ".github/workflows/lighthouse-ci.yml"

concurrency:
  group: lighthouse-${{ github.head_ref || github.ref }}
  cancel-in-progress: true

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Enable corepack
        run: corepack enable

      - name: Install dependencies
        working-directory: frontend
        run: pnpm install --frozen-lockfile

      - name: Run Lighthouse CI
        working-directory: frontend
        env:
          SKIP_ENV_VALIDATION: "1"
          LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}
        run: pnpm lhci autorun

      - name: Upload Lighthouse report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: lighthouse-report
          path: frontend/.lighthouseci/
          retention-days: 14
```

#### Step 5：添加 bundle size 预算（可选增强）

**文件：`frontend/package.json`**（追加）

```json
{
  "size-limit": [
    {
      "path": ".next/static/chunks/*.js",
      "limit": "300 kB",
      "gzip": true
    }
  ]
}
```

安装：
```bash
cd frontend && pnpm add -D size-limit @size-limit/file
```

新增 script：
```json
{
  "scripts": {
    "size": "size-limit"
  }
}
```

#### Step 6：验证

```bash
cd frontend

# 本地运行 Lighthouse
pnpm build && pnpm start &
sleep 5
pnpm lhci collect
pnpm lhci assert

# 查看报告
open .lighthouseci/lighthouse-*.html
```

### 3.4 预期收益

| 指标 | 当前 | 预期 |
|------|------|------|
| 性能回归发现 | 无，上线后用户反馈 | PR 阶段自动拦截 |
| Performance 分数 | 未知 | ≥ 80 持续守护 |
| Accessibility 分数 | axe-core 可选检查 | Lighthouse 强制 ≥ 90 |
| 报告可追溯性 | 无 | GitHub Artifact 保留 14 天 |

---

## 四、dependency-cruiser：架构边界强制

### 4.1 目标

- 前端强制分层：`components` → `core` → `lib`，禁止反向依赖
- 检测循环依赖
- CI 中作为 lint 门禁

### 4.2 前端架构分层规则

基于现有代码结构：

```
frontend/src/
├── app/           # 路由层（页面）
├── components/    # UI 组件层
│   ├── ui/        # 通用 UI 组件（不可依赖业务）
│   ├── ai-elements/  # AI 相关组件
│   └── workspace/    # 工作区业务组件
├── core/          # 业务逻辑层（API、状态、认证）
│   ├── api/
│   ├── agents/
│   ├── auth/
│   ├── skills/
│   └── workflows/
└── lib/           # 工具层（无状态工具函数）
```

**分层规则**：
1. `lib/` 不可导入 `core/`、`components/`、`app/`
2. `core/` 不可导入 `components/`、`app/`
3. `components/ui/` 不可导入 `components/workspace/`、`core/`
4. `app/` 可导入任意层
5. 任何层不可循环依赖

### 4.3 实现步骤

#### Step 1：安装

```bash
cd frontend && pnpm add -D dependency-cruiser
```

#### Step 2：初始化配置

```bash
cd frontend && npx depcruise --init
```

这会生成 `.dependency-cruiser.cjs`，然后按需修改规则。

#### Step 3：编写规则

**新建文件：`frontend/.dependency-cruiser.cjs`**

```javascript
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "no-circular",
      comment: "禁止循环依赖",
      severity: "error",
      from: {},
      to: { circular: true },
    },
    {
      name: "lib-no-upward",
      comment: "lib 层不可导入 core/components/app",
      severity: "error",
      from: { path: "^src/lib/" },
      to: { path: ["^src/core/", "^src/components/", "^src/app/"] },
    },
    {
      name: "core-no-components",
      comment: "core 层不可导入 components/app",
      severity: "error",
      from: { path: "^src/core/" },
      to: { path: ["^src/components/", "^src/app/"] },
    },
    {
      name: "ui-no-business",
      comment: "通用 UI 组件不可依赖业务组件或 core",
      severity: "error",
      from: { path: "^src/components/ui/" },
      to: {
        path: [
          "^src/components/workspace/",
          "^src/components/ai-elements/",
          "^src/core/",
          "^src/app/",
        ],
      },
    },
    {
      name: "no-orphans",
      comment: "检测孤立文件（无任何导入/导出关系）",
      severity: "warn",
      from: { orphan: true, pathNot: "\\.(d\\.ts|spec\\.ts|test\\.ts|stories\\.ts)$" },
      to: {},
    },
    {
      name: "no-deprecated",
      comment: "禁止使用标记为 deprecated 的模块",
      severity: "warn",
      from: {},
      to: { dependencyTypes: ["deprecated"] },
    },
  ],
  options: {
    doNotFollow: {
      path: "node_modules",
      dependencyTypes: ["npm", "npm-dev", "npm-optional", "npm-peer", "npm-bundled"],
    },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.json" },
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default"],
      extensions: [".ts", ".tsx", ".js", ".jsx"],
    },
    reporterOptions: {
      dot: { theme: { graph: { rankdir: "LR" } } },
    },
  },
};
```

#### Step 4：新增 Makefile target

**文件：`frontend/Makefile`**

```makefile
# 架构边界检查
arch-check:
	npx depcruise src/ --config .dependency-cruiser.cjs

# 生成依赖图（可视化）
arch-graph:
	npx depcruise src/ --config .dependency-cruiser.cjs --output-type dot | dot -T svg > dependency-graph.svg
	@echo "依赖图已生成: dependency-graph.svg"
```

#### Step 5：集成到 CI

**文件：`.github/workflows/lint-check.yml`**（追加到 frontend-lint job）

```yaml
  frontend-lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - name: Enable corepack
        run: corepack enable
      - name: Install dependencies
        working-directory: frontend
        run: pnpm install --frozen-lockfile
      - name: Format check
        working-directory: frontend
        run: pnpm format
      - name: Lint
        working-directory: frontend
        run: pnpm lint
      - name: Type check
        working-directory: frontend
        run: pnpm typecheck
      - name: Architecture boundary check    # 新增
        working-directory: frontend
        run: npx depcruise src/ --config .dependency-cruiser.cjs
      - name: Build
        working-directory: frontend
        run: pnpm build
```

#### Step 6：添加 pre-commit hook

**文件：`.pre-commit-config.yaml`**（追加）

```yaml
      - id: depcruiser
        name: dependency-cruiser (frontend)
        entry: bash -c 'cd frontend && npx depcruise src/ --config .dependency-cruiser.cjs' --
        language: system
        files: ^frontend/src/
        types_or: [javascript, tsx, ts]
```

#### Step 7：检测并修复现有违规

```bash
cd frontend

# 首次运行，查看当前违规
npx depcruise src/ --config .dependency-cruiser.cjs --output-type text

# 如果有违规，有两种处理方式：
# 方式 1：修复代码（推荐）
# 方式 2：对已知违规添加 exceptions（临时）
```

如果首次运行发现大量违规，可在规则中添加 `from.pathNot` 排除已知问题：
```javascript
{
  name: "core-no-components",
  severity: "error",
  from: { path: "^src/core/", pathNot: "^src/core/legacy/" },  // 排除遗留代码
  to: { path: ["^src/components/", "^src/app/"] },
}
```

#### Step 8：验证

```bash
cd frontend

# 检查无循环依赖
npx depcruise src/ --config .dependency-cruiser.cjs --output-type text | grep "no-circular"

# 生成可视化依赖图
npx depcruise src/ --config .dependency-cruiser.cjs --output-type dot | dot -T png -o deps.png

# 验证规则生效（故意创建一个违规导入）
echo "import { something } from '@/components/workspace/sidebar';" >> src/lib/test-violation.ts
npx depcruise src/ --config .dependency-cruiser.cjs  # 应报错
rm src/lib/test-violation.ts
```

### 4.4 预期收益

| 指标 | 当前 | 预期 |
|------|------|------|
| 架构违规发现 | 无，靠 code review 人眼检查 | CI 自动拦截 |
| 循环依赖 | 可能已存在但未知 | 首次运行即暴露 |
| 新人上手 | 不清楚模块边界 | 规则即文档 |

---

## 五、实施计划总览

### 阶段划分

| 阶段 | 工具 | 预估耗时 | 依赖 |
|------|------|---------|------|
| Phase 1 | pytest-xdist | 0.5 天 | 无 |
| Phase 2 | factory_boy 采纳 | 1 天 | 无（依赖已就绪） |
| Phase 3 | dependency-cruiser | 0.5 天 | 无 |
| Phase 4 | Lighthouse CI | 0.5 天 | 无 |

**总预估：2.5 天**

### 执行顺序建议

```
Phase 1 (Day 1 上午): pytest-xdist
  ├─ 添加依赖 + 配置
  ├─ 标记 serial 测试
  └─ 本地验证 + CI 调整

Phase 2 (Day 1 下午 - Day 2): factory_boy
  ├─ 创建 factories/ 模块
  ├─ 编写核心 Factory 类
  ├─ 注册 fixtures
  └─ 编写使用规范文档

Phase 3 (Day 3 上午): dependency-cruiser
  ├─ 安装 + 初始化配置
  ├─ 编写分层规则
  ├─ 首次运行 + 修复违规
  └─ CI 集成 + pre-commit hook

Phase 4 (Day 3 下午): Lighthouse CI
  ├─ 安装 + 配置
  ├─ 本地验证
  └─ CI 工作流创建
```

### 回滚方案

每个工具独立，可单独回滚：

| 工具 | 回滚方式 |
|------|---------|
| pytest-xdist | 从 pyproject.toml 移除依赖，删除 Makefile target |
| factory_boy | 删除 factories/ 目录，删除 conftest 中新增 fixture，旧 builder 未改动 |
| dependency-cruiser | 删除 .dependency-cruiser.cjs，从 CI 和 pre-commit 移除步骤 |
| Lighthouse CI | 删除 lighthouserc.json 和 CI workflow |

---

## 附录：与现有框架的整合点

### 与 validation-orchestrator 整合

```yaml
# validation-orchestrator 可在 Phase 1（代码质量）中新增：
- backend: "make test-parallel"     # 替代串行 test
- frontend: "make arch-check"       # 新增架构检查
- frontend: "make lighthouse"       # 新增性能检查（full 级别）
```

### 与 backend-validator 整合

```
Phase 2（静态分析）新增：
- 架构检查：dependency-cruiser / import-linter
- 并行测试：自动使用 test-parallel target
```

### 与 frontend-validator 整合

```
Phase 1（代码质量）新增：
- 架构边界检查：npx depcruise src/
Phase 2（性能分析）新增（full 级别）：
- Lighthouse CI 报告
- Bundle size 检查
```
