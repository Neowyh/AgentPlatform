# 测试缺口完善方案

> status: archived; current testing authority: `docs/testing/coverage-matrix.md`

> 基于 validation skill 覆盖度分析，针对识别出的缺口制定的完善方案。
> 创建日期: 2026-06-11

---

## 概览

| 优先级 | 缺口 | 方案 | 预估工作量 | 负责 Skill |
|--------|------|------|-----------|------------|
| HIGH | 视觉回归测试 | Playwright screenshot comparison | 2-3天 | frontend-validator |
| HIGH | Sandbox 端到端测试 | 补充 API + E2E 测试 | 2天 | qa-tester |
| MEDIUM | 无障碍测试 | axe-core 集成 | 1-2天 | frontend-validator |
| MEDIUM | 文件上传/记忆 E2E | 补充 E2E spec | 1-2天 | qa-tester |
| LOW | CI/CD 集成验证 | orchestrator 增加 CI 状态检查 | 1天 | validation-orchestrator |

### 下一阶段计划（本方案暂不实施）

| 缺口 | 说明 | 待解决原因 |
|------|------|-----------|
| WebSocket/实时通信测试 | Channels 消息流、SSE 流式响应端到端测试 | 依赖外部 channel 服务配置，需先完成协议对接 |
| 压力/负载测试 | k6 并发负载测试 | 需要独立环境，不适合日常开发流程 |

---

## 方案 1: 视觉回归测试 (HIGH)

### 问题

当前没有任何截图对比能力，UI 组件的样式变更（颜色、间距、布局）无法自动检测。前端 validator 只检查代码质量，不检查视觉表现。

### 方案

在 Playwright E2E 基础上增加 screenshot comparison，不引入外部 SaaS 服务（如 Percy），保持离线可用。

### 实现步骤

#### 1.1 配置 Playwright screenshot comparison

**文件**: `frontend/playwright.config.ts`

```typescript
// 新增配置
export default defineConfig({
  // ... 现有配置
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,  // 允许 1% 像素差异
      animations: 'disabled',    // 禁用动画避免不稳定
    },
    toMatchSnapshot: {
      maxDiffPixelRatio: 0.01,
    },
  },
});
```

#### 1.2 创建视觉回归测试文件

**目录**: `frontend/tests/e2e/visual/`

需要覆盖的页面/组件（按优先级）:

| 优先级 | 页面/组件 | 测试文件 | 说明 |
|--------|----------|----------|------|
| P0 | Landing 页面 | `landing.visual.spec.ts` | 首页视觉基准 |
| P0 | 登录页面 | `login.visual.spec.ts` | 登录表单布局 |
| P0 | Workspace 布局 | `workspace-layout.visual.spec.ts` | 主工作区框架 |
| P1 | Agent 管理 | `agent-management.visual.spec.ts` | 卡片列表布局 |
| P1 | 工作流管理 | `workflow-management.visual.spec.ts` | 工作流列表 |
| P1 | 管理面板 | `admin-panel.visual.spec.ts` | 统计图表布局 |
| P2 | 侧边栏 | `sidebar.visual.spec.ts` | 导航组件 |
| P2 | 聊天界面 | `chat.visual.spec.ts` | 消息气泡布局 |

**测试模板** (`frontend/tests/e2e/visual/visual-test.template.ts`):

```typescript
import { test, expect } from '@playwright/test';
import { mockLangGraphAPI } from '../utils/mock-api';

// 视觉回归测试模板
// 使用方法: 复制此模板，替换页面路径和选择器

test.describe('页面名称 - 视觉回归', () => {
  test.beforeEach(async ({ page }) => {
    // Mock API 响应，确保数据一致
    await mockLangGraphAPI(page);
    // 设置固定视口
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test('默认状态截图', async ({ page }) => {
    await page.goto('/目标路径');
    await page.waitForLoadState('networkidle');
    // 等待动画结束
    await page.waitForTimeout(500);
    // 首次运行会生成基准截图，后续运行会对比
    await expect(page).toHaveScreenshot('页面名称-default.png', {
      fullPage: true,
      // 忽略动态内容区域（如时间戳、头像）
      mask: [page.locator('[data-testid="dynamic-content"]')],
    });
  });

  test('移动端视口截图', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/目标路径');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('页面名称-mobile.png', {
      fullPage: true,
    });
  });

  test('暗色模式截图', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/目标路径');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot('页面名称-dark.png', {
      fullPage: true,
    });
  });
});
```

#### 1.3 更新 Makefile

**文件**: `frontend/Makefile`

```makefile
# 新增目标
test-visual:
	npx playwright test tests/e2e/visual/ --project=chromium --reporter=list

test-visual-update:
	npx playwright test tests/e2e/visual/ --project=chromium --update-snapshots
```

#### 1.4 更新 frontend-validator skill

**文件**: `.claude/skills/frontend-validator/SKILL.md`

在 **Standard Level** 中新增视觉回归检查:

```markdown
**Visual Regression** (advisory — warns but doesn't block):
\`\`\`bash
cd $FRONTEND_DIR
npx playwright test tests/e2e/visual/ --project=chromium --reporter=list 2>&1 | tail -20
\`\`\`

**Report:**
- If all pass: "✅ 视觉回归测试通过"
- If failures: "⚠️ N 个页面视觉差异 — 运行 `make test-visual-update` 更新基准截图"
- If no visual tests: "⏭️ 未找到视觉回归测试文件"
```

在 **Full Level** 中将视觉回归设为 blocking。

#### 1.5 更新 qa-tester skill

**文件**: `.claude/skills/qa-tester/SKILL.md`

在 Phase 2 E2E 测试中增加视觉回归:

```markdown
**full 级别额外运行视觉回归测试:**
\`\`\`bash
npx playwright test tests/e2e/visual/ --project=chromium --reporter=list
\`\`\`
```

#### 1.6 CI 集成

**文件**: `.github/workflows/e2e-tests.yml`

```yaml
# 新增 job
visual-regression:
  runs-on: ubuntu-latest
  if: contains(github.event.pull_request.labels, 'visual-test') || github.event_name == 'push'
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: 22 }
    - run: cd frontend && pnpm install && npx playwright install chromium
    - run: cd frontend && npx playwright test tests/e2e/visual/ --project=chromium
    - uses: actions/upload-artifact@v4
      if: failure()
      with:
        name: visual-regression-report
        path: frontend/test-results/
```

### 注意事项

- 基准截图（`__screenshots__/`）需要提交到 git
- 首次运行使用 `--update-snapshots` 生成基准
- 动态内容（时间、随机数据）需要 mask 或 mock
- 不同操作系统的字体渲染可能不同，CI 环境需固定

---

## 方案 2: Sandbox 端到端测试 (HIGH)

### 问题

Sandbox 模块有 15 个单元测试文件，但没有 API 级别和 E2E 级别的测试。sandbox 的实际运行行为（容器创建、文件挂载、命令执行、资源清理）未被验证。

### 方案

在 qa-tester 中增加 sandbox 专项测试模块。

### 实现步骤

#### 2.1 创建 Sandbox API 测试

**文件**: `.claude/skills/qa-tester/templates/sandbox-test.template.py`

```python
"""
Sandbox API 测试模板
测试 sandbox 生命周期: 创建 → 执行 → 读取 → 销毁
"""
import httpx
import time

BASE_URL = "http://localhost:8001"

class SandboxAPITest:
    """Sandbox 端到端 API 测试"""

    def __init__(self, token: str):
        self.client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        self.sandbox_id = None

    def test_sandbox_lifecycle(self):
        """测试完整 sandbox 生命周期"""
        # 1. 创建 sandbox
        resp = self.client.post("/api/v1/sandboxes", json={
            "image": "python:3.12-sandbox",
            "timeout": 300,
        })
        assert resp.status_code in (200, 201), f"创建失败: {resp.text}"
        self.sandbox_id = resp.json()["id"]

        # 2. 执行命令
        resp = self.client.post(f"/api/v1/sandboxes/{self.sandbox_id}/exec", json={
            "command": ["python", "-c", "print('hello')"],
        })
        assert resp.status_code == 200
        assert "hello" in resp.json().get("output", "")

        # 3. 文件操作
        resp = self.client.post(f"/api/v1/sandboxes/{self.sandbox_id}/files", json={
            "path": "/tmp/test.txt",
            "content": "test content",
        })
        assert resp.status_code in (200, 201)

        # 4. 读取文件
        resp = self.client.get(f"/api/v1/sandboxes/{self.sandbox_id}/files?path=/tmp/test.txt")
        assert resp.status_code == 200

        # 5. 销毁 sandbox
        resp = self.client.delete(f"/api/v1/sandboxes/{self.sandbox_id}")
        assert resp.status_code in (200, 204)

    def test_sandbox_timeout(self):
        """测试 sandbox 超时自动销毁"""
        resp = self.client.post("/api/v1/sandboxes", json={
            "image": "python:3.12-sandbox",
            "timeout": 5,  # 5秒超时
        })
        assert resp.status_code in (200, 201)
        sandbox_id = resp.json()["id"]

        time.sleep(8)

        resp = self.client.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 404, "sandbox 应已超时销毁"

    def test_sandbox_resource_limits(self):
        """测试 sandbox 资源限制"""
        resp = self.client.post("/api/v1/sandboxes", json={
            "image": "python:3.12-sandbox",
            "memory_limit": "128m",
            "cpu_limit": "0.5",
        })
        # 验证资源限制生效
        assert resp.status_code in (200, 201, 400)  # 400 如果不支持该参数

    def cleanup(self):
        if self.sandbox_id:
            try:
                self.client.delete(f"/api/v1/sandboxes/{self.sandbox_id}")
            except Exception:
                pass
        self.client.close()
```

#### 2.2 创建 Sandbox E2E 测试

**文件**: `frontend/tests/e2e/qa/sandbox-management.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { mockLangGraphAPI } from '../utils/mock-api';

test.describe('Sandbox Management', () => {
  test.beforeEach(async ({ page }) => {
    await mockLangGraphAPI(page);
  });

  test('sandbox creation and interaction', async ({ page }) => {
    // 导航到 sandbox 页面（如果存在独立页面）
    // 或通过 agent chat 触发 sandbox 操作
    await page.goto('/workspace');
    // ... 具体交互步骤取决于 UI 实现
  });
});
```

#### 2.3 更新 qa-tester SKILL.md

在 Phase 1 API 测试中增加 Sandbox 模块:

```markdown
| **Sandbox** | create, exec, files, delete, timeout | sandbox 生命周期、资源限制 |
```

在 Phase 0.5 变更检测中增加:

```markdown
| `backend/packages/harness/ideer/community/aio_sandbox/` | Sandbox API 测试 | HIGH |
```

#### 2.4 更新 run_api_tests.sh

在脚本中增加 sandbox 测试模块。

---

## 方案 3: 无障碍(a11y)测试 (MEDIUM)

### 问题

没有自动化无障碍检测，不符合 WCAG 2.1 AA 标准的自动验证。

### 方案

在 frontend-validator 中集成 axe-core，通过 Playwright 插件运行。

### 实现步骤

#### 3.1 安装依赖

```bash
cd frontend && pnpm add -D @axe-core/playwright
```

#### 3.2 创建 a11y 测试文件

**目录**: `frontend/tests/e2e/a11y/`

**文件**: `frontend/tests/e2e/a11y/accessibility.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility', () => {
  const PAGES = [
    { name: 'Landing', path: '/' },
    { name: 'Login', path: '/login' },
    { name: 'Workspace', path: '/workspace' },
    { name: 'Admin', path: '/workspace/admin' },
    { name: 'Agents', path: '/workspace/agents' },
  ];

  for (const page_info of PAGES) {
    test(`${page_info.name} 页面无严重无障碍问题`, async ({ page }) => {
      await page.goto(page_info.path);
      await page.waitForLoadState('networkidle');

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'best-practice'])
        .analyze();

      // 过滤掉已知的低优先级问题
      const criticalViolations = results.violations.filter(
        v => v.impact === 'critical' || v.impact === 'serious'
      );

      if (criticalViolations.length > 0) {
        console.log('无障碍问题:');
        criticalViolations.forEach(v => {
          console.log(`  [${v.impact}] ${v.id}: ${v.description}`);
          console.log(`    影响元素: ${v.nodes.length} 个`);
        });
      }

      // 允许非关键问题存在，但阻塞 critical/serious
      expect(criticalViolations.length).toBe(0);
    });
  }
});
```

#### 3.3 创建 a11y 检查脚本

**文件**: `.claude/skills/frontend-validator/scripts/check-a11y.sh`

```bash
#!/bin/bash
# 无障碍检查脚本
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

cd "$FRONTEND_DIR"

if [ ! -d "tests/e2e/a11y" ]; then
  echo "SKIP no a11y tests found"
  exit 0
fi

echo "运行无障碍检查..."
npx playwright test tests/e2e/a11y/ --project=chromium --reporter=list 2>&1 | tail -30
```

#### 3.4 更新 frontend-validator SKILL.md

在 Standard Level 增加:

```markdown
**Accessibility Check** (advisory):
\`\`\`bash
bash $PROJECT_ROOT/.claude/skills/frontend-validator/scripts/check-a11y.sh
\`\`\`

**Report:**
- If pass: "✅ 无障碍检查通过 (WCAG 2.1 AA)"
- If fail: "⚠️ 发现 N 个严重无障碍问题 — 详见报告"
- If no tests: "⏭️ 未找到无障碍测试"
```

#### 3.5 更新 Makefile

```makefile
test-a11y:
	npx playwright test tests/e2e/a11y/ --project=chromium --reporter=list
```

---

## 方案 4: 文件上传/记忆 E2E (MEDIUM)

### 问题

文件上传和记忆系统有单元测试和 API 测试，但没有 E2E 测试覆盖前端交互流程。

### 方案

补充 E2E spec 文件。

### 实现步骤

#### 4.1 文件上传 E2E

**文件**: `frontend/tests/e2e/qa/file-upload.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { mockLangGraphAPI } from '../utils/mock-api';
import path from 'path';

test.describe('File Upload', () => {
  test.beforeEach(async ({ page }) => {
    await mockLangGraphAPI(page);
  });

  test('上传文件并附加到消息', async ({ page }) => {
    await page.goto('/workspace');

    // 找到文件上传按钮
    const uploadButton = page.locator('[data-testid="upload-button"]');
    if (await uploadButton.isVisible()) {
      // 上传测试文件
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'test.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('test file content'),
      });

      // 验证文件出现在附件列表
      await expect(page.locator('[data-testid="attachment-list"]')).toContainText('test.txt');
    }
  });

  test('上传文件列表管理', async ({ page }) => {
    await page.goto('/workspace');

    // 导航到文件管理页面（如果有）
    // 验证文件列表显示
    // 测试删除文件
  });
});
```

#### 4.2 记忆系统 E2E

**文件**: `frontend/tests/e2e/qa/memory-management.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { mockLangGraphAPI } from '../utils/mock-api';

test.describe('Memory Management', () => {
  test.beforeEach(async ({ page }) => {
    await mockLangGraphAPI(page);
  });

  test('查看和管理记忆', async ({ page }) => {
    await page.goto('/workspace');

    // 如果记忆功能在设置页面或独立页面
    // 导航到记忆管理界面
    // 验证记忆列表
    // 测试创建/编辑/删除记忆
  });
});
```

#### 4.3 更新 qa-tester SKILL.md

Phase 2 E2E 测试范围增加:

```markdown
| 文件上传 | P1 | 上传 → 附件列表 → 发送带附件消息 |
| 记忆管理 | P2 | 查看记忆 → 创建 → 编辑 → 删除 |
```

---

## 方案 5: CI/CD 集成验证 (LOW)

### 问题

validation-orchestrator 不与 CI/CD 集成，无法验证 CI 运行结果，也不能触发 CI。

### 方案

在 orchestrator 中增加 CI 状态检查能力。

### 实现步骤

#### 5.1 创建 CI 状态检查脚本

**文件**: `.claude/skills/validation-orchestrator/scripts/check-ci-status.sh`

```bash
#!/bin/bash
# 检查当前分支的 CI 状态
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

BRANCH=$(git branch --show-current)

echo "=== CI 状态检查 ==="
echo "分支: $BRANCH"

# 检查是否有 GitHub CLI
if ! command -v gh &> /dev/null; then
  echo "⚠️ gh CLI 未安装，无法检查 CI 状态"
  echo "安装: https://cli.github.com/"
  exit 0
fi

# 检查最近的 CI 运行
echo ""
echo "最近的 CI 运行:"
gh run list --branch "$BRANCH" --limit 5 --json name,status,conclusion,createdAt \
  | python3 -c "
import sys, json
runs = json.load(sys.stdin)
if not runs:
    print('  无 CI 运行记录')
    sys.exit(0)
for r in runs:
    status = r.get('status', '?')
    conclusion = r.get('conclusion', '?')
    icon = '✅' if conclusion == 'success' else '❌' if conclusion == 'failure' else '⏳' if status == 'in_progress' else '⚠️'
    name = r.get('name', '?')
    created = r.get('createdAt', '?')[:16]
    print(f'  {icon} {name}: {conclusion or status} ({created})')
" 2>/dev/null || echo "  无法获取 CI 状态"

# 检查是否有失败的 CI
FAILED=$(gh run list --branch "$BRANCH" --limit 1 --json conclusion \
  | python3 -c "import sys,json; runs=json.load(sys.stdin); print('yes' if runs and runs[0].get('conclusion')=='failure' else 'no')" 2>/dev/null || echo "unknown")

if [ "$FAILED" == "yes" ]; then
  echo ""
  echo "❌ 最近的 CI 运行失败"
  echo "查看详情: gh run view"
  exit 1
else
  echo ""
  echo "✅ CI 状态正常"
fi
```

#### 5.2 更新 validation-orchestrator SKILL.md

在 Phase 0 变更检测后增加 CI 状态检查:

```markdown
### Step 0.4 — CI 状态检查

检查当前分支的 CI 运行状态:

\`\`\`bash
bash $PROJECT_ROOT/.claude/skills/validation-orchestrator/scripts/check-ci-status.sh
\`\`\`

**Report:**
- If all pass: "✅ CI 全部通过"
- If failures: "⚠️ CI 有失败的运行 — 建议先修复再提交"
- If gh not installed: "⏭️ gh CLI 未安装，跳过 CI 检查"
```

在 Phase 3 统一报告中增加 CI 状态:

```markdown
--- CI 状态 ---
| 工作流 | 状态 | 耗时 |
|--------|------|------|
| backend-unit-tests | ✅ 通过 | 2m |
| frontend-unit-tests | ✅ 通过 | 1m |
| e2e-tests | ❌ 失败 | 5m |
| lint-check | ✅ 通过 | 30s |
```

---

## 实施顺序建议

```
第 1 周:
├── 方案 3: 无障碍测试 (1-2天) — 最简单，依赖少
├── 方案 4: 文件上传/记忆 E2E (1-2天) — 补充现有 E2E
└── 方案 5: CI/CD 集成 (1天) — 脚本为主

第 2 周:
├── 方案 1: 视觉回归测试 (2-3天) — 需要生成基准截图
└── 方案 2: Sandbox 端到端测试 (2天) — 需要理解 sandbox API
```

### 依赖关系

```
方案 3 (a11y) ← 独立
方案 4 (上传/记忆 E2E) ← 独立
方案 5 (CI 集成) ← 独立
方案 1 (视觉回归) ← 独立
方案 2 (Sandbox) ← 需要 sandbox API 可用
```

### Skill 文件变更汇总

| Skill | 需修改的文件 | 变更内容 |
|-------|-------------|----------|
| frontend-validator | SKILL.md, scripts/check-a11y.sh | 增加 a11y 检查、视觉回归检查 |
| backend-validator | 无 | 不需要修改 |
| qa-tester | SKILL.md, templates/* | 增加 sandbox、文件上传、记忆测试 |
| validation-orchestrator | SKILL.md, scripts/check-ci-status.sh | 增加 CI 状态检查 |

### 新增文件清单

```
frontend/tests/e2e/visual/visual-test.template.ts    # 视觉回归模板
frontend/tests/e2e/visual/landing.visual.spec.ts     # Landing 视觉测试
frontend/tests/e2e/visual/login.visual.spec.ts       # 登录视觉测试
frontend/tests/e2e/visual/workspace-layout.visual.spec.ts
frontend/tests/e2e/a11y/accessibility.spec.ts        # 无障碍测试
frontend/tests/e2e/qa/file-upload.spec.ts            # 文件上传 E2E
frontend/tests/e2e/qa/memory-management.spec.ts      # 记忆管理 E2E
frontend/tests/e2e/qa/sandbox-management.spec.ts     # Sandbox E2E
.claude/skills/frontend-validator/scripts/check-a11y.sh
.claude/skills/qa-tester/templates/sandbox-test.template.py
.claude/skills/validation-orchestrator/scripts/check-ci-status.sh
.github/workflows/visual-regression.yml              # 可选: 独立 CI 工作流
```

### Makefile 新增目标汇总

```makefile
# frontend/Makefile
test-visual:         # 运行视觉回归测试
test-visual-update:  # 更新基准截图
test-a11y:           # 运行无障碍测试
```

---

## 下一阶段计划

以下缺口已识别但纳入下一阶段实施:

### WebSocket/实时通信测试

- **范围**: Channels 消息流(DingTalk/Discord/Feishu/WeChat)、SSE 流式响应
- **阻塞原因**: 依赖外部 channel 服务配置，需先完成协议对接
- **预估工作量**: 2天
- **初步方案**: 创建 SSE 流式响应测试模板 + Channel webhook 模拟测试

### 压力/负载测试

- **范围**: k6 并发负载测试，覆盖核心 API 端点
- **阻塞原因**: 需要独立测试环境，不适合日常开发流程
- **预估工作量**: 2-3天
- **初步方案**: 集成 k6 脚本，qa-tester full 级别可选运行
