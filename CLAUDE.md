# Repository Guidelines

## Guidance maintenance

Edit `AGENTS.md` as the sole source in each rule directory. Run `python3 scripts/sync_agent_guidance.py --write` to produce its regular UTF-8 `CLAUDE.md` copy, then run `--check`. Both files have identical content, including this convention. Merge valid copy-only rules before writing. Handle both files when moving or deleting a directory; inspect orphan copies before deleting them. CI checks the candidate revision and never repairs or commits copies. Team guidance belongs on `develop` and product branches; pure upstream `main` receives only fast-forward mirror updates. After an upstream merge, check for divergent pairs and use GitNexus `--index-only` for daily indexing.

## Implementation discipline

Keep each change limited to the requested behavior and follow nearby conventions. Before editing, state assumptions and identify any choice that changes the result; ask only when the available evidence cannot resolve it. Prefer the smallest implementation that meets the acceptance criteria. Define completion in observable checks, then run those checks and report their actual status.

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

### Test selection by risk and stage

Choose checks for the changed behavior and the stage of the work. For an ordinary local change, completion requires the focused regression test and the narrowest relevant type or lint check. Changes to public contracts, authorization, persistence, migrations, or core runtime behavior also need the matching contract and integration checks. Run one focused check per TDD slice. Run the applicable standard lane once when preparing the PR; retain `pr-standard` as the cross-stack PR gate. Use `core-full` only for an explicit release, delivery, or full-acceptance request.

A combined lane replaces its included base lanes for the same candidate. Reuse a successful result only when the candidate, dependencies, test configuration, and environment are unchanged. Rerun affected checks after relevant changes, failures, or incomplete evidence. Keep assertions and coverage intact; do not speed up a lane by weakening assertions, adding skips, or reducing its scope.

The lane contract and handoff rules live in [docs/testing/test-lane-runbook.md](docs/testing/test-lane-runbook.md). The [coverage matrix](docs/testing/coverage-matrix.md) maps behavior to test layers; the [test inventory](scripts/test_inventory.py) records discovered files, collected nodes, execution ownership, and status; the [migration ledger](docs/testing/test-migration-ledger.md) records test moves and deletions. After adding or moving tests, run `python3 scripts/test_inventory.py`; before a lane, run `python3 scripts/test_preflight.py <lane>` (the lane runner does this automatically). Smoke is an aggregate subset of mock E2E, not a second execution owner. Missing optional credentials are reported as unexecuted.

### Enterprise changes and upstream compatibility

Keep enterprise behavior at the extension boundary. Prefer, in order, Extension, Adapter, then a registered minimal runtime patch. Preserve Run and Thread lifecycles, streaming events, tool execution, state restoration, and persistence contracts. Offline capability switches and enterprise permission limits must be explicit in configuration and report their effective state. Verify compatibility behavior with customization disabled and enterprise constraints with it enabled.

For each harness patch, record its reason, alternatives, impact, validation, owner, and removal condition in the applicable patch ledger. Resolve upstream conflicts by behavior and contract; review each conflicted change instead of accepting one side globally. Track upstream synchronization, product integration, and compatibility validation as separate states. Contract and patch registration checks prove that changes are recorded, not that behavior is compatible; compatibility evidence comes from the relevant tests and review.

### Task documentation map

Use the document for the task at hand:

| Task | Read first | Validation or record |
| --- | --- | --- |
| Architecture or boundaries | [architecture index](docs/architecture/README.md), [architecture overview](docs/architecture/overview.md) | Relevant contract or integration checks |
| Domain terms or design decisions | [domain guide](docs/agents/domain.md), [glossary](docs/plans/2026-08-26-term-glossary.md), [ADR index](docs/decisions/README.md) | Add or update a decision only when behavior or an interface changes |
| Tests or coverage | [testing index](docs/testing/README.md), [coverage matrix](docs/testing/coverage-matrix.md), [lane runbook](docs/testing/test-lane-runbook.md) | [test inventory](scripts/test_inventory.py), [migration ledger](docs/testing/test-migration-ledger.md) |
| Upstream harness work | [upstream lock](docs/upgrades/deerflow-main-0f7d8709/UPSTREAM_LOCK.md), [patch ledger](UPSTREAM_PATCH_LEDGER.md) | Relevant compatibility checks |
| Local runtime patches | [runtime patch ledger](docs/local-runtime/PATCH_LEDGER.md) | Listed patch-specific validation |
| Issue triage | [issue tracker](docs/agents/issue-tracker.md), [triage labels](docs/agents/triage-labels.md) | Keep the issue state and labels current |

`docs/README.md` is the engineering documentation index. `docs/adr/` holds ADR records; `docs/decisions/` holds dated decisions, and both are indexed from the decisions README. Current documents govern active work. Drafts are proposals, superseded documents point to their replacement, and archived records provide history only. A historical test result never satisfies validation for the current candidate. Update documentation when behavior, interfaces, configuration, architecture, or workflow changes.

### Agent implementation checks

For each implementation slice, identify the public seam, add one focused regression test, verify it fails, implement the smallest change, and verify it passes. After each slice, run only that test and the narrowest relevant static check. At implementation completion, run the applicable standard lane once. Use `UV_CACHE_DIR=/tmp/deer-flow-uv-cache` for backend commands in restricted environments. If a socket test is denied by the sandbox, record the environment result and rerun the same lane where local sockets are permitted; do not alter product code or tests to bypass the restriction.

For auth, RBAC, persistence, memory, admin, Agent, Skill, or Workflow changes, run the matching standard lane and `pr-standard`. GitHub Actions selects Real E2E for protected high-risk paths; report that selection when handing off a pull request. Do not run a repository-wide lane for each TDD slice.

For a focused test or lane that hangs or times out, report it as incomplete with the exact command, elapsed time, and last observed test. Distinguish focused, standard-lane, PR-lane, and delivery-lane results. For `pr-standard` and `core-full`, report each sub-lane's final summary and the parent lane's `TEST_LANE_DURATION` status. A historical result does not replace a run on the current candidate.

## Enterprise interfaces and validation assets

KnowledgeBase list and create operations use `/api/resources` with Resource Governance visibility filtering. Responses expose canonical identity and visibility; provider infrastructure bindings stay server-side. Preserve these boundaries when editing Knowledge Center behavior.

Qodo Cover configurations are local validation assets. Stagehand tests live in `frontend/tests/e2e/stagehand/` and require their explicit specialty lane. The archived `frontend-validator`, `backend-validator`, `qa-tester`, and `validation-orchestrator` designs are historical proposals, not callable skills in this worktree. Read the nearest guidance and the current architecture index for active module paths.

## Commit & Pull Request Guidelines

Git history primarily uses Conventional Commit prefixes such as `fix(runs): ...`, `fix(frontend): ...`, and `fix(sandbox): ...`. Prefer `type(scope): summary` with a concise imperative summary. Pull requests should describe the user-visible change, list validation commands, link related issues, and include screenshots or before/after artifacts for visual changes.

## Security & Configuration Tips

Do not commit local secrets. Start from `config.example.yaml`, `.env.example`, or `extensions_config.example.json`, then keep local values in untracked config files. Use `make doctor` to validate configuration and system requirements before reporting environment issues. For production-mode local startup, `scripts/start-local.sh` validates required commands, `config.yaml`, and configured model-key environment variable names before invoking `make start`; `START_TARGET` and `REQUIRED_ENV_VARS` accept only simple targets and identifiers.

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
