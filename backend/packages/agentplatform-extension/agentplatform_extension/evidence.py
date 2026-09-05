"""Run Evidence Envelope projections owned by AgentPlatform."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from deerflow_extension_api import ExtensionData, RunEvidenceEnvelope, TaskInfo, TaskOutcome

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ResourceSnapshotRef:
    """Immutable UUID/version/hash identity frozen at Run creation."""

    resource_id: str
    version: int
    content_hash: str
    selection_role: str = "resolved"

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("resource_id must be non-empty")
        if self.version < 1:
            raise ValueError("resource version must be positive")
        if not _SHA256_RE.fullmatch(self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 digest")
        if self.selection_role not in {"root", "resolved", "preferred"}:
            raise ValueError(f"unsupported selection role: {self.selection_role}")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "version": self.version,
            "content_hash": self.content_hash,
            "selection_role": self.selection_role,
        }


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Caller-scoped authorization projection.

    Credentials are intentionally not represented. A shared Agent may carry
    the caller identity and effective permissions, but never the resource
    owner's private credential or memory identity.
    """

    caller_user_id: str
    effective_agent_id: str
    policy_revision: str
    allowed_tools: tuple[str, ...] = ()
    memory_scope: str | None = None

    def __post_init__(self) -> None:
        if not self.caller_user_id or not self.effective_agent_id or not self.policy_revision:
            raise ValueError("caller, effective agent and policy revision are required")
        if self.memory_scope is not None and self.memory_scope != self.caller_user_id:
            raise ValueError("memory_scope must remain caller-scoped")

    def as_mapping(self) -> dict[str, Any]:
        return {
            "caller_user_id": self.caller_user_id,
            "effective_agent_id": self.effective_agent_id,
            "policy_revision": self.policy_revision,
            "allowed_tools": list(self.allowed_tools),
            "memory_scope": self.memory_scope or self.caller_user_id,
        }


class EvidenceLifecycleContributor:
    """Bind AgentPlatform projections to DeerFlow's task-scoped envelope."""

    def __init__(
        self,
        *,
        snapshots: Iterable[ResourceSnapshotRef | Mapping[str, Any]],
        authorization: AuthorizationContext,
        runtime_assembly_fingerprint: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self._snapshots = tuple(snapshots)
        self._authorization = authorization
        self._runtime_assembly_fingerprint = runtime_assembly_fingerprint
        self._trace_id = trace_id

    async def on_task_start(self, app_store: ExtensionData, task_store: ExtensionData, info: TaskInfo) -> None:
        del app_store
        task_store.set(
            build_run_evidence_envelope(
                run_id=info.run_id,
                thread_id=info.thread_id,
                snapshots=self._snapshots,
                authorization=self._authorization,
                runtime_assembly_fingerprint=self._runtime_assembly_fingerprint,
                trace_id=self._trace_id,
            )
        )

    async def on_task_stop(
        self,
        app_store: ExtensionData,
        task_store: ExtensionData,
        info: TaskInfo,
        outcome: TaskOutcome,
    ) -> None:
        del app_store, info
        envelope = task_store.get(RunEvidenceEnvelope)
        if envelope is not None:
            task_store.set(replace(envelope, outcome=outcome))


def _normalize_snapshots(snapshots: Iterable[ResourceSnapshotRef | Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for snapshot in snapshots:
        value = snapshot.as_mapping() if isinstance(snapshot, ResourceSnapshotRef) else dict(snapshot)
        ref = ResourceSnapshotRef(
            resource_id=str(value.get("resource_id", "")),
            version=int(value.get("version", 0)),
            content_hash=str(value.get("content_hash", "")),
            selection_role=str(value.get("selection_role", "resolved")),
        )
        if ref.resource_id in seen:
            raise ValueError(f"duplicate resource snapshot: {ref.resource_id}")
        seen.add(ref.resource_id)
        normalized.append(ref.as_mapping())
    return tuple(normalized)


def build_run_evidence_envelope(
    *,
    run_id: str,
    thread_id: str,
    snapshots: Iterable[ResourceSnapshotRef | Mapping[str, Any]],
    authorization: AuthorizationContext,
    runtime_assembly_fingerprint: str | None = None,
    trace_id: str | None = None,
    policy_revision: str | None = None,
    tool_receipts: Sequence[Mapping[str, Any]] = (),
    subagent_verification: Sequence[Mapping[str, Any]] = (),
    artifact_receipts: Sequence[Mapping[str, Any]] = (),
) -> RunEvidenceEnvelope:
    """Create the single evidence envelope shared by runtime and control plane."""

    if not run_id or not thread_id:
        raise ValueError("run_id and thread_id are required")
    return RunEvidenceEnvelope(
        run_id=run_id,
        thread_id=thread_id,
        trace_id=trace_id,
        resource_snapshots=_normalize_snapshots(snapshots),
        runtime_assembly_fingerprint=runtime_assembly_fingerprint,
        authorization_context=authorization.as_mapping(),
        policy_revision=policy_revision or authorization.policy_revision,
        tool_receipts=tuple(dict(item) for item in tool_receipts),
        subagent_verification=tuple(dict(item) for item in subagent_verification),
        artifact_receipts=tuple(dict(item) for item in artifact_receipts),
    )
