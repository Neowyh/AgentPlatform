# Test Coverage Matrix

This matrix is the manual guardrail for the test-suite reorganization. Update it when moving or deleting tests, and do not delete a file until the same or stronger behavior assertion is listed in the target bucket.

| Capability | Unit | Integration | Contract | E2E | Notes |
| --- | --- | --- | --- | --- | --- |
| Agent | `backend/tests/unit/gateway/*agent*` | `backend/tests/integration/api/*agents*` | `backend/tests/contracts/test_visibility_applications*.py`, `backend/tests/contracts/test_user_isolation.py`, `backend/tests/contracts/test_setup_agent_e2e_user_isolation.py`, `backend/tests/contracts/test_update_agent_e2e_user_isolation.py` | `frontend/tests/e2e/workflows/*agent*`, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | Router, visibility, setup/update, and frontend API-shape consumption are no longer in the backend root. |
| Auth/RBAC/Admin | `backend/tests/unit/gateway/*auth*`, admin helpers | `backend/tests/integration/api/*auth*`, `*admin*` | `backend/tests/contracts/test_rbac_matrix.py`, `test_rbac_permission_matrix_extended.py`, `test_permission_model_edge_cases.py`, `test_rbac_security.py` | `frontend/tests/e2e/auth/`, admin workflow specs | Role matrix and permission-model files are the deletion gate for auth patch tests. |
| Runs/Threads/SSE | `backend/tests/unit/runtime/*run*`, `*thread*`, `*sse*` | `backend/tests/integration/api/test_runs_lifecycle.py`, `*runs*`, `*threads*` | `backend/tests/contracts/test_user_isolation.py`, `backend/tests/contracts/test_memory_thread_meta_isolation.py` | Chat/thread workflow specs | Lifecycle assertions cover run creation, SSE events, checkpoints, persisted run/thread state, cancel, and rollback recovery. |
| Memory | `backend/tests/unit/memory/` | `backend/tests/integration/api/*memory*` | `backend/tests/contracts/test_memory_*isolation.py`, `backend/tests/contracts/test_user_isolation.py` | `frontend/tests/e2e/workflows/memory-management.spec.ts`, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | Memory storage, queue, updater, thread metadata, and UI API-shape consumption are covered by concrete files. |
| Sandbox/Tools/MCP | `backend/tests/unit/sandbox/`, `backend/tests/unit/tools/` | `backend/tests/integration/sandbox/`, MCP/API router tests | `backend/tests/contracts/test_paths_user_isolation.py` | Sandbox/tools workflow specs | Blocking IO remains in `backend/tests/blocking_io/`. |
| Skills | `backend/tests/unit/skills/`, `backend/tests/unit/skills/test_public_skill_catalog.py` | `backend/tests/integration/api/*skills*` | `backend/tests/unit/skills/test_public_skill_catalog.py` | Skill workflow specs, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | Public catalog checks validate required fields, offline readability, and dangerous-instruction patterns. |
| Workflows | `backend/tests/unit/workflows/` | `backend/tests/integration/api/*workflow*` | `backend/tests/contracts/test_user_isolation.py`, path/user isolation contracts | Workflow workflow specs, `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | Frontend specs now live in `e2e/workflows/`; API-shape contract uses shared mock fixture. |
| Uploads/Artifacts | `backend/tests/unit/gateway/*upload*`, artifact helpers | `backend/tests/integration/api/*uploads*`, `*artifacts*` | `backend/tests/contracts/test_paths_user_isolation.py`, `backend/tests/contracts/test_user_isolation.py` | Artifact and file-upload workflow specs | Upload path isolation and artifact preview/download are covered by concrete contract, integration, and E2E files. |
| Channels | `backend/tests/unit/channels/` | `backend/tests/integration/api/*channels*` | Not planned | None | Channel tests are no longer in the backend root. |
| Persistence/Migrations | `backend/tests/unit/persistence/`, runtime persistence tests | `backend/tests/integration/persistence/test_migration_schema.py`, migration helper tests | `backend/tests/integration/persistence/test_migration_schema.py` | None | Migration workflow runs Alembic up/down/re-upgrade and the schema test entrypoint. |
| Deployment/Scripts | `backend/tests/unit/scripts/` | Intranet deploy script tests in unit/scripts use subprocess fakes | Not planned | None | First migrated backend batch. |

## Current Migration Rules

- Default backend tests include migrated `unit/`, `integration/`, and `contracts/`; the root `tests/*.py` transition glob has been removed.
- Backend CI shards test execution but uploads per-shard coverage data and checks the 98% threshold only after `coverage combine`.
- Default frontend Chromium E2E collects only `e2e/smoke/**/*.spec.ts` and `e2e/workflows/**/*.spec.ts`.
- Auth, visual, and a11y Playwright projects are isolated by directory.
- Frontend `qa/` E2E files were merged into primary smoke/workflow specs; retained QA assertions should use behavior-specific test names, not `*-qa.spec.ts` filenames.
- `frontend/tests/e2e/stagehand/` is experimental and excluded from the default Playwright config.
- Generated artifacts belong under `frontend/playwright-artifacts/`, not under `frontend/tests/`.
- Backend patch-test filenames no longer use `coverage`, `boost`, `gaps`, `full`, `extra`, `cov*`, or `fix`; retained assertions were mechanically renamed into behavior-specific files.
- `feat/improve-tests` is an audited source branch, not an additional collection root. Its retained behavior is represented only through the final `unit/`, `integration/`, and `contracts/` paths recorded in the migration ledger.
