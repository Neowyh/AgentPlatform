# Workflow YAML v2

Workflow definitions are governed YAML graphs with `schema_version: 2`.
Definitions are parsed and validated by `ideer.workflows.v2.parser`, compiled
to LangGraph by `WorkflowGraphCompiler`, and executed by the durable worker.

Every saved definition creates an immutable version. Runs reference the exact
definition version and use `wf:{run_id}` as their checkpoint thread. The API
creates queued runs; the worker owns execution, checkpointing, events, and
terminal state.

The public lifecycle endpoints are:

- `POST /api/workflows/{name}/run`
- `GET /api/workflows/{name}/runs/{run_id}`
- `GET /api/workflows/{name}/runs/{run_id}/events?after_seq=N`
- `POST /api/workflows/{name}/runs/{run_id}/commands`

Commands are idempotent and currently support `resume` and `cancel`.
