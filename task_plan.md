# Workflow Runtime v2 — Phase 2

## Goal

Implement the approved Phase 2 plan: lease-safe multi-worker execution, platform-level stream events, SSE-first run detail UI, and configurable run governance/audit.

## Phases

- [completed] 1. Re-establish Phase 1 baseline and map affected runtime/API/UI symbols.
- [completed] 2. Add lease CAS, atomic event sequencing, worker takeover, and focused backend tests.
- [completed] 3. Add action streaming/cancellation and platform-event persistence with tests.
- [completed] 4. Add runtime governance, immutable run ownership, and audit records with tests.
- [completed] 5. Replace run detail primary polling with replayable SSE client and frontend tests.
- [completed] 6. Run targeted and required checks; review changed execution-flow scope.

## Constraints

- The user-approved plan is the source of scope; do not weaken test gates.
- Maintain existing public routes and command idempotency.
- Use SQLite for automated lease/takeover proof; production remains persistent DB/checkpointer only.
- Every production behavior change starts with a focused failing test.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `uv` default cache is read-only in the sandbox | 1 | Used a temporary `/tmp/deer-flow-uv-cache` for verification only. |
| `pytest-rerunfailures` cannot create its local socket in the sandbox | 1 | Reran the identical verification command with approved local-process permission. |

## Phase 2 acceptance evidence

| Requirement | Current evidence |
| --- | --- |
| Lease safety, takeover, no duplicate prior action | SQLite dual-worker and lease-audit integration coverage. |
| Unified replayable lifecycle/action stream and private-run RBAC | Backend durable replay/RBAC contracts plus frontend SSE reconnect/approval reducer coverage. |
| Governance limits and auditability | Config, timeout, iteration-gate, event-budget, concurrency-rejection, and max-attempt terminal-event coverage. |
| Required validation | Backend focused suite: 198 passed; frontend workflow tests: 2 passed; `pnpm check`, `git diff --check`, Alembic single head, and GitNexus change review all passed. |
