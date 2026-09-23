# M5 Gate 7 retrieval evidence acceptance

> status: passed for the 2026-09-23 candidate matrix; see the current-candidate
> closeout below. Older dated ledger entries retain their original status.
>
> candidate: `5694971bc06648e8de958c6d5f4c8d7b5c1989bb`
> date: 2026-09-23 (Asia/Shanghai)

This is the formal acceptance record for
[Gate 7](../../.scratch/m5-retrieval-evidence/issues/05-gate7-acceptance.md).
Mock tests establish product contracts; they do not substitute for the real
provider, model, or browser checks.

## 2026-09-23 current-candidate closeout

Candidate `5694971bc06648e8de958c6d5f4c8d7b5c1989bb` completed the real Gate 7
matrix. The top-level artifact and all 16 per-scenario evidence files are under
[`evidence/5694971b/gate7/`](evidence/5694971b/gate7/). The strict artifact
validator passed:

```text
python3 scripts/acceptance/validate_gate7_artifact.py \
  docs/testing/evidence/5694971b/gate7/gate7-matrix.json
Gate 7 artifact: PASS (5694971bc06648e8de958c6d5f4c8d7b5c1989bb, 16 rows)
```

All 16 scenarios recorded `passed`, including live RAGFlow/Agnes Agent and
Workflow/Sub-Agent runs, access isolation/revocation, retrieval edge cases,
archive/citation/history failures, mixed web citations, streaming, and browser
loading/error/restricted and keyboard states. Evidence is sanitized by the
acceptance runners and candidate-bound; the matrix is the source of truth for
per-row provider/model/browser metadata and timings.

Implementation validation was not fully green. Focused runner/auth tests
passed (77 tests), relevant Ruff checks, frontend formatting, test inventory,
and `git diff --check` passed. The `backend-standard` lane completed with
26,067 passed, 145 skipped, and 12 failed (`TEST_LANE_DURATION`: 1,401s,
status 1). The required `pr-standard` lane also failed because its
`backend-standard` child had the same 12 failures; its other children passed:
`local-runtime` 192 passed/4 skipped, `frontend-standard` 10,221 passed (plus
Rstest 759/759), and `frontend-smoke` 29 passed. The backend failures were in
resource/run-artifact downloads, workflow fault-zeroing runtime, Gate 8
validator CLI, and canonical run skill projection tests. These are recorded
as unresolved lane failures, not attributed to Gate 7 without diagnosis.

## Acceptance commands

The real provider test creates and removes one marker document in an isolated
dataset and verifies the same provider content appears in the model delivery
and archived receipt:

```bash
cd backend
DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE7_DATASET_ID=<isolated-dataset-id> \
  uv run pytest tests/test_knowledge_gate7_live.py -q -s
```

The same command also validates the real-run artifacts. Export the run ID,
the JSON artifact for the persisted source chain, the JSON matrix artifact,
and the exact archived snippet:

```bash
RAGFLOW_GATE7_RUN_ID=<run-id> \
RAGFLOW_GATE7_SOURCE_CHAIN_JSON=<source-chain.json> \
RAGFLOW_GATE7_MATRIX_JSON=<gate7-matrix.json> \
RAGFLOW_GATE7_EXPECTED_SNIPPET=<exact-snippet> \
  uv run pytest tests/test_knowledge_gate7_live.py -q -s
```

The browser test requires a completed real chat whose rendered citation points
to a receipt item from the real run:

```bash
cd frontend
PLAYWRIGHT_SKIP_WEB_SERVER=1 \
E2E_GATE7_THREAD_ID=<thread-id> \
E2E_GATE7_RUN_ID=<run-id> \
E2E_GATE7_EXPECTED_SNIPPET=<exact-snippet> \
  pnpm exec playwright test tests/e2e/real/knowledge-evidence-gate7.spec.ts
```

The browser assertion navigates to the real chat, verifies the exact snippet,
observes the Evidence API request for the supplied run ID, and exercises the
rendered `evidence://` citation and its Evidence Panel. The test is also
included in `scripts/run-test-lane.sh frontend-real` when the standard
real-E2E harness exports those variables. Missing harness, provider, model,
browser, or credentials is recorded as `unexecuted`, never as pass.

## Candidate result ledger

| Check | Source | Result | Time / duration / exit | Notes |
| --- | --- | --- | --- | --- |
| Provider → adapter → archived receipt | `test_knowledge_gate7_live.py` | passed | 2026-09-15 / 5.95s / 0 | Real isolated RAGFlow service; dataset `737991f4ab7a11f1b2776b607031e48e`; 1 passed, 1 skipped. |
| Persisted Run → Tool Call → KB → Revision → Document → Chunk | `test_gate7_acceptance_artifacts.py` plus real-run artifact validation | unexecuted | 2026-09-15 / — / — | Requires a real run artifact and exact snippet; the validator rejects missing hops. |
| Required real Agent/Workflow/Sub-Agent and browser matrix | `test_gate7_acceptance_artifacts.py` plus matrix artifact validation | unexecuted | 2026-09-15 / — / — | Requires all matrix rows with a passing result and evidence artifact. |
| Acceptance artifact validators | `tests/unit/knowledge/test_gate7_acceptance_artifacts.py` | passed | 2026-09-15 / focused 5s / 0 | 3 passed; live artifact validation was skipped without isolated artifacts. |
| Browser click, exact snippet, keyboard focus restore | `knowledge-evidence-gate7.spec.ts` | unexecuted | 2026-09-15 / — / — | No real E2E manifest or seeded Gate 7 run was supplied. |
| Focused backend M5 contracts | `tests/test_knowledge_gate7_live.py`, `tests/unit/knowledge/test_retrieval_receipts.py`, `tests/unit/gateway/test_run_evidence.py` | passed | 2026-09-15 / focused / 0 | Retrieval/evidence regression tests passed; live provider case recorded separately below. |
| Current retrieval/evidence regression slice | `tests/unit/knowledge/test_retrieval_receipts.py`, `tests/unit/gateway/test_run_evidence.py`, `tests/test_tool_receipt_middleware.py` | passed | 2026-09-16 / focused / 0 | 17 + 6 + 18 passed; bounded delivery, exact evidence lookup beyond 50 receipts, archive failure/exception fail-closed behavior, and tool-call binding. |
| Structured source-chain projection regression | `test_structured_search_delivers_evidence_id_and_citation_to_model` | passed | 2026-09-16 / 5.55s / 0 | Archived logical document/chunk identity is retained while provider IDs are removed from model delivery. |
| Knowledge scope and retrieval regression | `tests/unit/knowledge/test_retrieval_receipts.py tests/unit/knowledge/test_effective_knowledge_scope.py` | passed | 2026-09-16 / 4.12s / 0 | 27 passed. |
| Real RAGFlow provider marker run | `tests/test_knowledge_gate7_live.py` with `RAGFLOW_GATE7_DATASET_ID=737991f4ab7a11f1b2776b607031e48e` | passed | 2026-09-17 / 15.52s / 0 | 1 passed, 1 skipped; current candidate read the parent RAGFlow configuration through a temporary symlink and process environment, and removed the marker document by fixture cleanup. |
| Focused frontend citation/evidence contracts | citation and receipt-card unit tests | passed | 2026-09-15 / 2s / 0 | 2 files, 14 passed. |
| `backend-standard` child | `bash scripts/run-test-lane.sh pr-standard` | passed | 2026-09-17 / 976s / 0 | 25,937 passed, 146 skipped; warnings only. |
| `backend-blocking-io` | `bash scripts/run-test-lane.sh backend-blocking-io` | passed | 2026-09-17 / 9s / 0 | 96 passed, 5 warnings. |
| `frontend test:full` | `pnpm test:full` | passed | 2026-09-16 /  — / 0 | Rstest 758/758, Vitest coverage, ESLint and TypeScript completed after regenerating corrupted generated `.next/dev/types`; existing warnings only. |
| `frontend-visual` | `bash scripts/run-test-lane.sh frontend-visual` | passed | 2026-09-17 / 500s / 0 | 173 passed, 1 skipped; landing screenshots freeze the 2200ms word-rotation timer so the visual baseline is deterministic. |
| `frontend-a11y` | `bash scripts/run-test-lane.sh frontend-a11y` | passed | 2026-09-17 / 114s / 0 | 3 WCAG 2.1 AA scenarios passed. |
| `frontend-real` preflight/matrix | `bash scripts/run-test-lane.sh frontend-real` | unexecuted | 2026-09-17 / 3s / 0 | Preflight passed with browser/socket permissions; all 9 real tests were explicitly skipped because the real backend/run environment variables were not supplied. |
| Workflow real sub-agent receipt integration | `tests/integration/workflows/test_v2_subagent_receipt_executed_workflow.py` | skipped | 2026-09-16 / 153.63s / 0 | Dedicated asyncio thread hit the documented restricted-sandbox aiosqlite wakeup limitation. |
| Test lane contracts | `bash scripts/run-test-lane.sh test-contracts` | passed | 2026-09-16 / 11s / 0 | Ownership and lane entry contracts passed. |
| `frontend-standard` child | `bash scripts/run-test-lane.sh pr-standard` | passed | 2026-09-17 / 299s / 0 | 10,064 passed; warnings only. |
| `frontend-smoke` child | `bash scripts/run-test-lane.sh pr-standard` | passed | 2026-09-17 / 28s / 0 | Preflight passed; canonical lane completed 29 smoke tests. |
| **2026-09-22 Step 1** `test_gate7_real_provider_content_matches_archived_delivery` | `DEER_FLOW_CONFIG_PATH=/home/neowyh/code/AgentPlatform/config.yaml DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE7_DATASET_ID=737991f4ab7a11f1b2776b607031e48e uv run --no-sync pytest tests/test_knowledge_gate7_live.py::test_gate7_real_provider_content_matches_archived_delivery -q -s` | passed | 2026-09-22 / 8.08s / 0 | Agnes `agnes-3.0-flash` first model; fresh marker uploaded, parsed, retrieved, evidence delivery verified, deleted |
| **2026-09-22 Step 1** `test_gate7_acceptance_artifacts.py` | `DEER_FLOW_CONFIG_PATH=/home/neowyh/code/AgentPlatform/config.yaml uv run --no-sync pytest tests/unit/knowledge/test_gate7_acceptance_artifacts.py -q` | passed | 2026-09-22 / 2.95s / 0 | 3 passed |
| **2026-09-22 Step 1** `test_knowledge_gate7_live.py` full | `DEER_FLOW_CONFIG_PATH=/home/neowyh/code/AgentPlatform/config.yaml DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE7_DATASET_ID=737991f4ab7a11f1b2776b607031e48e uv run --no-sync pytest tests/test_knowledge_gate7_live.py -q -s` | passed: 1 passed, 1 skipped | 2026-09-22 / 12.43s / 0 | artifact-only test skipped (needs RAGFLOW_GATE7_SOURCE_CHAIN_JSON/MATRIX_JSON/RUN_ID/SNIPPET env vars) |
| **2026-09-22 Step 1** regression slice | `DEER_FLOW_CONFIG_PATH=/home/neowyh/code/AgentPlatform/config.yaml uv run --no-sync pytest tests/unit/knowledge/test_retrieval_receipts.py tests/unit/gateway/test_run_evidence.py tests/test_tool_receipt_middleware.py -q` | passed | 2026-09-22 / 3.95s / 0 | 42 passed |
| **2026-09-22 current candidate** Agent source-chain replay | Isolated Gateway `:8003`, Agnes `agnes-3.0-flash`, run `3cd3d3f8-5ed2-4cdd-a504-13e2a7ec6d83` | passed for the Agent row; source-chain artifact persisted at `docs/testing/evidence/08643200/gate7/source-chain.json` and validates every persisted hop | 2026-09-22 / 16s / 0 |
| **2026-09-22 current candidate** Workflow/Sub-Agent replay | Isolated Gateway `:8003`, workflow `576e1690-4a56-4749-bf1a-a4d82e315df1`, run `cc9337ce-f3e9-4c8b-bf51-de085d131f26` | passed: workflow was created and published through the resource API, the real Agnes run completed with the frozen KB binding, and the exact marker/citation was observed; sanitized evidence is persisted at `workflow-subagent.json` | 2026-09-22 / ~1m / 0 |
| **2026-09-22 current candidate** browser citation replay | `knowledge-evidence-gate7.spec.ts` with real thread `fddbc087-0b6d-452f-b4c8-bc33cbd4861d` and run `3cd3d3f8-5ed2-4cdd-a504-13e2a7ec6d83` | passed: exact marker, Evidence Panel, keyboard open/close, and focus restoration verified | 2026-09-22 / 1.5m / 0 |
| **2026-09-22 current candidate** persisted artifact validation | `docs/testing/evidence/08643200/gate7/source-chain.json`, `workflow-subagent.json`, and `executed-matrix.json` | source-chain and Agent/Workflow/browser evidence are persisted; matrix artifact remains partial with 14 required rows unexecuted | 2026-09-22 / <1s / 0 |

## Required manual matrix

The isolated run must retain evidence for Agent and Workflow/Sub-Agent paths,
two users/two KBs, revoked access, archived Rev1 after Rev2, provider outage,
empty/truncated/retry/duplicate/failed-archive/forged/history-without-receipt
states, mixed web citations, streaming, loading/error/restricted states, and
keyboard open/close/focus recovery. Each row must record the real provider,
model, browser, substitute, skip reason, and artifact path.

The source-chain assertion is specifically:

`Run → Tool Call → KB → Revision → Document → Chunk`

and the browser assertion additionally requires the clicked snippet to equal
the content archived for the evidence identifier delivered to that run.

## Lane contract

Before each lane, run `python3 scripts/test_preflight.py <lane>` (the lane
runner performs this automatically). After adding the two tests, run
`python3 scripts/test_inventory.py`. Report every child lane summary and the
parent `TEST_LANE_DURATION`; a timeout is `incomplete`, not pass. `core-full`
is not required for this gate.
