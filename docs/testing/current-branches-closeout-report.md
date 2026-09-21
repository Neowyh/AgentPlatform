# Current branches closeout report

Date: 2026-09-21
Baseline: `develop@ca65c5770`  
Candidate: `develop@HEAD` (the final report commit below), containing the reviewed M5, M6, M9, and TTFT integration commits plus the closeout verification updates.

Status: **本机集成候选仍待复核；正式收口未完成**. The candidate is fast-forwarded into `develop`; local lanes pass, while real acceptance remains blocked by sandbox/runtime and external environment requirements.

## Completion correction

The integration branch was built in three reviewable commits and fast-forwarded
into `develop`. The original dirty develop worktree was preserved as
`stash@{0}` (`pre-closeout-develop-snapshot-2026-09-20`) before the fast-forward;
the source worktrees remain untouched. The Local Runtime lane is now part of the
runner, inventory, preflight, and PR composite, and the package declares its
Python 3.8 compatibility candidate.

## Integration record

- M5 was applied from the baseline through `feature/m5-retrieval-evidence@72bb9eb86`.
- M6 was applied from the M5 tip through `feature/m6-retrieval-test-eval@33179eb4e`; its merge base is the M5 tip, so M5 commits were not duplicated.
- M9 was applied from its fork point `ceae68859` through `feature/m9-local-mcp-secrets-tray@2892a4fbc`. The patch applied cleanly on top of the M4/M5/M6 candidate.
- The pre-existing TTFT upload change in `frontend/src/core/uploads/api.ts` was preserved. It adds optional `trace_id` response data and an `X-Trace-Id` upload header. No upload-concurrency optimization was added without a paired experiment.
- The candidate is committed on `develop`; the original feature branches and worktrees remain untouched. The protected dirty-worktree snapshot is retained in the stash until the integration is reviewed.
- The remaining uncommitted diffs in the three source worktrees were rechecked against the candidate: their content is already represented by the integrated M5 (`bd9ecfb2`), M9 (`7d6c44e8`), and TTFT (`e4bcfa71`) commits. A three-way apply in a disposable review worktree produced only duplicate-content/formatting conflicts, so no source-worktree changes were copied or merged a second time.

## Local verification

| Check | Result |
| --- | --- |
| `python3 scripts/test_inventory.py` | passed; inventory regenerated with new tests visible |
| M5/M6 backend focused tests | 63 passed |
| M9 backend/local-runtime focused tests in sandbox | 88 passed; socket tests blocked by sandbox |
| Same M9 command with local sockets permitted | 105 passed |
| Frontend `pnpm test` command (Rstest + Vitest) with local port permitted | Rstest 758 passed; Vitest 369 files / 10,221 tests passed |
| Backend `make test` preflight in sandbox | unexecuted: local socket bind denied |
| Backend `make test` with local sockets permitted (pre-final test-fix commit) | passed: 26,028 passed, 145 skipped, 818 warnings; 1,162s |
| Backend ruff check/format (changed files) | passed |
| Local-runtime focused ruff check | passed |
| `pr-standard` | passed on current candidate: local-runtime 192 passed / 4 skipped, backend-standard 26,046 passed / 147 skipped, frontend-standard Rstest 758 and Vitest 10,221 passed, frontend-smoke 29 passed; parent duration 2,778s, status 0 |
| `backend-blocking-io` | passed on current candidate: 97 passed, 16s (with `UV_CACHE_DIR=/tmp/deer-flow-uv-cache`) |
| `frontend-a11y` | passed: 3 passed, 177s |
| `frontend-visual` | passed: 173 passed, 1 skipped, 774s; Chromium launch and local socket preflight required the socket-enabled environment |
| `test-contracts` | passed: ownership and lane entry contracts, 20s |
| `local-runtime` | passed on current candidate in socket-enabled environment: 192 passed, 4 skipped, 1 warning, 7s; the sandboxed run hit the documented loopback bind restriction and was rerun unchanged with local sockets permitted |
| Gate 8 artifact validator unit tests | passed: 12 passed |
| Gate 7 real RAGFlow provider probe | passed on current candidate: 1 passed / 1 artifact-dependent case skipped; isolated dataset marker created, retrieved, archived, and deleted |
| Gate 8 real RAGFlow provider probe | passed on current candidate: 1 passed / 1 artifact-dependent case skipped; isolated marker search and unrelated zero-hit query both verified |
| PostgreSQL live schema/migration tests | passed on current candidate: 4 async schema/OAuth/migration tests with `postgresql+asyncpg://`, plus the synchronous schema test with `postgresql://`; 5 passed, 8 warnings |
| TTFT diagnostic unit tests | Existing diagnostic tests remain available; the configured DeepSeek probe passed. Real fault-zeroing runs were attempted with 0 files: LocalSandboxProvider rejected the Agent's required Skill isolation; an AIO retry emitted an SSE error and terminated the isolated Gateway. Both runs are `incomplete`; no performance conclusion is claimed |

## Gate status

- Gate 7: the real RAGFlow provider probe now passes on the current candidate; the persisted full source-chain artifact, 16-row permission/state matrix, real model run, and browser citation evidence remain `unexecuted`.
- Gate 8: the real RAGFlow marker/zero-hit provider probe now passes on the current candidate; evaluation APIs, persistence, publish gate, full artifact, real model evaluation, and browser acceptance remain `unexecuted`.
- M9: local MCP, secrets, tray, consent, redaction, and device-control tests pass in the socket-enabled environment. Windows 7 remains `unexecuted`.
- Upload sandbox authorization now honors a denied `sandbox:execute` decision by completing the upload without sandbox synchronization; the regression scenario passes.
- TTFT: trace/upload correlation is integrated. No performance improvement is claimed; 0/1/5/10/20-file paired experiments with a real business Agent and proxy path remain `unexecuted`.
- PostgreSQL migration verification now passes on the current candidate: an isolated PostgreSQL 16 container, newly installed `asyncpg==0.31.0`/`psycopg==3.3.3`, four async schema/OAuth/migration tests, and the separate psycopg synchronous schema test all passed. The temporary container was removed after verification. The async and sync test commands intentionally use their respective DSN formats.
- The original local Gateway data still fails closed with `CatalogConsistencyError`: the database catalog points at modified custom Agent/Skill versions whose canonical storage hashes no longer match. The bundled seed restored bundled files but intentionally did not overwrite user-modified resources. For diagnosis, an isolated `/tmp/deer-flow-closeout-home` snapshot was created and its copied hashes aligned to the copied disk contents; the original database and resource files were not changed. That snapshot Gateway passed startup, health, OpenAPI, login, model listing, and Agent discovery. A LocalSandboxProvider 0-file run failed before model invocation because it cannot enforce the Agent's Skill isolation. An AIO retry also returned `stream_error=true` with no token and the direct Gateway process exited. The cached AIO image is `version=1.0.0.156`; this code path requires the all-in-one-sandbox `/v1/bash/exec` API introduced in `>=1.9.3`. This is an environment blocker, not a code or DeepSeek performance result.
- The real fault-zeroing Agent is `56e2423d-37c3-52cb-a05f-d32677e6abcb` (`slug=fault-zeroing`). The 0-file diagnostic artifacts recorded timing and error flags only, no prompt, attachment body, or credentials; their temporary files and isolated resource snapshot were removed after the run. Attachment cases were not sent because the safety review requires explicit authorization for the exact local payload and external destination; 1/5/10/20-file performance claims therefore remain unexecuted.
- `make doctor` passes with `UV_CACHE_DIR=/tmp/deer-flow-uv-cache`; the direct DeepSeek probe using `config.yaml` constructed and invoked successfully.
- GitNexus required pre-merge change scan reported 76 files, 679 symbols, 78 affected processes, aggregate risk `critical`; after integration the repository was reindexed successfully in 448.6s (`94,557` nodes, `207,561` edges, `3,012` clusters, `1,080` ranked flows). The index reports budget truncation for some candidate entry points, so an empty result is not evidence of no impact.
- The landing visual fixture now waits for the deterministic `document processing` hero state before capture; the rerun passed all 173 executable visual cases without rewriting snapshots. The visual suite still reports expected health-check warnings where the backend proxy is intentionally unavailable.

## External replay checklist

## Latest replay ledger

All rows below were run against the current candidate before this report was
updated. Secrets, provider keys, cookies, prompts, and attachment bodies are
not stored in this ledger.

| Candidate | Command / environment | Result | Duration |
| --- | --- | --- | --- |
| `7da37fe0` | `DEER_FLOW_CONFIG_PATH=/home/neowyh/code/AgentPlatform/config.yaml DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE7_DATASET_ID=737991f4ab7a11f1b2776b607031e48e pytest tests/test_knowledge_gate7_live.py -q -s` | 1 passed, 1 skipped; marker upload, parse, retrieval, receipt binding, and cleanup completed | 31.05s |
| `7da37fe0` | `DEER_FLOW_CONFIG_PATH=/home/neowyh/code/AgentPlatform/config.yaml DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE8_DATASET_ID=737991f4ab7a11f1b2776b607031e48e pytest tests/test_knowledge_gate8_live.py -q -s` | 1 passed, 1 skipped after the independent zero-hit probe fix | 10.50s |
| `7da37fe0` | `pytest tests/unit/knowledge/test_gate8_acceptance_artifacts.py -q` | 8 passed | 7.78s |
| `4db7fb33` | Isolated `postgres:16-alpine`; async DSN for `test_pg_schema_integration.py`, `test_user_oauth_partial_index.py`, and `test_migration_0018_oauth_identity_pg_partial.py`, then `postgresql://` DSN for the synchronous schema test | passed: 5 live tests, 8 warnings; temporary container removed | 20.28s async group + 7.84s sync test |
| `c633ff4e` | `docker pull enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3` | `incomplete`: registry request timed out; cached image remains `1.0.0.156` | 120s timeout |

- Gate 7: set `DEER_FLOW_RUN_LIVE_TESTS=1`, `RAGFLOW_GATE7_DATASET_ID`, and the run/source-chain/matrix variables, then run `cd backend && uv run pytest tests/test_knowledge_gate7_live.py -q -s`; run the real citation browser case with the variables documented in [`m5-gate7-acceptance-report.md`](m5-gate7-acceptance-report.md).
- Gate 8: provide `RAGFLOW_GATE8_DATASET_ID` and `RAGFLOW_GATE8_ARTIFACT_JSON`, run the live test and artifact validator commands in [`knowledge-gate8-acceptance.md`](knowledge-gate8-acceptance.md), then execute the real browser lane.
- Windows 7: run the commands in [`M9_DELIVERY_REPORT.md`](../local-runtime/M9_DELIVERY_REPORT.md) on a native Windows 7 machine, including Credential Manager, MCP/WSS, tray, revocation, and descendant cleanup.
- TTFT: run `scripts/benchmark/multi_attachment_ttft.py` through the real business Agent and proxy path for 0/1/5/10/20 files, with at least five valid paired samples per condition; retain the JSON summary and do not claim an optimization without a paired improvement.
- PostgreSQL: execute the migration and persistence lane against the project PostgreSQL fixture and attach the resulting candidate-tagged report.

Formal closeout is therefore blocked on external environments. The candidate is now integrated into `develop` and suitable for review, but it must remain a draft until Gate 7, Gate 8, real MCP evidence, Windows 7, PostgreSQL, and TTFT external checks have independent evidence.
