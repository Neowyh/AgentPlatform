# Validation Orchestrator 实施计划

## 文档信息

| 项目 | 内容 |
|------|------|
| 创建日期 | 2026-06-10 |
| 依赖文档 | [ai-code-validation-skill-analysis.md](./ai-code-validation-skill-analysis.md) |

---

## 一、概述

### 1.1 目标

创建一个统一的验证编排器，协调 frontend-validator、backend-validator 和 qa-tester 三个 skill，提供一站式验证体验。

### 1.2 核心功能

1. **自动检测变更**：识别前端/后端/配置文件变更
2. **智能编排**：根据变更类型选择合适的验证 skill
3. **并行执行**：支持多个 skill 并行运行
4. **结果聚合**：生成统一的验证报告
5. **依赖管理**：确保 skill 按正确顺序执行

---

## 二、目录结构

```
.claude/skills/validation-orchestrator/
├── SKILL.md                          # 主 skill 定义
├── references/
│   ├── quick.md                      # 快速验证排错指南
│   ├── standard.md                   # 标准验证排错指南
│   └── full.md                       # 完整验证排错指南
└── scripts/
    ├── detect-changes.sh             # 变更检测脚本
    └── generate-report.sh            # 报告生成脚本
```

---

## 三、SKILL.md 内容

### 3.1 元数据

```yaml
---
name: validation-orchestrator
description: >
  统一验证编排器 — 编排 frontend-validator、backend-validator、qa-tester 三个 skill。
  提供一站式验证体验，自动检测变更、智能编排验证、生成统一报告。
  触发条件: "validate all", "full validation", "全面验证", "pre-commit", "pre-deploy",
  "验证所有", "提交前验证", "部署前验证"
  不要用于: 单独的前端/后端验证（用对应的 validator）、单独的功能测试（用 qa-tester）
allowed-tools:
  - Bash
  - Read
  - Agent
  - AskUserQuestion
  - mcp__gitnexus__detect_changes
  - mcp__gitnexus__impact
  - mcp__gitnexus__context
  - mcp__gitnexus__query
---
```

### 3.2 工作流程

```markdown
# Validation Orchestrator

统一验证编排器，协调三个验证 skill 提供一站式验证体验。

## When to Use

当用户说以下内容时触发:
- "validate all", "full validation", "全面验证"
- "pre-commit", "提交前验证"
- "pre-deploy", "部署前验证"
- "验证所有", "检查所有"

**不要用于:**
- 单独的前端验证（用 frontend-validator）
- 单独的后端验证（用 backend-validator）
- 单独的功能测试（用 qa-tester）

## Language

用中文与用户交流。报告使用中文。

## Phase Overview

| 阶段 | 名称 | quick | standard | full |
|------|------|:-----:|:--------:|:----:|
| Phase 0 | 变更检测 | ✅ | ✅ | ✅ |
| Phase 1 | 代码质量验证 | 前端或后端 | 并行 | 并行 |
| Phase 2 | 功能验证 | ❌ | 核心 | 完整 |
| Phase 3 | 统一报告 | ✅ | ✅ | ✅ |

**默认使用 standard 级别。**

## Quick Commands

| 用户输入 | 级别 | 说明 |
|----------|------|------|
| "quick validate" / "快速验证" | quick | ~2 min, 代码质量检查 |
| "validate" / "验证" | standard | ~10 min, 代码质量 + 功能验证 |
| "full validate" / "完整验证" | full | ~20 min, 全部验证 + 自动修复 |
| "pre-commit" / "提交前验证" | standard | 标准验证 |
| "pre-deploy" / "部署前验证" | full | 完整验证 |

---

## Phase 0: 变更检测

始终执行，检测未暂存、已暂存、已提交的变更。

### Step 0.1 — 检测变更文件

```bash
# 检测未暂存更改
UNSTAGED=$(git diff --name-only HEAD 2>/dev/null)

# 检测已暂存更改
STAGED=$(git diff --name-only --cached 2>/dev/null)

# 检测已提交未推送更改
COMMITTED=$(git log --name-only --oneline origin/main..HEAD 2>/dev/null)

# 合并所有变更
ALL_CHANGES=$(echo -e "$UNSTAGED\n$STAGED" | sort -u | grep -v '^$')
```

### Step 0.2 — 分类变更

```bash
# 按模块分类
FRONTEND_FILES=$(echo "$ALL_CHANGES" | grep "^frontend/" || true)
BACKEND_FILES=$(echo "$ALL_CHANGES" | grep "^backend/" || true)
CONFIG_FILES=$(echo "$ALL_CHANGES" | grep -E "\.(yaml|yml|json|toml)$" || true)

# 统计
FRONTEND_COUNT=$(echo "$FRONTEND_FILES" | grep -c '^frontend/' || echo 0)
BACKEND_COUNT=$(echo "$BACKEND_FILES" | grep -c '^backend/' || echo 0)
CONFIG_COUNT=$(echo "$CONFIG_FILES" | grep -c -E "\.(yaml|yml|json|toml)$" || echo 0)
```

### Step 0.3 — 变更报告

```
=== 变更检测报告 ===
未暂存更改: 5 个文件
已暂存更改: 10 个文件
已提交未推送: 0 个文件

分类统计:
  前端: 8 个文件
  后端: 5 个文件
  配置: 2 个文件

需要验证:
  ✅ 前端验证 (frontend-validator)
  ✅ 后端验证 (backend-validator)
  ⚠️ 功能验证 (qa-tester) — 需要服务运行
```

---

## Phase 1: 代码质量验证

根据变更类型选择验证 skill。

### Step 1.1 — 前端验证

如果有前端文件变更，运行 frontend-validator:

```bash
# 使用 Agent 调用 frontend-validator
# Level: quick (开发中) / standard (提交前) / full (部署前)
```

### Step 1.2 — 后端验证

如果有后端文件变更，运行 backend-validator:

```bash
# 使用 Agent 调用 backend-validator
# Level: quick (开发中) / standard (提交前) / full (部署前)
```

### Step 1.3 — 并行执行

如果同时有前端和后端变更，并行执行:

```bash
# 并行运行 frontend-validator 和 backend-validator
# 使用 Agent 并行调用
```

---

## Phase 2: 功能验证

代码质量验证通过后，运行功能验证。

### Step 2.1 — 服务状态检查

```bash
# 检查后端
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health || echo "DOWN")

# 检查前端
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "DOWN")
```

### Step 2.2 — 运行 qa-tester

如果服务运行中，运行 qa-tester:

```bash
# 使用 Agent 调用 qa-tester
# Level: quick (开发中) / standard (提交前) / full (部署前)
```

### Step 2.3 — 服务未运行处理

如果服务未运行:
- quick 级别：跳过功能验证，只报告代码质量
- standard 级别：提示用户启动服务
- full 级别：自动启动服务后运行验证

---

## Phase 3: 统一报告

聚合所有验证结果，生成统一报告。

### Step 3.1 — 收集结果

收集各阶段的验证结果:
- 前端验证报告
- 后端验证报告
- 功能验证报告（如果有）

### Step 3.2 — 生成统一报告

```
=== 统一验证报告 ===
时间: 2026-06-10 14:30:00
级别: standard
耗时: 8m 30s
变更文件: 15 (前端: 8, 后端: 7)

概要:
  ✅ 可以提交 / ❌ 暂时不能提交 / ⚠️ 建议检查

变更检测:
| 阶段 | 文件数 | 状态 |
|------|--------|------|
| 未暂存 | 5 | ✅ 已验证 |
| 已暂存 | 10 | ✅ 已验证 |
| 已提交 | 0 | - |

验证结果:
| 检查项 | Frontend | Backend | 状态 |
|--------|----------|---------|------|
| 类型检查 | ✅ | ✅ | 通过 |
| Lint | ✅ | ⚠️ 2 warnings | 警告 |
| 格式化 | ✅ | ✅ | 通过 |
| 单元测试 | 135 pass | 98 pass | 通过 |
| E2E 测试 | 8/8 pass | - | 通过 |
| API 测试 | - | 45/45 pass | 通过 |

问题列表:
| # | 优先级 | 类型 | 描述 | 修复建议 |
|---|--------|------|------|----------|
| 1 | HIGH | Lint | backend/config.py:45 未使用导入 | uvx ruff check . --fix |
| 2 | MEDIUM | 测试覆盖 | backend/admin.py 无单元测试 | 添加 TestAdmin 类 |

修复命令:
  cd backend && uvx ruff check . --fix && uvx ruff format .
  cd frontend && pnpm lint:fix && pnpm format:write

结论:
  ⚠️ 发现 2 个问题，建议修复后提交。
```

### Step 3.3 — 保存报告

将报告保存到 `.ideer/validation-reports/` 目录:

```bash
mkdir -p .ideer/validation-reports
REPORT_FILE=".ideer/validation-reports/$(date +%Y%m%d_%H%M%S).md"
echo "$REPORT" > "$REPORT_FILE"
```

---

## 自动修复（full 级别）

如果验证失败且是 full 级别，尝试自动修复。

### Step 4.1 — 分析问题

分析验证失败的问题，确定是否可以自动修复。

### Step 4.2 — 执行修复

```bash
# 前端自动修复
cd frontend && pnpm lint:fix && pnpm format:write

# 后端自动修复
cd backend && uvx ruff check . --fix && uvx ruff format .
```

### Step 4.3 — 回归验证

修复后重新运行验证。

---

## Troubleshooting

### 变更检测失败

```bash
# 手动检测变更
git status
git diff --name-only HEAD
git diff --name-only --cached
```

### 验证 skill 未找到

```bash
# 检查 skill 是否存在
ls -la .claude/skills/

# 重新创建 skill
# 参考 validation-orchestrator-implementation-plan.md
```

### 服务未运行

```bash
# 启动服务
make dev

# 或分别启动
cd backend && make dev
cd frontend && pnpm dev
```
```

---

## 四、变更检测脚本

### 4.1 scripts/detect-changes.sh

```bash
#!/usr/bin/env bash
# detect-changes.sh — 统一变更检测脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 输出格式
JSON_OUTPUT=false
VERBOSE=false

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# 检测函数
detect_unstaged() {
    git -C "$PROJECT_ROOT" diff --name-only HEAD 2>/dev/null || true
}

detect_staged() {
    git -C "$PROJECT_ROOT" diff --name-only --cached 2>/dev/null || true
}

detect_unpushed() {
    git -C "$PROJECT_ROOT" log --name-only --oneline origin/main..HEAD 2>/dev/null || true
}

# 分类函数
classify_changes() {
    local changes="$1"
    local category="$2"
    
    local frontend=()
    local backend=()
    local config=()
    local other=()
    
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        case "$file" in
            frontend/*) frontend+=("$file") ;;
            backend/*) backend+=("$file") ;;
            *.yaml|*.yml|*.json|*.toml) config+=("$file") ;;
            *) other+=("$file") ;;
        esac
    done <<< "$changes"
    
    echo "$category_FRONTEND: ${#frontend[@]}"
    echo "$category_BACKEND: ${#backend[@]}"
    echo "$category_CONFIG: ${#config[@]}"
    echo "$category_OTHER: ${#other[@]}"
    
    if $VERBOSE; then
        for f in "${frontend[@]}"; do echo "  [FRONTEND] $f"; done
        for f in "${backend[@]}"; do echo "  [BACKEND] $f"; done
        for f in "${config[@]}"; do echo "  [CONFIG] $f"; done
        for f in "${other[@]}"; do echo "  [OTHER] $f"; done
    fi
}

# 主函数
main() {
    local unstaged=$(detect_unstaged)
    local staged=$(detect_staged)
    local unpushed=$(detect_unpushed)
    
    local all_changes=$(echo -e "$unstaged\n$staged" | sort -u | grep -v '^$')
    
    local unstaged_count=$(echo "$unstaged" | grep -c '^' || echo 0)
    local staged_count=$(echo "$staged" | grep -c '^' || echo 0)
    local unpushed_count=$(echo "$unpushed" | grep -c '^' || echo 0)
    local total_count=$(echo "$all_changes" | grep -c '^' || echo 0)
    
    if $JSON_OUTPUT; then
        # JSON 输出格式
        cat <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "changes": {
    "unstaged": $unstaged_count,
    "staged": $staged_count,
    "unpushed": $unpushed_count,
    "total": $total_count
  },
  "needs_validation": {
    "frontend": $([ $(echo "$all_changes" | grep -c '^frontend/' || echo 0) -gt 0 ] && echo "true" || echo "false"),
    "backend": $([ $(echo "$all_changes" | grep -c '^backend/' || echo 0) -gt 0 ] && echo "true" || echo "false"),
    "config": $([ $(echo "$all_changes" | grep -c -E '\.(yaml|yml|json|toml)$' || echo 0) -gt 0 ] && echo "true" || echo "false")
  }
}
EOF
    else
        # 人类可读输出
        echo "=== 变更检测报告 ==="
        echo ""
        echo "未暂存更改: $unstaged_count 个文件"
        echo "已暂存更改: $staged_count 个文件"
        echo "已提交未推送: $unpushed_count 个文件"
        echo "总计: $total_count 个文件"
        echo ""
        
        if [[ $total_count -gt 0 ]]; then
            echo "--- 分类统计 ---"
            classify_changes "$all_changes" "总计"
            echo ""
            
            echo "--- 需要验证 ---"
            local needs_frontend=$(echo "$all_changes" | grep -c '^frontend/' || echo 0)
            local needs_backend=$(echo "$all_changes" | grep -c '^backend/' || echo 0)
            
            if [[ $needs_frontend -gt 0 ]]; then
                echo -e "${GREEN}✅ 前端验证 (frontend-validator)${NC}"
            else
                echo -e "${YELLOW}⏭️ 前端验证 — 无前端变更${NC}"
            fi
            
            if [[ $needs_backend -gt 0 ]]; then
                echo -e "${GREEN}✅ 后端验证 (backend-validator)${NC}"
            else
                echo -e "${YELLOW}⏭️ 后端验证 — 无后端变更${NC}"
            fi
            
            echo -e "${YELLOW}⚠️ 功能验证 (qa-tester) — 需要服务运行${NC}"
        else
            echo -e "${GREEN}✅ 无变更，无需验证${NC}"
        fi
    fi
}

main "$@"
```

---

## 五、报告生成脚本

### 5.1 scripts/generate-report.sh

```bash
#!/usr/bin/env bash
# generate-report.sh — 统一报告生成脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 输入参数
FRONTEND_REPORT="${1:-}"
BACKEND_REPORT="${2:-}"
QA_REPORT="${3:-}"
LEVEL="${4:-standard}"

# 报告目录
REPORT_DIR="$PROJECT_ROOT/.ideer/validation-reports"
mkdir -p "$REPORT_DIR"
REPORT_FILE="$REPORT_DIR/$(date +%Y%m%d_%H%M%S).md"

# 生成报告
generate_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local duration="${DURATION:-0m 0s}"
    local changed_files=$(git -C "$PROJECT_ROOT" diff --name-only HEAD 2>/dev/null | wc -l || echo 0)
    
    cat > "$REPORT_FILE" <<EOF
# 统一验证报告

| 项目 | 内容 |
|------|------|
| 时间 | $timestamp |
| 级别 | $LEVEL |
| 耗时 | $duration |
| 变更文件 | $changed_files |

## 概要

$(generate_summary)

## 验证结果

### 代码质量

$(generate_quality_table)

### 测试覆盖

$(generate_test_table)

## 问题列表

$(generate_issues)

## 修复命令

$(generate_fix_commands)

## 结论

$(generate_conclusion)
EOF

    echo "报告已保存到: $REPORT_FILE"
}

# 生成概要
generate_summary() {
    local has_errors=false
    
    if [[ -n "$FRONTEND_REPORT" ]] && grep -q "❌" "$FRONTEND_REPORT" 2>/dev/null; then
        has_errors=true
    fi
    if [[ -n "$BACKEND_REPORT" ]] && grep -q "❌" "$BACKEND_REPORT" 2>/dev/null; then
        has_errors=true
    fi
    if [[ -n "$QA_REPORT" ]] && grep -q "❌" "$QA_REPORT" 2>/dev/null; then
        has_errors=true
    fi
    
    if $has_errors; then
        echo "❌ 暂时不能提交"
    else
        echo "✅ 可以提交"
    fi
}

# 生成质量表格
generate_quality_table() {
    echo "| 检查项 | Frontend | Backend | 状态 |"
    echo "|--------|----------|---------|------|"
    
    # 从前端报告提取
    if [[ -n "$FRONTEND_REPORT" ]]; then
        local fe_type=$(grep "TypeCheck" "$FRONTEND_REPORT" | head -1 | awk '{print $2}' || echo "⏭️")
        local fe_lint=$(grep "Lint" "$FRONTEND_REPORT" | head -1 | awk '{print $2}' || echo "⏭️")
        local fe_format=$(grep "Format" "$FRONTEND_REPORT" | head -1 | awk '{print $2}' || echo "⏭️")
        echo "| 类型检查 | $fe_type | ⏭️ | - |"
        echo "| Lint | $fe_lint | ⏭️ | - |"
        echo "| 格式化 | $fe_format | ⏭️ | - |"
    fi
    
    # 从后端报告提取
    if [[ -n "$BACKEND_REPORT" ]]; then
        local be_lint=$(grep "Lint" "$BACKEND_REPORT" | head -1 | awk '{print $2}' || echo "⏭️")
        local be_format=$(grep "Format" "$BACKEND_REPORT" | head -1 | awk '{print $2}' || echo "⏭️")
        echo "| Lint | ⏭️ | $be_lint | - |"
        echo "| 格式化 | ⏭️ | $be_format | - |"
    fi
}

# 生成测试表格
generate_test_table() {
    echo "| 测试类型 | Frontend | Backend | 状态 |"
    echo "|----------|----------|---------|------|"
    
    # 从前端报告提取
    if [[ -n "$FRONTEND_REPORT" ]]; then
        local fe_tests=$(grep "Unit Tests" "$FRONTEND_REPORT" | head -1 | awk '{print $3, $4}' || echo "⏭️")
        echo "| 单元测试 | $fe_tests | ⏭️ | - |"
    fi
    
    # 从后端报告提取
    if [[ -n "$BACKEND_REPORT" ]]; then
        local be_tests=$(grep "Unit Tests" "$BACKEND_REPORT" | head -1 | awk '{print $3, $4}' || echo "⏭️")
        echo "| 单元测试 | ⏭️ | $be_tests | - |"
    fi
    
    # 从 QA 报告提取
    if [[ -n "$QA_REPORT" ]]; then
        local api_tests=$(grep "API Tests" "$QA_REPORT" | head -1 | awk '{print $3}' || echo "⏭️")
        local e2e_tests=$(grep "E2E Tests" "$QA_REPORT" | head -1 | awk '{print $3}' || echo "⏭️")
        echo "| API 测试 | - | $api_tests | - |"
        echo "| E2E 测试 | $e2e_tests | - | - |"
    fi
}

# 生成问题列表
generate_issues() {
    echo "| # | 优先级 | 类型 | 描述 | 修复建议 |"
    echo "|---|--------|------|------|----------|"
    
    local issue_num=1
    
    # 从前端报告提取问题
    if [[ -n "$FRONTEND_REPORT" ]]; then
        while IFS= read -r line; do
            if [[ "$line" == *"❌"* ]]; then
                echo "| $issue_num | HIGH | 前端 | $line | 参考 frontend-validator |"
                ((issue_num++))
            fi
        done < "$FRONTEND_REPORT"
    fi
    
    # 从后端报告提取问题
    if [[ -n "$BACKEND_REPORT" ]]; then
        while IFS= read -r line; do
            if [[ "$line" == *"❌"* ]]; then
                echo "| $issue_num | HIGH | 后端 | $line | 参考 backend-validator |"
                ((issue_num++))
            fi
        done < "$BACKEND_REPORT"
    fi
    
    if [[ $issue_num -eq 1 ]]; then
        echo "| - | - | - | 无问题 | - |"
    fi
}

# 生成修复命令
generate_fix_commands() {
    echo '```bash'
    
    if [[ -n "$FRONTEND_REPORT" ]] && grep -q "auto-fixable" "$FRONTEND_REPORT" 2>/dev/null; then
        echo "# 前端自动修复"
        echo "cd frontend && pnpm lint:fix && pnpm format:write"
    fi
    
    if [[ -n "$BACKEND_REPORT" ]] && grep -q "auto-fixable" "$BACKEND_REPORT" 2>/dev/null; then
        echo "# 后端自动修复"
        echo "cd backend && uvx ruff check . --fix && uvx ruff format ."
    fi
    
    echo '```'
}

# 生成结论
generate_conclusion() {
    local has_errors=false
    local has_warnings=false
    
    if [[ -n "$FRONTEND_REPORT" ]]; then
        if grep -q "❌" "$FRONTEND_REPORT" 2>/dev/null; then
            has_errors=true
        fi
        if grep -q "⚠️" "$FRONTEND_REPORT" 2>/dev/null; then
            has_warnings=true
        fi
    fi
    
    if [[ -n "$BACKEND_REPORT" ]]; then
        if grep -q "❌" "$BACKEND_REPORT" 2>/dev/null; then
            has_errors=true
        fi
        if grep -q "⚠️" "$BACKEND_REPORT" 2>/dev/null; then
            has_warnings=true
        fi
    fi
    
    if $has_errors; then
        echo "❌ 发现阻塞问题，请修复后重新验证。"
    elif $has_warnings; then
        echo "⚠️ 发现警告，建议检查后提交。"
    else
        echo "✅ 验证通过，可以提交。"
    fi
}

# 主函数
main() {
    generate_report
}

main "$@"
```

---

## 六、测试计划

### 6.1 单元测试

| 测试用例 | 输入 | 预期输出 |
|----------|------|----------|
| 变更检测 - 无变更 | 干净工作区 | 无变更报告 |
| 变更检测 - 仅前端 | 前端文件变更 | 前端验证建议 |
| 变更检测 - 仅后端 | 后端文件变更 | 后端验证建议 |
| 变更检测 - 混合 | 前后端文件变更 | 并行验证建议 |
| 报告生成 - 全部通过 | 所有验证通过 | ✅ 可以提交 |
| 报告生成 - 有失败 | 验证失败 | ❌ 暂时不能提交 |

### 6.2 集成测试

| 测试场景 | 验证内容 |
|----------|----------|
| quick 级别 | 代码质量检查 |
| standard 级别 | 代码质量 + 功能验证 |
| full 级别 | 完整验证 + 自动修复 |

### 6.3 端到端测试

| 测试流程 | 验证内容 |
|----------|----------|
| 开发 → 提交 | 未暂存 → 已暂存 → 已提交 |
| 提交 → 推送 | 已提交 → 已推送 |
| 推送 → 部署 | CI/CD 触发 |

---

## 七、实施时间表

| 阶段 | 任务 | 时间 | 产出 |
|------|------|------|------|
| **Phase 1** | 创建目录结构 | 0.5 天 | `.claude/skills/validation-orchestrator/` |
| **Phase 1** | 编写 SKILL.md | 0.5 天 | 主 skill 定义 |
| **Phase 1** | 编写变更检测脚本 | 0.5 天 | `scripts/detect-changes.sh` |
| **Phase 1** | 编写报告生成脚本 | 0.5 天 | `scripts/generate-report.sh` |
| **Phase 2** | 编写参考文档 | 0.5 天 | `references/*.md` |
| **Phase 2** | 测试和调试 | 0.5 天 | 测试报告 |
| **Phase 3** | 文档更新 | 0.5 天 | 更新 CLAUDE.md |
| **Phase 3** | 示例工作流 | 0.5 天 | 示例文件 |
| **总计** | - | **4 天** | 完整的 validation-orchestrator skill |

---

## 八、风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Agent 调用失败 | 验证中断 | 添加重试机制和错误处理 |
| 报告生成错误 | 无法生成报告 | 添加报告模板和验证 |
| 脚本执行失败 | 功能不可用 | 添加错误处理和日志 |
| 性能问题 | 验证耗时过长 | 优化脚本和并行执行 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-10 | 初始版本 |
