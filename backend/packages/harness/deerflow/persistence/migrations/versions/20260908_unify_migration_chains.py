"""merge AgentPlatform resource schema with DeerFlow upstream runtime

Revision ID: 20260908_unify_migration_chains
Revises: 20260828_run_snapshot_selection_role, 0018_oauth_identity_pg_partial
Create Date: 2026-09-08

Unifies the two formerly independent migration chains (the AgentPlatform
control-plane resource chain rooted at ``16147afec43b`` and the DeerFlow
runtime chain rooted at ``0001_baseline``) into a single forward-only chain
with one head, closing PATCH-006's dual version-table isolation.

This revision carries no DDL: the two parent chains create disjoint table
sets on every real path. The five shared core tables (``runs``,
``threads_meta``, ``run_events``, ``feedback``, ``users``) exist in both
chains' DDL, but on real databases they are created by the control-plane
chain (``c4d5e6f7a8b9``) -- whichever branch alembic traverses first -- and
the runtime baseline's own creates are inspector-guarded no-ops against them
(see the PATCH note in ``0001_baseline``). Every runtime-only table
(``channel_*``, ``agents``, ``mcp_tasks``, ``scheduled_tasks``,
``subagent_batches``, ``personal_access_tokens``) is created by the runtime
chain only. Production never executed ``0001_baseline.upgrade()`` unguarded
(the bootstrap stamps past it), so a from-scratch run of the merged chain
reproduces the exact table set existing deployments have.

Existing databases whose DeerFlow revisions were tracked in the separate
``deerflow_alembic_version`` table are bridged to this chain by
``bootstrap_schema`` / ``env.py`` before ``upgrade head`` runs.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260908_unify_migration_chains"
down_revision: str | Sequence[str] | None = (
    "20260828_run_snapshot_selection_role",
    "0018_oauth_identity_pg_partial",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two parent chains; no DDL (disjoint table sets)."""


def downgrade() -> None:
    """Split back into the two independent chain heads."""
