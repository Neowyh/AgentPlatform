# DeerFlow main upstream patch ledger

This ledger is the allow-list for local changes under
`backend/packages/harness/deerflow/**` during convergence.  The comparison is
against the locked DeerFlow commit `0f7d8709d3bbf0be26460b6277fbad9329302243`.

## Current inventory

| Scope | Comparison | Local patch count | Status |
|---|---|---:|---|
| `backend/packages/harness/deerflow/**` | `git diff 0f7d8709d3bbf0be26460b6277fbad9329302243 -- backend/packages/harness/deerflow` | 0 | closed: no local patch |

The integration branch currently keeps AgentPlatform-specific behavior in the
control plane and extension layers; no untracked or unregistered DeerFlow
runtime patch is permitted.  Any future runtime change must add a row below
before it is committed.

## Registration format

| ID | Path / symbol | Reason local behavior is required | Upstream alternative considered | Removal trigger | Verification | Status |
|---|---|---|---|---|---|---|
| — | — | No local DeerFlow harness patch at this baseline | N/A | N/A | zero-diff inventory above | closed |

## Enforcement

Before each convergence commit, rerun the comparison command above and update
this ledger.  A non-zero diff without a registered row is a gate failure.
Runtime behavior that belongs to AgentPlatform must be implemented in
`backend/app/agentplatform/` or `backend/packages/agentplatform-extension/`,
not by growing this fork.
