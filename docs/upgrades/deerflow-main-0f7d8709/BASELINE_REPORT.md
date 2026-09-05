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
| Discord typing tests in first standard run | failed | Local compatibility failure; the run was interrupted before a complete summary, so this remains unclassified pending a focused reproduction. |
| `UV_CACHE_DIR=/tmp/deer-flow-uv-cache TEST_LANE_MAX_SECONDS=120 bash scripts/run-test-lane.sh backend-standard` | incomplete | The lane reached 8% with passing tests but did not complete within the observed window; interrupted after 120s. Per test protocol this is not a pass. |
| GitNexus refresh | incomplete | Analyzer emitted a complete parse but persisted status remains `incremental-in-progress` against old commit `e648acbb2...`; graph-dependent edits are blocked until status is current. |
| `python scripts/smoke_srs_flow.py` | passed | Offline SRS outputs generated and validator returned `ALL CHECKS PASSED`. |
| `bash scripts/check-intranet.sh` | failed | Docker Compose/images and generated `env.intranet` are unavailable in this environment; config file itself is present. |
| `python scripts/run_fault_zeroing_acceptance.py` | fixed invocation path; acceptance incomplete | The script now adds `backend/` to `sys.path` when run from the repository root. It then requires the documented `--user-id`; a one-case run with a synthetic user exceeded the 30-second observation window without producing a verdict. |
| `tests/test_slash_skills.py` | focused behavior passes; full file incomplete in this environment | The synchronous activation and isolated async test pass. Running the async test after another `asyncio.run` test hangs during Python's `asyncio.to_thread` executor shutdown; this reproduces with a minimal Python 3.12 script and is classified as a test/runtime-environment issue, not a product regression. |

The standard lane now exports `PYTHONPATH=.:tests`, preserving the existing
collection roots while resolving shared test helpers. Re-run with
`UV_CACHE_DIR=/tmp/deer-flow-uv-cache` for the authoritative lane result.

## Scope notes

This report deliberately does not claim a product baseline pass. Full
`core-full`, intranet, business acceptance, offline packaging, database
migration and air-gapped installation are still pending and are release gates.

## Runtime Foundation focused evidence

The following focused slices are green on this branch:

- pluggable memory configuration and manager compatibility: 18 tests;
- extension API and run-evidence envelope contracts: 43 tests;
- task lifecycle evidence persistence: 50 tests;
- authorization assembly/runtime enforcement: 43 tests;
- sandbox mount contract and `/mnt/skills` defaults: 3 tests;
- SRS smoke flow: `ALL CHECKS PASSED`.

These results establish the next-stage baseline but do not close the semantic
ledger rows. Shared-resource, workflow receipt, migration, offline and fresh
intranet-install acceptance remain required.
