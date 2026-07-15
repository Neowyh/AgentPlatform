# AI 测试工具集成指南

> status: archived; current testing authority: `docs/testing/coverage-matrix.md`

## 概述

本项目集成了两个 AI 测试工具，与现有 validator skill 体系深度整合：

| 工具 | 用途 | 集成位置 |
|------|------|---------|
| **Qodo Cover** | AI 自动生成单元测试 | frontend-validator, backend-validator |
| **Stagehand** | 自然语言驱动 E2E 测试 | qa-tester |

## Qodo Cover

### 功能
- 分析源代码，自动生成符合项目约定的单元测试
- 支持前端（Vitest + React Testing Library）和后端（pytest）
- 识别测试缺口，生成测试存根

### 配置文件
- `frontend/.qodo-cover.json` — 前端测试约定（组件测试、API mock 模式）
- `backend/.qodo-cover.json` — 后端测试约定（class-based、fixtures、markers）

### 使用方式

**通过 validator skill 触发（推荐）:**
```
# 前端
"check frontend --level full"  → 自动运行 AI 测试生成

# 后端
"write tests"  → 分析缺口 + AI 生成测试
"check backend --level full"  → 完整验证含 AI 测试生成
```

**手动运行脚本:**
```bash
# 前端 — 识别测试缺口
bash .claude/skills/frontend-validator/scripts/generate-ai-tests.sh --level standard

# 后端 — 识别测试缺口
bash .claude/skills/backend-validator/scripts/generate-ai-tests.sh --level standard
```

### 约定
- 生成的测试必须经过人工审查后才能提交
- 遵循 `.qodo-cover.json` 中定义的命名和结构约定
- 测试文件放置在 `tests/unit/` 目录，镜像源码目录结构

## Stagehand

### 功能
- 用自然语言描述测试步骤，AI 自动执行浏览器操作
- 自愈能力：UI 变化时自动适配定位器
- 基于 Playwright，与现有 E2E 测试共存

### 配置
- npm 包: `@browserbasehq/stagehand`
- 测试目录: `frontend/tests/e2e/stagehand/`
- 辅助层: `frontend/tests/e2e/utils/stagehand-helper.ts`

### 环境变量
```bash
OPENAI_API_KEY=sk-...           # 必须，Stagehand 使用的 API key
STAGEHAND_MODEL=...             # 可选，AI 模型（默认 computer-use-preview）
STAGEHAND_VERBOSE=1             # 可选，启用详细日志
```

### 使用方式

**通过 qa-tester 触发（推荐）:**
```
"qa test --level standard"  → 经典 Playwright + Stagehand 关键流程
"qa test --level full"      → 全量测试含 Stagehand 全部流程
```

**手动运行:**
```bash
cd frontend
npx playwright test tests/e2e/stagehand/ --project=chromium
```

### 编写 Stagehand 测试
```typescript
import { stagehandAct, stagehandExpect, cleanupStagehand } from "../utils/stagehand-helper";

test("my feature", async ({ page }) => {
  await mockLangGraphAPI(page);

  await stagehandAct(page, "/workspace/path", [
    "click the Create button",
    'fill in name with "Test"',
    "click Save",
  ]);

  await stagehandExpect(page, 'a success message is visible');

  await cleanupStagehand();
});
```

### 与经典 Playwright 的关系
- **不替代**：现有 28 个 Playwright spec 保持不变
- **互补**：Stagehand 用于新功能、复杂交互、快速原型
- **共存**：两套测试在 CI 中并行执行

## 覆盖率

### 前端
```bash
cd frontend && make test-coverage
# 输出: terminal + html/ + coverage/
```

### 后端
```bash
cd backend && make test-coverage
# 输出: terminal (term-missing) + htmlcov/
```

### CI 集成
- `frontend-unit-tests.yml` — 自动运行覆盖率并输出摘要
- `backend-unit-tests.yml` — 自动运行覆盖率并输出摘要

## 文件清单

### 新增文件
| 文件 | 用途 |
|------|------|
| `frontend/.qodo-cover.json` | 前端 Qodo Cover 约定配置 |
| `backend/.qodo-cover.json` | 后端 Qodo Cover 约定配置 |
| `.claude/skills/frontend-validator/scripts/generate-ai-tests.sh` | 前端 AI 测试生成脚本 |
| `.claude/skills/backend-validator/scripts/generate-ai-tests.sh` | 后端 AI 测试生成脚本 |
| `frontend/tests/e2e/utils/stagehand-helper.ts` | Stagehand 辅助层 |
| `frontend/tests/e2e/stagehand/*.spec.ts` | Stagehand 测试用例 |
| `.claude/skills/qa-tester/templates/stagehand-e2e.template.ts` | Stagehand 测试模板 |
| `docs/archive/2026/testing/ai-test-tools-integration.md` | 本文档 |

### 修改文件
| 文件 | 变更 |
|------|------|
| `backend/pyproject.toml` | 添加 pytest-cov |
| `backend/Makefile` | 添加 test-coverage target |
| `frontend/package.json` | 添加 @vitest/coverage-v8, @browserbasehq/stagehand |
| `frontend/vitest.config.ts` | 添加 coverage 配置 |
| `frontend/Makefile` | 添加 test-coverage target |
| `.github/workflows/backend-unit-tests.yml` | 添加覆盖率输出 |
| `.github/workflows/frontend-unit-tests.yml` | 添加覆盖率输出 |
| `.claude/skills/frontend-validator/SKILL.md` | 集成 Qodo Cover |
| `.claude/skills/backend-validator/SKILL.md` | 集成 Qodo Cover + 覆盖率 |
| `.claude/skills/qa-tester/SKILL.md` | 集成 Stagehand |
| `.claude/skills/validation-orchestrator/SKILL.md` | 报告增加覆盖率和 AI 测试统计 |
| `CLAUDE.md` | 更新 Testing 和 Validation Skills 章节 |
