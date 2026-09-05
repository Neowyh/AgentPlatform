"""AgentPlatform resource-governance service seam.

The implementation remains in the transitional harness while the Resource
control plane is extracted from ``ideer``.  Gateway code imports this seam so
the eventual move changes one module boundary instead of every caller.
"""

from ideer.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceApprovalRequired,
    ResourceConflict,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceService,
    VisibilityClosureError,
)

__all__ = [
    "ResourceAction",
    "ResourceActor",
    "ResourceApprovalRequired",
    "ResourceConflict",
    "ResourceNotFound",
    "ResourcePermissionDenied",
    "ResourceService",
    "VisibilityClosureError",
]
