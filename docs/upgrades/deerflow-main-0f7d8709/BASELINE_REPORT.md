# Convergence baseline report

Date: 2026-09-05  
Branch: `integration/deerflow-main-0f7d8709`  
Locked DeerFlow SHA: `0f7d8709d3bbf0be26460b6277fbad9329302243`

## Results

| Check | Result | Classification / note |
|---|---|---|
| `bash scripts/run-test-lane.sh backend-standard` (without cache override) | blocked | Environment: uv attempted `/home/neowyh/.cache/uv`, which is read-only in this sandbox. |
| Backend collection before lane fix | 35 collection errors; 11,708 collected / 11,816 | Test-path issue: helper modules were imported as top-level names but `tests/` was absent from `PYTHONPATH`. |
| Focused collection after lane fix | passed | `tests/unit/runtime/test_cancel_run_idempotent.py`: 7 tests collected with `PYTHONPATH=.:tests`. |
| Full standard collection after helper fix | passed | 12,373 collected / 12,481 (108 deselected); no collection errors. `tests/conftest.py` now provides the shared `_make_rbac_user` helper required by the RBAC contract module. |
| Discord message-routing tests in `pr-standard` | failed | Focused reproduction shows the lane failures are test-path compatibility: the production path now commits through `_publish_reserved`/`InboundReservation`, while the legacy fixture only mocks `_publish` and uses a non-executing `MagicMock` main loop. The complete Discord file currently reports 97 passed / 13 failed for the same stale fixture/API family. No production failure is claimed; the tests need a reservation-aware fixture and updated legacy thread assertions before the lane can be green. |
| `UV_CACHE_DIR=/tmp/deer-flow-uv-cache bash scripts/run-test-lane.sh backend-standard` | incomplete | Latest 12-worker rerun reached 7% and exposed two additional stale channel assertions (Slack reservation scheduling and Telegram's expanded handler set), both fixed and focused-verified. The rerun still produced no final pytest summary within the observation window, so no lane pass is claimed; the remaining blocker is the restricted async/thread runtime. |
| Channel startup/reservation follow-up | passed | Slack reservation fallback, empty-channel handling and startup scheduling, plus Telegram's current handler set: 3 focused Slack tests and the Telegram startup regression pass. Full channel files remain subject to the lane's async executor teardown limitation. |
| MCP task configuration round-trip | passed/partial | Added `task_toolsets` to the Gateway MCP response model so DeerFlow durable submit/status/cancel bindings are not dropped. Toolset validation and runtime configuration: 17 passed; the four TestClient MCP config E2E cases collect but cannot complete under the restricted socket/runtime environment. |
| MCP caller-credential API boundary | passed | Added Gateway response validation, masking, masked round-trip merge, and case-insensitive static-header validation for `user_auth`; shared caller credential/header tests: 67 passed. |
| MCP request-scoped credential boundary | passed | Added `headers_from_context` response validation, safe declared-field round-trip, masked extras and partial/complete replacement semantics; combined request-scoped header, user-scoped auth, static-header and task-toolset tests: 123 passed. |
| MCP Gateway management surface | partial | Restored the complete upstream Settings/API router surface (server CRUD, state toggles, command validation, cache reset, concurrent-safe writes and all credential blocks) from locked DeerFlow lineage. MCP credential/task focused tests are green; the large config-secrets E2E group remains environment-incomplete when TestClient enters blocking filesystem paths. |
| Frontend MCP schema alignment | partial | Frontend MCP API/types now carry `user_auth`, `headers_from_context`, `task_toolsets`, routing and timeout fields emitted by the Gateway. Frontend dependency/typecheck gates remain blocked because the checked-out dependency tree lacks Next/Rstest/Vitest packages. |
| MCP config-secrets regression coverage | partial | The restored Gateway surface collects all 195 config-secrets tests. Focused credential/context/task groups are green; the full TestClient suite remains incomplete when restricted filesystem/thread execution stalls. |
| `timeout 180s env UV_CACHE_DIR=/tmp/deer-flow-uv-cache make -C backend test` | incomplete | The standard Make target entered pytest collection but emitted no collection summary within the observation window; no pass is claimed. |
| `timeout 120s env UV_CACHE_DIR=/tmp/deer-flow-uv-cache bash scripts/run-test-lane.sh pr-standard` | incomplete | Backend standard reached 10% and stalled at the async local-file test before frontend execution; no pytest summary was emitted. The focused channel seam failures were separately fixed and verified. |
| GitNexus refresh | passed with bounded-flow warnings | Incremental refresh completed in 158.5s at current commit `b24ce5b`: 91,329 nodes, 180,760 edges, 2,781 clusters and 1,013 flows. Analyzer reports bounded candidate/trace truncation for some high-branching flows; an empty impact result is not treated as proof of no callers. |
| `python scripts/smoke_srs_flow.py` | passed | Offline SRS outputs generated and validator returned `ALL CHECKS PASSED`. |
| `bash scripts/check-intranet.sh` | failed | Docker Compose/images and generated `env.intranet` are unavailable in this environment; config file itself is present. |
| `python scripts/run_fault_zeroing_acceptance.py` | fixed invocation path; acceptance incomplete | The script now adds `backend/` to `sys.path` when run from the repository root. It then requires the documented `--user-id`; a one-case run with a synthetic user exceeded the 30-second observation window without producing a verdict. |
| Fault-zeroing workflow focused tests | passed | Runtime/kernel coverage: 7 passed. A real one-case acceptance with the seeded user reached the 60-second observation timeout without output, so the product acceptance remains incomplete. |
| `tests/test_slash_skills.py` | focused behavior passes; full file incomplete in this environment | The synchronous activation and isolated async test pass. Running the async test after another `asyncio.run` test hangs during Python's `asyncio.to_thread` executor shutdown; this reproduces with a minimal Python 3.12 script and is classified as a test/runtime-environment issue, not a product regression. |
| `tests/test_migration_user_isolation.py` | fixed and passed | Restored the missing `migrate_skills` entry point and moved the one-time migration script to `deerflow.config.paths`; dry-run, conflict quarantine, history-directory and parent-directory preservation semantics: 19 passed. |
| `tests/integration/persistence/test_migration_schema.py` | partial pass; one environment-incomplete test | After switching Alembic's SQLite path to a synchronous engine, 48 migration/environment checks passed when excluding `test_stamp_alembic_head_interaction`. That async test still hangs at `aiosqlite.connect()` in this sandbox; the remaining result is incomplete, not a release pass. |
| `cd frontend && pnpm test` / `bash scripts/run-test-lane.sh frontend-standard` | blocked | The local pnpm client immediately fails with `unable to open database file`; the checked-out `frontend/node_modules` also lacks `next`, `@rstest/core` and `vitest`, so no frontend tests start. |
| `cd frontend && pnpm check` | blocked | Direct ESLint fails because `next/dist/compiled/babel/eslint-parser` is absent; direct `tsc --noEmit` reports the same incomplete dependency tree. Offline frozen install produced no output and exceeded the 60-second observation window. |
| `bash scripts/package-intranet-offline.sh --no-sandbox ...` | blocked | The packaging preflight requires Docker Compose v2, unavailable in this environment. `--help` and argument parsing pass. |
| `backend/tests/unit/scripts/test_intranet_deploy_scripts.py` | passed | After moving `--skills-manifest` existence checks ahead of Docker/image work, the complete suite passes: 36 passed in 235.91s. Individual package-build cases are slow (56–76s) but terminate successfully. |
| `backend/scripts/e2e_safety_termination_demo.py` | passed | Migrated the standalone safety-termination acceptance driver from `ideer.*` to `deerflow.*`; real DeerFlow client stream completed with `=== PASS ===`. |
| `tests/integration/api/test_suggestions_router_e2e.py` | passed | Switched the suggestions router's model factory import to `deerflow.models`; focused router regression: 3 passed. |
| `tests/unit/runtime/test_serialization.py` + `tests/integration/api/test_runs_stateless_router.py` | passed | Switched stateless runs serialization to `deerflow.runtime`; focused serialization/router regressions: 27 passed. |
| `tests/integration/api/test_thread_runs_router.py` + edge/cancel regressions | passed | Switched thread-run serialization to `deerflow.runtime` while retaining the legacy `RunRecord` compatibility types; focused regressions: 44 passed. |
| `tests/integration/api/test_mcp_config_router_e2e.py` + MCP secret config tests | passed | Switched MCP config read/reload accessors to `deerflow.config.extensions_config`; retained the enterprise path resolver and user model boundary; focused regressions: 23 passed. |
| `tests/integration/api/test_threads_router_comprehensive.py` + thread edge/cancel regressions | passed | Switched thread serialization to `deerflow.runtime`; focused regressions: 150 passed. |
| `tests/unit/agentplatform/test_memory_adapter.py` + memory router regressions | passed | Added the AgentPlatform control-plane adapter backed by DeerFlow `MemoryManager`, preserving caller/user and agent scope; 28 passed. |
| Memory config response and client compatibility regressions | passed | `/api/memory/config` now exposes DeerFlow `mode`, `manager_class`, `backend_config` and shutdown budget while projecting legacy fields; 172 existing tests plus 1 focused schema test passed. |
| Memory isolation/migration acceptance groups | passed | User/agent isolation and migration contracts: 26 passed; storage/restart edge cases: 38 passed; queue isolation: 32 passed; legacy Markdown migration CLI: 5 passed. |
| Upload router and middleware regressions | passed | Generic upload path management and document conversion now use DeerFlow; enterprise Code Evidence remains separate; 118 focused tests passed after updating the stale exception fixture. |
| Tool router and assembly adapter regressions | passed | Gateway tool listing/detail/test execution now assemble through the DeerFlow adapter while AgentPlatform retains visibility/RBAC filtering; adapter + router regressions: 21 passed. |
| MCP config router regressions | passed | MCP file config parsing and model boundary now use DeerFlow `ExtensionsConfig`; secret-preservation and config API regressions: 23 passed. |
| Suggestions router config-boundary regression | passed | Replaced the route-only `AppConfig` annotation with DeerFlow's type; focused E2E: 3 passed. |
| Models/uploads config-boundary regressions | passed | Replaced route-only `AppConfig` annotations with DeerFlow's type; combined model and upload route regressions: 193 passed. |
| Thread metadata utility regressions | partial | Switched metadata validation, invalid-filter exception boundaries, and the gateway thread router's ISO time helpers to DeerFlow. The legacy fixture now tolerates removed checkpoint-builder seams; the four reserved-metadata tests pass. The timestamp creation case still stalls in the sandbox's async/thread runtime, so the 95-test module is not a product pass. |
| Resource/authorization/receipt/skill acceptance group | partial | 128 synchronous tests passed across skill projection, tool authorization, receipt verification and worker snapshot binding. The async archive-install projection test cannot run to completion in the restricted sandbox: with the async plugin it exceeds 30 seconds; without plugin loading it is unsupported. No product pass is claimed for that async case. |
| Shared-agent and workflow receipt focused regressions | passed | AgentPlatform extension/shared-agent authorization boundary: 26 passed; sub-agent caller snapshot, receipt verification and report-contract selection: 37 passed. |
| MCP/Sandbox/runtime lifecycle regressions | partial | MCP task runtime configuration: 9 passed; sandbox network policy: 12 passed; sandbox authorization has 13 synchronous policy tests passing, while two TestClient upload/artifact cases remain incomplete after the old route-config seam was removed. Gateway lifespan now runs 3 current shutdown/startup tests with 9 explicitly skipped legacy memory/retrieval tests whose ownership moved to DeerFlow runtime; no collection failures remain. |

The standard lane now exports `PYTHONPATH=.:tests`, preserving the existing
collection roots while resolving shared test helpers. Re-run with
`UV_CACHE_DIR=/tmp/deer-flow-uv-cache` for the authoritative lane result.

## Scope notes

This report deliberately does not claim a product baseline pass. Full
`core-full`, intranet, business acceptance, offline packaging, database
migration and air-gapped installation are still pending and are release gates.

## Runtime Foundation focused evidence

The branch still has 46 textual `ideer` imports under `backend/app`,
`backend/scripts` and the AgentPlatform-facing harness adapters, concentrated
in the transitional Workflow V2 and Resource runtime seams. Gateway callers
now use the AgentPlatform ResourceService, Resource runtime, and Workflow V2
runtime seams, leaving 4 direct production `ideer` import files under
`backend/app`. This is an inventory signal only;
the final `import ideer` failure gate is intentionally not claimed until the
Workflow/resource control-plane extraction is complete.

The following focused slices are green on this branch:

- pluggable memory configuration and manager compatibility: 18 tests;
- extension API and run-evidence envelope contracts: 43 tests;
- task lifecycle evidence persistence: 50 tests;
- authorization assembly/runtime/provider enforcement, including shared-agent
  caller identity: 44 tests;
- sandbox mount contract and `/mnt/skills` defaults: 3 tests;
- AgentPlatform extension boundary and lifecycle binding (snapshot identity,
  caller-scoped memory, default-deny network, explicit install registration):
  7 tests, including shared-agent owner-state exclusion;
- sandbox network policy and intranet proxy workflow: 14 tests;
- sandbox authorization coverage: 13 synchronous policy tests pass; the two
  legacy upload/artifact cases now tolerate the removed route-config seam but
  remain incomplete because their TestClient path stalls in this sandbox;
- intranet runtime config path and default-deny contract: 1 test;
- sub-agent tool receipts, report contract, acceptance checks and delegation
  ledger: 270 passed, 1 skipped;
- SRS smoke flow: `ALL CHECKS PASSED`.
- Resource version snapshot regression: 14 passed (`tests/unit/resources/test_resource_service_versions.py`), including freezing the selected version for an already-started Run.
- Workflow run-record integration: 7 passed (`tests/integration/workflows/test_v2_run_record.py`), covering JSONL event mirroring, terminal Markdown rendering and exhausted-run records.
- Workflow artifact/schema/precondition integration: 15 passed across
  `test_v2_artifact_gates.py`, `test_v2_write_schemas.py` and
  `test_v2_preconditions.py`.
- Skill projection and mount isolation: 115 passed across projection,
  three-way mount, local sandbox mount, container-path and requested-skill
  resolver tests.
- Memory migration, manager configuration, user/agent isolation and restart
  persistence: 75 passed, 1 skipped across the focused memory contract suite.
- Channel runtime boundary: inbound upload management, application-config
  lookup and dynamic channel resolution now import DeerFlow directly. The
  focused channel regressions were updated to patch those canonical seams and
  are green: 44 upload-attachment tests, 67 channel-service tests and 78
  manager/store edge-case tests. The repository-wide PR lane remains
  incomplete because it stalls before producing a pytest summary.
- Run-preparation memory preload now goes through the AgentPlatform memory
  adapter and DeerFlow application config; the focused preload/service group
  is green (41 passed).
- Upload gateway sandbox provider now resolves through DeerFlow while
  enterprise Code Evidence and AgentPlatform path/identity policy remain at
  the gateway boundary; upload-router focused regressions: 80 passed.
- Tool authorization assembly/runtime deny coverage: 28 passed across
  `test_authorization_enforcement.py` and `test_authorization_tool_filter.py`;
  an unrelated `test_client.py` collection drift remains separately recorded.
- Run/Checkpoint gateway boundary: `thread_runs` now consumes DeerFlow
  `RunRecord`/`RunStatus`; direct stateless and thread-runs router regressions:
  32 passed.
- Resource Gateway upload helpers now consume DeerFlow's shared safe filename
  and no-symlink file primitives; Resource API focused regressions: 18 passed.
- Canonical Resource router workflow limits, model allowlist and runtime
  configuration now resolve through DeerFlow `get_app_config`; enterprise paths
  and catalog ORM remain in the AgentPlatform boundary. The focused resource
  API run reached 13 passed before the existing DB-backed response test stalled
  under this restricted test environment, so the full file remains incomplete.
- Admin resource inventory now also consumes DeerFlow configuration while
  retaining AgentPlatform RBAC/catalog persistence; module import and lint
  verification pass. Full admin TestClient coverage remains environment-
  incomplete under the same restricted socket/test-runtime conditions.
- Gateway run services now consume DeerFlow RunManager/RunRecord/RunStatus,
  StreamBridge and run naming; services behavior regressions: 77 passed.
- Gateway agent-factory resolution now returns DeerFlow's `make_lead_agent`;
  the same 77 service regressions cover the factory identity contract.
- Gateway startup configuration now binds to DeerFlow's `AppConfig` and
  `get_app_config`; enterprise persistence imports remain local to the Gateway
  control-plane functions. Extension/startup focused regressions remain green
  (18 passed, one TestClient route case separately incomplete under restricted
  sockets).
- Gateway Extension host wiring is now active: configured plugins load once at
  `create_app()`, publish the process/app registry and live diagnostics, mount
  contributed routers after host routes, and receive a caller-only principal
  projection (PAT admin capability is suppressed). The focused app-loading
  slice is green (8 passed); the principal contract slice is green (13 passed).
  The TestClient route case is environment-incomplete under the restricted
  socket policy.
- Run Evidence now has a dynamic per-run binding: `prepare_run` projects the
  frozen resource UUID/version/hash closure and caller-scoped authorization into
  an immutable ContextVar inherited by the background worker and sub-agents,
  including a deterministic runtime-assembly SHA-256 fingerprint;
  the AgentPlatform extension consumes it without static owner state. Extension
  boundary, run-start propagation and real DeerFlow lifecycle regressions are
  green (8, 1 and 13 passed).
- Workflow worker configuration now resolves through DeerFlow's runtime
  `get_app_config`; enterprise Workflow v2 persistence, resource loaders and
  adapters remain imported from the AgentPlatform control-plane boundary. The
  focused contract test passed (1 passed); full workflow DB integration remains
  incomplete under the restricted test environment.
- Trusted Gateway authorization projection now strips client-supplied
  `is_internal`, `authz_attributes`, `channel_user_id`, LangGraph auth identity,
  and sandbox lease fields from both runtime config sections; it derives
  `is_internal` from the authenticated source, admits `channel_user_id` only
  for internal callers, and projects server-owned role/OAuth fields for normal
  users. Focused gateway authz regressions: 26 passed; internal channel caller
  boundary: 3 passed. The broader Gateway config suite still has pre-existing
  compatibility failures outside this slice and remains open.
- Internal Gateway callers now consume DeerFlow's canonical `DEFAULT_USER_ID`
  and accept the upstream `DEER_FLOW_INTERNAL_AUTH_TOKEN` environment variable
  while retaining the legacy token name for compatibility. The focused internal
  auth regression suite passed (4 passed).
- Gateway channel storage, artifact resolution, upload routing, and auth
  middleware now use DeerFlow's canonical path and user-context runtime modules.
  ChannelStore/path focused coverage passed (10 selected channel tests plus 27
  user-context tests); the broader channel suite still has pre-existing API
  signature mismatches and restricted-environment hangs.
- Memory, credential-file, Admin, and Threads routers now use DeerFlow's
  canonical user/path runtime where the enterprise persistence models remain
  AgentPlatform-owned. Memory adapter coverage passed (4 tests) and credential
  file coverage passed (9 tests); legacy router suites still contain stale
  patch seams for the removed memory/checkpoint helpers.
- Workflow worker execution now obtains its async checkpointer and canonical
  resource storage paths from DeerFlow while retaining AgentPlatform Workflow
  v2 persistence, compiler, and adapters. The runtime-config contract passed
  (1 test); canonical worker DB loading remains incomplete under the restricted
  environment.
- Run Evidence now exposes a caller-safe projection from the immutable binding
  and persists that same projection under Run metadata during preparation;
  resource UUID/version/hash, authorization context, policy revision and the
  runtime assembly fingerprint remain on one envelope boundary, with no
  credentials serialized. Extension boundary and background-run evidence
  regressions passed (9 and 1 targeted tests).
- Canonical Run Skill views now replace the generic managed projection at the
  single `/mnt/skills` mount, including Local and AIO sandbox paths and the
  lead-agent prompt. The previous parallel `/mnt/run-skills` namespace is gone;
  canonical sandbox, prompt, and exact AIO mount regressions passed (20 unit
  tests plus 1 exact mount test).
- Gateway startup resource seeding, canonical storage reconciliation, and
  anomaly auditing now resolve filesystem paths through DeerFlow's path
  runtime. The compose/launcher delivery contract now uses `uv --no-sync`,
  exposes a gateway healthcheck, waits for readiness, and emits failure
  diagnostics; all five deployment assertions and the nine startup/extension
  tests pass.
- Gateway run-config hardening now enforces a server-owned recursion ceiling,
  rejects client checkpoint-channel mode overrides, preserves the canonical
  thread ID in both runtime containers, dual-writes custom Agent identity for
  LangGraph context compatibility, and copies metadata before merging. Focused
  run-config regressions: 3 recursion-limit tests, 2 checkpoint-mode tests and
  10 identity/metadata tests passed. Scheduler dispatch and full Gateway
  configuration compatibility remain open.
- Requested checkpoints now pass through one Gateway validation seam before Run
  admission: thread identity, namespace/map and checkpoint existence are checked,
  then server-owned checkpoint fields are attached to the runtime config. The
  focused validation/404 contract tests passed (2 passed). Scheduler helper
  dispatch still awaits its idempotent `start_run` contract migration.
- Scheduler dispatch now reuses the Gateway admission path with a live
  `scheduler.recursion_limit` clamp, internal `non_interactive` context, owner
  identity propagation, and `scheduled-task:<run_id>` idempotency keys. The
  focused scheduler launcher contract passed (5 passed). Full scheduler
  persistence/recovery and multi-instance acceptance remain open.
- Run Evidence API projections now redact legacy `auth_token` metadata and
  request-scoped config secrets without mutating persisted run records. The
  run metadata secret-safety suite passed (15 tests), and the combined evidence,
  extension-boundary and secret-safety regression slice passed (26 passed,
  3 deselected).
- Resource Snapshot acceptance already contains the required version-freeze
  assertion: publishing a new dependency version after run start leaves the
  persisted run snapshot on the original UUID/version/hash. The focused
  `test_resource_service_versions.py` lane was started but produced no output
  for over 60 seconds in this restricted environment and was interrupted; it
  remains incomplete rather than being reported as passed.
- Tool authorization now has evidence for both assembly-time filtering and
  runtime guardrail denial. The shared-agent caller-principal boundary plus
  tool-filter suite passed (22 tests), and the enforcement/provider/principal
  runtime slice passed (77 tests).
- Skill Projection synchronous coverage passed (43 tests), including
  enabled-only projection and the single `/mnt/skills` namespace. The async
  archive-install projection test could not complete in the restricted
  environment (the explicit AnyIO invocation produced no result and was
  interrupted); the default pytest path is also blocked by the sandbox's
  socket-using rerun plugin.
- Memory migration coverage outside the stale router patch seam passed 42
  tests with one skipped test, covering the DeerFlow `MemoryManager` contract,
  user isolation, Markdown/legacy JSON migration, retrieval adapter and
  restart persistence. The legacy `test_memory_router.py` module still has 29
  collection-time failures because it patches the removed `get_memory_manager`
  seam; those are classified as test-path compatibility debt, not counted as
  runtime regressions.
- Sub-Agent receipt acceptance passed: the report contract and tool-receipt
  middleware slice passed 36 tests, and the task-tool receipt verdict slice
  passed 3 tests (including missing-receipt `UNVERIFIED` behavior). The full
  task-tool module remains outside this focused result because it enters the
  restricted async executor path.
- Workflow canonical-run acceptance remains incomplete in this environment:
  the focused canonical registry/run/worker/runtime-config group produced no
  output for over 30 seconds and was interrupted. It must be rerun with an
  initialized test database and unrestricted async SQLite executor before the
  Workflow row can close.
- Business-package checks: the offline SRS smoke flow completed with
  `ALL CHECKS PASSED` and generated both DOCX artifacts plus the traceability
  catalog. Fault-zeroing acceptance was started for one case but entered the
  restricted async worker path without output and was interrupted.
- Intranet/offline delivery checks remain blocked by environment prerequisites:
  `scripts/check-intranet.sh` reports missing Docker Compose v2, images and
  `env.intranet`; `scripts/package-intranet-offline.sh` exits immediately with
  `docker compose v2 is required`.
- Canonical Agent preparation now routes the legacy factory through the
  AgentPlatform control-plane adapter `app.agentplatform.runtime_adapter`; the
  Gateway no longer imports the `ideer` lead-agent factory directly. The
  adapter delegation regression passed (1 test) and Ruff checks passed. The
  adapter is intentionally a bridge, not final DeerFlow parity; the canonical
  preparation database lane remains incomplete.
- Migration inventory remains split across two independent Alembic trees:
  AgentPlatform `20260828_run_snapshot_selection_role` and DeerFlow
  `0018_oauth_identity_pg_partial` each report a head. No merge revision or
  PostgreSQL/fresh-install validation has been performed yet, so the migration
  gate remains open.
- Memory Router now maps optional-backend capability gaps to stable HTTP 501,
  hides corruption details behind HTTP 500, and preserves conflict semantics
  at the AgentPlatform adapter seam. The async edge-case regression file passed
  (13 tests).
- The pre-migration `backend/tests/test_memory_router.py` module is now
  explicitly marked legacy and skipped (29 tests); its patch seam targeted the
  removed `get_memory_manager` symbol. Current Memory API coverage remains in
  `tests/integration/api/test_memory_router.py` and the adapter/edge-case
  suites, so no compatibility shim was added to production code.

These results establish the next-stage baseline but do not close the semantic
ledger rows. Shared-resource, workflow receipt, migration, offline and fresh
intranet-install acceptance remain required.

The selected V2 workflow integration group was started with the same cache
override but produced no test output within 60 seconds and was interrupted.
It is therefore recorded as incomplete (not passed); database-backed workflow
validation needs a dedicated follow-up with an initialized test database.

The isolated `tests/unit/workflows/test_v2_runtime_config.py` contract passed
(1 test) when pytest plugin autoload was disabled; the default rerun plugin
cannot bind its status socket in this sandbox. The canonical registry test was
rerun separately with the explicit async plugin, produced no output within 30
seconds, and was interrupted, so it remains environment-incomplete rather than
being reported as green.

Workflow runtime configuration now has a DeerFlow-owned schema at
`deerflow.config.workflow_runtime_config`; the former `ideer` module is a
compatibility import and DeerFlow `AppConfig` exposes `workflow_runtime`.
The migration/identity regression passed (3 tests) with Ruff check and format
validation. No runtime behavior changed; existing AgentPlatform config callers
continue to resolve the same model class during the dual-runtime period.

GitNexus verification for this uncommitted slice is not available: the local
index was removed during the prior refresh recovery attempt, and both
`gitnexus impact WorkflowRuntimeConfig --direction upstream` and
`gitnexus detect-changes --scope all` report no indexed repository. This is an
explicit graph-verification gate; no convergence commit is being created until
the index can be rebuilt and the checks return complete (non-truncated) output.
A bounded `gitnexus analyze --index-only --force` retry on this slice timed out
after 60 seconds without registering an index; `status` and `detect-changes`
still report no indexed repository.

Workflow Run Evidence now persists the frozen UUID/version/hash closure and
caller-scoped authorization projection and a deterministic runtime assembly
fingerprint under `WorkflowV2RunRow.snapshot.run_evidence` when a canonical Run
is created. Mutable recovery snapshots preserve that
immutable envelope across worker checkpoint updates. The pure projection and
merge contract passed (2 tests), and the existing WorkflowV2Store unit suite
passed (22 tests). The database-backed canonical-run acceptance remains
environment-incomplete as recorded above.

The Workflow worker now binds the persisted envelope to the runtime context
while compiling and invoking the graph, so tool/sub-agent observers receive the
same caller-scoped evidence rather than a second parallel identity model. The
worker binding regression is included in the 3-test evidence slice; Ruff and
format checks passed.

The Extension evidence boundary now has a runtime receipt collector. DeerFlow's
runtime-owned ToolReceiptMiddleware contributes stamped tool receipts when the
AgentPlatform extension is active; lifecycle stop publishes collected tool and
sub-agent verification records into the same `RunEvidenceEnvelope`. Missing
sub-agent receipts are explicitly recorded as `UNVERIFIED`, while a cited,
validated receipt verdict is `VERIFIED`. Extension boundary tests passed (13),
the receipt projection slice passed (2), and the DeerFlow tool receipt suites
passed (30).
The task-tool receipt behavior regression slice also passed (3 tests), covering
verified, missing-receipt, and failed-sub-agent result paths.

Config Phase 6 now has an operator migration path for legacy Memory structure:
`scripts/config-upgrade.sh` honors `DEER_FLOW_CONFIG_PATH`, runs the structural
Memory migration even when `config_version` is already current, moves legacy
DeerMem fields under `memory.backend_config`, and drops file-style
`storage_path: memory.json` in favor of the per-user directory default. The
same upgrade path now migrates current-schema legacy `ideer.*` selections to
their DeerFlow equivalents wherever the upstream module exists, while leaving
product-only compatibility extensions explicit. A local schema-10 profile was
upgraded to schema 27 and verified to load through DeerFlow configuration.
The example and intranet profiles are aligned at config version 27 and include the
checkpoint mode, fail-closed skill evolution, and verification fields. The
config-version suite passed (12 tests).

Frontend Agent resource-boundary convergence is now implemented: Agent list,
published detail, draft/publish, archive, favorite, name availability,
import, and export calls use UUID-backed `/api/resources` endpoints. The
legacy `/api/agents` route is no longer used as the enterprise Agent
canonical source. Canonical Agent contract tests cover these calls. The
local pnpm runner cannot open its database and the installed Vitest package
is absent, so focused frontend tests are environment-incomplete; TypeScript
reported no errors in changed Agent source files.

Migration convergence now isolates DeerFlow's Alembic bookkeeping in
`deerflow_alembic_version`. The bootstrap adopts only numeric legacy DeerFlow
revisions from the former shared table and ignores AgentPlatform date-based
heads. The three isolation/adoption tests passed. The broader persistence
bootstrap suite was incomplete in this sandbox because it produced no output
within the guarded run window and was interrupted.

Authorization boundary evidence was audited: assembly-time tool filtering and
runtime forced-call denial passed in the focused authorization suites (15 and
17 tests), while shared-Agent caller identity, caller-only credential
projection, and caller-scoped memory invariants are covered by the extension
boundary tests. The sandbox upload-router subset has a test import-path issue
when invoked directly (`_router_auth_helpers`), so the end-to-end shared
resource acceptance remains open and must run through the standard lane.

Skill Projection acceptance was rerun after the authorization audit: the
canonical Run skill-view and three-way sandbox mount suites passed (26 tests).
They verify frozen version/hash copies, read-only category mounts, one
`/mnt/skills` namespace, and no competing root mount for canonical Runs.

Workflow/Run focused contracts also passed: Run Evidence, WorkflowV2Store and
runtime-config suites completed with 28 tests, and the canonical Agent adapter
suite completed with 17 tests. The database-backed `test_v2_run_record.py`
integration suite collected seven tests but its first test produced no output
within the 30-second guard and was interrupted; it remains incomplete.

The Workflow timeout was minimized independently of pytest: a plain
`sqlite+aiosqlite` engine hangs on its first `begin()` in this sandbox even
without ORM metadata, whereas synchronous SQLite creates the same database in
about 0.4 seconds. This is an environment blocker in the aiosqlite connection
thread, not evidence of a Workflow schema or event-sink regression.

GitNexus refresh was retried in this turn: the documented local
`.gitnexus/run.cjs` is absent, the CLI `analyze --index-only --force` ran for
90 seconds without output and was interrupted, and the repository remains
unindexed. Graph impact/detect-changes therefore remain an explicit gate.

The direct `ideer` import inventory was corrected to include function-local
imports: 26 `backend/app` files remain, all in the enterprise control-plane,
persistence, and compatibility seams. The `scripts/check-runtime-boundary.sh`
guard passes at baseline 26 and fails if future changes increase that count. It is now a preflight for both
`pr-standard` and `core-full`, so the standard acceptance lanes cannot start
with a widened runtime boundary.

`pr-standard` was rerun with `UV_CACHE_DIR=/tmp/deer-flow-uv-cache`. The lane
started successfully and reached 8% with the changed foundation tests passing;
it exposed a stale Telegram shutdown assertion (the production stop contract
now schedules bridge cancellation and loop stop, while the test expected one
callback). The focused test was updated to assert the two-call contract and
passes; the full lane was interrupted after the first unrelated long-running
channel batch and is therefore incomplete.

The next Runtime Foundation slice moved the canonical resource router's path
resolver from `ideer.config` to `deerflow.config.paths`, matching the adopted
DeerFlow runtime path semantics. The focused source-boundary regression passed
(1 test), and Ruff check/format validation passed. Persistence and resource
model imports in that router remain enterprise-owned and are intentionally
separate follow-up slices.

The authentication configuration slice now resolves the persisted JWT secret
path through `deerflow.config.paths` instead of the legacy `ideer` config
module. The six-case AuthConfig focused suite passed after updating its path
patches; Ruff check/format validation passed. The boundary inventory decreased
from 26 to 25 files while the guard baseline remains 26, preventing rollback
or new import growth.

Code Evidence product entrypoints now use the AgentPlatform-owned
`app.agentplatform.code_evidence` implementation. Upload, resource, and Run
preparation paths no longer import the old Harness package; the package
validation and runtime path-projection focused suite passed (13 tests), and Ruff validation passed. The
runtime's built-in static analysis tool now consumes the runtime-neutral
`deerflow.uploads.code_evidence.package_root` projection, and the old Harness
package implementation has been removed. The deterministic scanner,
normalization, confidence, and report writers now live in
`deerflow.uploads.code_analysis`; its focused suite passed (5 tests), with no
`ideer.uploads.code_*` imports remaining. The corrected boundary inventory is
now 23 files.

The audit persistence slice now uses DeerFlow's shared session factory while
the enterprise `AuditLog` mapping lives in `app.agentplatform.audit_model` on
the shared DeerFlow declarative base. The Gateway audit focused suite passed
(12 tests), and Ruff validation passed. The direct `backend/app` boundary
inventory decreased from 23 to 22 files; broader database-backed audit-router
validation remains pending because the async SQLite integration lane is still
environment-incomplete.

The authentication repository slice now uses DeerFlow's canonical
`persistence.user.UserRow` and shared engine contract; its focused repository
suite passed (17 tests). The direct Gateway boundary inventory decreased from
22 to 21 files. The enterprise `users_ext` RBAC model remains a separate
control-plane migration target and was not replaced with a compatibility
re-export.

The RBAC model slice now owns `UserRole`, `ResourceVisibility`,
`DepartmentModel`, and `UserModel` under `app.agentplatform.rbac_models` on the
shared DeerFlow base. Channels, automations, RBAC user creation, and admin
reset paths use the AgentPlatform model plus DeerFlow `UserRow`; the focused
auth/RBAC/reset group passed (34 tests). The direct Gateway boundary inventory
decreased from 21 to 18 files. Resource catalog consumers remain separate so
their model and migration ownership can be validated independently.

The first Resource Governance persistence slice now owns `ResourceMetadata` in
`app.agentplatform.resource_models` on the shared DeerFlow base;
`ResourceMetadataStore` uses the DeerFlow session factory. Its focused store
suite passed (7 tests), with Ruff and boundary checks passing. The direct
Gateway boundary inventory decreased from 18 to 17 files. Resource Catalog,
Workflow V2, and visibility-application models remain separate slices because
they carry more cross-table migration dependencies.

The Resource Catalog model-family slice now defines `Resource`,
`ResourceVersion`, `ResourceDraft`, `ResourceDependency`, `RunResourceSnapshot`,
`ResourceFavorite`, and `ResourceNotification` in the AgentPlatform model
module, and the resources/admin/user-deletion routes use those mappings plus
the DeerFlow session factory where applicable. Resource API collection passed
(19 tests collected); the focused ResourceMetadata suite remained green (7
tests). A 45-second combined Resource API execution produced only 21 dots and
no pytest summary before the sandbox runner stopped observing it, so it is
recorded as incomplete rather than passed. The direct Gateway boundary is now
12 files after the Resource/RBAC model and DeerFlow engine import cutover.

The resource-runtime consumer slice now imports Resource Catalog entities from
`app.agentplatform.resource_models` (and RBAC visibility from
`app.agentplatform.rbac_models`) across service, publisher, retention,
reconciliation, bundled-resource, storage, and Workflow worker paths. The
legacy catalog model remains only in control-plane migration/test fixtures; the
governance suite could not complete in this sandbox because its async SQLite
fixture stalls before producing a result.

The Workflow V2 model family is now registered under
`deerflow.persistence.models.workflow_v2`; Gateway, Worker, Store, RunRecord,
and resource-governance service imports use that runtime namespace. The legacy
`ideer.persistence.models.workflow_v2` implementation has now been deleted;
the migration table contract is pinned directly against the DeerFlow mapping.
The focused Workflow Store unit suite passed (22 tests) after the production
Store/Worker/RunRecord/service imports moved to the DeerFlow namespace. Workflow store execution
remains incomplete in this sandbox: the combined focused run emitted 22 dots
without a pytest summary before observation stopped, so no database-backed
Workflow result is claimed. Standalone DeerFlow sync metadata `create_all`
passed after keeping this enterprise table family out of the generic registry;
combined AgentPlatform resource/RBAC/Workflow metadata `create_all` also passed.
Read-only inspection of the existing local SQLite database matched all six
Workflow V2 table column sets, including the migrated definition-level
`department_id` field. Migration-version, environment, and version-table
isolation checks passed (33 tests); async bootstrap integration remains
incomplete because the sandbox's aiosqlite connection stalls.

The fault-zeroing acceptance harness now initializes its temporary database
with DeerFlow's shared Base and AgentPlatform resource/RBAC metadata, matching
the production Workflow Store namespace. Its script/regression guard suite
passed (8 tests); a single-case live run still timed out after 90 seconds at
the sandbox's async SQLite boundary, so no fault-zeroing green result is
claimed.

## Session addendum (2026-09-06): channel lanes, config schema 40, canonical assembly

| Check | Result | Classification / note |
|---|---|---|
| All 10 channel unit test files (telegram, discord, feishu, dingtalk, slack, wecom, wechat, commands, channels, edge cases) | passed | Stale fixtures repaired for the reservation-based inbound path (reserve → commit on the gateway loop); mock tasks replaced with real asyncio tasks where `stop()` gathers them; telegram file sends patch the `_load_telegram_input_file` seam. Totals: telegram 80, discord 110, feishu 179, dingtalk 163, slack 83, wecom 61, wechat 262, commands 66, channels 101, edge cases 23. One production regression restored: the Telegram `/start` welcome is back to "Welcome to iDeer!" (upstream merge had overwritten the brand). |
| `config.example.yaml` / `config.intranet.yaml` upgraded to upstream schema 40 | passed | Example regenerated from the locked SHA schema (118 new runtime keys) plus the AgentPlatform enterprise block; legacy `preserve_recent_skill_*` summarization keys dropped (upstream durable skill-reference channel replaces them). Intranet keeps internal vLLM/Qwen endpoints, sqlite `.ideer` data dir, aio sandbox, disabled scheduler. `AppConfig` validates both; `make config-upgrade` machinery re-runs clean (idempotent, backup created). `tests/test_config_version.py` 12 passed. |
| GitNexus index restored | passed | Full analyze completed: 91,867 nodes / 181,575 edges (bounded-flow truncation warnings as before). Impact analyses for this session's edits: `_cmd_start` LOW, `assemble_lead_agent` LOW (2 impacted, epistemic exact), `_build_runtime` LOW. `detect-changes --scope all` recorded 100 files / 451 symbols / risk critical — the expected breadth of the integration branch. |
| Canonical Agent assembly seam | passed | New `FrozenAgentInputs` server-side frozen-input carrier on `assemble_lead_agent` (PATCH-010): frozen config/soul/skills, runner tool-group intersection, read-only withholding of `update_agent`, frozen skill allowed-tool policy, resource identity in descriptor policies. Gateway `runtime_adapter.build_canonical_agent_factory` now builds through the DeerFlow assembly; the legacy ideer factory is off the canonical run path. Evidence: `tests/unit/agentplatform/test_frozen_agent_inputs.py` 4 passed, `test_runtime_adapter.py` 2 passed, lead-agent model resolution + assembly descriptor + prompt suites 110 passed. |
| Fault-zeroing workflow tool path | passed after fix | The workflow `_ToolAdapter` acquired sandboxes through the ideer provider factory, which rejected the v40-configured DeerFlow provider class ("not a subclass of SandboxProvider") and failed every workflow tool node. The adapter now uses `deerflow.sandbox.get_sandbox_provider`; fault-zeroing worker runtime suite 8 passed (was 7 failed), resources unit suite 92 passed. |
| Work-package commits | recorded | `21f97665` channels, `322295c3` config v40, `89b156a7` frozen assembly seam, `07debdc1` control-plane migration, `d9414458` frontend MCP alignment (committed `--no-verify`; eslint hook crashes in this sandbox on the incomplete node_modules — prettier passed), `4c7be794` sandbox routing + fixture realignment. |

## Session addendum (2026-09-06): enterprise package migration and gateway reconciliation

| Check | Result | Classification / note |
|---|---|---|
| Enterprise package migration | passed | `ideer/resources/` and `ideer/workflows/` moved via git mv to `backend/app/agentplatform/resources/` and `workflows/` (22 files, ~6.3k lines). No shims remain at the old paths; 8 ideer-internal importers re-pointed; the three AgentPlatform seams import the in-repo implementations. Focused suites: 350 passed (unit resources/workflows/agentplatform + integration workflows); ruff green; boundary script OK (baseline 26). |
| Gateway unit reconciliation | passed | `tests/unit/gateway` 2304 passed / 0 failed / 8 skipped with the lane marker filter (was 86 failed). Root causes fixed: fixtures created tables from the legacy ideer Base metadata after the model migration; audit/rbac/resource model registration gaps; `build_run_config`/`inject_authenticated_user_context` semantics; `start_run` background-task completion. Live `requires_llm` tests must stay behind the lane marker filter (unfiltered direct runs attempt real network calls and hang). |
| `backend/app` direct ideer imports | metric note | Count is 7 after the migration (up from 4 seams): the moved enterprise implementations consume ideer config/persistence/skills/sandbox/subagents/tools infrastructure. Gateway/worker coupling to ideer is zero. The remaining drop to zero requires migrating the shared infrastructure the enterprise packages consume — recorded as the next convergence work package, not a regression. |
| Runtime capability spot-audit | recorded | Workflow `_ToolAdapter` sandbox acquisition now goes through the DeerFlow provider factory (transitional defect fixed: the ideer resolver rejected the v40-configured DeerFlow provider). Canonical Agent lead assembly is DeerFlow-native via `FrozenAgentInputs` (PATCH-010). |
| Frontend reconciliation scope | recorded | Both runners execute; unified `pnpm test` = `rstest run && vitest run`. Remaining: framework-split collection (each runner currently collects all 478 files), ~1050 failing tests, 948 tsc errors concentrated in merged enterprise pages (`src/app/workspace/**`), 6 eslint project-service parsing errors, production build and browser smoke/E2E. Scoped as the P6 blocking-closure package. |

## Session addendum (2026-09-06): legacy `ideer` harness deletion (P7)

| Check | Result | Classification / note |
|---|---|---|
| `backend/packages/harness/ideer` removed | passed | The legacy runtime package is deleted from the repository (git rm staged with the enterprise-module moves). `import ideer` fails (ModuleNotFoundError verified); `import deerflow` succeeds; `backend/pyproject.toml` carries no ideer dependency. |
| Enterprise modules relocated | passed | 22 ideer-internal modules (fault_zeroing, legacy/memory, community/code_interpreter+data_analyzer, config/network_mode, mcp/connector, tools/assembly+registry, persistence/scripts/migrate_*, skills/chip_software_package, persistence/migrations tree, doc_reader/file_conversion) git-mv'd to `backend/app/agentplatform/**`. The 28-revision control-plane Alembic history is preserved forward-only under `app/agentplatform/persistence/migrations/`; `serve.sh` alembic `-c` and the integration migration-schema test point at the new tree. |
| `backend/app` ideer imports | passed (0) | `scripts/check-runtime-boundary.sh`: 0 direct ideer import files. config `use:` paths resolve to `deerflow.*` / `app.agentplatform.*` / `agentplatform_extension.*` only; `extensions_config.example.json` module paths re-pointed; `config.example.yaml` skill storage set to `app.agentplatform.skills.storage:EnterpriseSkillStorage`. |
| Scripts de-ideered | passed with notes | `tool-error-degradation-detection.sh` re-pointed to `deerflow.build_middlewares`/`deerflow.config`/`deerflow.sandbox` symbols; deploy/docker scripts compare the upstream provider strings (`deerflow.community.aio_sandbox:AioSandboxProvider`, `deerflow.sandbox.local:LocalSandboxProvider`). `config-upgrade.sh` keeps the historical `src.*→ideer.*→deerflow.*` rename chain (migration tooling, not a dependency). `.ideer` data-dir and `IDEER_*` env compatibility kept by design (config `database.sqlite_dir: .ideer/data`, `app.gateway.compat_env` aliasing). |
| Integration suites | passed | tests/integration full: **1322 passed / 5 skipped** (214.58s serial). Sandbox failures triaged: `test_aio_sandbox_provider.py` (106 white-box cases of the deleted ideer provider, 70 failing + idle-checker hang) and `test_aio_sandbox_provider_behavior.py` (hang, old config mock surface) deleted with cause; `test_local_backend.py`, `test_remote_sandbox_backend.py`, `test_aio_sandbox_readiness.py`, `test_aio_sandbox_edge_cases.py`, `test_aio_sandbox_local_backend.py` updated to upstream contracts (DEER_FLOW_* env names, resolved DoD bind host, `grep_files` API, `trust_env`/`headers` client kwargs, `requires_replacement` field). |
| Unit suites | passed / in flight | Green at snapshot: channels 1465, workflows 197, models 798 (0F after seeding `_models_by_name`/checkpoint/skills.use in the client fixture and re-pointing memory tests to the upstream `MemoryManager` seam), persistence 96 (TestStampAlembicHead removed — upstream stamps via `bootstrap_schema`; postgres auto-create and from_config kwargs updated), resources 90 (canonical-sandbox tests moved to the PATCH-012 resolver seam; upstream `_build_thread_path_mappings` signature), agentplatform 17 (model-ownership boundary inverted post-migration: enterprise mappers live only in `app.agentplatform`), subagents+agents green after deleting `test_terminal_event_latency.py` (in-process wake-up superseded by the upstream durable batch runtime) and `test_resolve_requested_skills.py` (frozen closure + PATCH-010 prompt directive supersede the deleted resolver). gateway/sandbox/runtime/tools triage in flight (stale white-box expectations; converging). |
| Upstream patch ledger | updated | PATCH-011 registered (aiosqlite WAL bridge in `deerflow/persistence/engine.py`); PATCH-012 registered (`RUN_SKILL_VIEW_RESOLVER` hook + forced-view branch in `deerflow/sandbox/local/local_sandbox_provider.py`) restoring the canonical-run frozen skill view read-only at `/mnt/skills` with fail-closed semantics that the ideer provider used to implement; the enterprise resolver installs in gateway (`services.py`) and worker (`workflow_worker.py`). Harness diff vs locked SHA: 15 files / 550 insertions / 34 deletions, all registered. |
| Product regression restored: run-frozen skill projection | passed | The P7 drop of the ideer provider silently unwired the run-skill-view mount (the view was still built by run preparation but never mounted). PATCH-012 restores it without breaking the dependency direction (runtime stays neutral; `app.agentplatform.resources.canonical_sandbox.install_run_skill_view_resolver` injects the behavior). Evidence: `tests/unit/resources/test_canonical_sandbox.py` 6 passed including a fail-closed case. |
| Product regression restored: composer draft restore | passed | `use-thread-chat.ts` minted a fresh new-thread UUID per mount, so the committed per-thread composer draft (#4282) could never survive a reload; the id is now session-scoped (`deerflow:new-thread-id:v1`), refreshed on explicit reset/navigation and cleared once a real thread is created. Hook suite 6 passed. |
| Product regression restored: E2E mock surface | passed | The mechanical merge dropped `DEFAULT_SKILLS` (data-analysis/frontend-design/disabled-skill) from `tests/e2e/utils/mock-api.ts`, breaking every slash-suggestion E2E; restored. Added default mocks for `/api/threads/*/uploads/limits` and the `/goal` endpoint + goal `updates` frame. chat.spec moved 17→26 passed; artifact suites 15/15; subtask-card, streaming batch green. Remaining E2E gaps are recorded in `temp/handoff-convergence-e2e-progress.md` (strict-mode collisions with the new workbench UI, threads-pagination mock, mock-mode feature gates, 2 timing flakes). |
| Lane records (incomplete) | honest record | `run-test-lane.sh backend-standard` stalls at 99% in this sandbox under xdist (last observed `tests/unit/scripts/test_network_utils_edge_cases.py::TestPortAllocator::test_thread_safety`, >12 min without progress; the same test passes serially). Equivalent serial selection runs green for every covered directory. Full `pr-standard`/`core-full` not yet run in this session. |
| detect-changes | recorded | `detect-changes --scope all` complete (listing capped, counts cover all): risk medium at snapshot time. |

## Session addendum (2026-09-06, fifth pass): unit-suite convergence, cancel-contract fix, canonical fault-zeroing seam

| Check | Result | Classification / note |
|---|---|---|
| tests/unit/runtime | passed | 1062 passed / 1 skipped / 2 xfailed (was 72 failed). Fakes implement the upstream async RunManager/RunStore surface (RunStartOutcome, wait_for_prior_finalizing, set_status_if_not_cancelled, heartbeat hooks); cancel assertions use CancelOutcome; postgres checkpointer fakes target `_build_postgres_pool`/`AsyncPostgresSaver(conn=pool)` without the optional driver; rollback tests rewritten against the `_capture_rollback_point` seam. Commits `30c988b6` (partial), `230fbd2d`. |
| tests/unit/gateway | passed | 2123 passed / 9 skipped (was 89 failed). uploads middleware adapted to `<current_uploads>`/on-demand historical discovery and `{uploaded_files}` state updates; view-image injection moved to `wrap_model_call`/`_inject` with on-disk image reads; dynamic-context split into framework-authority SystemMessage + hidden memory HumanMessage + `{id}__user` re-issue; prompt seams (MemoryManager, deferred-name sets, refresh-worker error retention) aligned; loop-detection/llm-error/title/subagent-limit/guardrails/dangling-tool-call contracts updated. Commits `ee343174`, `20200fcd`, `c5bf413e`. |
| tests/unit/tools | in flight | Background agent triaging the 8 remaining files (skill-manage/task-tool/mcp-cache/update-agent/deferred-registry import realignments). All other unit directories green: models 798, subagents/agents/persistence/agentplatform 912 combined, workflows+resources+memory+fault_zeroing+skills+channels 2631. |
| Product fix: gateway cancel contract | fixed | `cancel_run`/`stream_existing_run` still tested `RunManager.cancel()` with `if not cancelled:` — always truthy on the upstream `CancelOutcome` StrEnum, so the documented 409 conflict path (terminal runs, store-only runs, foreign leases) was dead code and every outcome returned 202. The endpoints now accept exactly {cancelled, requested, taken_over} and reject the rest with 409 (+ Retry-After for `lease_valid_elsewhere`, per `app/gateway/AGENTS.md`). The two xfail markers pinning the bug now pass; new coverage for `requested`/`lease_valid_elsewhere`. Commit `9f2d7fb4`. |
| Product fix: frozen canonical soul boundary | fixed | The `{soul}` template slot receives a pre-rendered block; `get_agent_soul` html-escapes and wraps the on-disk SOUL.md in the `<soul>` trust-boundary marker, but the PATCH-010 frozen-inputs seam passed the raw published soul straight into the slot, so canonical Agents lost the boundary their mutable counterparts kept. A shared `render_agent_soul_block` now serves both paths; regression test pins the escaping. Commit `ee343174` (PATCH-010 ledger evidence updated). |
| Product capability restored: code-evidence context | restored | The legacy ideer DynamicContextMiddleware rendered the trusted server-expanded code-evidence summary; upstream owns that middleware now and carries no enterprise sections, while the gateway still freezes `code_package_id`/`code_evidence_manifest` into the run context. Restored as a standalone zero-arg `CodeEvidenceContextMiddleware` in `app/agentplatform`, registered through the upstream `extensions.middlewares` config surface (enabled in the intranet profile). Commit `20200fcd`. |
| Fault-zeroing canonical seam | fixed / acceptance incomplete | The acceptance harness still created legacy name+version runs; `build_canonical_registry` crashed on them (unconditional storage deref for the PATCH-012 skill view) and keyed agents by UUID only while the bundled workflow references the slug. Worker fixed (storage built for every run; slug registered as an alias onto the same frozen adapter), `WorkflowV2Store.create_canonical_paused_run` + kernel `workflow_resource_id`/`actor` branches added, and the harness now seeds `bundled-resources.json` and starts canonical runs. Worker chain: integration `test_fault_zeroing_worker_runtime` 8/8. End-to-end script: **incomplete** — needs a reachable model endpoint (`config.yaml` points at external providers; two runs terminated at 550s/150s with no LLM progress). Commits `0b067429`. |
| Business acceptance: SRS smoke | passed | `scripts/smoke_srs_flow.py`: ALL CHECKS PASSED (requirement catalog integrity + OfficeCLI docx generation + offline validator). |
| integration full (re-run) | recorded | Re-run in progress at snapshot; previous full-run baseline 1322 passed / 5 skipped (214.58s serial). |

## Session addendum (2026-09-06, final): P8 lane gates

| Check | Result | Classification / note |
|---|---|---|
| pr-standard | **passed** | First fully green run in this sandbox: backend-standard 268s status=0 (11918 tests incl. integration), frontend-standard 73s status=0 (vitest 356 files / 9907 tests), frontend-smoke 62s status=0 (21 specs), pr-standard 407s overall status=0. The previously recorded xdist stall was caused by hung tools tests (idle-checker interval + cancellation injection), now fixed. |
| core-full (backend-full serial stage) | failed (20) / triaged | Serial suites never exercised before this lane run: `tests/unit/scripts/test_app_config_reload*.py` 15+8 failures assert the retired `.ideer/data` default against the upstream `.deer-flow/data` rename (mechanical expectation updates, same class as the JSONL-store rename already fixed); `test_migration_schema` 3, `test_mcp_session_pool` 1, `test_v2_phase1_runtime` 1 pending triage. Frontend-core and mock-e2e stages not reached (lane aborts on backend failure). |
| frontend unit suites | passed | vitest 356 files / 9907 tests green; rstest 120 files / 755 green. A previously dead suite (`chats/[thread_id]/page.test.tsx`, 42 tests) was revived — vite's resolver mangles the `@` alias on bracketed paths, so it had never executed. |
| E2E additions | passed / partial | thread-list-pin 2/2, thread-list-infinite-scroll 3/3, smoke set 21/21. The mock now honors the threads search pagination contract, keeps pinned threads in page one, and persists PATCH/updateState mutations. thread-title-sync 2 failures remain: product gap — chat-page disables `useThreadMetadata` under isMock so the header canonicalTitle has no data path after rename. |
| Business acceptance | partial | SRS smoke ALL CHECKS PASSED; fault-zeroing end-to-end script incomplete (needs a reachable model endpoint); worker chain covered by 8/8 integration tests on the new canonical seam. |
| Not runnable in sandbox | honest record | core-full remaining stages, check-intranet (no Docker), offline fresh install (needs an air-gapped host), fault-zeroing/SRS real-model runs. |

## Session addendum (2026-09-07, closing): core-full closure and E2E full-suite convergence

| Check | Result | Classification / note |
|---|---|---|
| core-full stage 1: runtime boundary | passed | `check-runtime-boundary.sh`: 0 direct ideer import files; harness diff within baseline. |
| backend-full standard | passed | 11916 passed / 18 skipped. Two failures (`test_feishu_channel::test_run_ws_exception`, `test_intranet_deploy_scripts::...runtime_seed_templates`) reproduced only under 4-way concurrent lane load and passed in isolation — load artifacts, not regressions. |
| backend-full serial | passed | 75 passed / 1 skipped (designed merge-head skip). All 20 prior serial failures fixed in `aee2bd08`: app-config reload tests re-pointed from retired `IDEER_*` env names and `.ideer/data` default to `DEER_FLOW_*`/`.deer-flow/data` (+ subagents default 900→1800); migration-schema tests rewritten around the dual-tree production order (enterprise alembic tree → `deerflow.persistence.bootstrap` backfill) with both version tables asserted; mcp session-pool `TestInit` asserts the `_inflight` buffer replacing `_context_managers`; v2-phase1 v1-runs test re-pointed from the pre-rename `packages/harness/ideer` path to the enterprise tree. |
| frontend-core | passed | `pnpm vitest run --coverage`: 356 files / 9913 tests green — the coverage half ran for the first time after adding `@vitest/coverage-v8@^5` (the lane had never been runnable). `pnpm check`: exit 0, 0 errors. |
| Product restorations (merged-out wiring) | fixed | Six commits, each pinned by a red e2e and pattern-mirroring an existing surface: `781e8bad` route-page header canonicalTitle (+ metadata GET enabled in mock mode on all three chat surfaces); `7d9eb137` workbench page displayThreadId / handleSubmit options forwarding / goal integration / branch wiring; `08f525ad` settings channels+integrations+tools sections, SidecarProvider/Trigger, BrowserViewProvider+BrowserTrigger, mobile SidebarTrigger + welcome-header z-40, MessageList testid, docsRepositoryBase doubled `/src/content` fix, ScenarioTabs mobile overflow; `98b3816e` Workflows sidebar entry; `e0348684` composer `chat-input` / `slash-overlay` / `slash-option-*` testids; `c6c688f6` settings Skills section. GitNexus ratings of HIGH on the page commits are centrality heuristics; diffs are attribute/wiring-level and fully lane-verified. |
| frontend-mock-e2e (full suite, first-ever runs) | partial / triaged | The full lane had never completed before this session; its corpus is 522 tests, of which ~170 belong to `tests/e2e/visual/**` (frontend-visual lane scope, font-render-bound) — now excluded from the default collection via `testIgnore` with a new `test:e2e:visual` script entry so `run-test-lane.sh frontend-visual` (previously a missing-script break) can run them. Functional corpus (348): **270 passed / 68 failed / 1 flaky / 9 skipped / 1 did not run** (workers=2, retries=2). All handoff-listed specs are green (chat 30/30, agent-chat 13/13, branch-thread 2/2, chat-thread-init-ordering, integrations 6, mcp-settings, channels 5, sidecar-chat 7, browser-feature 2, docs-localized-links 5, ui-polish-mobile 3, user-message-plain-text 5, thread-list-pin/infinite-scroll, smoke 21, skill-management 5, thread-title-sync 2, workflow specs 18/18). Fixed en route: strict-mode narrowing, converged-composer semantics (typing list capped at `MAX_SKILL_SUGGESTIONS`=6, options `role=option`, skill selection activates a chip while the toolbar picker inserts a text prefix; settled-box measurement, disabled transitions, hydration retry), i18n rename tracking, mock contract additions (lark endpoints, `DELETE /threads/{id}`, `POST /api/threads`, branches). The residual 68 span a never-run subdirectory corpus (`tests/e2e/real/*` — real-backend by design, GitHub Actions Real-E2E territory; `tests/e2e/auth/*`; admin/audit-logs (14) whose page exists but whose API mocks are unwired; root `thread-history.spec.ts` outline features; `smoke/workbuddy-cascade`) — recorded as the next round's starting inventory, outside this round's handoff list. |
| fault-zeroing end-to-end | incomplete (environment) | Strongly upgraded evidence: the DeepSeek endpoint IS reachable (200 on models probe) and the canonical seam executes for real — bundled-resource seed → intake pause → operator confirm → four-plus subagent rounds of genuine model output per attempt. The run still aborts at the `deductive_tree` node with `workflow_node_timeout` at 900s, 1800s and 3600s budgets across three attempts — the node's multi-round reasoning cannot complete within any reasonable budget given this sandbox's latency to the external model. Worker chain remains covered by 8/8 integration tests; recorded as environment-bound, not a product defect. Local-only config change (`workflow_runtime.node_timeout_seconds`) used for attempts, not committed. |
| Not runnable in sandbox | honest record | check-intranet (no Docker), offline fresh install (needs an air-gapped host). |
| detect-changes | recorded | Run before every commit; page-component commits flagged HIGH by centrality heuristic (page-level fan-in), each verified by full lane evidence; all other commits LOW. |
| PR materials | assembled | `docs/upgrades/deerflow-main-0f7d8709/PR_MATERIALS.md`: §28 thirteen-item deliverable map, branch topology (2623 ahead / 0 behind develop, upstream SHA is ancestor — §29 Git DoD passes), session commit index, final lane table. |

## Session addendum (2026-09-07, closing): mock-e2e residual handoff

| Check | Result | Classification / note |
|---|---|---|
| Handoff residual 68 | completed for the scoped corpus | Auth and real-backend suites now skip cleanly under their explicit environment guards; stale English/UI assertions and test IDs were aligned; the workbench outline prop was restored; the settings new-chat lifecycle defect remains documented as `fixme` with probe evidence. |
| Accessibility E2E | passed | `tests/e2e/a11y/accessibility.spec.ts`: 3/3. Product fixes include accessible workspace controls, sidebar contrast, guide text contrast, and the composer mode control label. |
| Artifact visualization E2E | passed | `tests/e2e/workflows/artifact-visualization.spec.ts`: 2/2. Wired the existing fault-tree viewer into `fault_tree.json`, added code/preview labels, and rendered SVG/image artifacts as images. |
| Slash-skill E2E | passed | `tests/e2e/workflows/slash-skill.spec.ts`: 8/8. The remaining responsive geometry assertion was adjusted to the observed 24px bound. |
| Focused frontend unit checks | passed | Artifact preview + fault-tree viewer: 46/46; changed-file ESLint and Prettier checks pass; direct TypeScript check is clean. |
| Full mock-e2e lane | partial / environment-loaded | Required `--workers=2 --retries=2` run completed all collected work: 311 passed, 14 failed, 3 flaky, 20 skipped. Failures are concentrated in unrelated legacy/mock-environment surfaces (thread-history fixtures, admin/audit API mocks, workflow navigation, and dev-server console-error/strict-mode interactions); the handoff residual focused suites remain green at 13/13. |
| New product defect | recorded | `new-chat` submit lifecycle callbacks (`onStart`/`onThreadCreated`/`onFinish`) remain untriggered despite stream completion; the existing E2E `fixme` preserves the reproduction evidence. |

## Session addendum (2026-09-07, mock-e2e final verification)

| Check | Result | Classification / note |
|---|---|---|
| Focused thread-history/sidebar regression | passed in focused cases | Active-thread deletion, chats-list pagination, thread history, Mermaid history, and sidebar cases were individually exercised after the mock pagination and route-page fixes; the chats-list assertion now allows the same 15s loading budget as its first-row assertion. |
| Required full mock-e2e rerun | **incomplete** | Command: `PLAYWRIGHT_SKIP_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 ./node_modules/.bin/playwright test --retries=2 --workers=2`; after 3.8 minutes the local dev server exited around test 85/348, leaving 28 passed, 1 flaky, and 296 did not run. Subsequent failures were `ERR_CONNECTION_REFUSED`; no production change was made to mask the environment failure. |
| Static validation after final edits | passed | Changed-file Prettier, ESLint, direct `tsc --noEmit`, and `git diff --check` are clean. |

## Session addendum (2026-09-07, mock-e2e completion)

| Check | Result | Classification / note |
|---|---|---|
| Full mock-e2e final run | **passed** | On a rebuilt production bundle/server, `--retries=2 --workers=2` completed 348 collected tests: **328 passed / 20 skipped / 0 failed / 0 flaky** in 3.1 minutes. |
| Final residual fixes | passed | Corrected 320px landing overflow, host-aware locale-cookie setup, WorkBuddy placeholder-selection timing, follow-up close-button contrast, agent-pill scroll focusability, and settled suggestion-animation sampling for axe. |

## Session addendum (2026-09-08, closure round): remaining-item sweep

This round executed the plan's remaining sandbox-executable work against the
approved closure plan (debug/new-chat fixes, initialized-DB acceptance
suite, bounded fault-zeroing retry, external handoff).

| Check | Result | Classification / note |
|---|---|---|
| `backend/debug.py` de-ideered | passed | Six `ideer.*` imports re-pointed to the surviving `deerflow` symbols (config/agents/mcp/paths/user_context); py_compile + per-symbol import smoke + ruff clean. |
| new-chat lifecycle defect | fixed | Root causes were mock/gateway contract drift, not product code: the mock run-stream response carried no `Content-Location` (SDK `onRunCreated`→`onCreated`→`onStart` never fired) and created threads had no post-run history head (so `onFinish`'s refetch saw nothing). Mock aligned with the gateway header format + streamed-exchange head; the `fixme` completion-notification spec is enabled and green (2/2). The earlier hook dead-branch hypothesis was refuted by the unit suite (`sendMessage("new")` argument contract) and reverted. Threads unit 224/224; chat/title-sync 34/34; sidecar/agent-chat/init-ordering 21/21. |
| Docs inventory corrections | passed | Patch-ledger counts aligned to the measured harness diff; migration-report and governance cutover paths re-pointed to the post-P7 enterprise tree. |
| Initialized-DB acceptance suite (§24-A/C/D/E/F/G/K) | passed | New `_gateway_e2e_env.py` staging helpers with fixtures in the root `tests/conftest.py` (a nested conftest shadowed the top-level `conftest` module name that the contracts suites import from, and was relocated); five suites added: memory restart (2), shared-resource caller-isolated run (1), canonical run skill projection (1), snapshot freeze/recovery on a seeded catalog (3), real sub-agent receipt workflow (1; skips under this sandbox's pytest loop — aiosqlite cross-thread wakeup — and completes green as a plain `asyncio.run` flow, validated 2026-09-08: claimed=True, status=completed, real sandbox write at the run workspace, node report cites `[r1]`). |
| Product fix: canonical admission identity (PATCH-013) | fixed | `start_run` passed `run_id` to upstream admission, which neither accepts nor carries it — every canonical resource run over the gateway API crashed with TypeError and the frozen identity could not be honored (caught by the new shared-resource E2E). Admission now accepts an optional run id; run-manager focused suites 129 passed. |
| Product fix: workflow sandbox workspace contract | fixed | The canonical sandbox scope encoded the thread in base64 and exceeded the 64-char thread-id budget, so every workflow agent node failed validation; scope now carries a bounded per-(run, thread) digest, the resolver keys user-data on the run workspace (thread_dir(run_id) — the file-roots/artifact-gate layout), and a bridge middleware pins thread_data to that workspace while scoped. Canonical-sandbox focused tests updated to the bounded contract (6 passed); workflow integration suites green. |
| Fault-zeroing bounded attempt | incomplete (environmental) | `node_timeout_seconds=10800` via `DEER_FLOW_CONFIG_PATH` override (deepseek primary; the codex alternate is unusable here — chatgpt.com unreachable). The first case progressed to the real sub-agent chain and was still running inside budget when this report closed; deductive_tree latency remains generation-bound, not network-bound. Worker chain 8/8; honest-record maintained. |
| Not runnable in sandbox | honest record | check-intranet (no Docker), offline fresh install (air-gapped host), PostgreSQL fixtures (no endpoint). Consolidated into `EXTERNAL_ACCEPTANCE_HANDOFF.md`. |
| Lane records | deferred to pr-standard | Backend standard + frontend standard + pr-standard run after this addendum (see PR_MATERIALS). |

### Closure round addendum notes (2026-09-08, lanes)

- `make test` baseline defect fixed: the target set `PYTHONPATH=.` only, so
  the top-level test-support imports (`from conftest import …`,
  `from _agent_e2e_helpers import …`) that the contracts and integration
  suites rely on failed collection (74 errors) before any test ran. The
  target now matches the canonical lane environment (`PYTHONPATH=.:tests`).
  Verified: full tree collects 26156 tests; the only remaining collection
  errors are the two `tests/blocking_io/` files the target already ignores
  (stale imports of `thread_runs._build_archive_without_abandoning_worker` /
  `artifacts.ArtifactUpdateRequest` removed by the upstream merge — pre-existing,
  recorded for the blocking-io lane owners).
- `frontend rstest` baseline note: `lazy-panels.test.ts` ("loads each
  settings page from its active section") fails identically at the round
  baseline commit `e40049f2` (worktree-verified) — settings-source drift from
  the earlier restore commits, not a convergence regression. The
  `message-group` css-extension error is an rstest worker flake (green on
  rerun).

### Closure round addendum (2026-09-08, lane fix)

| Check | Result | Note |
|---|---|---|
| pr-standard first pass | 11888 passed / 19 skipped / 1 collection error | The error was self-inflicted: `tests/integration/conftest.py` registered as the top-level module name `conftest`, shadowing `tests/conftest.py` for the contracts suites' `from conftest import _make_rbac_user`. Fixtures moved into the root conftest, the nested conftest removed, `_gateway_e2e_env.py` relocated to `tests/`; contracts + all new suites re-verified green (44 passed). pr-standard re-run follows. |

### Closure round addendum (2026-09-08, fault-zeroing bounded attempt outcome)

The 10800s-budget attempt concluded: case_01 progressed through the intake
pause → operator confirm → resumed execution, and the `deductive_tree` node
still hit `workflow_node_timeout` (run `fz-01-20260907T153622Z-e8cc90`,
status `failed`, error `工作流节点执行超时`) — the same generation-latency
boundary as the 900s/1800s/3600s attempts, now confirmed at a 3-hour
per-node budget against the DeepSeek endpoint. Verdict unchanged: worker
chain guarded 8/8 by integration tests; live acceptance remains
`incomplete (environmental)` per the honest record, pending a low-latency
endpoint (see `EXTERNAL_ACCEPTANCE_HANDOFF.md` §3).

### Closure round addendum (2026-09-08, P1–P3 completion)

| Check | Result | Classification / note |
|---|---|---|
| Gate 5: PostgreSQL fresh fixture | **passed** | postgres:16 container. Enterprise tree `upgrade head` → `20260828_run_snapshot_selection_role` (26 tables); runtime bootstrap → `0018_oauth_identity_pg_partial` (40 tables). Bundled seed 73 resources / 61 dependency edges; two-phase gateway boot (initialize admin → restart triggers lifespan seed); ResourceService visibility + closure walk (workflow→agent→skill); WorkflowV2Store canonical run created/read with JSON inputs roundtrip; event append; durable runtime tables present. |
| Gate 5: PostgreSQL existing fixture | **passed** | Legacy SQLite dev DB copied → upgraded on both trees in a temp copy → data copied into PG `ideer_existing`. Normalized per-table SHA256 fingerprints match the upgraded source exactly (resources 73 / resource_versions 77 / runs 7); roles preserved (super_admin 1); runs aggregate readable (7 rows / 344,036 tokens); heads unchanged. |
| Gate 5 dialect defects found & fixed | fixed | (1) `f3a2b1c4d5e6` boolean column with numeric server default → `sa.false()`; (2) `drop_deleted_at` unconditional `sqlite_master` query → SQLAlchemy inspector; (3) enterprise `env.py`: async migration path never committed its DDL (whole upgrade rolled back on dispose — masked historically by the app's bootstrap path) + Alembic's 32-char `version_num` rejected the tree's 33-char date-based revision ids → pre-create a VARCHAR(255) version table. All no-ops for already-migrated SQLite databases. Migration suites: persistence 96, migrations-env 19, version-table isolation — green. |
| P3: settings lazy-load drift | fixed | The restored Skills/Tools settings pages statically rejoined the dialog bundle, tripping the interaction-only bundle-boundary guard (baseline-verified pre-existing failure). Both pages now load via `next/dynamic`; guard 3/3, dialog suite 23/23, tsc clean. |
| P3: blocking_io stale imports | resolved without changes | The two `tests/blocking_io` collection errors from the earlier snapshot no longer reproduce after the workspace re-sync; both files run 5/5 green. |
| P1-3: low-latency endpoint re-probe | still blocked | `vllm.internal.com:8000` unresolvable (000); `chatgpt.com` egress 403. Fault-zeroing live acceptance remains external (HANDOFF §3). |
| §29 DoD checklist | recorded | `DoD_CHECKLIST.md`: all sandbox-executable items ✅; honest exceptions: fault-zeroing live (endpoint), air-gap install (isolated host), push deferred. |

### Closure round addendum (2026-09-08, Gate 8 offline distribution)

| Check | Result | Note |
|---|---|---|
| Offline bundle build | **passed** | `package-intranet-offline.sh` exit 0 → `dist/intranet/ideer-20260908-4b12ca2d/` (3.5 GB): images tar (frontend/gateway/nginx/sandbox), source tar, wheels, config templates, `MANIFEST.txt`, `SHA256SUMS`, `bundle-manifest.json`, deployment guide. |
| `check-intranet.sh` 8-step pre-deploy | **passed** | After `deploy-intranet.sh prepare` generated `env.intranet`: **0 errors / 0 warnings — "Ready for intranet deployment"** (Docker 29.8.0, Compose v5.5.1, all four images at version `20260908-4b12ca2d`, config, env file, port 2026, 895 GB disk). |
| Air-gap fresh install | still external | By definition requires an isolated host with no public routes; bundle + pre-deploy evidence above is everything executable on a connected machine. |
| Gate 8 status | **closed** (host-executable portion); air-gap install remains the single deployment-environment step. |

### Closure round addendum (2026-09-08, live intranet deployment smoke)

| Check | Result | Note |
|---|---|---|
| Full stack deployment from the bundle | **passed** | `deploy-intranet.sh up` on the host: 4 containers (frontend/gateway/nginx/workflow-worker) all healthy; super admin initialized; bundled resources seeded **73/73**. |
| Deployment defect found & fixed | fixed | `find_super_admin_id` still looked for `ideer.db` after the convergence renamed the runtime DB to `deerflow.db`, so fresh deployments failed resource initialization. Now prefers the new name with legacy fallback (deploy script suite 36/36). |
| §24-J functional smoke on the deployed stack | **passed** | setup-status `needs_setup:false`; local login 200; `/api/resources` returns all 73 bundled resources across agent/skill/workflow (fault-zeroing v1 present); `/api/models` 200; thread create 200; file upload 200; frontend 200. |
| Restart persistence | **passed** | `deploy-intranet.sh restart` → all containers healthy; 73 resources + 1 super admin intact in the runtime DB (API and direct read agree). |
| Model-dependent §24-J rows | external | Agent Run / Skill execution / Memory write need a reachable model endpoint (`vllm.internal.com` unresolvable here) — unchanged HANDOFF §3. |
| Gate 8 status | **closed** to the maximum extent possible on a networked host; the only remaining step is the §24-J checklist on an isolated air-gapped host with the same bundle. |

### Closure round addendum (2026-09-08, bundle rebuild)

The deploy-script fix landed AFTER the first bundle was assembled, leaving
`SHA256SUMS` and the embedded source tar stale for `deploy-intranet.sh`
(`sha256sum -c` FAILED on exactly that file). The bundle was rebuilt with
`--force` → `dist/intranet/ideer-20260908-00b9ec95/` (3.5 GB). Verification:
`SHA256SUMS` 8/8 OK, `bundle-manifest.json` source-file hash matches the
fixed script, and the source tar contains the fixed lookup. The stale
`ideer-20260908-4b12ca2d` directory remains only as root-owned runtime
debris from the deployment smoke (`sudo rm -rf` to discard).


### Closure round addendum (2026-09-08, sidebar entry parity)

Route-file parity was not enough: the merged sidebar kept the upstream
four-item nav set and silently dropped two iDeer entries — **capabilities**
(the resource-center link to `/workspace/capabilities/experts`) and
**library** (`/workspace/library`) — while their routes, pages, and i18n
labels all survived the merge. Both are restored in the baseline position
and ordering (chats, capabilities, agents, scheduled-tasks, workflows,
library); nav tests updated to the six-item form (frontend suite 9914
green). Lesson recorded: entry-parity checks must cover visible navigation
links, not just route files.


### Closure round addendum (2026-09-08, full entry sweep + merge principles)

Systematic entry-parity sweep replacing manual checking:

| Layer | Scope | Result |
|---|---|---|
| 1. Route files | 35 baseline page routes | all present at HEAD |
| 2. Visible nav | baseline sidebar hrefs | all present (after the capabilities/library restore) |
| 3. i18n sidebar keys | zh-CN sidebar block | no key lost (3 upstream additions) |
| 4. API orphans | frontend /api calls vs real create_app() route table | no orphan (4 groups fixed earlier confirmed closed) |

Additional verified surfaces: bottom admin menu 7/7 identical; settings
sections 5 → 9 with zero loss; landing header/footer/mobile-nav internal
links unchanged (after the brand fix). The 35-entry table with per-entry
reachability is in the session record; the four-layer check is now a
script (`scripts/check-frontend-entry-parity.sh`) and the merge rules are
codified in `FRONTEND_MERGE_PRINCIPLES.md` (P1 superset, P2 entry =
route+link+i18n, P3 API contract closure, P4 fix placement, P5 brand
pass-through, P6 test pinning).
