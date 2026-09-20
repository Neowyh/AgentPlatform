# M5 Gate 7 retrieval evidence acceptance

> status: partial — live provider and browser execution require the isolated
> RAGFlow/model harness described below.
>
> candidate: `feature/m5-retrieval-evidence` at the reviewed commit (`HEAD`)
> date: 2026-09-15 (Asia/Shanghai)

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
| Provider → adapter → archived receipt | `test_knowledge_gate7_live.py` | unexecuted | 2026-09-15 / — / — | No isolated RAGFlow dataset was supplied in this workspace. |
| Persisted Run → Tool Call → KB → Revision → Document → Chunk | `test_gate7_acceptance_artifacts.py` plus real-run artifact validation | unexecuted | 2026-09-15 / — / — | Requires a real run artifact and exact snippet; the validator rejects missing hops. |
| Required real Agent/Workflow/Sub-Agent and browser matrix | `test_gate7_acceptance_artifacts.py` plus matrix artifact validation | unexecuted | 2026-09-15 / — / — | Requires all matrix rows with a passing result and evidence artifact. |
| Acceptance artifact validators | `tests/unit/knowledge/test_gate7_acceptance_artifacts.py` | passed | 2026-09-15 / focused 5s / 0 | 3 passed; live artifact validation was skipped without isolated artifacts. |
| Browser click, exact snippet, keyboard focus restore | `knowledge-evidence-gate7.spec.ts` | unexecuted | 2026-09-15 / — / — | No real E2E manifest or seeded Gate 7 run was supplied. |
| Focused backend M5 contracts | `tests/test_knowledge_gate7_live.py`, `tests/unit/knowledge/test_retrieval_receipts.py`, `tests/unit/gateway/test_run_evidence.py` | passed | 2026-09-15 / focused 6s / 0 | 15 passed; Gate 7 live case was correctly unexecuted without provider credentials. |
| Focused frontend citation/evidence contracts | citation and receipt-card unit tests | passed | 2026-09-15 / 2s / 0 | 2 files, 14 passed. |
| `backend-standard` child | `bash scripts/run-test-lane.sh backend-standard` | passed | 2026-09-15 / 1,012s / 0 | 25,929 passed, 147 skipped; 820 warnings. |
| `frontend-standard` child | `bash scripts/run-test-lane.sh pr-standard` | passed | 2026-09-15 / 308s / 0 | 10,064 passed; Rstest 758/758. |
| `frontend-smoke` child | `bash scripts/run-test-lane.sh pr-standard` | passed | 2026-09-15 / 120s / 0 | 29 passed. |
| `pr-standard` parent | `bash scripts/run-test-lane.sh pr-standard` | passed | 2026-09-15 / 1,366s / 0 | `TEST_LANE_DURATION lane=pr-standard seconds=1366 status=0`. |

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
