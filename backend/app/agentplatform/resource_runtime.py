"""AgentPlatform Resource runtime seam.

Resource catalog semantics are owned by AgentPlatform.  Gateway and worker
callers import the implementation through this single seam instead of the
implementation submodules directly.
"""

from app.agentplatform.resources.bundled import seed_bundled_resources
from app.agentplatform.resources.publisher import ResourcePublisher, write_agent_draft_source
from app.agentplatform.resources.reconciliation import reconcile_catalog_storage
from app.agentplatform.resources.retention import build_retention_report
from app.agentplatform.resources.runtime import CanonicalResourceLoader, ResourceRuntimeError, load_validated_agent_definition
from app.agentplatform.resources.storage import ResourceStorage, StorageConflict, StorageValidationError

__all__ = [
    "CanonicalResourceLoader",
    "ResourcePublisher",
    "ResourceRuntimeError",
    "ResourceStorage",
    "StorageConflict",
    "StorageValidationError",
    "build_retention_report",
    "load_validated_agent_definition",
    "reconcile_catalog_storage",
    "seed_bundled_resources",
    "write_agent_draft_source",
]
