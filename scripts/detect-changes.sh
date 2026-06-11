#!/usr/bin/env bash
# detect-changes.sh — 统一变更检测脚本
# 用法: bash scripts/detect-changes.sh [--json] [--verbose]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
    --help|-h)
      echo "用法: bash scripts/detect-changes.sh [--json] [--verbose]"
      echo ""
      echo "选项:"
      echo "  --json      输出 JSON 格式"
      echo "  --verbose   显示详细文件列表"
      echo "  --help      显示帮助信息"
      exit 0
      ;;
    *)
      echo "未知选项: $1" >&2
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
    git -C "$PROJECT_ROOT" log --name-only --oneline origin/main..HEAD 2>/dev/null | grep -v "^[0-9a-f]" || true
}

# 分类函数
classify_changes() {
    local changes="$1"
    local prefix="$2"

    local frontend=()
    local backend=()
    local config=()
    local docs=()
    local scripts=()
    local other=()

    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        case "$file" in
            frontend/*) frontend+=("$file") ;;
            backend/*) backend+=("$file") ;;
            *.yaml|*.yml|*.json|*.toml|*.env*) config+=("$file") ;;
            docs/*|*.md) docs+=("$file") ;;
            scripts/*) scripts+=("$file") ;;
            *) other+=("$file") ;;
        esac
    done <<< "$changes"

    echo "${prefix}_FRONTEND: ${#frontend[@]}"
    echo "${prefix}_BACKEND: ${#backend[@]}"
    echo "${prefix}_CONFIG: ${#config[@]}"
    echo "${prefix}_DOCS: ${#docs[@]}"
    echo "${prefix}_SCRIPTS: ${#scripts[@]}"
    echo "${prefix}_OTHER: ${#other[@]}"

    if $VERBOSE; then
        for f in "${frontend[@]}"; do echo "  ${BLUE}[FRONTEND]${NC} $f"; done
        for f in "${backend[@]}"; do echo "  ${GREEN}[BACKEND]${NC} $f"; done
        for f in "${config[@]}"; do echo "  ${YELLOW}[CONFIG]${NC} $f"; done
        for f in "${docs[@]}"; do echo "  [DOCS] $f"; done
        for f in "${scripts[@]}"; do echo "  [SCRIPTS] $f"; done
        for f in "${other[@]}"; do echo "  [OTHER] $f"; done
    fi
}

# 判断需要的验证 skill
determine_validation_needs() {
    local all_changes="$1"

    local needs_frontend=false
    local needs_backend=false
    local needs_qa=false

    # 检查是否有前端变更
    if echo "$all_changes" | grep -q "^frontend/"; then
        needs_frontend=true
    fi

    # 检查是否有后端变更
    if echo "$all_changes" | grep -q "^backend/"; then
        needs_backend=true
    fi

    # 如果有代码变更，需要功能验证
    if $needs_frontend || $needs_backend; then
        needs_qa=true
    fi

    echo "NEEDS_FRONTEND=$needs_frontend"
    echo "NEEDS_BACKEND=$needs_backend"
    echo "NEEDS_QA=$needs_qa"
}

# 将多行文本转为 JSON 数组（不依赖 jq）
lines_to_json_array() {
    local lines="$1"
    local result="["
    local first=true
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        if $first; then
            first=false
        else
            result+=","
        fi
        # 转义 JSON 字符串中的特殊字符
        local escaped=$(echo "$line" | sed 's/\\/\\\\/g; s/"/\\"/g')
        result+="\"$escaped\""
    done <<< "$lines"
    result+="]"
    echo "$result"
}

# 主函数
main() {
    local unstaged=$(detect_unstaged)
    local staged=$(detect_staged)
    local unpushed=$(detect_unpushed)

    # 合并未暂存和已暂存的变更
    local all_changes=$(echo -e "$unstaged\n$staged" | sort -u | grep -v '^$')

    # 统计数量
    local unstaged_count=0
    local staged_count=0
    local unpushed_count=0
    local total_count=0

    if [[ -n "$unstaged" ]]; then
        unstaged_count=$(echo "$unstaged" | wc -l)
    fi
    if [[ -n "$staged" ]]; then
        staged_count=$(echo "$staged" | wc -l)
    fi
    if [[ -n "$unpushed" ]]; then
        unpushed_count=$(echo "$unpushed" | wc -l)
    fi
    if [[ -n "$all_changes" ]]; then
        total_count=$(echo "$all_changes" | wc -l)
    fi

    if $JSON_OUTPUT; then
        # JSON 输出格式
        local needs_frontend="false"
        local needs_backend="false"
        local needs_qa="false"

        if echo "$all_changes" | grep -q "^frontend/"; then
            needs_frontend="true"
        fi
        if echo "$all_changes" | grep -q "^backend/"; then
            needs_backend="true"
        fi
        if [[ "$needs_frontend" == "true" ]] || [[ "$needs_backend" == "true" ]]; then
            needs_qa="true"
        fi

        cat <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "project_root": "$PROJECT_ROOT",
  "changes": {
    "unstaged": $unstaged_count,
    "staged": $staged_count,
    "unpushed": $unpushed_count,
    "total": $total_count
  },
  "classification": {
    "frontend": $(echo "$all_changes" | { grep -c "^frontend/" || true; }),
    "backend": $(echo "$all_changes" | { grep -c "^backend/" || true; }),
    "config": $(echo "$all_changes" | { grep -c -E "\.(yaml|yml|json|toml|env)" || true; }),
    "docs": $(echo "$all_changes" | { grep -c -E "^(docs/|.*\.md$)" || true; }),
    "scripts": $(echo "$all_changes" | { grep -c "^scripts/" || true; })
  },
  "needs_validation": {
    "frontend": $needs_frontend,
    "backend": $needs_backend,
    "qa": $needs_qa
  },
  "files": {
    "unstaged": $(lines_to_json_array "$unstaged"),
    "staged": $(lines_to_json_array "$staged"),
    "unpushed": $(lines_to_json_array "$unpushed")
  }
}
EOF
    else
        # 人类可读输出
        echo ""
        echo "=========================================="
        echo "       变更检测报告"
        echo "=========================================="
        echo ""
        echo "项目根目录: $PROJECT_ROOT"
        echo ""

        echo "--- 变更统计 ---"
        echo -e "未暂存更改: ${YELLOW}$unstaged_count${NC} 个文件"
        echo -e "已暂存更改: ${YELLOW}$staged_count${NC} 个文件"
        echo -e "已提交未推送: ${YELLOW}$unpushed_count${NC} 个文件"
        echo -e "总计: ${YELLOW}$total_count${NC} 个文件"
        echo ""

        if [[ $total_count -gt 0 ]]; then
            echo "--- 分类统计 ---"
            classify_changes "$all_changes" "总计"
            echo ""

            echo "--- 需要验证的 Skill ---"
            local needs_frontend="false"
            local needs_backend="false"

            if echo "$all_changes" | grep -q "^frontend/"; then
                needs_frontend="true"
                echo -e "${GREEN}✅ frontend-validator${NC} — 检测到前端文件变更"
            else
                echo -e "${YELLOW}⏭️  frontend-validator${NC} — 无前端文件变更"
            fi

            if echo "$all_changes" | grep -q "^backend/"; then
                needs_backend="true"
                echo -e "${GREEN}✅ backend-validator${NC} — 检测到后端文件变更"
            else
                echo -e "${YELLOW}⏭️  backend-validator${NC} — 无后端文件变更"
            fi

            if [[ "$needs_frontend" == "true" ]] || [[ "$needs_backend" == "true" ]]; then
                echo -e "${GREEN}✅ qa-tester${NC} — 代码变更需要功能验证"
            else
                echo -e "${YELLOW}⏭️  qa-tester${NC} — 无代码变更"
            fi

            echo -e "${GREEN}✅ validation-orchestrator${NC} — 统一编排验证"
        else
            echo -e "${GREEN}✅ 无变更，无需验证${NC}"
        fi

        echo ""
        echo "=========================================="
    fi
}

main "$@"
