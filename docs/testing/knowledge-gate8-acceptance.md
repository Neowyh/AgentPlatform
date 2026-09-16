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
`E2E_GATE8_KB_SLUG` and `E2E_GATE8_EXPECTED_SNIPPET`.

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
records its exact command, zero exit status, and evidence path. The validator
rejects missing scenarios, mocked environments, stale/unexecuted steps, and
provider identity or secret fields.

## Verdict and cleanup

Gate 8 is **passed** only when the artifact validator and all applicable real
checks pass. Otherwise record **not passed** and list the remaining blockers.
Clean only assets created for this run; record anything intentionally left for
manual cleanup. Do not modify real user knowledge data, run `core-full`, or
expand scope to M10/M11/M12 by default.
