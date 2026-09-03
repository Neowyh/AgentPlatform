## Local Startup Helper

`scripts/start-local.sh` is a POSIX `sh` wrapper for production-mode local startup. It checks required commands, validates `config.yaml`, and verifies required model-key environment variables before running `make start` from the repository root.

Use `START_TARGET` to select another make target and `REQUIRED_ENV_VARS` for a comma-separated list of required environment variable names. Keep both values to simple identifiers/targets; the script validates them before invoking `make`.

## Enterprise Platform Modules

This project has been extended with enterprise intranet platform capabilities on top of the iDeer open-source framework.

### RBAC & Admin
- RBAC model: 4 roles (super_admin > department_admin > user > viewer)
- DB models: `backend/packages/harness/ideer/persistence/models/user.py`
- Auth bridge: `backend/app/gateway/authz.py` (`get_current_rbac_user`)
- Admin API: `backend/app/gateway/routers/admin.py`

### Test Accounts (密码 = 邮箱名)

| 角色 | 邮箱 | 密码 | 数据库位置 |
|------|------|------|------------|
| 超级管理员 | `super_admin@test.com` | `super_admin@test.com` | `backend/.ideer/data/ideer.db`（运行时生成） |
| 部门管理员 | `department_admin@test.com` | `department_admin@test.com` | `backend/.ideer/data/ideer.db`（运行时生成） |
| 普通用户 | `user@test.com` | `user@test.com` | `backend/.ideer/data/ideer.db`（运行时生成） |
| 只读用户 | `viewer@test.com` | `viewer@test.com` | `backend/.ideer/data/ideer.db`（运行时生成） |
| 管理员 | `admin@test.com` | `admin@test.com` | `backend/.ideer/data/ideer.db`（运行时生成） |

**注意:** 这些账号仅适用于已初始化或已 seed 的本地数据库；进行角色测试前请确认实际角色值。若 `department_admin@test.com` 仍为 `user`，需先通过 admin 页面修改为 `department_admin`。

### Workflow Engine
- YAML DSL with 7 step types: agent, tool, human_review, condition, parallel, loop, retry
- Core module: `backend/packages/harness/ideer/workflows/`
- API: `backend/app/gateway/routers/workflows.py`
- Frontend: `frontend/src/app/workspace/workflows/`

### Enterprise Tools
- `read_document`: PDF/Word/Excel/PPT → Markdown (`community/doc_reader/`)
- `code_interpreter`: Python/JS execution (`community/code_interpreter/`)
- `data_analyzer`: CSV/Excel/JSON analysis (`community/data_analyzer/`)
- Each tool has both Community Tool and MCP Server deployment modes

### Testing
- Workflow tests: `backend/tests/unit/workflows/test_schema_parser.py`, `backend/tests/unit/scripts/test_template.py`
- Tool tests: `backend/tests/unit/tools/test_doc_reader.py`, `test_code_interpreter.py`, `test_data_analyzer.py`
- Default backend suite: `cd backend && make test` (unit, integration, and contract tests; excludes `serial` and `requires_llm` markers)

### AI 测试工具

- **Qodo Cover**: AI 自动生成单元测试（前端 Vitest + 后端 pytest），配置文件 `frontend/.qodo-cover.json` 和 `backend/.qodo-cover.json`
- **Stagehand**: AI 驱动的自然语言 E2E 测试（基于 Playwright），测试目录 `frontend/tests/e2e/stagehand/`
- **覆盖率**: 前端 `@vitest/coverage-v8`，后端 `pytest-cov`；分别运行 `cd frontend && make test-coverage` 或 `cd backend && make test-coverage`

### AI 验证资产

- Qodo Cover 配置位于 `frontend/.qodo-cover.json` 和 `backend/.qodo-cover.json`。
- Stagehand E2E 测试位于 `frontend/tests/e2e/stagehand/`；默认 Playwright 配置不包含该实验性目录。
- 当前 `.claude/skills/` 仅包含 GitNexus 相关技能；`frontend-validator`、`backend-validator`、`qa-tester` 与 `validation-orchestrator` 是 `docs/archive/2026/testing/ai-code-validation-skill-analysis.md` 中记录的设计/历史方案，不能作为本 worktree 可直接调用的技能。

## Agent skills

### Issue tracker

Issues 跟踪于 GitHub Issues，仓库 `Neowyh/AgentPlatform`（远程 `agentplatform`）。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用默认五角色词汇：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文布局（根 `CONTEXT.md` + `docs/adr/`）。详见 `docs/agents/domain.md`。

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **AgentPlatform** (47479 symbols, 96181 relationships, 886 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact analysis before editing.** Use `impact({target: "symbolName", direction: "upstream"})` (MCP) or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .` (CLI fallback); report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "product/offline-1.x"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "product/offline-1.x" --repo .`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/AgentPlatform/context` | Codebase overview, check index freshness |
| `gitnexus://repo/AgentPlatform/clusters` | All functional areas |
| `gitnexus://repo/AgentPlatform/processes` | All execution flows |
| `gitnexus://repo/AgentPlatform/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
