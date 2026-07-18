# Workflow LangGraph Runtime v2 — Phase 1

## Goal

Implement the first phase in `docs/workflow-langgraph-runtime-v2-implementation-plan.md`: a governed YAML v2 DSL and single-instance durable LangGraph worker path, while preserving legacy data as read-only.

## Status

- [accepted] Phase 1 acceptance completed on 2026-07-18: durable single-worker SQLite/checkpointer execution, interrupt/resume recovery, legacy migration, and durable SSE replay are verified.
- [completed] Persist resume intent on the claimed task and use its exact command payload after the worker changes the run status to `running`.
- [completed] Add real SQLite + LangGraph checkpointer acceptance coverage for restart, idempotent action execution, snapshot/event consistency, and `after_seq` replay.
- [completed] Upgrade a real v1 workflow database and verify historical runs remain read-only while active work is explicitly failed with `workflow_runtime_replaced`.

## Constraints

- Do not edit the user's pre-existing changes to `AGENTS.md`, `CLAUDE.md`, or the implementation-plan document.
- Keep v1 historical definitions/runs queryable but prevent new v1 execution.
- Do not weaken tests or add unrequested compatibility behavior.
