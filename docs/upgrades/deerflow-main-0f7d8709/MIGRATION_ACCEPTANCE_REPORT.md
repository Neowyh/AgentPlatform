# Migration acceptance report

## Scope

This report records the database migration evidence for the DeerFlow
convergence branch. The branch currently has two intentionally separate
Alembic script trees:

| Database boundary | Migration tree | Current head | Ownership |
|---|---|---|---|
| AgentPlatform control plane | `backend/app/agentplatform/persistence/migrations` | `20260828_run_snapshot_selection_role` | resources, workflow governance, users and enterprise control-plane tables |
| DeerFlow runtime | `backend/packages/harness/deerflow/persistence/migrations` | `0018_oauth_identity_pg_partial` | runtime runs, scheduler, MCP tasks, sub-agent batches and runtime auth tables |

The trees each have one head. They remain separate revision histories, but the
DeerFlow runtime now records its head in `deerflow_alembic_version` rather than
the control-plane `alembic_version` table. This is the forward-only bridge for
the dual-runtime period: legacy DeerFlow-only rows are adopted once, while an
AgentPlatform date-based head is never interpreted as a DeerFlow revision.
The histories are therefore not rewritten or falsely joined.

## Evidence collected

| Check | Result | Evidence |
|---|---|---|
| AgentPlatform migration heads | passed | `alembic -c app/agentplatform/persistence/migrations/alembic.ini heads` → `20260828_run_snapshot_selection_role (head)` |
| DeerFlow migration heads | passed | `alembic -c packages/harness/deerflow/persistence/migrations/alembic.ini heads` → `0018_oauth_identity_pg_partial (head)` |
| Version-table isolation bridge | passed | Dedicated `deerflow_alembic_version` config/env path plus legacy adoption tests (3 passed) and bootstrap URL/config tests (8 passed) |
| Existing local SQLite revision | passed | `alembic ... current` reports `20260828_run_snapshot_selection_role (head)` |
| Migration schema focused suite | passed | Migration-version, migration-environment, version-table isolation, and existing-database bootstrap regression tests pass; the async SQLite cases were run outside the restricted sandbox because its cross-thread event-loop wakeup is unavailable |
| Fresh SQLite migration path | passed for covered cases | 29-test migration schema suite exercises fresh upgrade, downgrade/upgrade steps and revision shape checks |
| Workflow V2 runtime namespace contract | passed for covered cases | DeerFlow ORM mappings match the six-table Alembic contract; combined DeerFlow metadata creates the six Workflow V2 tables alongside AgentPlatform resource/RBAC tables; generic DeerFlow model exports intentionally exclude the enterprise Workflow family |
| Workflow Store model cutover | focused passed | Store unit suite 22 passed with Store/Worker/RunRecord/resource-governance production imports using `deerflow.persistence.models.workflow_v2`; async database-backed integration remains incomplete in this sandbox |
| Existing local Workflow V2 schema vs DeerFlow ORM | passed | Read-only inspection of `backend/.ideer/data/ideer.db` matched all six Workflow V2 table column sets, including `workflow_definition_versions.department_id` |
| Existing AgentPlatform DB | passed on a temporary copy | `backend/.ideer/data/ideer.db` copied to a temporary SQLite file; `init_engine` upgraded it to `0018_oauth_identity_pg_partial` while retaining the control-plane head. Before/after fingerprints were identical: `resources` 73 rows (`200342c973d12c8ea3e74916532b32ec5d33382b071153b008a5ebde5316a48b`), `resource_versions` 77 (`e295c5ab327021355c7cd054838c973a5d679c214ef05decdb83f9216cab2bde`), and `runs` 7 (`36807132f3ecf6324f433605153c94a3e8c93c928f8639f59386846ca17da9c3`). The `users_ext` role distribution remained `super_admin: 1`; `RunRepository.aggregate_tokens_by_thread()` read successfully; no source DB was modified. |
| PostgreSQL fresh/existing fixtures | passed (2026-09-08) | postgres:16 container; C1 fresh: enterprise tree `upgrade head` (26 tables) + runtime bootstrap (head `0018_oauth_identity_pg_partial`, 40 tables total) + bundled seed (73 resources / 61 edges) + two-phase gateway boot (initialize admin → restart seed) + ResourceService closure walk + WorkflowV2Store canonical run with JSON roundtrip + durable runtime tables present. C2 existing: legacy SQLite copy upgraded on both trees, data copied into PG, normalized per-table fingerprints match (resources 73 / resource_versions 77 / runs 7), roles preserved, runs aggregate readable |

## Gate status

Gate 5 is **closed** (2026-09-08): existing-SQLite and PostgreSQL
fresh/existing fixtures have all passed. The PG acceptance surfaced and fixed
three real dialect defects in the enterprise migration assets: a boolean
column with a numeric server default (`f3a2b1c4d5e6`, now `sa.false()`), an
unconditional `sqlite_master` index lookup (`drop_deleted_at`, now the
SQLAlchemy inspector), and the async migration path never committing plus
Alembic's 32-char `version_num` rejecting this tree's 33-char date-based
revision ids (`env.py` now pre-creates a VARCHAR(255) version table and
commits). All fixes are no-ops for already-migrated SQLite databases; the
migration-focused suites (persistence 96, migrations-env 19, version-table
isolation) remain green.

The earlier Workflow SQLite timeout was isolated outside pytest: a plain
`create_async_engine("sqlite+aiosqlite://...")` hangs on the first
`engine.begin()` even with no imported ORM metadata, while synchronous SQLite
connect/create completes in about 0.4 seconds. A minimal
`call_soon_threadsafe` reproducer shows the same behavior, identifying the
blocker as the sandbox's aiosqlite connection-thread environment rather than a
schema or Workflow event-sink regression. The production PRAGMA hooks use
aiosqlite's supported `run_async` bridge, and the successful outside-sandbox
bootstrap tests cover that path.
