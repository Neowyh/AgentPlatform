# Current branches closeout report

Date: 2026-09-21
Baseline: `develop@ca65c5770`  
Candidate: `develop@9d1e235f`, containing the reviewed M5, M6, M9, and TTFT integration commits plus the closeout verification updates.

Status: **本机集成完成；正式收口未完成**. The candidate is now fast-forwarded into `develop`; external acceptance gates remain open.

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

## Local verification

| Check | Result |
| --- | --- |
| `python3 scripts/test_inventory.py` | passed; inventory regenerated with new tests visible |
| M5/M6 backend focused tests | 63 passed |
| M9 backend/local-runtime focused tests in sandbox | 88 passed; socket tests blocked by sandbox |
| Same M9 command with local sockets permitted | 105 passed |
| Frontend `pnpm test` command (Rstest + Vitest) with local port permitted | Rstest 758 passed; Vitest 369 files / 10,221 tests passed |
| Backend `make test` preflight in sandbox | unexecuted: local socket bind denied |
| Backend `make test` with local sockets permitted | passed: 26,028 passed, 145 skipped, 818 warnings; 1,162s |
| Backend ruff check/format (changed files) | passed |
| Local-runtime focused ruff check | passed |
| `pr-standard` | current-candidate run: frontend-standard Rstest 758 and Vitest 10,221 passed; frontend-smoke 29 passed. Backend-standard completed with 26,010 passed, 145 skipped, and 38 failures after 4,285s; the failures were stale migration-head/extension-test expectations and were corrected, with the affected 149-test subset passing afterward. Parent lane remains failed and requires a fresh full rerun before release. |
| `backend-blocking-io` | passed on current candidate: 97 passed, 16s (with `UV_CACHE_DIR=/tmp/deer-flow-uv-cache`) |
| `frontend-a11y` | passed: 3 passed, 177s |
| `frontend-visual` | passed: 173 passed, 1 skipped, 774s; Chromium launch and local socket preflight required the socket-enabled environment |
| `test-contracts` | passed: ownership and lane entry contracts, 20s |
| `local-runtime` | passed on the integrated candidate: 192 passed, 4 skipped, 9s |
| TTFT diagnostic unit tests | passed: 4 benchmark tests; timing/journal/upload focus 108 passed |

## Gate status

- Gate 7: local acceptance assets and focused tests are present; real RAGFlow, model, permission matrix, and browser evidence are `unexecuted`.
- Gate 8: evaluation APIs, persistence, publish gate, and acceptance assets are present; real model evaluation and browser acceptance are `unexecuted`.
- M9: local MCP, secrets, tray, consent, redaction, and device-control tests pass in the socket-enabled environment. Windows 7 remains `unexecuted`.
- TTFT: trace/upload correlation is integrated. No performance improvement is claimed; 0/1/5/10/20-file paired experiments with a real business Agent and proxy path remain `unexecuted`.
- PostgreSQL migration verification is `unexecuted`; SQLite and migration unit coverage remain available locally.
- GitNexus required pre-merge change scan reported 76 files, 679 symbols, 78 affected processes, aggregate risk `critical`; after integration the repository was reindexed successfully in 448.6s (`94,557` nodes, `207,561` edges, `3,012` clusters, `1,080` ranked flows). The index reports budget truncation for some candidate entry points, so an empty result is not evidence of no impact.
- The landing visual fixture now waits for the deterministic `document processing` hero state before capture; the rerun passed all 173 executable visual cases without rewriting snapshots. The visual suite still reports expected health-check warnings where the backend proxy is intentionally unavailable.

Formal closeout is therefore blocked on external environments. The candidate is now integrated into `develop` and suitable for review, but it must remain a draft until Gate 7, Gate 8, real MCP evidence, Windows 7, PostgreSQL, and TTFT external checks have independent evidence.
