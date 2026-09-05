# DeerFlow main upstream patch ledger

This ledger is the allow-list for local changes under
`backend/packages/harness/deerflow/**` during convergence.  The comparison is
against the locked DeerFlow commit `0f7d8709d3bbf0be26460b6277fbad9329302243`.

## Current inventory

| Scope | Comparison | Local patch count | Status |
|---|---|---:|---|
| `backend/packages/harness/deerflow/**` | `git diff 0f7d8709d3bbf0be26460b6277fbad9329302243 -- backend/packages/harness/deerflow` | 2 files / 13 insertions | registered below; not closed |

The integration branch currently keeps AgentPlatform-specific behavior in the
control plane and extension layers; no untracked or unregistered DeerFlow
runtime patch is permitted.  Any future runtime change must add a row below
before it is committed.

## Registration format

| ID | Path / symbol | Reason local behavior is required | Upstream alternative considered | Removal trigger | Verification | Status |
|---|---|---|---|---|---|---|
| PATCH-002 | `deerflow/extensions/notify.py` (`notify_task_start/stop`) | Initialize and finalize the shared Run Evidence Envelope at the runtime task lifecycle boundary | Upstream task lifecycle hooks do not own AgentPlatform's cross-cutting evidence envelope | Remove when the AgentPlatform extension owns this lifecycle binding without a harness patch | `tests/test_extension_task_lifecycle.py`, extension API contract tests | open |
| PATCH-003 | `deerflow/config/AGENTS.md` (memory schema guidance) | Document the merged host-shared/pluggable Memory schema and migration boundary | Upstream documentation does not describe AgentPlatform's legacy profile migration | Remove when equivalent guidance is supplied by the extension/config package | `tests/test_memory_manager_pluggable.py` | open |

## Enforcement

Before each convergence commit, rerun the comparison command above and update
this ledger.  A non-zero diff without a registered row is a gate failure.
Runtime behavior that belongs to AgentPlatform must be implemented in
`backend/app/agentplatform/` or `backend/packages/agentplatform-extension/`,
not by growing this fork.
