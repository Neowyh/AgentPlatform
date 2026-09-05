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
| `UV_CACHE_DIR=/tmp/deer-flow-uv-cache TEST_LANE_MAX_SECONDS=120 bash scripts/run-test-lane.sh backend-standard` | incomplete | The lane reached 8% with passing tests but did not complete within the observed window; interrupted after 120s. Per test protocol this is not a pass. |
| `timeout 180s env UV_CACHE_DIR=/tmp/deer-flow-uv-cache make -C backend test` | incomplete | The standard Make target entered pytest collection but emitted no collection summary within the observation window; no pass is claimed. |
| `timeout 150s env UV_CACHE_DIR=/tmp/deer-flow-uv-cache TEST_LANE_MAX_SECONDS=120 bash scripts/run-test-lane.sh pr-standard` | incomplete/failed | The lane reached about 11%; the same Discord fixture failures appeared before the bounded observation window completed. The focused classification is recorded above. |
| GitNexus refresh | passed with bounded-flow warnings | Incremental refresh completed in 158.5s at current commit `b24ce5b`: 91,329 nodes, 180,760 edges, 2,781 clusters and 1,013 flows. Analyzer reports bounded candidate/trace truncation for some high-branching flows; an empty impact result is not treated as proof of no callers. |
| `python scripts/smoke_srs_flow.py` | passed | Offline SRS outputs generated and validator returned `ALL CHECKS PASSED`. |
| `bash scripts/check-intranet.sh` | failed | Docker Compose/images and generated `env.intranet` are unavailable in this environment; config file itself is present. |
| `python scripts/run_fault_zeroing_acceptance.py` | fixed invocation path; acceptance incomplete | The script now adds `backend/` to `sys.path` when run from the repository root. It then requires the documented `--user-id`; a one-case run with a synthetic user exceeded the 30-second observation window without producing a verdict. |
| Fault-zeroing workflow focused tests | passed | Runtime/kernel coverage: 7 passed. A real one-case acceptance with the seeded user reached the 60-second observation timeout without output, so the product acceptance remains incomplete. |
| `tests/test_slash_skills.py` | focused behavior passes; full file incomplete in this environment | The synchronous activation and isolated async test pass. Running the async test after another `asyncio.run` test hangs during Python's `asyncio.to_thread` executor shutdown; this reproduces with a minimal Python 3.12 script and is classified as a test/runtime-environment issue, not a product regression. |
| `tests/test_migration_user_isolation.py` | fixed and passed | Restored the missing `migrate_skills` entry point and moved the one-time migration script to `deerflow.config.paths`; dry-run, conflict quarantine, history-directory and parent-directory preservation semantics: 19 passed. |
| `tests/integration/persistence/test_migration_schema.py` | partial pass; one environment-incomplete test | After switching Alembic's SQLite path to a synchronous engine, 48 migration/environment checks passed when excluding `test_stamp_alembic_head_interaction`. That async test still hangs at `aiosqlite.connect()` in this sandbox; the remaining result is incomplete, not a release pass. |
| `cd frontend && pnpm test` | blocked | The checked-out frontend dependencies do not provide the `rstest` binary. |
| `cd frontend && pnpm check` | blocked | With the available install, ESLint cannot load `next/dist/compiled/babel/eslint-parser` through `eslint-config-next`; TypeScript is not reached. Offline install lacks the required package artifacts. |
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
| Thread metadata utility regressions | passed | Switched metadata validation and invalid-filter exception boundaries to DeerFlow; thread/router edge regressions: 172 passed. Time/identity utilities remain unchanged due HIGH/CRITICAL blast radius. |

The standard lane now exports `PYTHONPATH=.:tests`, preserving the existing
collection roots while resolving shared test helpers. Re-run with
`UV_CACHE_DIR=/tmp/deer-flow-uv-cache` for the authoritative lane result.

## Scope notes

This report deliberately does not claim a product baseline pass. Full
`core-full`, intranet, business acceptance, offline packaging, database
migration and air-gapped installation are still pending and are release gates.

## Runtime Foundation focused evidence

The branch still has 155 textual `ideer` imports under `backend/app`,
`backend/scripts` and the AgentPlatform-facing harness adapters. This is an
inventory signal only; the final `import ideer` failure gate is intentionally
not claimed until the Workflow/resource control-plane extraction is complete.

The following focused slices are green on this branch:

- pluggable memory configuration and manager compatibility: 18 tests;
- extension API and run-evidence envelope contracts: 43 tests;
- task lifecycle evidence persistence: 50 tests;
- authorization assembly/runtime/provider enforcement, including shared-agent
  caller identity: 44 tests;
- sandbox mount contract and `/mnt/skills` defaults: 3 tests;
- AgentPlatform extension boundary and lifecycle binding (snapshot identity,
  caller-scoped memory, default-deny network, explicit install registration):
  6 tests;
- sandbox network policy and intranet proxy workflow: 14 tests;
- intranet runtime config path and default-deny contract: 1 test;
- sub-agent tool receipts, report contract, acceptance checks and delegation
  ledger: 270 passed, 1 skipped;
- SRS smoke flow: `ALL CHECKS PASSED`.
- Resource version snapshot regression: 14 passed (`tests/unit/resources/test_resource_service_versions.py`), including freezing the selected version for an already-started Run.
- Workflow run-record integration: 7 passed (`tests/integration/workflows/test_v2_run_record.py`), covering JSONL event mirroring, terminal Markdown rendering and exhausted-run records.
- Workflow artifact/schema/precondition integration: 15 passed across
  `test_v2_artifact_gates.py`, `test_v2_write_schemas.py` and
  `test_v2_preconditions.py`.
- Skill projection and mount isolation: 71 passed across projection,
  three-way mount, container-path and requested-skill resolver tests.
- Memory migration, manager configuration, user/agent isolation and restart
  persistence: 75 passed, 1 skipped across the focused memory contract suite.
- Channel runtime boundary: inbound upload management, application-config
  lookup and dynamic channel resolution now import DeerFlow directly. The
  focused channel subset remains incomplete because the current branch's
  existing channel test surface reports unrelated API drift (143 failures in
  the full pair, including missing legacy helper signatures); no new channel
  assertion was introduced by this import-only slice.
- Run-preparation memory preload now goes through the AgentPlatform memory
  adapter and DeerFlow application config; the focused preload/service group
  is green (41 passed).
- Upload gateway sandbox provider now resolves through DeerFlow while
  enterprise Code Evidence and AgentPlatform path/identity policy remain at
  the gateway boundary; upload-router focused regressions: 80 passed.

These results establish the next-stage baseline but do not close the semantic
ledger rows. Shared-resource, workflow receipt, migration, offline and fresh
intranet-install acceptance remain required.

The selected V2 workflow integration group was started with the same cache
override but produced no test output within 60 seconds and was interrupted.
It is therefore recorded as incomplete (not passed); database-backed workflow
validation needs a dedicated follow-up with an initialized test database.
