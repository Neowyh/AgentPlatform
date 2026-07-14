## Local Startup Helper

`scripts/start-local.sh` is a POSIX `sh` wrapper for production-mode local startup. It checks required commands, validates `config.yaml`, and verifies required model-key environment variables before running `make start` from the repository root.

Use `START_TARGET` to select another make target and `REQUIRED_ENV_VARS` for a comma-separated list of required environment variable names. Keep both values to simple identifiers/targets; the script validates them before invoking `make`.

## Enterprise Platform Modules

This project has been extended with enterprise intranet platform capabilities on top of the iDeer open-source framework.

### RBAC & Admin
- RBAC model: 4 roles (super_admin > department_admin > user > viewer)
- DB models: `backend/packages/harness/ideer/persistence/models/rbac.py`
- Auth bridge: `backend/app/gateway/authz.py` (`get_current_rbac_user`)
- Admin API: `backend/app/gateway/routers/admin.py`

### Test Accounts (密码 = 邮箱名)

| 角色 | 邮箱 | 密码 | 数据库位置 |
|------|------|------|------------|
| 超级管理员 | `super_admin@test.com` | `super_admin@test.com` | `backend/.ideer/data/ideer.db` |
| 部门管理员 | `department_admin@test.com` | `department_admin@test.com` | `backend/.ideer/data/ideer.db` |
| 普通用户 | `user@test.com` | `user@test.com` | `backend/.ideer/data/ideer.db` |
| 只读用户 | `viewer@test.com` | `viewer@test.com` | `backend/.ideer/data/ideer.db` |
| 管理员 | `admin@test.com` | `admin@test.com` | `backend/.ideer/data/ideer.db` |

**注意:** `department_admin@test.com` 在数据库中角色为 `user`，需要通过 admin 页面修改为 `department_admin` 才能测试部门管理员权限。

### Workflow Engine
- YAML DSL with 6 step types: agent, tool, human_review, condition, parallel, loop
- Core module: `backend/packages/harness/ideer/workflows/`
- API: `backend/app/gateway/routers/workflows.py`
- Frontend: `frontend/src/app/workspace/workflows/`

### Enterprise Tools
- `read_document`: PDF/Word/Excel/PPT → Markdown (`community/doc_reader/`)
- `code_interpreter`: Python/JS execution (`community/code_interpreter/`)
- `data_analyzer`: CSV/Excel/JSON analysis (`community/data_analyzer/`)
- Each tool has both Community Tool and MCP Server deployment modes

### Testing
- Workflow tests: `backend/tests/test_schema_parser.py`, `test_template.py`
- Tool tests: `backend/tests/test_doc_reader.py`, `test_code_interpreter.py`, `test_data_analyzer.py`
- Run with venv: `.venv/bin/python -m pytest backend/tests/`

### AI 测试工具

- **Qodo Cover**: AI 自动生成单元测试（前端 Vitest + 后端 pytest），配置文件 `frontend/.qodo-cover.json` 和 `backend/.qodo-cover.json`
- **Stagehand**: AI 驱动的自然语言 E2E 测试（基于 Playwright），测试目录 `frontend/tests/e2e/stagehand/`
- **覆盖率**: 前端 `@vitest/coverage-v8`，后端 `pytest-cov`，运行 `make test-coverage` 查看

### Validation Skills

四个验证 skill 提供 AI 生成代码的全流程测试验证，集成 Qodo Cover（AI 测试生成）和 Stagehand（自然语言 E2E）：

| Skill | 职责 | 触发命令 |
|-------|------|----------|
| **frontend-validator** | 前端代码质量验证 + AI 测试生成 | "check frontend", "前端验证", "generate tests" |
| **backend-validator** | 后端 Python 代码验证 + AI 测试生成 | "check backend", "后端验证", "write tests" |
| **qa-tester** | 整个应用功能验证（Playwright + Stagehand） | "qa test", "功能测试" |
| **validation-orchestrator** | 统一编排三个 skill | "validate all", "全面验证" |

**验证级别**:
- **quick**: 快速反馈（1-2 min）— TypeCheck + Lint + 格式 + 受影响测试
- **standard**: 标准验证（3-5 min）— Quick + 覆盖率报告 + AI 测试缺口分析 + E2E 关键流程
- **full**: 完整验证（10+ min）— Standard + AI 自动生成测试 + 全量 E2E + Stagehand + PR 就绪评分

**变更阶段覆盖**:
- 未暂存更改：代码质量检查
- 已暂存更改：构建验证、完整测试、覆盖率报告
- 提交后更改：功能验证、集成验证、AI 测试生成

**详细文档**: `docs/ai-code-validation-skill-analysis.md`

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **deer-flow** (51504 symbols, 97474 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/deer-flow/context` | Codebase overview, check index freshness |
| `gitnexus://repo/deer-flow/clusters` | All functional areas |
| `gitnexus://repo/deer-flow/processes` | All execution flows |
| `gitnexus://repo/deer-flow/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
