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
    EvidenceLifecycleContributor,
    ResourceSnapshotRef,
    RunEvidenceBinding,
    bind_run_evidence,
    build_run_evidence_envelope,
    current_run_evidence,
    record_local_execution_receipt,
    record_retrieval_receipt,
    record_subagent_verification,
    record_tool_receipt,
)
from agentplatform_extension.local_runtime import LocalAuthorization, LocalToolContributor
from agentplatform_extension.network_policy import NetworkPolicy


@extension(api="0.2", name="agentplatform")
def install(registry: ExtensionRegistry, config: Mapping[str, Any]) -> None:
    """Install the enterprise boundary.

    The runtime remains generic: the extension is registered only when the
    host explicitly enables it. Policy objects are immutable projections and
    never contain caller credentials or private owner state.
    """

    authorization = config.get("authorization")
    if config.get("dynamic_context") is True:
        registry.task_lifecycle(EvidenceLifecycleContributor())
        return
    if not isinstance(authorization, Mapping):
        return
    effective = frozenset(str(item) for item in authorization.get("allowed_tools", ()))
    registry.tools(LocalToolContributor(LocalAuthorization.from_capabilities(effective, device_online=bool(authorization.get("device_online", True)))))
    registry.task_lifecycle(
        EvidenceLifecycleContributor(
            snapshots=config.get("resource_snapshots", ()),
            authorization=AuthorizationContext(
                caller_user_id=str(authorization.get("caller_user_id", "")),
                effective_agent_id=str(authorization.get("effective_agent_id", "")),
                policy_revision=str(authorization.get("policy_revision", "")),
                allowed_tools=tuple(str(item) for item in authorization.get("allowed_tools", ())),
                memory_scope=(str(authorization["memory_scope"]) if "memory_scope" in authorization else None),
            ),
            runtime_assembly_fingerprint=(str(config["runtime_assembly_fingerprint"]) if "runtime_assembly_fingerprint" in config else None),
            trace_id=str(config["trace_id"]) if "trace_id" in config else None,
        )
    )


__all__ = [
    "AuthorizationContext",
    "EvidenceLifecycleContributor",
    "NetworkPolicy",
    "ResourceSnapshotRef",
    "RunEvidenceBinding",
    "build_run_evidence_envelope",
    "bind_run_evidence",
    "current_run_evidence",
    "record_subagent_verification",
    "record_tool_receipt",
    "record_retrieval_receipt",
    "record_local_execution_receipt",
    "install",
]
