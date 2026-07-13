# Test Migration Ledger

This ledger is the deletion and move gate for the test-suite reorganization.
Do not delete an old test file unless this file records an equal or stronger
replacement assertion and the validation command for that batch.

## Batch 2026-07-13: Phase 3 evidence-backed duplicate consolidation

Only test cases with an equal-or-stronger retained owner were deleted. No
production code, skip rule, coverage threshold, or public API changed.

| Deleted source | Retained primary owner | Contract retained | Validation |
| --- | --- | --- | --- |
| `frontend/tests/e2e/workflows/admin-panel.spec.ts`: dashboard access, statistics cards, user navigation, department navigation | `admin-management.spec.ts`: Dashboard plus click-based navigation access control | Dashboard route, exactly six `admin-stat-card` elements, and user/department navigation | Affected workflow collection: 58 tests / 7 files; `pnpm exec playwright test --project=chromium tests/e2e/workflows/admin-management.spec.ts` (12 passed) |
| `agent-chat.spec.ts`: agent gallery load | `agent-management.spec.ts`: gallery agent cards | Gallery load; keeper additionally checks normal and template cards | Same frontend collection |
| `chat-flow.spec.ts`: new-chat load and send/receive | `chat.spec.ts`: input-page and streamed reply contracts | New-chat input and mocked stream response; chat export remains in `chat-flow.spec.ts` | Same frontend collection |
| `settings-management.spec.ts`: Skills tabs and public Skills list | `skill-management.spec.ts`: Settings Page cases | Public/custom tabs and public skill content; non-Skills settings remain in source | Same frontend collection |
| `backend/tests/unit/channels/test_channel_file_attachments.py`: base receive/send/default/outbound checks, all `_make_inbound` cases, and base channel properties | `test_channel_base.py::{TestReceiveFile,TestSendFileDefault,TestOnOutbound,TestMakeInbound,TestInit,TestProperties}` | Base-channel behavior; attachment file retains upload ordering, failure continuation, false return, and send-failure behavior | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/channels/test_channel_base.py tests/unit/channels/test_channel_file_attachments.py -q` (78 passed; exactly 17 fewer than the 95-test baseline) |
| `backend/tests/contracts/test_visibility_applications_e2e.py`: invalid type, unknown/terminal/stale/self review, unknown/foreign/terminal withdraw, non-admin list, super-admin and regular-user review duplicates | `test_visibility_applications.py` matching router tests | Mock-router error/RBAC boundary; e2e file retains resource-metadata approval, rejection, cross-department rules, withdraw mutation/conflict, and submit-to-approve/withdraw/reject workflows | `PYTHONPATH=. uv run pytest tests/contracts/test_visibility_applications.py tests/contracts/test_visibility_applications_e2e.py -v` (41 passed) |

The isolated real-browser visibility lane remains the primary SQLite-backed UI
proof for approval and rejection. The similarly named backend `*_e2e.py` file
uses mocked sessions; it is not presented as SQLite coverage.

## Batch 2026-07-12: Isolated Real E2E Lane

This is additive coverage; no existing mock, auth, visual, or a11y test was
deleted or moved. The lane uses its own Playwright config and an ephemeral
backend state managed by `backend/scripts/run-real-e2e.sh`.

| New path | Primary responsibility | Persistent-state proof | Validation |
| --- | --- | --- | --- |
| `frontend/tests/e2e/real/role-access-boundaries.spec.ts` | Seeded super-admin, user, viewer, and department-admin access boundaries | Isolated SQLite rows agree with the browser-observed role result. | `cd frontend && E2E_STATE_DIR=/tmp E2E_RUN_ID=collect-only IDEER_INTERNAL_GATEWAY_BASE_URL=http://127.0.0.1:8001 pnpm exec playwright test --config=playwright.real.config.ts --list`; `QA_ISOLATED=1 bash backend/scripts/run-real-e2e.sh` |
| `frontend/tests/e2e/real/memory-persistence.spec.ts` | Create, reload, and delete a user memory fact | The isolated user's memory files agree with the UI. This behavior is deliberately not represented as a SQLite assertion. | `cd frontend && E2E_STATE_DIR=/tmp E2E_RUN_ID=collect-only IDEER_INTERNAL_GATEWAY_BASE_URL=http://127.0.0.1:8001 pnpm exec playwright test --config=playwright.real.config.ts --list`; `QA_ISOLATED=1 bash backend/scripts/run-real-e2e.sh` |
| `frontend/tests/e2e/real/visibility-application-flow.spec.ts` | Owner submission plus independent approval and rejection by a super-admin | UI status, `visibility_applications.status`, and affected resource metadata agree in the isolated SQLite database. | `cd frontend && E2E_STATE_DIR=/tmp E2E_RUN_ID=collect-only IDEER_INTERNAL_GATEWAY_BASE_URL=http://127.0.0.1:8001 pnpm exec playwright test --config=playwright.real.config.ts --list`; `QA_ISOLATED=1 bash backend/scripts/run-real-e2e.sh` |

The separate `Real E2E Tests` workflow runs this lane on pull requests that
change `frontend/**`, `backend/**`, or its own workflow file. It installs the
backend and frontend dependencies plus Chromium, and uploads the isolated-run
logs, report, and traces when the lane fails.

### Phase 2 execution evidence and necessary product repairs

The isolated lane exposed three product-path defects. These repairs are part of
the Phase 2 commit because without them the required browser-to-persistence
contracts cannot be exercised. No public endpoint shape changed.

| Defect | Repair and boundary | Failure and regression evidence |
| --- | --- | --- |
| A successful login wrote the cookie but App Router navigation could race the subsequent SSR request. | `login/page.tsx` uses a full-document navigation after login/register; the admin route is guarded server-side by `workspace/admin/layout.tsx`, with the super-admin-only audit-log subroute guarded separately. Client pages no longer navigate during render. | The real lane previously timed out at login despite successful `/auth/me`; login unit tests cover valid/invalid next paths and `location.assign`, admin-layout unit tests cover allow/deny roles, and the final isolated run passed all seven scenarios. |
| A viewer could not discover a public custom agent owned by another user because `/api/agents` scanned only the requester directory. | `list_agents` discovers metadata-backed accessible agents, loads them from the owner directory, and returns them read-only with the owner's SOUL content. Access remains fail-closed through `check_resource_access`. | The corrected integration test switches the effective user to a distinct viewer and asserts visibility, owner, read-only status, and SOUL. The real viewer scenario failed before this repair and passes in the final lane. GitNexus impact was attempted for `list_agents`; the current index did not contain the symbol, so direct API regression and full real-lane evidence are authoritative. |
| The approval scenario selected reviewed items using CSS/text assumptions instead of the approval page state machine. | It identifies the component card by run-scoped reason, switches to the resulting approved/rejected filter, and asserts the status within that card. | The runner first showed the application correctly moved out of the pending filter; the revised scenario and SQLite terminal-state assertions pass for both approval and rejection. |

Final Phase 2 verification used:

```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache PYTHONPATH=. uv run pytest tests/scripts/test_real_e2e_scripts.py -q
UV_CACHE_DIR=/tmp/uv-cache PYTHONPATH=. uv run pytest tests/integration/api/test_agents_router_behavior.py -q

cd ../frontend
pnpm exec vitest run tests/unit/app/workspace/admin
pnpm exec vitest run 'tests/unit/app/(auth)/login/page.test.tsx'
pnpm exec tsc --noEmit

cd ..
UV_CACHE_DIR=/tmp/uv-cache QA_ISOLATED=1 REAL_E2E_ARTIFACTS_DIR=/tmp/real-e2e-artifacts-phase2-final-2 bash backend/scripts/run-real-e2e.sh
```

The final isolated execution passed 7/7 and cleaned its temporary run state.

## Batch 2026-07-09: Frontend E2E Directory Split

| Old path | New path | Core assertions retained | Stronger replacement | Delete old path | Validation |
| --- | --- | --- | --- | --- | --- |
| `frontend/tests/e2e/landing.spec.ts` | `frontend/tests/e2e/smoke/landing.spec.ts` | Landing route smoke assertions | Default Chromium project now collects only `smoke/` and `workflows/` | Yes | `cd frontend && pnpm exec playwright test --list` |
| `frontend/tests/e2e/brand-and-offline.spec.ts` | `frontend/tests/e2e/smoke/brand-and-offline.spec.ts` | Brand/offline smoke assertions | Isolated from workflow specs | Yes | `cd frontend && pnpm exec playwright test --project=chromium tests/e2e/smoke` |
| `frontend/tests/e2e/sidebar.spec.ts` | `frontend/tests/e2e/smoke/sidebar.spec.ts` | Workspace navigation/sidebar assertions | Isolated as smoke navigation | Yes | `cd frontend && pnpm exec playwright test --project=chromium tests/e2e/smoke` |
| `frontend/tests/e2e/qa/smoke-landing.spec.ts` | `frontend/tests/e2e/smoke/smoke-landing.spec.ts` | QA landing smoke assertions | Removed from `qa/` bucket and default duplicate collection | Yes | `cd frontend && pnpm exec playwright test --list` |
| `frontend/tests/e2e/qa/auth-flow.spec.ts` | `frontend/tests/e2e/auth/auth-flow.spec.ts` | Real-auth login/logout/setup assertions | Runs only through `playwright.auth.config.ts` with auth enabled | Yes | `cd frontend && pnpm exec playwright test --config=playwright.auth.config.ts --list` |
| `frontend/tests/e2e/qa/smoke-login.spec.ts` | `frontend/tests/e2e/auth/smoke-login.spec.ts` | Real-auth login smoke assertions | Runs only through `playwright.auth.config.ts` with auth enabled | Yes | `cd frontend && pnpm exec playwright test --config=playwright.auth.config.ts --list` |
| `frontend/tests/e2e/qa/visual-screenshot.spec.ts` | `frontend/tests/e2e/visual/visual-screenshot.spec.ts` | Visual capture entrypoint | Isolated from default Chromium project | Yes | `cd frontend && pnpm exec playwright test --project=visual --list` |
| `frontend/tests/e2e/*.spec.ts` business specs | `frontend/tests/e2e/workflows/*.spec.ts` | Existing user-path assertions | Default Chromium project explicitly matches workflow specs once | Yes | `cd frontend && pnpm exec playwright test --list` |
| `frontend/tests/e2e/qa/*.spec.ts` business specs | `frontend/tests/e2e/workflows/*-qa.spec.ts` where needed | Existing QA workflow assertions | Removed `qa/` bucket from project collection | Yes | `cd frontend && pnpm exec playwright test --list` |

The intermediate `smoke/smoke-landing.spec.ts` and retained `*-qa.spec.ts`
workflow files were later merged into the primary specs in the
2026-07-10 duplicate QA merge batch below.

## Batch 2026-07-09: Backend Script Tests

| Old path | New path | Core assertions retained | Stronger replacement | Delete old path | Validation |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/test_check_script.py` | `backend/tests/unit/scripts/test_check_script.py` | Script command behavior and subprocess handling | Runs under unit/scripts domain | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/scripts -v` |
| `backend/tests/test_doctor.py` | `backend/tests/unit/scripts/test_doctor.py` | Doctor command and environment checks | Runs under unit/scripts domain | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/scripts -v` |
| `backend/tests/test_intranet_deploy_scripts.py` | `backend/tests/unit/scripts/test_intranet_deploy_scripts.py` | Intranet deploy script assertions with fakes | Runs under unit/scripts domain | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/scripts -v` |
| `backend/tests/test_start_local_script.py` | `backend/tests/unit/scripts/test_start_local_script.py` | Local startup script behavior | Runs under unit/scripts domain | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/scripts -v` |

## Batch 2026-07-09: Backend Root Test Domain Move

All remaining `backend/tests/test_*.py` files were moved without content edits into:

- `backend/tests/unit/{gateway,runtime,memory,sandbox,workflows,skills,channels,models,tools,scripts,persistence}/`
- `backend/tests/integration/{api,persistence,sandbox}/`
- `backend/tests/contracts/`

Core assertions are retained because the test bodies were not changed. The
replacement is stronger at the suite level because `backend/Makefile` now runs
`tests/unit tests/integration tests/contracts` directly and no longer depends on
the root `tests/*.py` transition glob.

Validation:

```bash
cd backend
find tests -maxdepth 1 -type f -name 'test_*.py'
PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit tests/integration tests/contracts -v -m "not serial and not requires_llm"
```

## Batch 2026-07-09: Stable Contract Entrypoints

| Previous migrated path | Final path | Core assertions retained | Stronger replacement | Delete old path | Validation |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/contracts/test_rbac_permission_matrix.py` | `backend/tests/contracts/test_rbac_matrix.py` | Role, resource, and action permission matrix | Stable platform-level RBAC contract path | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/contracts/test_rbac_matrix.py -v` |
| `backend/tests/contracts/test_owner_isolation.py` | `backend/tests/contracts/test_user_isolation.py` | Cross-user read/update/delete isolation for thread/run/event/feedback stores | Stable user-isolation contract path alongside memory, path, setup-agent, and update-agent isolation contracts | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/contracts/test_user_isolation.py tests/contracts/test_memory_*isolation.py tests/contracts/test_paths_user_isolation.py -v` |
| `backend/tests/integration/api/test_runtime_lifecycle_e2e.py` | `backend/tests/integration/api/test_runs_lifecycle.py` | Run creation, SSE stream events, checkpoint writes, run store, thread message state, cancel, rollback recovery | Stable run lifecycle integration entrypoint | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration/api/test_runs_lifecycle.py -v -m "not requires_llm"` |
| `backend/tests/integration/persistence/test_alembic_migrations.py` | `backend/tests/integration/persistence/test_migration_schema.py` | Alembic head schema, ORM table/column checks, downgrade/re-upgrade, merge revision round-trip, stamp-head behavior | Migration workflow now calls this final path | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration/persistence/test_migration_schema.py -v` |
| `backend/tests/unit/skills/test_skills_bundled.py` | `backend/tests/unit/skills/test_public_skill_catalog.py` | Bundled `skills/public/**/SKILL.md` validation | Adds required frontmatter fields, UTF-8/offline readability, and dangerous-instruction scans | Yes | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/skills/test_public_skill_catalog.py -v` |
| Missing | `frontend/tests/e2e/workflows/cross-feature-contracts.spec.ts` | N/A | Shared mock fixture now locks Agent, Workflow, Memory, and Skills API shapes through UI consumption | N/A | `cd frontend && pnpm exec playwright test --project=chromium tests/e2e/workflows/cross-feature-contracts.spec.ts` |

## Batch 2026-07-09: Patch-Name File Cleanup

Files whose names contained `coverage`, `boost`, `gaps`, `full`, or `extra`
were not deleted. They were mechanically renamed in place so the same assertions
remain in their migrated domain bucket:

| Old filename fragment | New filename fragment | Decision | Replacement path rule | Validation |
| --- | --- | --- | --- | --- |
| `coverage_boost` | `behavior` | Rename | Same directory, same test body | `find backend/tests -type f \( -name '*coverage*.py' -o -name '*boost*.py' -o -name '*gaps*.py' -o -name '*full*.py' -o -name '*extra*.py' \)` |
| `coverage` | `edge_cases` | Rename | Same directory, same test body | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit tests/integration tests/contracts -v -m "not serial and not requires_llm"` |
| `boost` | `behavior` | Rename | Same directory, same test body | `cd backend && make test-coverage` |
| `gaps` | `missing_paths` | Rename | Same directory, same test body | `cd backend && make test-coverage` |
| `full` | `comprehensive` | Rename | Same directory, same test body | `cd backend && make test-coverage` |
| `extra` | `additional` | Rename | Same directory, same test body | `cd backend && make test-coverage` |

## Batch 2026-07-10: Residual Patch-Name Cleanup

The first cleanup removed `coverage`, `boost`, `gaps`, `full`, and `extra`
fragments, but a later static gate still found residual `cov3` and `fix`
filenames. These files were renamed without changing assertions:

| Old path | New path | Core assertions retained | Validation |
| --- | --- | --- | --- |
| `backend/tests/integration/api/test_auth_router_cov3.py` | `backend/tests/integration/api/test_auth_router_session_and_setup_edges.py` | Auth password validation, secure session cookie attributes, trusted proxy client IP extraction, and setup-status cache behavior | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration/api/test_auth_router_session_and_setup_edges.py -v` |
| `backend/tests/unit/gateway/test_llm_error_middleware_cov3.py` | `backend/tests/unit/gateway/test_llm_error_middleware_circuit_breaker.py` | Circuit-breaker state transitions, fast-fail responses, retry-event fallback, GraphBubbleUp probe reset, and Retry-After parsing | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/gateway/test_llm_error_middleware_circuit_breaker.py -v` |
| `backend/tests/unit/runtime/test_checkpointer_none_fix.py` | `backend/tests/unit/runtime/test_checkpointer_default_memory_saver.py` | Sync and async default checkpointer contexts return usable `InMemorySaver` instances | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/runtime/test_checkpointer_default_memory_saver.py -v` |
| `backend/tests/unit/runtime/test_worker_cov3.py` | `backend/tests/unit/runtime/test_worker_context_and_rollback.py` | Run worker app config/store propagation, multi-mode stream filtering, and rollback checkpoint id injection | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/runtime/test_worker_context_and_rollback.py -v` |
| `backend/tests/unit/scripts/test_network_cov3.py` | `backend/tests/unit/scripts/test_network_port_allocator.py` | Port availability, reservation, release, context manager cleanup, and concurrent allocation behavior | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/scripts/test_network_port_allocator.py -v` |
| `backend/tests/unit/tools/test_image_search_edge_cases_fix.py` | `backend/tests/unit/tools/test_image_search_import_and_filters.py` | Local `ddgs` import handling, filter forwarding, empty results, import errors, and search exceptions | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/tools/test_image_search_import_and_filters.py -v` |
| `backend/tests/unit/workflows/test_parser_cov3.py` | `backend/tests/unit/workflows/test_parser_nested_condition_branches.py` | Nested condition `then`/`else` parsing and recursive step reference validation | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/workflows/test_parser_nested_condition_branches.py -v` |

The residual static gate may still match
`backend/tests/unit/runtime/test_gateway_run_recovery.py` because `recovery`
contains the substring `cov`. That is a false positive: the file name describes
gateway run recovery behavior and is not a patch-name exception.

## Batch 2026-07-11: `feat/improve-tests` Content Audit

`feat/improve-tests` was not merged directly. Its `auth/`, `routers/`,
`sandbox/`, and similar top-level directories conflict with the final
`unit/`, `integration/`, and `contracts/` hierarchy used by this branch.

| Source | Decision | Evidence | Validation |
| --- | --- | --- | --- |
| Backend test-directory reorganization in `9c9956e2` | Not copied | The source test node names are already represented in the final layered suite; copying its aggregated files would duplicate collection under a second taxonomy. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit tests/integration tests/contracts --collect-only -q` |
| RBAC-only source nodes absent by name | Not copied | They encode superseded department-admin expectations, including denial of department listing. `tests/contracts/test_rbac_matrix.py` is the current contract: department admins can read departments but cannot mutate them. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/contracts/test_rbac_matrix.py -v` |
| Sandbox async-lock exception node | Not copied | It targets the removed executor-based lock acquisition and expects a `RuntimeError`. The current polling implementation is covered by lock-acquisition and cancellation tests in `tests/integration/sandbox/test_aio_sandbox_provider.py`. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration/sandbox/test_aio_sandbox_provider.py -v` |
| `error_codes.py` change and five frontend test deletions | Excluded | They are non-test changes or deletions without an equal-or-stronger replacement proof. | `git diff --check` and targeted test collection |

The source branch itself has collection errors in its aggregated agents,
workflows, and local-sandbox modules. Those files are audit inputs only; they
are not a valid replacement suite for the current branch.

Final verification collected 12,817 current-suite tests and the default backend
run passed with 12,717 passed, 3 skipped, and 97 deselected. The coverage run
reached 98% but had one order-sensitive failure in
`test_stream_run_executes_real_lead_agent_setup_agent_business_path`: its run
completed, then the status poll received `token_invalid` with a malformed
token. The same test passed alone under coverage and with its immediately
preceding module, so this remains a separate full-suite isolation issue rather
than a reason to import the source branch.

## Batch 2026-07-10: Frontend E2E Duplicate QA Merge

The initial E2E directory split preserved some `qa/` filenames as `*-qa.spec.ts`
so no assertions were lost during migration. These duplicate entrypoints were
then merged into the primary smoke/workflow specs:

| Removed path | Replacement path | Core assertions retained | Validation |
| --- | --- | --- | --- |
| `frontend/tests/e2e/smoke/smoke-landing.spec.ts` | `frontend/tests/e2e/smoke/landing.spec.ts` | Landing page load, title/brand signal, visible workspace entrypoint, and CTA navigation | `cd frontend && pnpm exec playwright test --project=chromium tests/e2e/smoke/landing.spec.ts --list` |
| `frontend/tests/e2e/workflows/agent-management-qa.spec.ts` | `frontend/tests/e2e/workflows/agent-management.spec.ts` | Agent listing, create-page navigation, valid-name setup progression, detail-page rendering, and delete dialog behavior | `cd frontend && pnpm exec playwright test --project=chromium tests/e2e/workflows/agent-management.spec.ts --list` |
| `frontend/tests/e2e/workflows/workflow-management-qa.spec.ts` | `frontend/tests/e2e/workflows/workflow-management.spec.ts` | Workflow listing, create-page navigation, YAML editor input behavior, detail navigation, run dialog, edit page, and delete dialog behavior | `cd frontend && pnpm exec playwright test --project=chromium tests/e2e/workflows/workflow-management.spec.ts --list` |

## Batch 2026-07-11: `offline_feature` Product-Test Intake

| Removed assertion/API | Replacement coverage | Core contract retained | Validation |
| --- | --- | --- | --- |
| `ResourceMetadataStore.soft_delete` timestamp behavior | `test_resource_metadata_store.py` hard-delete execution and failure handling | Metadata is removed atomically and a database failure is reported without restoring tombstones | `cd backend && uv run pytest tests/unit/gateway/test_resource_metadata_store.py tests/integration/api/test_workflow_router.py tests/integration/api/test_workflows_router.py tests/integration/api/test_workflows_router_e2e.py -q` |
| Workflow router mocks of `soft_delete` | Workflow delete tests mock `ResourceMetadataStore.delete` and retain non-fatal metadata-cleanup assertions | A workflow deletion remains successful when metadata cleanup fails, while pending applications are still handled | Same command as above |

The product merge imported five root-level backend tests. They were moved
directly into the existing layered layout; no root collection entrypoint was
restored.

| Source path | Final path | Core assertions retained | Validation |
| --- | --- | --- | --- |
| `backend/tests/test_agents_same_name.py` | `backend/tests/integration/api/test_agents_same_name.py` | Per-owner metadata reads, upserts, favourites, and deletion remain isolated when agent names match. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration/api/test_agents_same_name.py -q` |
| `backend/tests/test_audit_logs.py` | `backend/tests/integration/api/test_audit_logs.py` | Department-admin audit-log list and detail access. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration/api/test_audit_logs.py -q` |
| `backend/tests/test_user_deletion.py` | `backend/tests/integration/api/test_user_deletion.py` | Database commit precedes filesystem cleanup; cleanup failure remains auditable and retryable. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/integration/api/test_user_deletion.py -q` |
| `backend/tests/test_reconcile_user_state.py` | `backend/tests/unit/scripts/test_reconcile_user_state.py` | Read-only inventory and guarded deletion for stale runtime-user state. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/scripts/test_reconcile_user_state.py -q` |
| `backend/tests/test_runtime_user_context.py` | `backend/tests/unit/runtime/test_runtime_user_context.py` | Pytest uses a temporary `IDEER_HOME`, distinct from production runtime state. | `cd backend && PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 uv run pytest tests/unit/runtime/test_runtime_user_context.py -q` |
