"""AgentPlatform Workflow V2 runtime seam.

Workflow V2 remains an AgentPlatform-owned product capability.  Until its
implementation is fully extracted from the compatibility harness, Gateway and
worker code import the complete public seam from this module.
"""

from ideer.workflows.v2.adapters import ActionAdapterRegistry, _CanonicalAgentAdapter, _ToolAdapter
from ideer.workflows.v2.compiler import WorkflowCancelled, WorkflowGraphCompiler
from ideer.workflows.v2.errors import (
    WorkflowInvalidRootsError,
    WorkflowMissingInputRootsError,
    WorkflowRunError,
    run_failure_payload,
)
from ideer.workflows.v2.file_roots import (
    collect_artifacts,
    make_host_resolver,
    render_roots,
    validate_read_roots,
    validate_workflow_roots,
    workflow_log_root,
    workflow_record_path,
)
from ideer.workflows.v2.parser import parse_workflow_v2
from ideer.workflows.v2.run_record import RunRecordWriter
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowPaused, WorkflowWorker, workflow_snapshot

__all__ = [
    "ActionAdapterRegistry",
    "RunRecordWriter",
    "WorkflowCancelled",
    "WorkflowGraphCompiler",
    "WorkflowInvalidRootsError",
    "WorkflowMissingInputRootsError",
    "WorkflowPaused",
    "WorkflowRunError",
    "WorkflowV2Store",
    "WorkflowWorker",
    "_CanonicalAgentAdapter",
    "_ToolAdapter",
    "collect_artifacts",
    "make_host_resolver",
    "parse_workflow_v2",
    "render_roots",
    "run_failure_payload",
    "validate_read_roots",
    "validate_workflow_roots",
    "workflow_log_root",
    "workflow_record_path",
    "workflow_snapshot",
]
