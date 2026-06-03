# Repository Guidelines

## Project Structure & Module Organization

iDeer is a full-stack agent application. `backend/` contains the Python FastAPI/LangGraph gateway, channel integrations, and tests in `backend/tests/`. `frontend/` contains the Next.js app: routes in `frontend/src/app/`, UI in `frontend/src/components/`, domain logic in `frontend/src/core/`, and tests in `frontend/tests/`. Shared scripts live in `scripts/`, deployment assets in `docker/`, public skills in `skills/public/`, and planning material in `docs/`. Respect narrower guidance in `backend/AGENTS.md` and `frontend/AGENTS.md`.

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

Place backend tests in `backend/tests/test_*.py`. Place frontend unit tests in `frontend/tests/unit/`, mirroring the relevant `src/` area, and E2E tests in `frontend/tests/e2e/`. Add focused tests for changed behavior and run the smallest relevant suite before broader checks.

## Commit & Pull Request Guidelines

Git history primarily uses Conventional Commit prefixes such as `fix(runs): ...`, `fix(frontend): ...`, and `fix(sandbox): ...`. Prefer `type(scope): summary` with a concise imperative summary. Pull requests should describe the user-visible change, list validation commands, link related issues, and include screenshots or before/after artifacts for visual changes.

## Security & Configuration Tips

Do not commit local secrets. Start from `config.example.yaml`, `.env.example`, or `extensions_config.example.json`, then keep local values in untracked config files. Use `make doctor` to validate configuration and system requirements before reporting environment issues.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **ideer** (26213 symbols, 48319 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
| `gitnexus://repo/ideer/context` | Codebase overview, check index freshness |
| `gitnexus://repo/ideer/clusters` | All functional areas |
| `gitnexus://repo/ideer/processes` | All execution flows |
| `gitnexus://repo/ideer/process/{name}` | Step-by-step execution trace |

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
