"""AgentPlatform resource-governance service seam.

The Resource control plane is owned by AgentPlatform.  Gateway code imports
this seam so future moves change one module boundary instead of every caller.
"""

from app.agentplatform.resources.service import (
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
