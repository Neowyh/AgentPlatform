# 测试增强路线图

> 基于当前覆盖率基线（后端 98.6%、前端 98.01%），制定后续测试质量与深度提升方案。

## 当前基线

| 维度 | 语句覆盖率 | 测试文件数 | 测试用例数 | 通过率 |
|------|-----------|-----------|-----------|--------|
| 后端 (pytest) | 98.6% (25,136/25,498) | ~280 | 11,071 | 100% |
| 前端 (vitest) | 98.01% (6,607/6,741) | ~290 | 7,061 | 100% |

---

## 一、覆盖率诊断与盲区治理

### 1.1 后端不可测代码标注

剩余 362 语句未覆盖，大部分属于以下类别：

| 类别 | 典型模块 | 处理方式 |
|------|---------|---------|
| Windows 专用路径 | `sandbox/tools.py` L307-313 | `# pragma: no cover` + 注释说明 |
| 信号处理器 | `aio_sandbox_provider.py` 信号分支 | `# pragma: no cover`（信号处理在测试环境中不可靠） |
| 线程竞争条件 | `aio_sandbox_provider.py` lock acquire 失败 | `# pragma: no cover`（竞态不可稳定复现） |
| 平台锁 (msvcrt) | `aio_sandbox_provider.py` L61-71 | `# pragma: no cover if not sys.platform == "win32"` |

**执行步骤：**
1. 运行 `pytest --cov-report=term-missing` 获取所有未覆盖行
2. 逐行审查，将确实不可测的代码标注 `# pragma: no cover`
3. 将可测但困难的代码归入后续增强计划
4. 使用报告定位可观察的业务盲区；不以全局百分比作为合并门槛

### 1.2 前端 SSR 与死代码排除

剩余 134 语句未覆盖，主要类别：

| 类别 | 典型文件 | 处理方式 |
|------|---------|---------|
| SSR 分支 | `flickering-grid.tsx` L43-44 `typeof window === "undefined"` | vitest 配置 `coverage.exclude` 或注释 |
| 穷尽守卫 | `usage-model.ts` L194,262,409 `return null` | `/* istanbul ignore next */` 注释 |
| 私有函数体 | `api-client.ts` L29-38 `injectCsrfHeader` | 重构为可导出函数或标注排除 |

**vitest 配置建议：**
```typescript
// vitest.config.ts
coverage: {
  exclude: [
    '**/*.d.ts',
    '**/types.ts',        // 纯类型定义
  ],
}
```

---

## 二、测试质量提升

### 2.1 变异测试（Mutation Testing）

**目标**：验证测试是否真正能发现 bug，而非仅追求行覆盖率。

**后端 — mutmut：**
```bash
pip install mutmut
mutmut run --paths-to-mutate=packages/harness/ideer/ --tests-dir=tests/
mutmut results
mutmut show <mutation_id>
```

**前端 — Stryker：**
```bash
npx stryker init
npx stryker run
```

**重点关注模块**：
- `workflows/parser.py` — YAML 解析逻辑复杂，变异存活率高风险
- `condition_step.py` — 条件表达式评估，边界条件敏感
- `threads/hooks.ts` — 前端状态管理核心，逻辑分支多

**预期收益**：发现 5-15 个测试盲区（测试通过但代码行为变更未被检测）。

### 2.2 属性测试（Property-based Testing）

对逻辑密集模块使用 Hypothesis 生成随机输入，验证不变量。

**适用模块：**

```python
# workflows/parser.py — YAML 解析不变量
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=10000))
def test_parse_yaml_never_crashes(yaml_text):
    """无论输入什么 YAML 文本，parser 都不应抛出未捕获异常"""
    try:
        parse_workflow(yaml_text)
    except WorkflowValidationError:
        pass  # 预期的业务异常

# condition_step.py — 表达式评估一致性
@given(st.dictionaries(st.text(), st.one_of(st.integers(), st.text(), st.booleans())))
def test_eval_expression_deterministic(context):
    """相同上下文下，表达式评估结果应一致"""
    result1 = evaluate_expression("{{x}}", context)
    result2 = evaluate_expression("{{x}}", context)
    assert result1 == result2
```

**前端适用场景：**
- `mergeMessages` — 消息合并函数，随机生成消息列表验证不变量
- `validateYaml` — YAML 验证，随机生成 YAML 文本
- `sanitizeRunStreamOptions` — 参数清洗，随机输入验证安全性

### 2.3 快照测试回归

为关键 UI 组件添加快照测试，防止意外 UI 变更。

```typescript
// 示例：关键组件快照
describe('MessageGroup snapshots', () => {
  it('matches snapshot for AI message with tool calls', () => {
    const { container } = render(<MessageGroup message={mockAiMessage} />);
    expect(container).toMatchSnapshot();
  });

  it('matches snapshot for human message', () => {
    const { container } = render(<MessageGroup message={mockHumanMessage} />);
    expect(container).toMatchSnapshot();
  });
});
```

**适用组件：**
- `MessageGroup` / `MessageListItem` — 消息渲染核心
- `PromptInput` — 输入框组件
- `ArtifactFileDetail` — 文件详情面板
- `InputBox` — 主输入区域

### 2.4 测试数据工厂

统一测试数据生成，减少 mock 样板代码。

**后端 — factory_boy：**
```python
import factory
from ideer.persistence.models.rbac import User

class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    role = "user"
    department_id = factory.LazyFunction(lambda: uuid4())
```

**前端 — @faker-js/faker：**
```typescript
import { faker } from '@faker-js/faker';

export const createMockMessage = (overrides = {}) => ({
  id: faker.string.uuid(),
  role: faker.helpers.arrayElement(['human', 'ai']),
  content: faker.lorem.paragraph(),
  timestamp: faker.date.recent().toISOString(),
  ...overrides,
});
```

---

## 三、集成与 E2E 测试

### 3.1 API 契约测试（Fuzz Testing）

用 schemathesis 对 FastAPI 路由做自动化的契约测试。

```bash
pip install schemathesis
schemathesis run http://localhost:8000/openapi.json \
  --checks=all \
  --max-response-time=5000 \
  --hypothesis-max-examples=100
```

**验证项：**
- 所有端点返回符合 OpenAPI schema 的响应
- 必填字段缺失时返回 422
- 未认证请求返回 401/403
- 不存在的资源返回 404
- 响应时间在合理范围内

**CI 集成方式：**
```yaml
# .github/workflows/api-contract-tests.yml
- name: Start backend
  run: cd backend && uvicorn app.gateway.main:app &
- name: Run schemathesis
  run: schemathesis run http://localhost:8000/openapi.json --checks=all
```

### 3.2 数据库集成测试

当前 persistence 层测试大量 mock 数据库连接，应补充真实数据库测试。

**方案 — testcontainers：**
```python
import pytest
from testcontainers.sqlite import SqliteContainer

@pytest.fixture(scope="module")
def db_container():
    with SqliteContainer() as container:
        yield container

@pytest.fixture
def real_db_session(db_container):
    engine = create_engine(db_container.get_connection_url())
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
```

**测试范围：**
- CRUD 操作的事务完整性
- 并发写入的锁行为
- 迁移脚本的正确性
- 大数据量下的查询性能

### 3.3 前端 E2E 补全

当前 Stagehand E2E 测试覆盖有限，需补充以下关键流程：

| 流程 | 优先级 | 测试场景 |
|------|--------|---------|
| 管理员 CRUD | P0 | 用户/部门/工具的增删改查 |
| 工作流编辑 | P0 | 创建、编辑、运行、查看结果 |
| 聊天全流程 | P0 | 发送消息、接收回复、工具调用、文件上传 |
| 认证流程 | P0 | 登录、注册、密码修改、权限验证 |
| 设置页面 | P1 | 主题切换、语言切换、技能配置 |
| 文件管理 | P1 | 上传、下载、预览、删除 |

**Stagehand 测试示例：**
```typescript
// tests/e2e/stagehand/chat-flow.spec.ts
import { stagehand } from '@stagehand/testing';

test('complete chat flow', async ({ page }) => {
  await page.goto('/workspace/chats');
  await stagehand.act('Click the new chat button');
  await stagehand.act('Type "Hello, help me write a Python script" in the input box');
  await stagehand.act('Click the send button');
  await stagehand.waitFor('AI response appears in the chat');
  const response = await stagehand.extract('Get the AI response text');
  expect(response).toContain('Python');
});
```

### 3.4 跨浏览器组件测试

当前 vitest 只在 jsdom 中运行，无法验证真实浏览器行为。

**方案 — Playwright Component Tests：**
```typescript
// tests/component/prompt-input.ct.tsx
import { test, expect } from '@playwright/experimental-ct-react';
import { PromptInput } from '@/components/ai-elements/prompt-input';

test('file drag and drop works in real browser', async ({ mount, page }) => {
  await mount(<PromptInput />);
  // 真实浏览器的拖拽事件
  const input = page.locator('[data-testid="file-input"]');
  await input.setInputFiles({ name: 'test.txt', mimeType: 'text/plain', buffer: Buffer.from('hello') });
  await expect(page.locator('[data-testid="attachment"]')).toBeVisible();
});
```

---

## 四、性能与可靠性测试

### 4.1 并发压力测试

对关键并发模块做压力测试，暴露竞态问题。

**后端重点模块：**
```python
# aio_sandbox_provider — 并发沙箱获取
@pytest.mark.stress
async def test_concurrent_sandbox_acquire():
    """100 个并发请求不应产生重复沙箱或死锁"""
    provider = AioSandboxProvider(config)
    tasks = [provider.acquire_async(f"thread_{i}") for i in range(100)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"{len(errors)} errors in 100 concurrent acquires"

# mcp_session_pool — 并发会话创建
@pytest.mark.stress
async def test_concurrent_mcp_session_creation():
    """并发创建 MCP 会话不应产生重复连接"""
    pool = McpSessionPool(config)
    tasks = [pool.get_or_create(f"conn_{i}") for i in range(50)]
    results = await asyncio.gather(*tasks)
    # 验证没有重复会话
    session_ids = [s.id for s in results]
    assert len(set(session_ids)) == len(session_ids)
```

**前端重点场景：**
- 快速切换聊天线程（hooks 状态竞争）
- 并发文件上传（upload 状态管理）
- 消息流式接收中的 UI 更新（渲染与状态同步）

### 4.2 内存泄漏检测

**后端 — tracemalloc：**
```python
import tracemalloc

def test_no_memory_leak_in_sandbox_lifecycle():
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    for _ in range(100):
        sandbox = create_sandbox(config)
        sandbox.execute("echo hello")
        sandbox.destroy()

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    # 检查是否有持续增长的分配
    for stat in top_stats[:5]:
        assert stat.size_diff < 1024 * 1024, f"Memory leak: {stat}"
```

**前端 — vitest detectLeaks：**
```bash
npx vitest run --detectLeaks --reporter=verbose
```

### 4.3 超时机制验证

确保所有异步操作有合理的超时。

```python
# 验证 HTTP 客户端超时
async def test_api_client_respects_timeout():
    """API 客户端在超时后应抛出异常，不应无限等待"""
    with pytest.raises(httpx.ReadTimeout):
        async with httpx.AsyncClient(timeout=0.001) as client:
            await client.get("http://slow-server/api")

# 验证沙箱命令超时
async def test_sandbox_command_timeout():
    """沙箱命令执行超时后应被终止"""
    sandbox = create_sandbox(config)
    with pytest.raises(TimeoutError):
        await sandbox.execute_command("sleep 1000", timeout=1)
```

---

## 五、CI/CD 集成优化

### 5.1 覆盖率报告

CI 发布后端与前端 coverage 报告，用于识别回归和测试盲区；报告本身不以全局
statements 百分比阻断合并。合并判断依赖 capability matrix 中的唯一主责任测试，
以及真实跨栈写操作的 isolated real E2E。

### 5.2 增量覆盖率

只检查新增/修改代码的覆盖率，而非全局数字。

```bash
# 安装 diff-cover
pip install diff-cover

# 生成增量覆盖率报告
diff-cover coverage.xml --compare-branch=main --fail-under=95
```

**前端增量覆盖率：**
```bash
npx vitest run --coverage
npx diff-cover coverage/coverage-final.json --compare-branch=main --fail-under=95
```

### 5.3 测试分片并行

将 11,000+ 后端测试分片并行执行，缩短 CI 时间。

```yaml
# .github/workflows/backend-tests.yml
strategy:
  matrix:
    shard: [1, 2, 3, 4]
- name: Run tests (shard ${{ matrix.shard }})
  run: |
    .venv/bin/python -m pytest tests/ \
      --splits 4 \
      --group ${{ matrix.shard }} \
      --splitting-algorithm least_duration \
      --cov=app --cov=packages
```

**工具推荐：**
- `pytest-split` — 基于历史运行时间的智能分片
- `pytest-xdist` — 基于进程的并行执行（需注意测试隔离性）

### 5.4 测试报告可视化

```bash
# 后端 — Allure 报告
pip install allure-pytest
pytest --alluredir=allure-results
allure serve allure-results

# 前端 — vitest-ui
npx vitest --ui
```

---

## 六、测试可维护性

### 6.1 公共 Fixture 抽取

当前 136 个新后端测试文件中 mock 模式不一致，应统一到 `conftest.py`。

**建议的公共 fixture：**

```python
# tests/conftest.py — 新增公共 fixture

@pytest.fixture
def mock_app_config():
    """统一的应用配置 mock"""
    config = MagicMock()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4"
    config.sandbox.enabled = True
    return config

@pytest.fixture
def mock_http_client():
    """统一的 HTTP 客户端 mock"""
    client = AsyncMock()
    client.get = AsyncMock(return_value=MagicMock(status_code=200, json=MagicMock(return_value={})))
    client.post = AsyncMock(return_value=MagicMock(status_code=200, json=MagicMock(return_value={})))
    return client

@pytest.fixture
def mock_db_session():
    """统一的数据库会话 mock"""
    session = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session
```

### 6.2 测试目录重组

当前测试文件扁平分布在 `tests/` 目录下，建议按层级组织：

```
backend/tests/
├── unit/                    # 单元测试（mock 依赖）
│   ├── channels/
│   ├── agents/
│   ├── sandbox/
│   ├── workflows/
│   └── persistence/
├── integration/             # 集成测试（真实依赖）
│   ├── api/
│   ├── database/
│   └── mcp/
├── e2e/                     # 端到端测试
│   └── test_client_e2e.py
├── performance/             # 性能测试
│   └── test_concurrent_*.py
└── conftest.py              # 公共 fixture
```

### 6.3 Mock 规范文档

编写团队测试规范，统一 mock 策略：

| 原则 | 说明 |
|------|------|
| **Mock 边界，不Mock 内部** | 只 mock 外部依赖（HTTP、数据库、SDK），不 mock 被测模块内部函数 |
| **Mock 最小化** | 只 mock 测试所需的最小依赖集，不要过度 mock |
| **验证调用，不验证实现** | 断言 mock 被正确调用，而非断言 mock 的内部状态 |
| **使用真实数据结构** | mock 返回值应符合真实数据结构，不要用 `MagicMock()` 代替字典 |
| **测试行为，不测试代码** | 测试应验证业务行为，而非代码行的执行顺序 |

### 6.4 死测试清理

```bash
# 查找未使用的 fixture
pytest --collect-only -q 2>/dev/null | grep "unused"

# 查找重复测试名
pytest --collect-only -q 2>/dev/null | sort | uniq -d

# 查找始终跳过的测试
pytest -v --tb=no 2>/dev/null | grep "SKIPPED"
```

---

## 七、安全测试

### 7.1 认证/授权边界测试

```python
# RBAC 越权测试
class TestRBACBoundary:
    def test_viewer_cannot_create_agent(self, viewer_client):
        """viewer 角色不应有创建 agent 的权限"""
        response = viewer_client.post("/api/agents", json={...})
        assert response.status_code == 403

    def test_user_cannot_access_other_department(self, user_client):
        """用户不应能访问其他部门的资源"""
        response = user_client.get("/api/departments/other-dept/users")
        assert response.status_code == 403

    def test_expired_token_rejected(self, client):
        """过期 token 应被拒绝"""
        token = create_expired_token()
        response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_csrf_protection(self, client):
        """POST 请求应验证 CSRF token"""
        response = client.post("/api/agents", json={...}, headers={"X-CSRF-Token": "invalid"})
        assert response.status_code in (401, 403)
```

### 7.2 输入验证 Fuzz 测试

```python
# SQL 注入防护
@pytest.mark.parametrize("malicious_input", [
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "admin'--",
])
def test_sql_injection_blocked(malicious_input):
    response = client.get(f"/api/users?search={malicious_input}")
    assert response.status_code in (200, 400, 422)

# 路径遍历防护
@pytest.mark.parametrize("path", [
    "../../../etc/passwd",
    "..\\..\\windows\\system32",
    "/etc/shadow",
])
def test_path_traversal_blocked(path):
    response = client.get(f"/api/files/{path}")
    assert response.status_code in (400, 403, 404)

# XSS 防护
def test_xss_in_message_content():
    response = client.post("/api/threads/1/messages", json={
        "content": "<script>alert('xss')</script>"
    })
    # 验证响应中内容被转义
    if response.status_code == 200:
        assert "<script>" not in response.json().get("content", "")
```

### 7.3 沙箱逃逸测试

```python
# code_interpreter 安全边界
class TestSandboxSecurity:
    def test_cannot_access_host_filesystem(self):
        """沙箱内不应能访问宿主机文件系统"""
        result = sandbox.execute("import os; os.listdir('/')")
        # 应该只能看到沙箱内的文件系统
        assert "etc" not in str(result) or "passwd" not in str(result)

    def test_cannot_make_network_requests(self):
        """沙箱内不应能发起外部网络请求"""
        result = sandbox.execute("import urllib.request; urllib.request.urlopen('http://evil.com')")
        assert "Error" in str(result) or "blocked" in str(result).lower()

    def test_cannot_execute_system_commands(self):
        """沙箱内不应能执行系统级命令"""
        result = sandbox.execute("import subprocess; subprocess.run(['rm', '-rf', '/'])")
        assert "Error" in str(result) or "blocked" in str(result).lower()

    def test_resource_limits_enforced(self):
        """沙箱应强制执行资源限制"""
        # 内存限制
        with pytest.raises(ResourceLimitExceeded):
            sandbox.execute("x = ' ' * (1024 * 1024 * 1024)")  # 1GB

        # CPU 时间限制
        with pytest.raises(ResourceLimitExceeded):
            sandbox.execute("while True: pass", timeout=5)
```

### 7.4 依赖安全扫描

```yaml
# .github/workflows/security-scan.yml
- name: Python dependency audit
  run: |
    pip install pip-audit
    pip-audit --strict --desc

- name: Frontend dependency audit
  run: |
    cd frontend
    npm audit --audit-level=high

- name: Container vulnerability scan
  uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'fs'
    scan-ref: '.'
    severity: 'CRITICAL,HIGH'
```

---

## 执行路线图

### Phase 1：基础加固（1-2 周）

| 任务 | 预计工时 | 产出 |
|------|---------|------|
| 覆盖率报告 CI 集成 | 2h | 发布诊断报告并关联 capability matrix |
| 增量覆盖率检查 | 2h | diff-cover 集成到 PR 检查 |
| 不可测代码 `pragma` 标注 | 3h | 覆盖率报告更准确 |
| 公共 fixture 抽取 | 4h | 减少 50%+ 的 mock 样板代码 |

### Phase 2：质量提升（2-4 周）

| 任务 | 预计工时 | 产出 |
|------|---------|------|
| API 契约测试 (schemathesis) | 4h | 自动发现 API 边界问题 |
| RBAC 安全边界测试 | 4h | 补充权限测试覆盖 |
| 关键组件快照测试 | 3h | 防止意外 UI 变更 |
| 测试数据工厂 | 4h | 统一测试数据生成 |
| 测试目录重组 | 6h | 更清晰的测试结构 |

### Phase 3：深度测试（4-6 周）

| 任务 | 预计工时 | 产出 |
|------|---------|------|
| 变异测试 (mutmut + Stryker) | 8h | 发现测试盲区 |
| 并发压力测试 | 6h | 暴露竞态问题 |
| 沙箱安全测试 | 6h | 验证沙箱隔离性 |
| 前端 E2E 补全 | 8h | Stagehand 覆盖核心流程 |
| 数据库集成测试 | 4h | 真实数据库验证 |

### Phase 4：持续优化（长期）

| 任务 | 预计工时 | 产出 |
|------|---------|------|
| 测试分片并行 | 4h | CI 时间缩短 50%+ |
| 内存泄漏检测 | 4h | 长期稳定性保障 |
| 测试报告可视化 | 2h | Allure/vitest-ui 集成 |
| Mock 规范文档 | 2h | 团队测试标准 |
| 死测试定期清理 | 持续 | 保持测试健康度 |

---

## 附录：工具清单

| 工具 | 用途 | 语言 |
|------|------|------|
| `mutmut` | Python 变异测试 | 后端 |
| `hypothesis` | Python 属性测试 | 后端 |
| `schemathesis` | API 契约测试 | 后端 |
| `testcontainers` | 数据库集成测试 | 后端 |
| `pip-audit` | Python 依赖安全扫描 | 后端 |
| `diff-cover` | 增量覆盖率检查 | 两者 |
| `pytest-split` | 测试智能分片 | 后端 |
| `allure-pytest` | 测试报告可视化 | 后端 |
| `@stryker-mutator` | JS/TS 变异测试 | 前端 |
| `@faker-js/faker` | 测试数据生成 | 前端 |
| `@playwright/experimental-ct-react` | 组件测试（真实浏览器） | 前端 |
| `trivy` | 容器/依赖漏洞扫描 | CI |
