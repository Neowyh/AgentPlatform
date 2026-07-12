# Progress: 测试体系完整化重构

## 2026-07-10

### Current-State Audit

- Replaced stale offline-deployment planning files with test-reorganization execution plan.
- Verified backend root test files are cleared:
  - `find backend/tests -maxdepth 1 -type f -name 'test_*.py'`
- Verified frontend root E2E specs are cleared:
  - `find frontend/tests -maxdepth 1 -type f \( -name '*.spec.ts' -o -name '*.spec.tsx' \)`
- Verified current frontend coverage from `frontend/coverage/coverage-final.json`:
  - `7289/7522 = 96.90%`
- Verified current backend coverage from `backend/coverage.json`:
  - `97%`, `27080` statements, `729` missing.
- Verified `git diff --check` currently passes.
- Found generated artifacts still present:
  - `frontend/coverage`
  - `frontend/playwright-report`
  - `frontend/playwright-artifacts`

### Next

- Add focused frontend behavior tests for high-miss modules.
- Run targeted Vitest after each batch.
- Re-run frontend coverage and continue until statement coverage is at least 98%.

## 2026-07-11

### Phase 0: Merge Baseline and Contract Reconciliation

- Began the approved staged plan in the existing `fix/test-issues` worktree.
- Preserved the large pre-existing staged/unstaged migration and merge state;
  no reset, checkout, or new worktree was performed.
- Historical evidence identifies the immediate blockers as merged RBAC,
  hard-delete/resource-metadata contracts and seven frontend TypeScript test
  contracts. Fresh collection and gate runs are next.
- Fresh `frontend/pnpm check` exits 0; the seven TypeScript errors recorded
  before the merge resolution are no longer present.
- Default and auth Playwright lists collect successfully (325 and 5 tests).
- First backend collection attempt from the frontend directory failed before
  pytest started because uv attempted to write `/home/wangyh/.cache/uv`; rerun
  it from `backend/` with `UV_CACHE_DIR=/tmp/uv-cache`.
- Backend collection with the temporary uv cache passed: 12,745 selected and
  100 marker-deselected, with no collection error.
- Full default backend baseline: `12681 passed, 53 failed, 11 skipped, 100
  deselected` in 443.93s. Confirmed root-cause groups:
  - stale `soft_delete` calls after the hard-delete metadata contract;
  - stale RBAC tests for implicit first-user creation/promotion;
  - integration fixtures combining context user `test-user-autouse` with a
    database that lacks its `users_ext` record, producing metadata FK errors;
  - stale router mocks and migration-script expectations.
- GitNexus impact: `ResourceMetadataStore` is medium risk (7 direct importers),
  so the removed soft-delete API will not be restored. `get_current_rbac_user`
  is critical (35 direct dependents); its RBAC-first implementation will not
  be changed merely to satisfy legacy tests.
- Fixed the Agent integration fixture so the context user and seeded RBAC row
  share the same ID. This exposed (rather than masked) a real first-update
  optimistic-lock conflict: `_ensure_agent_meta` wrote an existing row and
  incremented its version before validation. The helper now only creates
  missing owner metadata. Focused verification:
  `84 passed` in `test_agents_router_behavior.py`.
- Replaced stale soft-delete metadata tests and workflow router mocks with the
  hard-delete contract. Focused verification: `87 passed` across metadata and
  workflow-delete tests; the only command-side issue was an `rg` path typo
  before pytest, not a test failure.
- Replaced the first RBAC batch of implicit-provisioning assertions with the
  RBAC-first contract: missing profiles return 403 and an unavailable store
  returns 503. Focused verification: `5 passed`.
- Replaced remaining concurrent implicit-provisioning and NULL-role full-access
  expectations with fail-closed/RBAC-first contracts. Full RBAC verification:
  `154 passed` across `test_rbac_matrix.py` and `test_rbac_security.py`.
- Department administrators are now asserted to reject cross-department and
  unscoped visibility applications; the visibility-application contract suite
  passed `33` tests.
- Fresh default backend suite: `12715 passed, 19 failed, 11 skipped, 100
  deselected` in 409.70s (down from 53 failures). Remaining groups are
  password endpoint fixture contracts, three router mocks/Agent metadata
  fallback expectations, and migration-script default-owner expectations.
- Corrected strong-password register/initialize tests to mock the current
  `create_auth_user_with_rbac` and session dependencies, and corrected the
  initialize race test to exercise its `IntegrityError` path. The three
  focused endpoint tests pass.

### `offline_feature` Merge Verification

- Started the required no-commit, no-fast-forward merge into `fix/test-issues` after creating `backup-fix-test-issues-before-offline-merge-20260711`.
- Resolved the seven text conflicts while preserving the layered backend test entrypoints and QA isolation guard.
- Moved the five incoming root backend tests into `unit/` or `integration/api/`; no root `test_*.py` files remain.
- Targeted verification passed: backend `93 passed`; frontend `927 passed`.
- Structure verification passed: layered backend collection, default/auth Playwright lists, root-test gates, and `git diff --check`.
- Full backend default suite did not pass: `12681 passed, 53 failed, 11 skipped, 100 deselected`. Failures cluster around RBAC-first test fixtures and changed metadata/deletion/department-admin contracts.
- Frontend `pnpm check` did not pass: ESLint had warnings only, then TypeScript reported seven test-contract errors, including obsolete skills visibility API expectations.

### Next

- Reconcile the remaining backend test contracts with the merged RBAC-first and hard-delete metadata behavior, then rerun `make test`.
- Update the seven frontend test type contracts and rerun `pnpm check`.
- Only after those gates pass, run coverage, GitNexus change detection, and create the merge commit.
