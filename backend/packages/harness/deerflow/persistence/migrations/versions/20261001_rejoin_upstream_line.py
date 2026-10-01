"""rejoin the upstream v2.1.0 runtime line with the local unified chain

Revision ID: 20261001_rejoin_upstream_line
Revises: 20260918_knowledge_publish_eval_gate, 0025_repair_run_change_seq
Create Date: 2026-10-01

The deer-flow v2.1.0 sync extended the upstream runtime chain linearly past
``0018_oauth_identity_pg_partial`` (``0019_projects`` .. ``0025_repair_run_change_seq``).
Locally that same ``0018`` revision had already been joined into the unified
chain by ``20260908_unify_migration_chains``, whose line continued through the
AgentPlatform control-plane revisions up to
``20260918_knowledge_publish_eval_gate``. After the sync the script directory
therefore branched at ``0018`` again and exposed two heads:
``0025_repair_run_change_seq`` (upstream tail) and
``20260918_knowledge_publish_eval_gate`` (local tail).

This revision is the v2.1.0 convergence re-join: it merges both heads back
into a single forward-only head (the follow-up to ``20260908_unify_migration_chains``
for the second round of chain divergence). It carries no DDL — the two parent
lines touch disjoint schema families (the upstream tail adds runtime-family
projects / thread incarnation / batch acceptance / occurrence-seq /
run-change-clock / user-preferences / project-documents schema; the local tail
adds the AgentPlatform control-plane knowledge/device schema), and every
step on both lines is idempotent or inspector-guarded, so databases stamped
anywhere on either line converge through the missing ancestors to this one
head. Existing databases are never restamped below their recorded revision
(forward-only discipline); alembic simply applies whichever ancestors each
database is still missing.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20261001_rejoin_upstream_line"
down_revision: str | Sequence[str] | None = (
    "20260918_knowledge_publish_eval_gate",
    "0025_repair_run_change_seq",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two post-sync heads; no DDL (disjoint schema families)."""


def downgrade() -> None:
    """Split back into the pre-convergence heads (never executed in practice)."""
