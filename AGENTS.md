# Repository Guidelines

## Project Structure & Module Organization

iDeer is a full-stack agent application. `backend/` contains the Python FastAPI/LangGraph gateway, channel integrations, and tests in `backend/tests/`. `frontend/` contains the Next.js app: routes in `frontend/src/app/`, UI in `frontend/src/components/`, domain logic in `frontend/src/core/`, and tests in `frontend/tests/`. Shared scripts live in `scripts/`, deployment assets in `docker/`, public skills in `resources/skills/`, and planning material in `docs/`. Respect narrower guidance in `backend/AGENTS.md` and `frontend/AGENTS.md`.

## Build, Test, and Development Commands

- `make setup`: run the interactive setup wizard.
- `make install`: install backend, frontend, and pre-commit dependencies.
- `make dev`: start all local services with hot reload.
- `make start`: start the optimized production-mode local stack.
- `make docker-start` / `make docker-stop`: run or stop the Docker development environment.
- `cd backend && make test`: run backend pytest suite.
- `cd backend && make lint`: run ruff lint and format checks.
- `cd frontend && pnpm test`: run Vitest unit tests.
- `cd frontend && pnpm test:e2e`: run Playwright tests.
- `cd frontend && pnpm check`: run ESLint plus TypeScript checks.

## Coding Style & Naming Conventions

Backend code targets Python 3.12 and is formatted with ruff. Use snake_case for modules, functions, and test files; keep FastAPI gateway code under `backend/app/gateway/`. Frontend code uses TypeScript, React, Next.js App Router, ESLint, and Prettier with Tailwind sorting. Use PascalCase for components, camelCase for functions/hooks, and `use*` for hooks. Keep feature logic in `src/core/` and UI composition in `src/components/`.

## Testing Guidelines

Place backend tests in the relevant `backend/tests/unit/`, `backend/tests/integration/`, or `backend/tests/contracts/` package, using `test_*.py` filenames. Place frontend unit tests in `frontend/tests/unit/`, mirroring the relevant `src/` area, and E2E tests in `frontend/tests/e2e/`. Add focused tests for changed behavior and run the smallest relevant suite before broader checks.

## Commit & Pull Request Guidelines

Git history primarily uses Conventional Commit prefixes such as `fix(runs): ...`, `fix(frontend): ...`, and `fix(sandbox): ...`. Prefer `type(scope): summary` with a concise imperative summary. Pull requests should describe the user-visible change, list validation commands, link related issues, and include screenshots or before/after artifacts for visual changes.

## Security & Configuration Tips

Do not commit local secrets. Start from `config.example.yaml`, `.env.example`, or `extensions_config.example.json`, then keep local values in untracked config files. Use `make doctor` to validate configuration and system requirements before reporting environment issues.

## Session / Working Files (dev-log)

Developer session artifacts (`task_plan.md`, `progress.md`, `findings.md`, and any scratch notes produced during a working session) must live in `dev-log/`, not the repo root. `dev-log/`, coverage outputs, qodo cover config, `pr-build/`, `.opencode/`, `.agents/`, and `.mimocode/` are git-ignored and guarded by a pre-commit hook — never `git add -f` them, and delete them when the session ends.

## Test Accounts (密码 = 邮箱名)

数据库位置: `backend/.ideer/data/ideer.db`（运行时生成，未初始化的 worktree 不包含该文件）。

| 角色 | 邮箱 | 密码 |
|------|------|------|
| 超级管理员 | `super_admin@test.com` | `super_admin@test.com` |
| 部门管理员 | `department_admin@test.com` | `department_admin@test.com` |
| 普通用户 | `user@test.com` | `user@test.com` |
| 只读用户 | `viewer@test.com` | `viewer@test.com` |
| 管理员 | `admin@test.com` | `admin@test.com` |

**注意:** 这些账号仅适用于已初始化或已 seed 的本地数据库；进行角色测试前请确认实际角色值。若 `department_admin@test.com` 仍为 `user`，需先通过 admin 页面修改为 `department_admin`。

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **deer-flow** (46312 symbols, 93112 relationships, 853 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact analysis before editing.** Use `impact({target: "symbolName", direction: "upstream"})` (MCP) or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .` (CLI fallback); report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
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
| `gitnexus://repo/deer-flow/context` | Codebase overview, check index freshness |
| `gitnexus://repo/deer-flow/clusters` | All functional areas |
| `gitnexus://repo/deer-flow/processes` | All execution flows |
| `gitnexus://repo/deer-flow/process/{name}` | Step-by-step execution trace |

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
# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
