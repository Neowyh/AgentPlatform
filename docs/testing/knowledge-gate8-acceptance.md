# Knowledge Gate 8 acceptance record

This runbook is the evidence boundary for the M6 final integration candidate.
It does not manufacture a pass from unit tests or from an older branch.

## Preconditions

Record the candidate commit and branch, the M5 Gate 7 artifact path, the
isolated RAGFlow dataset, the isolated Knowledge Center KBs, the fixed
questions and canonical expected document IDs, and the date in the artifact
passed as `RAGFLOW_GATE8_ARTIFACT_JSON`. Do not put provider dataset IDs,
addresses, API keys, or secrets in that artifact.

Use separate isolated assets for this run. `RAGFLOW_GATE8_DATASET_ID` is
required for the backend provider probe. The browser lane additionally needs
`E2E_GATE8_KB_SLUG`, `E2E_GATE8_EXPECTED_SNIPPET`,
`E2E_GATE8_EXPECTED_EVIDENCE`, `E2E_GATE8_EXPECTED_COMPARISON`, and
`E2E_GATE8_EXPECTED_GATE_FEEDBACK`.

## Exact commands

```bash
python3 scripts/test_inventory.py
python3 scripts/test_preflight.py backend-standard
python3 scripts/test_preflight.py frontend-standard
UV_CACHE_DIR=/tmp/deer-flow-uv-cache uv run --project backend pytest backend/tests/unit/knowledge/test_gate8_acceptance_artifacts.py -q
DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE8_DATASET_ID=<isolated-dataset> \
  RAGFLOW_GATE8_ARTIFACT_JSON=<artifact.json> \
  UV_CACHE_DIR=/tmp/deer-flow-uv-cache uv run --project backend \
  pytest backend/tests/test_knowledge_gate8_live.py -q
bash scripts/run-test-lane.sh pr-standard
```

When real browser assets and credentials are present, also run:

```bash
E2E_GATE8_KB_SLUG=<isolated-kb-slug> \
E2E_GATE8_EXPECTED_SNIPPET=<canonical-marker> \
E2E_GATE8_EXPECTED_EVIDENCE=<evidence-marker> \
E2E_GATE8_EXPECTED_COMPARISON=<comparison-marker> \
E2E_GATE8_EXPECTED_GATE_FEEDBACK=<gate-feedback-marker> \
  bash scripts/run-test-lane.sh frontend-real
```

Record each command, start/end time, duration, exit status, and final summary.
Missing services or credentials are `unexecuted`; a hang or timeout is
`incomplete` with the last observed test. Separate mock, real, and unexecuted
results. For `pr-standard`, include each child lane summary and its
`TEST_LANE_DURATION` line.

## Required artifact scenarios

The JSON artifact must contain the current candidate, Gate 7 prerequisite,
real RAGFlow environment, isolated assets, and passed evidence for candidate
preparation, trial retrieval, eval-case maintenance, Profile A/B comparison,
matching-candidate evaluation, formal publish, run snapshot freeze, RBAC and
secrecy, failure/retry/restart recovery, and browser review. Every scenario
records its exact command, executed status, zero exit status, ISO timestamps,
non-negative duration, non-empty assertions, and scenario-specific
`observations`. The validator checks evidence files exist, Gate 7 names the
same candidate commit, and the current checkout commit matches the artifact.
Each evidence JSON must itself contain the same `candidate_commit`, its
`scenario` name, `real_execution: true`, and a non-empty `observed_steps`
list, so a copied or hand-written summary cannot stand in for an execution
record.
It rejects missing scenarios, mocked environments, stale/unexecuted steps,
placeholders, provider identity/address/secret fields, and sensitive values
embedded in ordinary strings.

The observations must show the revision and manifest trace, applied Profile
parameters, expected documents and de-duplicated rankings, recomputable
metrics, publish/latest pointer behavior, frozen old/new run snapshots,
two-user/two-KB RBAC checks, failure/retry/restart/history outcomes, and
browser evidence/comparison/gate feedback plus loading/empty/error/restricted
and keyboard-focus coverage.

## Verdict and cleanup

Gate 8 is **passed** only when the artifact validator and all applicable real
checks pass. Otherwise record **not passed** and list the remaining blockers.
Clean only assets created for this run; record anything intentionally left for
manual cleanup. Do not modify real user knowledge data, run `core-full`, or
expand scope to M10/M11/M12 by default.
