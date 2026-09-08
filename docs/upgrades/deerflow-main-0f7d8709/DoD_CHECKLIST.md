# §29 Definition of Done — final checklist (2026-09-08)

Verdict against the convergence plan's §29 DoD after the closure round.
`✅` = passed with evidence, `⚠️` = honestly-recorded exception.

## Git

- ✅ `git merge-base --is-ancestor 0f7d8709d3bbf0be26460b6277fbad9329302243 HEAD` → exit 0 (verified on `integration/deerflow-main-0f7d8709` and `develop` @ `cd28a054`).

## Runtime

- ✅ `deerflow.*` is the sole runtime (`import deerflow` OK, `import ideer` ModuleNotFoundError; boundary check: 0 direct ideer import files).
- ✅ Harness diff fully registered: 16 files / 554+/35- under PATCH-001..013 (`UPSTREAM_PATCH_LEDGER.md`, counts verified against `git diff`).
- ✅ Extension API active (`agentplatform_extension` loads; Run Evidence binding, task lifecycle observers).
- ✅ Memory / SubAgent / MCP / Guardrail / Run on upstream implementations; enterprise behavior injected via extension + adapter seams.

## AgentPlatform

- ✅ Resource Governance V2 (canonical `/api/resources`, UUID/version/hash, visibility, fingerprints on migrated data).
- ✅ Workflow V2 (frozen snapshots survive recovery; closure walks; durable runtime tables).
- ✅ Business packages: SRS smoke ALL CHECKS PASSED; fault-zeroing worker chain 8/8.
- ✅ Run Resource Snapshot: fresh + existing fixtures (SQLite + PostgreSQL).

## Security

- ✅ Assembly-time + runtime tool authorization (focused suites; authorization acceptance report).
- ✅ Network default-deny (13 network/config checks; NETWORK_EGRESS_REPORT).
- ✅ Shared-resource caller boundary: new end-to-end HTTP run asserts caller principal/memory scope, no owner identity in the evidence envelope.
- ✅ Canonical admission identity (PATCH-013) with frozen `run_id`.

## Data

- ✅ Fresh DB: SQLite (prior round) + PostgreSQL `ideer_fresh` (enterprise head `20260828…` + runtime head `0018…`, 40 tables, seed 73 resources/61 edges, two-phase gateway boot, RunStore JSON roundtrip).
- ✅ Existing DB: SQLite copy upgraded (both heads) with fingerprints preserved; data copied into PG `ideer_existing` with normalized per-table fingerprints matching (73/77/7); roles preserved; history readable.
- ✅ Memory migration: facts durable across a full gateway restart, per-user isolated, stored under the per-user DeerMem scope.
- ⚠️ PostgreSQL schema/constraint/JSON semantics exercised via the live fixtures above; the report retains the async-SQLite pytest-loop caveat of this sandbox.

## Tests

- ✅ Focused suites green (migration 96+19+2, run-manager 129, canonical-sandbox 6, threads 224, settings-dialog 23, lazy-panels 3, blocking-io 5).
- ✅ backend standard: green via `pr-standard` (11924+ passed; final run clean).
- ✅ frontend standard: green (vitest 356 files / 9913 tests); rstest corpus: lazy-panels now green; one `settings-notification` fixme enabled earlier — mock-e2e lane green in the prior round (328/0) and smoke green here.
- ✅ pr-standard: **exit 0** (backend-standard 546s, frontend-standard 79s, frontend-smoke 69s).
- ⚠️ core-full: ran in the 2026-09-07 round per plan decision (not re-run for the closure round; this round validated with pr-standard).
- ⚠️ fault-zeroing live acceptance (`run_fault_zeroing_acceptance.py`): `incomplete (environmental)` — `deductive_tree` times out at 900/1800/3600/10800s budgets against DeepSeek (generation-latency bound); needs a low-latency endpoint (vLLM unreachable from this sandbox; chatgpt.com egress 403).

## Offline

- ✅ Bundle build: `dist/intranet/ideer-20260908-4b12ca2d/` (3.5 GB, SHA256SUMS + manifest).
- ✅ `check-intranet.sh`: 8/8 steps, **0 errors / 0 warnings** after `deploy-intranet.sh prepare`.
- ⚠️ Air-gap fresh install still requires an isolated host by definition (bundle + pre-deploy evidence complete).
- ✅ No public-API dependency in the intranet profile (config checks; default-deny).

## Merge

- ✅ `integration/deerflow-main-0f7d8709` → `develop` merged locally (`cd28a054`, `--no-ff`).
- ⏳ Push to `origin/develop` deliberately deferred pending maintainer confirmation (local develop leads origin by 2644+ commits).

## Remaining externals (tracked in EXTERNAL_ACCEPTANCE_HANDOFF.md)

1. ~~Air-gap fresh install~~ — bundle + pre-deploy checks complete; only the §24-J checklist run on an isolated host remains.
2. Fault-zeroing live run against a low-latency intranet endpoint.
3. (Optional hardening) PostgreSQL schema/constraint differential review beyond the fixture smokes.
