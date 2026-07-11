# Task Plan: 测试体系完整化重构收口

## Goal

按照当前测试体系重构计划继续执行，直到结构、覆盖率、完整验证、artifact 清理和 review 视角全部满足验收条件。

## Current Phase

Phase 2: Frontend coverage gap closure

## Acceptance Criteria

- 后端根目录没有 `backend/tests/test_*.py`。
- 前端根目录没有 `frontend/tests/*.spec.ts(x)`。
- 后端默认、QA、blocking IO、lint、coverage、migration schema 验证全部通过。
- 前端 unit、coverage、typecheck/lint、Chromium/auth/visual/a11y E2E 全部通过。
- 后端和前端 coverage 均 `>= 98%`。
- CI workflow 不再包含 `tests/*.py` 过渡入口。
- `docs/testing/coverage-matrix.md` 无大面积 `Planned/Partial`。
- `docs/testing/test-migration-ledger.md` 能解释删除、迁移、重命名和例外。
- `git diff --cached --name-status --find-renames=50%` 对主要迁移可审查。
- 没有未预期 generated artifacts 或快照进入 diff。

## Phases

### Phase 1: Current-State Audit

- [x] 核对后端根目录测试残留。
- [x] 核对前端根目录 E2E spec 残留。
- [x] 核对当前前后端 coverage 结果。
- [x] 核对 artifacts 残留。
- **Status:** complete

### Phase 2: Frontend Coverage Gap Closure

- [ ] 针对 `tool-settings-page.tsx`、admin pages、card/API/hooks 等高收益缺口补行为测试。
- [ ] 运行 targeted Vitest，确认新增测试通过。
- [ ] 运行 `pnpm vitest run --coverage`，确认 statements `>= 98%`。
- **Status:** in_progress

### Phase 3: Backend Coverage Gap Closure

- [ ] 重新跑 `make test-coverage`，获取包含最新测试的真实缺口。
- [ ] 针对 routers/client/storage 等高收益缺口补行为测试。
- [ ] 再次运行 `make test-coverage`，确认 coverage `>= 98%`。
- **Status:** pending

### Phase 4: Full Verification

- [ ] 后端默认 suite：`tests/unit tests/integration tests/contracts -m "not serial and not requires_llm"`。
- [ ] 后端 `tests/qa`。
- [ ] 后端 `tests/blocking_io`。
- [ ] 后端 `tests/integration/persistence/test_migration_schema.py`。
- [ ] 后端 `make lint`。
- [ ] 前端 `pnpm test`。
- [ ] 前端 `pnpm check`。
- [ ] Playwright Chromium/auth/visual/a11y 全项目执行。
- **Status:** pending

### Phase 5: Cleanup, Review View, and Impact Check

- [ ] 清理 generated artifacts：coverage、htmlcov、playwright-report、playwright-artifacts、test-results 等。
- [ ] 运行静态门禁：`git diff --check`、根测试查找、坏命名查找、E2E 反模式查找。
- [ ] `git add -A` 后检查 `git diff --cached --name-status --find-renames=50%`。
- [ ] 跑 GitNexus `detect_changes`，确认影响范围符合预期。
- **Status:** pending

## Current Evidence

- Backend root test files: cleared.
- Frontend root E2E specs: cleared.
- Frontend statements coverage: `7289/7522 = 96.90%`, below 98%.
- Backend coverage: `97%`, below 98%.
- Generated artifacts still exist under `frontend/coverage`, `frontend/playwright-report`, and `frontend/playwright-artifacts`.
- `git diff --check` currently passes.

## Stop Conditions

- 不降低 98% coverage threshold。
- 不删除测试，除非 ledger 记录等价或更强替代断言和验证命令。
- 不把真实 LLM、真实三方 channel、真实 Docker/remote sandbox 放入默认 PR 必跑。
- 若某个完整门禁三次同类失败，先记录 root cause，再调整计划。
