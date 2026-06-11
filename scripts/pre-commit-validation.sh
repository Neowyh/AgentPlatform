#!/usr/bin/env bash
# pre-commit-validation.sh — 提交前自动验证
# 用法: 作为 git pre-commit hook 使用，或手动运行
#
# 根据暂存的变更文件自动触发对应的 validator:
# - 前端文件变更 → frontend-validator (quick)
# - 后端文件变更 → backend-validator (quick)
# - 无代码变更 → 跳过验证
#
# 安装为 git hook:
#   cp scripts/pre-commit-validation.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  Pre-commit Validation"
echo "=========================================="
echo ""

# 检测暂存的变更
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || true)

if [[ -z "$STAGED_FILES" ]]; then
    echo "✅ No staged files, skipping validation"
    exit 0
fi

STAGED_COUNT=$(echo "$STAGED_FILES" | wc -l)
echo "📁 Staged files: $STAGED_COUNT"
echo ""

# 分类变更
FRONTEND_FILES=$(echo "$STAGED_FILES" | grep "^frontend/" || true)
BACKEND_FILES=$(echo "$STAGED_FILES" | grep "^backend/" || true)

NEEDS_FRONTEND=false
NEEDS_BACKEND=false

if [[ -n "$FRONTEND_FILES" ]]; then
    # 过滤源代码文件
    FE_SOURCE=$(echo "$FRONTEND_FILES" | grep -E "\.(ts|tsx|js|jsx|css)$" || true)
    if [[ -n "$FE_SOURCE" ]]; then
        NEEDS_FRONTEND=true
        FE_COUNT=$(echo "$FE_SOURCE" | wc -l)
        echo "  📦 Frontend: $FE_COUNT source files changed"
    fi
fi

if [[ -n "$BACKEND_FILES" ]]; then
    # 过滤 Python 文件
    BE_SOURCE=$(echo "$BACKEND_FILES" | grep -E "\.py$" || true)
    if [[ -n "$BE_SOURCE" ]]; then
        NEEDS_BACKEND=true
        BE_COUNT=$(echo "$BE_SOURCE" | wc -l)
        echo "  🐍 Backend: $BE_COUNT Python files changed"
    fi
fi

echo ""

# 如果没有代码变更，跳过
if [[ "$NEEDS_FRONTEND" == "false" ]] && [[ "$NEEDS_BACKEND" == "false" ]]; then
    echo "✅ No source code changes, skipping validation"
    exit 0
fi

OVERALL_STATUS="pass"

# 前端验证
if [[ "$NEEDS_FRONTEND" == "true" ]]; then
    echo "=== Frontend Validation (quick) ==="
    cd "$PROJECT_ROOT/frontend"
    if pnpm typecheck && pnpm lint && pnpm format; then
        echo "✅ Frontend validation passed"
    else
        echo "❌ Frontend validation failed"
        OVERALL_STATUS="fail"
    fi
    echo ""
fi

# 后端验证
if [[ "$NEEDS_BACKEND" == "true" ]]; then
    echo "=== Backend Validation (quick) ==="
    cd "$PROJECT_ROOT/backend"
    if uvx ruff check . && uvx ruff format --check .; then
        echo "✅ Backend validation passed"
    else
        echo "❌ Backend validation failed"
        OVERALL_STATUS="fail"
    fi
    echo ""
fi

# 结论
echo "=========================================="
if [[ "$OVERALL_STATUS" == "fail" ]]; then
    echo "❌ Pre-commit validation FAILED"
    echo ""
    echo "修复建议:"
    if [[ "$NEEDS_FRONTEND" == "true" ]]; then
        echo "  cd frontend && pnpm lint:fix && pnpm format:write"
    fi
    if [[ "$NEEDS_BACKEND" == "true" ]]; then
        echo "  cd backend && uvx ruff check . --fix && uvx ruff format ."
    fi
    echo ""
    echo "跳过验证: git commit --no-verify"
    echo "=========================================="
    exit 1
else
    echo "✅ Pre-commit validation PASSED"
    echo "=========================================="
    exit 0
fi
