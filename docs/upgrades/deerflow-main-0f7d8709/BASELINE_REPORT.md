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
