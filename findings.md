# Findings

- The current workflow router imports and launches the legacy `WorkflowExecutor` in an in-process `asyncio.create_task`; the Phase 1 plan requires replacing that execution path with a durable worker.
- Legacy workflow code is located under `backend/packages/harness/ideer/workflows/`; it includes the parser, executor, store, schema, and step implementations.
- The existing migration `d7e0060b1ebc_add_workflow_runs_table.py` and workflow persistence model are the legacy run-state boundary named in the Phase 1 plan.
- GitNexus did not resolve `/api/workflows/{workflow_name}/run` through its API-route index, so route impact will be assessed from the handler symbol/file before any router edit.
- The isolated branch is `refactor/workflow-module` at `/home/wangyh/workspace/code/deer-flow/.worktrees/refactor-workflow`; no new worktree is needed.
- The harness-to-app import firewall means the compiler and durable runtime adapters must remain in `ideer.*` only if they have no gateway dependency; gateway-specific worker wiring belongs in `backend/app/`.
- `backend/uv.lock` already includes `langgraph`, although `backend/pyproject.toml` directly lists only `langgraph-sdk`; dependency declaration needs confirmation before implementation.
- GitNexus found the legacy `WorkflowStore` and `WorkflowExecutor` definitions but did not surface a reliable backend execution flow for the route, so code-level context and impact reports are required before changing those symbols.
- Pre-change GitNexus impact: replacing `WorkflowExecutor` is LOW risk with four direct test importers. Replacing `WorkflowStore` is MEDIUM risk with five direct importers: the executor, human-review step, and three test modules. No indexed process flow was reported.
- GitNexus could not resolve the `run_workflow` handler or route despite its source presence, so router impact must be verified by focused router tests and a post-change API impact/detect-changes review.
