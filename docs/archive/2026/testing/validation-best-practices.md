# 验证最佳实践指南

> status: archived; current testing authority: `docs/testing-guidelines.md`

## 文档信息

| 项目 | 内容 |
|------|------|
| 创建日期 | 2026-06-10 |
| 适用范围 | AI 生成代码的全流程测试验证 |

---

## 一、验证流程概述

### 1.1 验证阶段

```
代码生成 → 未暂存验证 → 暂存验证 → 提交验证 → 推送验证 → 部署验证
    ↓           ↓           ↓           ↓           ↓           ↓
  AI生成    代码质量    构建测试    功能验证    集成验证    生产验证
```

### 1.2 验证 Skill 矩阵

| 阶段 | frontend-validator | backend-validator | qa-tester | validation-orchestrator |
|------|:-----------------:|:-----------------:|:---------:|:---------------------:|
| 未暂存 | ✅ | ✅ | - | ✅ |
| 已暂存 | ✅ | ✅ | - | ✅ |
| 提交前 | ✅ | ✅ | ✅ | ✅ |
| 推送前 | - | - | ✅ | ✅ |
| 部署前 | - | - | ✅ | ✅ |

---

## 二、日常开发最佳实践

### 2.1 开发中（快速反馈）

**目标**: 快速发现问题，不影响开发流程

**推荐操作**:
```bash
# 代码写完后，快速检查
quick check

# 或分别检查
# 前端
cd frontend && pnpm typecheck && pnpm lint

# 后端
cd backend && uvx ruff check . && uvx ruff format --check .
```

**频率**: 每完成一个小功能就检查一次

**耗时**: 1-2 分钟

### 2.2 功能完成（标准验证）

**目标**: 确保功能完整且符合质量标准

**推荐操作**:
```bash
# 标准验证
standard check

# 或使用 validation-orchestrator
validate
```

**检查内容**:
- 代码质量（TypeCheck、Lint、Format）
- 单元测试
- 安全扫描
- 构建验证

**频率**: 每个功能完成后

**耗时**: 3-5 分钟

### 2.3 提交前（完整验证）

**目标**: 确保代码可以安全提交

**推荐操作**:
```bash
# 完整验证
pre-commit

# 或使用 validation-orchestrator
full validate
```

**检查内容**:
- 代码质量
- 单元测试
- 安全扫描
- 构建验证
- 功能验证（如果服务运行中）
- 集成验证

**频率**: 每次提交前

**耗时**: 10-20 分钟

### 2.4 推送前（功能验证）

**目标**: 确保功能在运行环境中正常工作

**推荐操作**:
```bash
# 功能测试
qa test

# 或完整测试
full test
```

**检查内容**:
- API 端点测试
- E2E 浏览器测试
- 集成验证
- 性能基准测试

**前提**: 服务需要运行（`make dev`）

**频率**: 每次推送前

**耗时**: 10-20 分钟

---

## 三、验证级别选择指南

### 3.1 级别对比

| 级别 | 耗时 | 检查内容 | 适用场景 |
|------|------|----------|----------|
| **quick** | 1-2 min | 基础检查 | 开发中快速反馈 |
| **standard** | 3-10 min | 标准检查 | 日常开发、提交前 |
| **full** | 10-20 min | 完整检查 | 发布前、部署前 |

### 3.2 选择建议

**使用 quick 当**:
- 开发中需要快速反馈
- 只做了小的修改
- 时间紧迫

**使用 standard 当**:
- 功能开发完成
- 准备提交代码
- 日常验证

**使用 full 当**:
- 准备发布
- 重要功能变更
- 需要完整验证

---

## 四、变更阶段验证指南

### 4.1 未暂存更改

**验证内容**:
- 代码风格检查
- 类型检查
- 基础 Lint

**命令**:
```bash
# 检测未暂存更改
git diff --name-only HEAD

# 快速验证
quick check
```

**目的**: 在暂存前发现基础问题

### 4.2 已暂存更改

**验证内容**:
- 构建验证
- 完整测试
- 安全扫描

**命令**:
```bash
# 检测已暂存更改
git diff --name-only --cached

# 标准验证
standard check
```

**目的**: 确保代码可以构建和测试

### 4.3 提交后更改

**验证内容**:
- 功能验证
- 集成验证
- API 契约检查

**命令**:
```bash
# 检测提交后更改
git log --oneline origin/main..HEAD

# 功能测试
qa test
```

**目的**: 确保功能在运行环境中正常工作

---

## 五、问题处理优先级

### 5.1 优先级定义

| 优先级 | 问题类型 | 处理方式 | 时间要求 |
|--------|----------|----------|----------|
| **P0 (阻塞)** | 类型错误、构建失败、安全漏洞 | 立即修复 | 立即 |
| **P1 (高)** | 测试失败、Lint 错误 | 提交前修复 | 当天 |
| **P2 (中)** | 测试覆盖率不足、代码风格 | 尽快修复 | 1-2 天 |
| **P3 (低)** | 文档更新、注释优化 | 后续修复 | 1 周内 |

### 5.2 处理流程

**P0 问题**:
1. 立即停止当前工作
2. 分析问题原因
3. 修复问题
4. 重新验证
5. 确认修复后继续

**P1 问题**:
1. 记录问题
2. 分析问题原因
3. 修复问题
4. 重新验证
5. 提交代码

**P2 问题**:
1. 记录问题
2. 评估影响
3. 计划修复时间
4. 按计划修复

**P3 问题**:
1. 记录问题
2. 放入待办列表
3. 有空时修复

---

## 六、自动修复使用指南

### 6.1 可自动修复的问题

| 问题类型 | 自动修复命令 | 成功率 |
|----------|--------------|--------|
| Lint 错误 | `ruff check --fix` | 90% |
| 格式化问题 | `ruff format` | 100% |
| 前端 Lint | `pnpm lint:fix` | 80% |
| 前端格式化 | `pnpm format:write` | 100% |

### 6.2 不可自动修复的问题

| 问题类型 | 原因 | 处理方式 |
|----------|------|----------|
| 类型错误 | 需要理解业务逻辑 | 手动修复 |
| 测试失败 | 需要理解测试意图 | 手动修复 |
| 安全漏洞 | 需要评估影响 | 手动修复 |
| 逻辑错误 | 需要理解需求 | 手动修复 |

### 6.3 自动修复流程

```bash
# 1. 运行自动修复
cd frontend && pnpm lint:fix && pnpm format:write
cd backend && uvx ruff check . --fix && uvx ruff format .

# 2. 验证修复结果
quick check

# 3. 如果仍有问题，手动修复
# 4. 重新验证
standard check
```

---

## 七、CI/CD 集成建议

### 7.1 GitHub Actions 集成

```yaml
# .github/workflows/validation.yml
name: Validation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Frontend Validation
        run: |
          cd frontend
          pnpm install
          pnpm typecheck
          pnpm lint
          pnpm format
          pnpm test

      - name: Backend Validation
        run: |
          cd backend
          uv sync
          uvx ruff check .
          uvx ruff format --check .
          make test

      - name: Security Scan
        run: |
          cd frontend && pnpm audit --audit-level=moderate 2>/dev/null || true
          cd backend && uv run pip-audit 2>/dev/null || echo "pip-audit not available"
          cd backend && uv run bandit -r packages/ -f json 2>/dev/null | python3 -c "
          import sys, json
          try:
              data = json.load(sys.stdin)
              issues = data.get('results', [])
              if issues:
                  print(f'⚠️ Found {len(issues)} security issues')
                  for i in issues[:5]:
                      print(f'  [{i[\"issue_severity\"]}] {i[\"filename\"]}:{i[\"line_number\"]} — {i[\"issue_text\"]}')
              else:
                  print('✅ No security issues')
          except:
              print('⏭️ bandit not available or parse error')
          " || echo "⏭️ bandit not available"
```

### 7.2 Pre-commit Hook 集成

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Running pre-commit validation..."

# 检测变更
CHANGED_FILES=$(git diff --cached --name-only)

# 前端验证
if echo "$CHANGED_FILES" | grep -q "^frontend/"; then
    cd frontend
    pnpm typecheck || exit 1
    pnpm lint || exit 1
    pnpm format || exit 1
    cd ..
fi

# 后端验证
if echo "$CHANGED_FILES" | grep -q "^backend/"; then
    cd backend
    uvx ruff check . || exit 1
    uvx ruff format --check . || exit 1
    cd ..
fi

echo "Pre-commit validation passed!"
```

---

## 八、常见问题解答

### 8.1 验证太慢怎么办？

**解决方案**:
1. 使用更轻量的验证级别（quick 而非 full）
2. 只验证变更的部分
3. 并行执行验证
4. 优化测试执行

### 8.2 验证失败怎么办？

**处理步骤**:
1. 查看错误详情
2. 尝试自动修复
3. 手动修复问题
4. 重新验证
5. 如果是误报，添加忽略规则

### 8.3 如何跳过某些检查？

**方法**:
1. 使用更轻量的验证级别
2. 明确指定验证范围
3. 添加忽略规则

### 8.4 如何自定义验证规则？

**方法**:
1. 修改对应的配置文件
2. 添加自定义检查脚本
3. 更新验证级别定义

---

## 九、验证报告解读

### 9.1 报告结构

```
统一验证报告
├── 概要（总体状态）
├── 变更检测（变更文件统计）
├── 代码质量（各检查项状态）
├── 测试覆盖（测试结果）
├── 问题列表（发现的问题）
├── 修复命令（自动修复命令）
└── 结论（是否可以提交）
```

### 9.2 状态图标说明

| 图标 | 含义 | 处理方式 |
|------|------|----------|
| ✅ | 通过 | 无需处理 |
| ⚠️ | 警告 | 建议处理 |
| ❌ | 失败 | 必须处理 |
| ⏭️ | 跳过 | 无需处理 |

### 9.3 问题优先级说明

| 优先级 | 含义 | 处理时间 |
|--------|------|----------|
| HIGH | 阻塞问题 | 立即处理 |
| MEDIUM | 重要问题 | 当天处理 |
| LOW | 次要问题 | 后续处理 |

---

## 十、持续改进

### 10.1 验证规则优化

**定期检查**:
- 验证规则是否过严/过松
- 验证耗时是否合理
- 误报率是否可接受

**优化方法**:
- 调整验证级别定义
- 更新忽略规则
- 优化检查脚本

### 10.2 测试覆盖率提升

**目标**:
- 核心功能：100% 覆盖
- 重要功能：80% 覆盖
- 一般功能：60% 覆盖

**方法**:
- 分析测试缺口
- 补充测试用例
- 优化测试执行

### 10.3 文档更新

**需要更新的情况**:
- 验证规则变更
- 新增验证功能
- 问题处理流程变更

**更新内容**:
- 最佳实践指南
- 排错指南
- 使用文档

---

## 附录

### A. 快速命令参考

| 命令 | 说明 | 适用场景 |
|------|------|----------|
| `quick check` | 快速代码质量检查 | 开发中 |
| `standard check` | 标准验证 | 功能完成 |
| `full check` | 完整验证 | 提交前 |
| `write tests` | 分析测试缺口并编写测试 | 开发中 |
| `analyze gaps` | 仅分析测试缺口 | 开发中 |
| `qa test` | 功能测试 | 推送前 |
| `smoke test` | 冒烟测试 | 推送前 |
| `test auth` | 仅测试认证模块 | 推送前 |
| `test agent` | 仅测试 Agent 模块 | 推送前 |
| `test workflow` | 仅测试 Workflow 模块 | 推送前 |
| `cross check` | 交叉验证 | 推送前 |
| `cross browser` | 跨浏览器 E2E 测试 | 部署前 |
| `full test` | 完整功能测试 | 部署前 |
| `validate all` | 全面验证 | 发布前 |
| `pre-commit` | 提交前验证 | 提交前 |
| `pre-deploy` | 部署前验证 | 部署前 |
| `validation history` | 查看验证历史和趋势 | 持续改进 |

### B. 文件位置索引

| 文件 | 位置 | 说明 |
|------|------|------|
| Frontend Validator | `.claude/skills/frontend-validator/` | 前端验证 skill |
| Backend Validator | `.claude/skills/backend-validator/` | 后端验证 skill |
| Backend Validator Evals | `.claude/skills/backend-validator/evals/` | 评估用例 |
| QA Tester | `.claude/skills/qa-tester/` | 功能测试 skill |
| Validation Orchestrator | `.claude/skills/validation-orchestrator/` | 统一编排 skill |
| 变更检测脚本 | `scripts/detect-changes.sh` | 统一变更检测 |
| 报告生成脚本 | `.claude/skills/validation-orchestrator/scripts/generate-report.sh` | 统一报告生成 |
| 验证历史 | `.ideer/validation-history/history.jsonl` | 验证历史记录 |
| 最佳实践指南 | `docs/archive/2026/testing/validation-best-practices.md` | 本文档 |

### C. 相关文档

| 文档 | 位置 | 说明 |
|------|------|------|
| 详细分析 | `docs/archive/2026/testing/ai-code-validation-skill-analysis.md` | 完整分析报告 |
| 执行摘要 | `docs/archive/2026/testing/ai-code-validation-executive-summary.md` | 快速参考 |
| 实施计划 | `docs/archive/2026/testing/validation-orchestrator-implementation-plan.md` | 实施步骤 |
| CLAUDE.md | `/CLAUDE.md` | 项目指令 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-10 | 初始版本 |
