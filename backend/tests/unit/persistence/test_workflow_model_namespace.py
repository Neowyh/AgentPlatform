"""Contracts for the DeerFlow-owned Workflow V2 metadata boundary."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from app.agentplatform import rbac_models as _rbac_models  # noqa: F401
from app.agentplatform import resource_models as _resource_models  # noqa: F401
from deerflow.persistence.base import Base as DeerFlowBase
from deerflow.persistence.models.workflow_v2 import (
    WorkflowCommandRow as DeerFlowWorkflowCommandRow,
)
from deerflow.persistence.models.workflow_v2 import (
    WorkflowDefinitionVersionRow as DeerFlowWorkflowDefinitionVersionRow,
)
from deerflow.persistence.models.workflow_v2 import (
    WorkflowLeaseAuditRow as DeerFlowWorkflowLeaseAuditRow,
)
from deerflow.persistence.models.workflow_v2 import (
    WorkflowTaskRow as DeerFlowWorkflowTaskRow,
)
from deerflow.persistence.models.workflow_v2 import (
    WorkflowV2EventRow as DeerFlowWorkflowV2EventRow,
)
from deerflow.persistence.models.workflow_v2 import (
    WorkflowV2RunRow as DeerFlowWorkflowV2RunRow,
)

_RUNTIME_MODELS = (
    DeerFlowWorkflowDefinitionVersionRow,
    DeerFlowWorkflowV2RunRow,
    DeerFlowWorkflowTaskRow,
    DeerFlowWorkflowLeaseAuditRow,
    DeerFlowWorkflowV2EventRow,
    DeerFlowWorkflowCommandRow,
)

_EXPECTED_COLUMNS = {
    "workflow_definition_versions": {
        "id",
        "workflow_name",
        "version",
        "definition",
        "content_hash",
        "created_by",
        "department_id",
        "created_at",
    },
    "workflow_v2_runs": {
        "run_id",
        "workflow_name",
        "workflow_resource_id",
        "definition_version",
        "checkpoint_thread_id",
        "status",
        "inputs",
        "model_name",
        "snapshot",
        "runner_tool_groups",
        "event_seq",
        "error",
        "created_by",
        "department_id",
        "created_at",
        "updated_at",
    },
    "workflow_tasks": {
        "task_id",
        "run_id",
        "status",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
        "attempts",
        "cancel_requested",
        "resume_command_id",
    },
    "workflow_lease_audit": {"id", "run_id", "task_id", "event_type", "worker_id", "attempt", "created_at"},
    "workflow_v2_events": {"id", "run_id", "seq", "event_type", "payload", "created_at"},
    "workflow_commands": {"command_id", "run_id", "command_type", "payload", "created_by", "created_at"},
}


def test_runtime_workflow_mappings_match_the_migration_table_contract() -> None:
    for runtime_model in _RUNTIME_MODELS:
        runtime_table = runtime_model.__table__
        assert set(runtime_table.columns.keys()) == _EXPECTED_COLUMNS[runtime_table.name]


def test_workflow_tables_are_in_combined_runtime_metadata_but_not_generic_deerflow_registry() -> None:
    engine = create_engine("sqlite:///:memory:")
    DeerFlowBase.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())

    assert {model.__tablename__ for model in _RUNTIME_MODELS} <= tables
    assert "resources" in tables
    assert "users_ext" in tables
    assert "departments" in tables

    # Workflow tables depend on AgentPlatform's resources table and therefore
    # are deliberately not imported by deerflow.persistence.models.__init__.
    from deerflow.persistence.models import __all__ as deerflow_model_exports

    assert "WorkflowV2RunRow" not in deerflow_model_exports
