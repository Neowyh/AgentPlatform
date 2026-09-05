"""AgentPlatform's enterprise boundary for the DeerFlow runtime.

The package deliberately depends only on ``deerflow-extension-api``. Resource
governance, caller authorization and network policy stay outside the runtime
fork and cross the boundary through small, serializable projections.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from deerflow_extension_api import ExtensionRegistry, extension

from agentplatform_extension.evidence import (
    AuthorizationContext,
    ResourceSnapshotRef,
    build_run_evidence_envelope,
)
from agentplatform_extension.network_policy import NetworkPolicy


@extension(api="0.2", name="agentplatform")
def install(registry: ExtensionRegistry, config: Mapping[str, Any]) -> None:
    """Install the enterprise boundary.

    The runtime remains generic: the extension is registered only when the
    host explicitly enables it. Policy objects are immutable projections and
    never contain caller credentials or private owner state.
    """

    # Keep registration intentionally small until the host supplies the
    # resource resolver service. The exported builders are usable by the
    # gateway/workflow adapters without importing DeerFlow internals.
    _ = registry
    _ = config


__all__ = [
    "AuthorizationContext",
    "NetworkPolicy",
    "ResourceSnapshotRef",
    "build_run_evidence_envelope",
    "install",
]
