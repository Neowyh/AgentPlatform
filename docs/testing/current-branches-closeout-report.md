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
| `local-runtime` | passed on current candidate in socket-enabled environment: 192 passed, 4 skipped, 1 warning; `TEST_LANE_DURATION=10s` |
| M9 Local Runtime/MCP backend integration | passed on current candidate in socket-enabled environment: 36 passed, 4 warnings | 6.73s |
| `frontend-a11y` | passed: 3 passed, 177s |
| `frontend-visual` | passed: 173 passed, 1 skipped, 774s; Chromium launch and local socket preflight required the socket-enabled environment |
| `test-contracts` | passed: ownership and lane entry contracts, 20s |
| `local-runtime` | passed on current candidate in socket-enabled environment: 192 passed, 4 skipped, 1 warning, 7s; the sandboxed run hit the documented loopback bind restriction and was rerun unchanged with local sockets permitted |
| Gate 8 artifact validator unit tests | passed: 12 passed |
| Gate 7 real RAGFlow provider probe | passed on current candidate: 1 passed / 1 artifact-dependent case skipped; isolated dataset marker created, retrieved, archived, and deleted |
| Gate 8 real RAGFlow provider probe | passed on current candidate: 1 passed / 1 artifact-dependent case skipped; isolated marker search and unrelated zero-hit query both verified |
| PostgreSQL live schema/migration tests | passed on current candidate: 4 async schema/OAuth/migration tests with `postgresql+asyncpg://`, plus the synchronous schema test with `postgresql://`; 5 passed, 8 warnings |
| TTFT diagnostic unit tests | Existing diagnostic tests remain available; the configured DeepSeek probe passed. A real fault-zeroing 0-file run through AIO image `1.9.3` with formally seeded temporary resources completed with `stream_error=false`, sandbox creation, DeepSeek calls, and run success; it produced no assistant token because the Agent requested clarification. No performance conclusion is claimed |
| Fault-zeroing production acceptance harness | `scripts/run_fault_zeroing_acceptance.py --user-id 3e4e04b5-96c7-4230-806f-3e1a31d506f1` | `incomplete`: no result after more than 60 seconds; interrupted per lane contract | >60s |
| TTFT diagnostic harness tests | `backend/.venv/bin/pytest scripts/benchmark/test_multi_attachment_ttft.py -q` | passed: 4 passed | 0.18s |
| `frontend-real` | `bash scripts/run-test-lane.sh frontend-real` in socket-enabled environment | preflight passed; 10 real browser tests skipped because Gate 7/8, model, and RBAC environment variables were not supplied; `TEST_LANE_DURATION=4s` | 4s |
| Gate 7 formal resource setup | Temporary fresh SQLite database through `/api/v1/auth/initialize`; `/api/resources` KB create/bind/upload, initialization, Revision prepare, and publish | passed setup chain: isolated KB and one marker document reached ready; Revision prepare reached ready and publish reached published; a dedicated Agent was created and published through the resource API | 2026-09-21; 3 API phases |
| Gate 7 real Agent retrieval Run | Fresh formal resource setup, AIO 1.9.3, temporary config with the missing `knowledge` tool group added, real DeepSeek Run `f33df1e0-efab-4135-84de-797fa020e319` | `incomplete`: the minimal Agent loaded one knowledge tool, but DeepSeek timed out after retries before issuing a retrieval call; Run ended `error`, no retrieval receipt or source-chain artifact | 62s |
| Gate 7 thinking-disabled Agent retrieval Run | Fresh isolated API resource chain, published Agent `1d747b60-4f58-42c1-880e-01d1e27fe13e`, `thinking_enabled=false`, one `knowledge_search` tool, real DeepSeek Run `8c7cb083-959e-4b37-9598-5b810b8785c3` | `incomplete`: Gateway logged `thinking_enabled: False` and `Total tools loaded: 1`, but DeepSeek still timed out after retries before issuing a tool call; no retrieval receipt or source-chain artifact | 2026-09-21; ~60s |
| DeepSeek direct function-call probe (historical) | Current `config.yaml` model/base URL, direct `ChatDeepSeek` call with one minimal `knowledge_search` schema and `max_retries=0` | `incomplete`: direct model invocation returned `APITimeoutError: Request timed out` without Gateway or Agent middleware; retained as historical evidence, not a current endpoint verdict | 2026-09-21; 30s timeout |
| Gate 8 real evaluation chain | Fresh isolated SQLite database, official API resource flow, current RAGFlow dataset, one canonical document/eval case, Revision publish, retrieval test, and queued evaluation | passed after fixing SQLite evaluation defects; evaluation completed with `expected_hit_rate=1.0`, `recall_at_k=1.0`, `mrr_at_k=1.0`, `qualification_status=passed` | 2026-09-21; <1s evaluation |
| Gate 8 Profile A/B comparison | Same isolated KB, revision, and eval case; `frozen` versus `configured` profiles through the comparison API | passed: both runs completed, comparison eligible, outcome `unchanged`, metric delta `0.0` for hit rate, Recall@K, and MRR | 2026-09-21; <3s |

## Gate status

- Gate 7: the real RAGFlow provider probe was rerun on `094e7cc9` and passed (1 passed / 1 artifact-dependent case skipped); the persisted full source-chain artifact, 16-row permission/state matrix, real model run, and browser citation evidence remain `unexecuted`.
- Gate 7 resource preparation now has fresh formal API chains through KB publish and Agent publish. Two real Agent runs were incomplete because DeepSeek timed out before issuing a tool call; the second run explicitly logged `thinking_enabled: False` and one loaded knowledge tool, ruling out thinking mode and tool-group assembly as the immediate cause. No retrieval receipt/source-chain artifact is claimed. The ignored local `config.yaml` has the required `knowledge` group; this correction still needs to be carried into the deployed candidate configuration.
- A historical direct DeepSeek function-call probe using the same configured model and endpoint timed out with `max_retries=0`; no Gateway, Agent, sandbox, or RAGFlow middleware was involved. A later external-network replay reached DNS/TLS successfully, completed `/models` and the minimal function-call request, and the application factory completed 20 consecutive tool-call requests without error. This does not clear the real Agent run: its full prompt/tool payload and request timing still need capture, and no valid Gate 7 source-chain pass is claimed.
- The existing `DeerFlowClient` live tool seam was rerun with the isolated AIO configuration: `test_client_live.py::TestLiveToolUse::test_agent_uses_ls_tool` passed in 9.20s. This confirms the current DeepSeek → Agent → tool boundary, but it does not create the Gate 7 knowledge receipt/source-chain artifact.
- Gate 8: the real RAGFlow marker/zero-hit provider probe was rerun on `094e7cc9` and passed (1 passed / 1 artifact-dependent case skipped). A fresh isolated API chain completed one real retrieval evaluation with all three metrics at `1.0`, then a frozen/configured comparison completed with `eligible=true` and zero deltas. The full multi-scenario artifact, publish-gate rejection case, RBAC matrix, and browser acceptance remain `unexecuted`.
- M9: local MCP, secrets, tray, consent, redaction, and device-control tests pass in the socket-enabled environment. Windows 7 remains `unexecuted`.
- Upload sandbox authorization now honors a denied `sandbox:execute` decision by completing the upload without sandbox synchronization; the regression scenario passes.
- TTFT: trace/upload correlation is integrated. No performance improvement is claimed; 0/1/5/10/20-file paired experiments with a real business Agent and proxy path remain `unexecuted`.
- The production fault-zeroing workflow harness was started with the checked-in evaluation cases and an existing local user id, but produced no result after more than 60 seconds and was interrupted. It is `incomplete`; no workflow acceptance conclusion is claimed. The four TTFT diagnostic harness tests pass.
- `frontend-real` preflight now passes with Chromium and loopback access; all 10 tests remain explicitly skipped without the seeded Gateway, Gate 7/8 artifacts, and real browser environment variables.
- PostgreSQL migration verification now passes on the current candidate: an isolated PostgreSQL 16 container, newly installed `asyncpg==0.31.0`/`psycopg==3.3.3`, four async schema/OAuth/migration tests, and the separate psycopg synchronous schema test all passed. The temporary container was removed after verification. The async and sync test commands intentionally use their respective DSN formats.
- The original local Gateway data still fails closed with `CatalogConsistencyError`: the database catalog points at modified custom Agent/Skill versions whose canonical storage hashes no longer match. The bundled seed restored bundled files but intentionally did not overwrite user-modified resources. For diagnosis, an isolated `/tmp/deer-flow-closeout-home` snapshot was created and its copied hashes aligned to the copied disk contents; the original database and resource files were not changed. That snapshot Gateway passed startup, health, OpenAPI, login, model listing, and Agent discovery. LocalSandboxProvider still fails before model invocation because it cannot enforce the Agent's Skill isolation. With the newly installed AIO image `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3` (image id prefix `7eb67c59e1aa`), the same 0-file run created the isolated container, mounted the Skill and user roots, reached DeepSeek, and completed successfully with `stream_error=false`; the run ended in clarification, so no assistant-token TTFT was available. The configured DeepSeek path and AIO sandbox are therefore operational for this case; attachment and performance evidence remain outstanding.
- The original local Gateway data still fails closed with `CatalogConsistencyError`: the database catalog points at modified custom Agent/Skill versions whose canonical storage hashes no longer match. The bundled seed restored bundled files but intentionally did not overwrite user-modified resources. A separate fresh temporary database was then initialized through the official `/api/v1/auth/initialize` and bundled-resource seed path; the fault-zeroing Agent was discovered through `/api/resources?type=agent` without direct database edits. With the newly installed AIO image `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3` (image id prefix `7eb67c59e1aa`) and a valid temporary evaluation mount, the fresh 0-file run created the isolated container, mounted the Skill and user roots, reached DeepSeek, and completed successfully with `stream_error=false` (first SSE 1004.1ms, run completion 21886.7ms); the run ended in clarification, so no assistant-token TTFT was available. The configured DeepSeek path and AIO sandbox are operational for this case; attachment and performance evidence remain outstanding.
- The Gate 8 evaluation worker had two real SQLite defects exposed by the isolated API chain: SQLAlchemy's default in-memory bulk-update synchronizer compared SQLite's naive lease value with an aware UTC timestamp, and qualification compared aggregate metric names with threshold names. The candidate now disables session synchronization for the claim update and maps `min_*` thresholds to aggregate metrics; the focused regression and full knowledge evaluation unit file pass, and the fresh real evaluation completed and qualified.
- The real fault-zeroing Agent is `56e2423d-37c3-52cb-a05f-d32677e6abcb` (`slug=fault-zeroing`). The AIO 0-file diagnostic artifact recorded timing and error flags only, no prompt, attachment body, or credentials; the temporary Gateway, container, cookies, and isolated resource snapshot were removed after the run. Attachment cases were not sent because the safety review requires explicit authorization for the exact local payload and external destination; 1/5/10/20-file performance claims therefore remain unexecuted.
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
| `beb0a061` | `UV_CACHE_DIR=/tmp/deer-flow-uv-cache uv sync --all-packages --extra postgres` | passed: installed `asyncpg==0.31.0`, `psycopg==3.3.3`, `psycopg-binary==3.3.3`, and `langgraph-checkpoint-postgres==3.1.1` | 5.4s |
| `beb0a061` | isolated `postgres:16-alpine`; async DSN for schema/OAuth/migration tests, then `postgresql://` DSN for the synchronous schema test | passed: 5 live tests, 8 warnings; temporary container removed | 20.28s async group + 7.84s sync test |
| `094e7cc9` | `DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE7_DATASET_ID=737991f4ab7a11f1b2776b607031e48e UV_CACHE_DIR=/tmp/deer-flow-uv-cache .venv/bin/pytest tests/test_knowledge_gate7_live.py -q -s` with current `config.yaml` | 1 passed, 1 skipped; isolated marker uploaded, parsed, retrieved, evidence delivery checked, and deleted | 10.14s |
| `094e7cc9` | `DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE8_DATASET_ID=737991f4ab7a11f1b2776b607031e48e UV_CACHE_DIR=/tmp/deer-flow-uv-cache .venv/bin/pytest tests/test_knowledge_gate8_live.py -q -s` with current `config.yaml` | 1 passed, 1 skipped; marker hit and independent zero-hit query checked, marker deleted | 10.80s |
| `094e7cc9` | AIO image `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3` (image id prefix `7eb67c59e1aa`), temporary config, real DeepSeek Agent, `multi_attachment_ttft.py --count 0` | passed operational run: sandbox created, DeepSeek reached, `stream_error=false`, run completed; no assistant token because the Agent requested clarification | 23.50s run; 852.4ms first SSE |
| `3a638602` | fresh temporary database initialized through `/api/v1/auth/initialize` and bundled resource seed; AIO image `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.9.3`; `multi_attachment_ttft.py --count 0` | passed operational run: fault-zeroing discovered through the resource API, sandbox created, DeepSeek reached, `stream_error=false`, run completed; no assistant token because the Agent requested clarification | 21.89s run; 1004.1ms first SSE |
| `b3b4ee20` | fresh isolated Gate 8 database retained from the resource/evaluation chain; current candidate Gateway; `POST /api/resources/{kb}/evaluations` with frozen published Revision and one real eval case | passed: evaluation completed with `qualification_status=passed`, `failed_cases=0`, expected hit rate/Recall@K/MRR all `1.0` | <1s worker execution |
| `48082161` | restricted-sandbox replay of Gate 7 and Gate 8 provider probes with configured RAGFlow dataset | `incomplete`: both probes failed before upload with `ConnectError: All connection attempts failed`; classified as environment network restriction, not a provider assertion failure | 2026-09-21; 3.9s each |
| `48082161` | external-network replay of the same Gate 7 and Gate 8 provider probes | passed: each probe reported `1 passed, 1 skipped`; marker upload/search/cleanup and zero-hit distinction completed | 2026-09-21; 6.43s / 6.59s |
| `48082161` | external-network DeepSeek boundary replay using factory-created `PatchedChatDeepSeek`, one knowledge tool, sync and async stream variants | passed: DNS/TLS and HTTP health succeeded; 20 consecutive factory tool calls passed, and sync/async streaming passed; no secrets or prompts retained | 2026-09-21; 25s |
| `408d0b2b` | isolated AIO 1.9.3 configuration; `DEER_FLOW_RUN_LIVE_TESTS=1 uv run --project backend pytest tests/test_client_live.py::TestLiveToolUse::test_agent_uses_ls_tool -q -s` | passed: 1 test, 9.20s; real Agent emitted tool-call/result events and completed the run | 2026-09-21; 9.20s |

- Gate 7: set `DEER_FLOW_RUN_LIVE_TESTS=1`, `RAGFLOW_GATE7_DATASET_ID`, and the run/source-chain/matrix variables, then run `cd backend && uv run pytest tests/test_knowledge_gate7_live.py -q -s`; run the real citation browser case with the variables documented in [`m5-gate7-acceptance-report.md`](m5-gate7-acceptance-report.md).
- Gate 8: provide `RAGFLOW_GATE8_DATASET_ID` and `RAGFLOW_GATE8_ARTIFACT_JSON`, run the live test and artifact validator commands in [`knowledge-gate8-acceptance.md`](knowledge-gate8-acceptance.md), then execute the real browser lane.
- Windows 7: run the commands in [`M9_DELIVERY_REPORT.md`](../local-runtime/M9_DELIVERY_REPORT.md) on a native Windows 7 machine, including Credential Manager, MCP/WSS, tray, revocation, and descendant cleanup.
- TTFT: run `scripts/benchmark/multi_attachment_ttft.py` through the real business Agent and proxy path for 0/1/5/10/20 files, with at least five valid paired samples per condition; retain the JSON summary and do not claim an optimization without a paired improvement.
- PostgreSQL: the current candidate already passed the isolated PostgreSQL 16 migration/schema lane (four async tests plus the synchronous schema test); rerun against the project fixture if a fixture-specific artifact is required.

Formal closeout is therefore blocked on external environments. The candidate is now integrated into `develop` and suitable for review, but it must remain a draft until Gate 7, Gate 8, real MCP evidence, Windows 7, and TTFT external checks have independent evidence.
