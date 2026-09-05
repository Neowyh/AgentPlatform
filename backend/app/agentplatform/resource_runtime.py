"""AgentPlatform Resource runtime seam.

Resource catalog semantics are owned by AgentPlatform.  During the staged
runtime extraction the filesystem/runtime implementation remains in the
compatibility harness, but Gateway and worker callers use this single seam.
"""

from ideer.resources.bundled import seed_bundled_resources
from ideer.resources.publisher import ResourcePublisher, write_agent_draft_source
from ideer.resources.reconciliation import reconcile_catalog_storage
from ideer.resources.retention import build_retention_report
from ideer.resources.runtime import CanonicalResourceLoader, ResourceRuntimeError, load_validated_agent_definition
from ideer.resources.storage import ResourceStorage, StorageConflict, StorageValidationError

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
