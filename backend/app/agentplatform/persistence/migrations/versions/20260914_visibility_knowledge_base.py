"""allow KnowledgeBase resources in visibility applications"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_visibility_knowledge_base"
down_revision: str | None = "20260913_knowledge_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("visibility_applications"):
        return
    constraints = {item.get("name") for item in inspector.get_check_constraints("visibility_applications")}
    with op.batch_alter_table("visibility_applications", schema=None) as batch:
        if "ck_visibility_app_resource_type" in constraints:
            batch.drop_constraint("ck_visibility_app_resource_type", type_="check")
        batch.create_check_constraint(
            "ck_visibility_app_resource_type",
            "resource_type IN ('tool', 'skill', 'workflow', 'agent', 'knowledge_base')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("visibility_applications"):
        return
    constraints = {item.get("name") for item in inspector.get_check_constraints("visibility_applications")}
    with op.batch_alter_table("visibility_applications", schema=None) as batch:
        if "ck_visibility_app_resource_type" in constraints:
            batch.drop_constraint("ck_visibility_app_resource_type", type_="check")
        batch.create_check_constraint(
            "ck_visibility_app_resource_type",
            "resource_type IN ('tool', 'skill', 'workflow', 'agent')",
        )
