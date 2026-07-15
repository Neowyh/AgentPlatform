# Test Coverage Matrix

This matrix is the manual guardrail for the test-suite reorganization. Update it when moving or deleting tests, and do not delete a file until the same or stronger behavior assertion is listed in the target bucket.

## Coverage Quality Policy

- Coverage reports are diagnostic only; no global statements percentage blocks a merge.
- Core business domains are reviewed through explicit denial, rollback,
  recovery, idempotency, and isolated-real-E2E contracts.
- Coverage scope, skip markers, assertions, and exclusions must not be changed solely to satisfy a percentage.

| Capability | Unit | Integration | Contract | E2E | Notes |
| --- | --- | --- | --- | --- | --- |
| Agent | `backend/tests/unit/gateway/*agent*` | `backend/tests/integration/api/*agents*`, `test_agents_same_name.py` | `backend/tests/contracts/test_visibility_applications*.py`, `backend/tests/contracts/test_user_isolation.py`, `backend/tests/contracts/test_setup_agent_e2e_user_isolation.py`, `backend/tests/contracts/test_update_agent_e2e_user_isolation.py` | `frontend/tests/e2e/workflows/*agent*`, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | Router, visibility, setup/update, same-name owner isolation, and frontend API-shape consumption are no longer in the backend root. |
| Auth/RBAC/Admin | `backend/tests/unit/gateway/*auth*`, admin helpers | `backend/tests/integration/api/*auth*`, `*admin*`, `test_audit_logs.py`, `test_user_deletion.py` | `backend/tests/contracts/test_rbac_matrix.py`, `test_rbac_permission_matrix_extended.py`, `test_permission_model_edge_cases.py`, `test_rbac_security.py` | `frontend/tests/e2e/auth/`, admin workflow specs, `frontend/tests/e2e/real/role-access-boundaries.spec.ts` | The real lane is the primary browser-to-persistence responsibility for seeded super-admin, user, viewer, and department-admin boundaries; it verifies UI results against the isolated SQLite state. |
| Runs/Threads/SSE | `backend/tests/unit/runtime/*run*`, `*thread*`, `*sse*` | `backend/tests/integration/api/test_runs_lifecycle.py`, `*runs*`, `*threads*` | `backend/tests/contracts/test_user_isolation.py`, `backend/tests/contracts/test_memory_thread_meta_isolation.py` | Chat/thread workflow specs | Lifecycle assertions cover run creation, SSE events, checkpoints, persisted run/thread state, cancel, and rollback recovery. |
| Memory | `backend/tests/unit/memory/` | `backend/tests/integration/api/*memory*` | `backend/tests/contracts/test_memory_*isolation.py`, `backend/tests/contracts/test_user_isolation.py` | `frontend/tests/e2e/workflows/memory-management.spec.ts`, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts`, `frontend/tests/e2e/real/memory-persistence.spec.ts` | The real lane is the primary UI persistence check: create, reload, and delete are verified against the isolated user's memory files. Memory persistence is not asserted as SQLite state. |
| Visibility applications | Resource metadata and visibility helpers | Visibility/admin API router tests | `backend/tests/contracts/test_visibility_applications.py` owns mock-router validation/RBAC failures; `test_visibility_applications_e2e.py` owns resource updates, cross-department boundaries, withdraw conflicts, and multi-step workflows | `frontend/tests/e2e/real/visibility-application-flow.spec.ts` | The real lane is the primary end-to-end responsibility: a seeded owner submits two applications, then a super-admin approves one and rejects one; UI status, `visibility_applications.status`, and approved-resource metadata state must agree. |
| Sandbox/Tools/MCP | `backend/tests/unit/sandbox/`, `backend/tests/unit/tools/` | `backend/tests/integration/sandbox/`, MCP/API router tests | `backend/tests/contracts/test_paths_user_isolation.py` | Sandbox/tools workflow specs | Blocking IO remains in `backend/tests/blocking_io/`. |
| Skills | `backend/tests/unit/skills/`, `backend/tests/unit/skills/test_public_skill_catalog.py` | `backend/tests/integration/api/*skills*` | `backend/tests/unit/skills/test_public_skill_catalog.py` | Skill workflow specs, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | Public catalog checks validate required fields, offline readability, and dangerous-instruction patterns. |
| Workflows | `backend/tests/unit/workflows/` | `backend/tests/integration/api/*workflow*` | `backend/tests/contracts/test_user_isolation.py`, path/user isolation contracts | Workflow workflow specs, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | Frontend specs now live in `e2e/workflows/`; API-shape contract uses shared mock fixture. |
| Uploads/Artifacts | `backend/tests/unit/gateway/*upload*`, artifact helpers | `backend/tests/integration/api/*uploads*`, `*artifacts*` | `backend/tests/contracts/test_paths_user_isolation.py`, `backend/tests/contracts/test_user_isolation.py` | Artifact and file-upload workflow specs | Upload path isolation and artifact preview/download are covered by concrete contract, integration, and E2E files. |
| Channels | `test_channel_base.py` owns generic Channel behavior; `test_channel_file_attachments.py` owns attachment-specific upload and failure behavior | `backend/tests/integration/api/*channels*` | Not planned | None | Channel tests are no longer in the backend root; generic base behavior is not duplicated in attachment tests. |
| Persistence/Migrations | `backend/tests/unit/persistence/`, runtime persistence tests | `backend/tests/integration/persistence/test_migration_schema.py`, migration helper tests | `backend/tests/integration/persistence/test_migration_schema.py` | None | Migration workflow runs Alembic up/down/re-upgrade and the schema test entrypoint. |
| Deployment/Scripts | `backend/tests/unit/scripts/`, `test_reconcile_user_state.py` | Intranet deploy script tests in unit/scripts use subprocess fakes | Not planned | None | Includes stale runtime-user inventory and guarded cleanup. |

## Current Migration Rules

- Default backend tests include migrated `unit/`, `integration/`, and `contracts/`; the root `tests/*.py` transition glob has been removed.
- Backend CI shards test execution and publishes a combined coverage report;
  it does not enforce a global percentage gate.
- Default frontend Chromium E2E collects only `e2e/smoke/**/*.spec.ts` and `e2e/workflows/**/*.spec.ts`.
- PR mock Chromium collects `e2e/smoke/**/*.spec.ts`; full mock
  `smoke/` + `workflows/` runs on `main`, nightly, and manual dispatch.
- Isolated real E2E remains the browser-to-persistence proof and is selected
  for high-risk PR paths; visual and public-page a11y run nightly.
- Frontend `qa/` E2E files were merged into primary smoke/workflow specs; retained QA assertions should use behavior-specific test names, not `*-qa.spec.ts` filenames.
- `frontend/tests/e2e/stagehand/` is experimental and excluded from the default Playwright config.
- `frontend/tests/e2e/real/` is excluded from default, auth, visual, and a11y collection. Its config requires isolated-run variables even for collection: `cd frontend && E2E_STATE_DIR=/tmp E2E_RUN_ID=collect-only IDEER_INTERNAL_GATEWAY_BASE_URL=http://127.0.0.1:8001 pnpm exec playwright test --config=playwright.real.config.ts --list`. Execute it from an isolated backend with `QA_ISOLATED=1 bash backend/scripts/run-real-e2e.sh`.
- The real E2E workflow is the sole PR/merge browser gate for real auth and
  persistence; standalone auth remains local diagnostic coverage only.
- Generated artifacts belong under `frontend/playwright-artifacts/`, not under `frontend/tests/`.
- Backend patch-test filenames no longer use `coverage`, `boost`, `gaps`, `full`, `extra`, `cov*`, or `fix`; retained assertions were mechanically renamed into behavior-specific files.
- `feat/improve-tests` is an audited source branch, not an additional collection root. Its retained behavior is represented only through the final `unit/`, `integration/`, and `contracts/` paths recorded in the migration ledger.
