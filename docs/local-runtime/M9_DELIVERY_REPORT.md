# M9 delivery verification

## Current candidate

The candidate is the working tree on `feature/m9-local-mcp-secrets-tray` at
commit `2892a4fb`, with the M9 implementation changes listed in
[`PATCH_LEDGER.md`](PATCH_LEDGER.md). The current worktree is intentionally
uncommitted for review.

## Automated gates

Historical lane results (the current-candidate local-runtime rerun is recorded below):

| Lane | Result | Duration |
| --- | --- | ---: |
| `local-runtime` (historical run) | 191 passed, 4 skipped | 7 s |
| `backend-standard` | 25,878 passed, 146 skipped | 832 s |
| `pr-standard` | passed | 1,367 s |
| `backend-full` | 26,168 selected/deselected as configured; 54 passed, 9 skipped | 888 s |
| `frontend-core` | 9,978 passed | 557 s |
| `frontend-mock-e2e` | 326 passed | 509 s |
| `core-full` | passed | 1,963 s |

The local `config.yaml` was copied from the `develop` worktree and kept
untracked. Entries requiring unavailable DeepSeek and RAGFlow credentials were
removed; the Codex model uses the documented `gpt-5.4` name. `make doctor`
now reports `Status: Ready` (with web-capture and host-bash warnings).

The real-model smoke test was then opted into with the Codex auth file present.
The request reached the configured endpoint but returned HTTP 400, so model
behavioral acceptance remains incomplete. The repository `backend-llm` lane
still skips its 11 tests because its contract is keyed to `OPENAI_API_KEY`.

On the current candidate, `UV_CACHE_DIR=/tmp/deer-flow-uv-cache make test-llm`
completed with `TEST_LANE_DURATION=23s`; 38 live-model tests were skipped
because `OPENAI_API_KEY` is absent (26,211 tests were deselected). This is a
cleanly reported unexecuted lane, not real-model acceptance.

A separately authorized, minimal Codex OAuth diagnostic request (no tools and
no business data) reached the configured endpoint and returned HTTP 400. Its
redacted response body was: `The 'gpt-5.4' model is not supported when using
Codex with a ChatGPT account.` The provider therefore has a confirmed
account/model compatibility blocker; no model-name substitution was made
without service evidence.

The Codex provider now logs only status, request ID, and a bounded allowlisted
error detail when an HTTP request fails; credentials and arbitrary response
fields are excluded. Provider regression tests pass (`22 passed`).

The same-account Codex CLI comparison was attempted with its configured model
and a read-only prompt. The CLI did not reach a model response within 30
seconds; it reported a model-catalog refresh timeout while waiting for a child
process. This is an environment/service availability failure, so it cannot
establish that the application provider alone is at fault.

## Windows acceptance

Windows acceptance remains an external gate. On a Windows runner, execute the
following from the repository root after configuring the local backend and
model credentials:

```powershell
python -m pytest local-runtime/tests -q
python -m pytest local-runtime/tests/test_secrets.py -q
python -m pytest local-runtime/tests/test_python.py -q
python -m core.cli tray --config "$env:LOCALAPPDATA\iDeer\local-runtime.json"
```

The demonstration must cover Credential Manager set/read/rotate/delete,
Python timeout/cancel/descendant cleanup, tray pairing and reconnect, and
revocation preventing a new connection. Linux runs retain the restricted-file
fallback for development and cannot substitute for these Windows checks.

## Graph checks

GitNexus is indexed for this worktree. `impact load_settings` reports exact,
low-risk upstream impact. The aggregate `detect-changes --scope all` reports
33 files, 197 symbols, 26 affected flows, and critical aggregate risk because
the change spans the device control plane and production Agent assembly. The
full lanes above cover those changed flows; no commit was made.

## Follow-up verification (2026-09-16)

The desktop entry point was rechecked after the report was drafted. The status
line now uses a real Tk label (the previous implementation called `pack()` on
`tk.StringVar`), and the periodic refresh callback is cancelled during Exit.
The Windows Job Object definition now includes `PeakProcessMemoryUsed` and
`PeakJobMemoryUsed`; Windows child processes are created suspended, assigned
to the Job, and resumed only after assignment.

Window-close behavior now withdraws the Tk window while leaving the runtime
supervisor alive; the explicit Exit action performs controller shutdown and
destroys the window. The Windows notification-area interaction still requires
the Windows CI/desktop runner to verify.

Focused checks passed:

| Command | Result |
| --- | --- |
| `cd local-runtime && ruff check core/python.py core/tray.py tests/test_tray_actions.py` | passed |
| `python -m pytest local-runtime/tests/test_tray_actions.py -q` | 7 passed |
| `python -m pytest local-runtime/tests/test_python.py -q` | 15 passed |
| `python -m pytest local-runtime/tests/test_secrets.py local-runtime/tests/test_tray_actions.py -q` | 53 passed, 1 skipped |

`local-runtime/tests/test_mcp.py` plus `test_mcp_secrets.py` produced no
output for more than 60 seconds in this environment and was interrupted; that
run is incomplete and does not count as a pass. Windows desktop interaction,
the configured real-model request, and the production MCP Evidence chain
remain external acceptance gates.

The canonical `bash scripts/run-test-lane.sh local-runtime` lane was also
started after a successful preflight, reached the same test collection point,
and was interrupted after more than 60 seconds without a summary. Its result
is incomplete.

A Windows CI workflow is now present at
`.github/workflows/local-runtime-windows.yml`. It provisions Python 3.12 on
`windows-latest`, installs the Local Runtime package and test dependencies,
and runs the complete runtime test directory. CI execution itself remains
pending until GitHub Actions runs the workflow.

For Windows 7 compatibility, the runtime package now targets CPython 3.8+
through 3.12 and pins the MCP transport to the last Python 3.8-compatible
websockets line. The CI matrix checks Python 3.8 and 3.12 on the available
Windows runner; GitHub does not provide a Windows 7 hosted runner, so an
actual Windows 7 machine is still required for OS-level acceptance.

The stdio transport now uses the native asyncio subprocess stream API instead
of blocking `Popen` pipes. The complete local-runtime suite passes when local
loopback sockets are permitted.

| Command | Result |
| --- | --- |
| `python -m pytest local-runtime/tests/test_mcp.py local-runtime/tests/test_mcp_secrets.py -q` (loopback enabled) | 39 passed |
| `python -m pytest local-runtime/tests -q` (loopback enabled) | 192 passed, 4 skipped |
| `bash scripts/run-test-lane.sh local-runtime` (loopback enabled, after Windows 7 compatibility changes) | 192 passed, 4 skipped; `TEST_LANE_DURATION=8s` |
| `uv run --project backend pytest backend/tests/unit/device_control/test_broker.py backend/tests/unit/device_control/test_secrets_gate.py -q` | 17 passed |
| `uv run --project backend pytest backend/tests/test_local_runtime_mcp_integration.py backend/tests/integration/api/test_devices_router.py -q` (loopback enabled) | 36 passed |
