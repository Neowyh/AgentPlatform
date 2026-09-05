# Migration acceptance report

## Scope

This report records the database migration evidence for the DeerFlow
convergence branch. The branch currently has two intentionally separate
Alembic script trees:

| Database boundary | Migration tree | Current head | Ownership |
|---|---|---|---|
| AgentPlatform control plane | `backend/packages/harness/ideer/persistence/migrations` | `20260828_run_snapshot_selection_role` | resources, workflow governance, users and enterprise control-plane tables |
| DeerFlow runtime | `backend/packages/harness/deerflow/persistence/migrations` | `0018_oauth_identity_pg_partial` | runtime runs, scheduler, MCP tasks, sub-agent batches and runtime auth tables |

The trees each have one head. They are not presented as a single merged
revision chain because they own different schema boundaries and are stamped
by different bootstrap paths. A future merge must be an explicit forward-only
revision decision, not a rewrite of either history.

## Evidence collected

| Check | Result | Evidence |
|---|---|---|
| AgentPlatform migration heads | passed | `alembic -c packages/harness/ideer/persistence/migrations/alembic.ini heads` → `20260828_run_snapshot_selection_role (head)` |
| DeerFlow migration heads | passed | `alembic -c packages/harness/deerflow/persistence/migrations/alembic.ini heads` → `0018_oauth_identity_pg_partial (head)` |
| Existing local SQLite revision | passed | `alembic ... current` reports `20260828_run_snapshot_selection_role (head)` |
| Migration schema focused suite | partial | 29 tests passed; `test_stamp_alembic_head_interaction` is incomplete in this sandbox because the async test cannot load a suitable async pytest plugin (the explicit plugin run exceeded the 60s guard) |
| Fresh SQLite migration path | passed for covered cases | 29-test migration schema suite exercises fresh upgrade, downgrade/upgrade steps and revision shape checks |
| Existing AgentPlatform DB | incomplete | Local DB is present and stamped at the AgentPlatform head; full row-count/resource/run-history comparison is still pending |
| PostgreSQL fresh/existing fixtures | not run | No PostgreSQL test endpoint is configured in this environment |

## Gate status

This is an evidence ledger, not a release sign-off. Gate 5 remains **open**
until an existing AgentPlatform database and PostgreSQL fresh/existing fixtures
have completed schema, constraint, JSON semantics, RunStore, ResourceService,
scheduler and durable-batch checks.

