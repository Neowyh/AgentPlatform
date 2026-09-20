# M5 Gate 7 retrieval evidence acceptance

> status: partial — live provider passed against the configured isolated
> RAGFlow stack; browser execution and the complete 16-row matrix remain
> unexecuted. GitNexus could not register this worktree after a full index
> attempt, so impact and detect-changes gates remain blocked.
>
> candidate: `feature/m5-retrieval-evidence` working tree, based on
> `72bb9eb861a175352c159998c0293c1f1a289f0e` (uncommitted changes)
> date: 2026-09-17 (Asia/Shanghai)

This is the formal acceptance record for
[Gate 7](../../.scratch/m5-retrieval-evidence/issues/05-gate7-acceptance.md).
Mock tests establish product contracts; they do not substitute for the real
provider, model, or browser checks.

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
| `pr-standard` parent | `bash scripts/run-test-lane.sh pr-standard` | passed | 2026-09-17 / 1,304s / 0 | backend-standard, frontend-standard, and frontend-smoke all passed. |

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
