"""Run Evidence Envelope projections owned by AgentPlatform."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any

from deerflow_extension_api import ExtensionData, RunEvidenceEnvelope, TaskInfo, TaskOutcome, set_runtime_evidence_hooks

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_KNOWLEDGE_CITATION_RE = re.compile(r"\[citation:[^\]]+\]\(evidence://([A-Za-z0-9_-]+)\)")
_FENCED_CODE_RE = re.compile(r"(^|\n)(`{3,}|~{3,})[^\n]*(?:\n[\s\S]*?\n\2[^\n]*(?=\n|$)|[\s\S]*$)", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"(`+)[\s\S]*?\1")


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


@dataclass(frozen=True, slots=True)
class DelegationEvidenceContext:
    """Parent call identity inherited by one delegated execution."""

    parent_tool_receipt_id: str
    child_agent_id: str | None = None


_delegation_evidence_context: ContextVar[DelegationEvidenceContext | None] = ContextVar(
    "agentplatform_delegation_evidence_context",
    default=None,
)


@contextmanager
def bind_delegation_evidence(context: DelegationEvidenceContext) -> Iterator[None]:
    token = _delegation_evidence_context.set(context)
    try:
        yield
    finally:
        _delegation_evidence_context.reset(token)


def current_delegation_evidence() -> DelegationEvidenceContext | None:
    return _delegation_evidence_context.get()


@dataclass(frozen=True, slots=True)
class RunEvidenceBinding:
    """Per-run evidence projected into the extension lifecycle."""

    snapshots: tuple[ResourceSnapshotRef | Mapping[str, Any], ...]
    authorization: AuthorizationContext
    runtime_assembly_fingerprint: str | None = None
    trace_id: str | None = None
    tool_receipts: tuple[Mapping[str, Any], ...] = ()
    retrieval_receipts: tuple[Mapping[str, Any], ...] = ()
    subagent_verification: tuple[Mapping[str, Any], ...] = ()
    artifact_receipts: tuple[Mapping[str, Any], ...] = ()
    run_id: str | None = None
    knowledge_scope: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshots", tuple(self.snapshots))
        object.__setattr__(self, "tool_receipts", tuple(dict(item) for item in self.tool_receipts))
        object.__setattr__(self, "retrieval_receipts", tuple(dict(item) for item in self.retrieval_receipts))
        object.__setattr__(self, "subagent_verification", tuple(dict(item) for item in self.subagent_verification))
        object.__setattr__(self, "artifact_receipts", tuple(dict(item) for item in self.artifact_receipts))

    def as_mapping(self) -> dict[str, Any]:
        """Return the caller-safe projection suitable for Run metadata.

        The projection deliberately contains only immutable resource identities,
        authorization attributes and fingerprints. Credentials and other
        request-local secrets never cross into durable Run metadata.
        """
        return {
            "resource_snapshots": list(_normalize_snapshots(self.snapshots)),
            "authorization_context": self.authorization.as_mapping(),
            "runtime_assembly_fingerprint": self.runtime_assembly_fingerprint,
            "trace_id": self.trace_id,
            "policy_revision": self.authorization.policy_revision,
            "tool_receipts": list(self.tool_receipts),
            "retrieval_receipts": list(self.retrieval_receipts),
            "subagent_verification": list(self.subagent_verification),
            "artifact_receipts": list(self.artifact_receipts),
            "run_id": self.run_id,
            "knowledge_scope": dict(self.knowledge_scope) if self.knowledge_scope is not None else None,
        }


_run_evidence_binding: ContextVar[RunEvidenceBinding | None] = ContextVar(
    "agentplatform_run_evidence_binding",
    default=None,
)


@contextmanager
def bind_run_evidence(binding: RunEvidenceBinding) -> Iterator[None]:
    """Bind one immutable evidence projection to the current run task."""
    token = _run_evidence_binding.set(binding)
    try:
        yield
    finally:
        _run_evidence_binding.reset(token)


def current_run_evidence() -> RunEvidenceBinding | None:
    """Return the binding inherited by the current async task, if any."""
    return _run_evidence_binding.get()


class RuntimeEvidenceHooks:
    """Adapt AgentPlatform evidence functions to the DeerFlow host contract."""

    def current_run_evidence(self) -> RunEvidenceBinding | None:
        return current_run_evidence()

    def record_subagent_verification(self, verification: Mapping[str, Any]) -> None:
        record_subagent_verification(verification)

    def record_tool_receipt(self, receipt: Mapping[str, Any]) -> None:
        record_tool_receipt(receipt)

    def record_retrieval_citations(self, content: str) -> None:
        record_retrieval_citations(content)

    def bind_delegation_evidence(self, parent_tool_receipt_id: str, child_agent_id: str | None = None):
        return bind_delegation_evidence(DelegationEvidenceContext(parent_tool_receipt_id, child_agent_id))

    def record_delegated_retrieval_receipts(
        self,
        receipts: Iterable[Mapping[str, Any]],
        *,
        parent_tool_receipt_id: str,
        child_task_id: str,
        child_agent_id: str | None = None,
    ) -> int:
        return record_delegated_retrieval_receipts(
            receipts,
            parent_tool_receipt_id=parent_tool_receipt_id,
            child_task_id=child_task_id,
            child_agent_id=child_agent_id,
        )


set_runtime_evidence_hooks(RuntimeEvidenceHooks())


def _append_evidence_item(field: str, item: Mapping[str, Any]) -> None:
    """Append runtime-owned evidence to the current binding, if one exists."""

    binding = current_run_evidence()
    if binding is None:
        return
    values = list(getattr(binding, field))
    normalized = dict(item)
    identity = _evidence_item_identity(normalized)
    if any(_evidence_item_identity(value) == identity for value in values):
        return
    values.append(normalized)
    _run_evidence_binding.set(replace(binding, **{field: tuple(values)}))


def _evidence_item_identity(item: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return the event identity used for retry/re-delivery idempotency.

    Query hashes are deliberately absent: two calls in one or different Runs
    may ask the same question and must remain independently auditable.
    """

    for field in ("receipt_id", "tool_call_id", "event_id"):
        value = item.get(field)
        if value:
            return (field, str(value))
    if item.get("task_id"):
        return ("task_id", str(item["task_id"]), str(item.get("status", "")))
    return ("value", repr(sorted(item.items(), key=lambda pair: str(pair[0]))))


def record_tool_receipt(receipt: Mapping[str, Any]) -> None:
    """Record a runtime-stamped tool receipt in the active Run envelope."""

    _append_evidence_item("tool_receipts", receipt)
    if receipt.get("tool_name") == "knowledge_search":
        binding = current_run_evidence()
        if binding is not None:
            values = list(binding.retrieval_receipts)
            for index in range(len(values) - 1, -1, -1):
                item = values[index]
                if item.get("parent_tool_receipt_id") is None:
                    values[index] = {
                        **item,
                        "tool_call_id": receipt.get("tool_call_id"),
                        "parent_tool_receipt_id": receipt.get("tool_call_id"),
                    }
                    _run_evidence_binding.set(replace(binding, retrieval_receipts=tuple(values)))
                    break


def record_retrieval_receipt(receipt: Mapping[str, Any]) -> None:
    """Record a retrieval receipt only inside the active run evidence binding."""

    _append_evidence_item("retrieval_receipts", receipt)


def record_delegated_retrieval_receipts(
    receipts: Iterable[Mapping[str, Any]],
    *,
    parent_tool_receipt_id: str,
    child_task_id: str,
    child_agent_id: str | None = None,
) -> int:
    """Adopt child retrieval evidence into the active parent Run.

    Adoption is fail-closed. A child receipt is usable only when it carries
    the current Run identity and a logical KB in the parent's frozen scope.
    Missing parent linkage or a scope mismatch is retained as an unavailable
    delegation status by the caller, never as a verifiable citation.
    """

    binding = current_run_evidence()
    if binding is None or not parent_tool_receipt_id or not child_task_id:
        return 0
    scope = binding.knowledge_scope
    bindings = scope.get("bindings") if isinstance(scope, Mapping) else None
    if not isinstance(bindings, Mapping):
        _append_evidence_item(
            "subagent_verification",
            {
                "task_id": child_task_id,
                "status": "UNAVAILABLE",
                "reason": "delegated_retrieval_unavailable",
                "parent_tool_receipt_id": parent_tool_receipt_id,
            },
        )
        return 0
    allowed = {str(value) for value in bindings}
    allowed.update(str(value) for value in bindings.values())
    adopted = 0
    for raw in receipts:
        receipt = dict(raw)
        if receipt.get("run_id") != binding.run_id:
            continue
        logical_kb = receipt.get("logical_knowledge_base")
        if str(logical_kb) not in allowed:
            continue
        if not receipt.get("receipt_id") or not receipt.get("parent_tool_receipt_id"):
            continue
        if receipt["parent_tool_receipt_id"] != parent_tool_receipt_id:
            continue
        record_retrieval_receipt(
            {
                **receipt,
                "delegated": True,
                "child_task_id": child_task_id,
                "child_agent_id": child_agent_id,
                "parent_tool_receipt_id": parent_tool_receipt_id,
            }
        )
        adopted += 1
    if adopted == 0:
        _append_evidence_item(
            "subagent_verification",
            {
                "task_id": child_task_id,
                "status": "UNAVAILABLE",
                "reason": "delegated_retrieval_unavailable",
                "parent_tool_receipt_id": parent_tool_receipt_id,
            },
        )
    return adopted


def record_retrieval_citations(text: str) -> None:
    """Mark only archived retrieval items explicitly cited by a final message."""

    binding = current_run_evidence()
    if binding is None:
        return
    cited_ids = set(_KNOWLEDGE_CITATION_RE.findall(_mask_code(text)))
    if not cited_ids:
        return
    receipts = list(binding.retrieval_receipts)
    changed = False
    for receipt_index, receipt in enumerate(receipts):
        items = receipt.get("items")
        if not isinstance(items, list):
            continue
        cited = [str(item["evidence_id"]) for item in items if isinstance(item, dict) and item.get("evidence_id") in cited_ids]
        if cited:
            receipts[receipt_index] = {**receipt, "cited_item_ids": cited}
            changed = True
    if changed:
        _run_evidence_binding.set(replace(binding, retrieval_receipts=tuple(receipts)))


def _mask_code(text: str) -> str:
    def mask(match: re.Match[str]) -> str:
        return match.group(1) + re.sub(r"[^\n]", " ", match.group(0)[len(match.group(1)) :])

    fenced = _FENCED_CODE_RE.sub(mask, text)
    return _INLINE_CODE_RE.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), fenced)


def record_local_execution_receipt(receipt: Mapping[str, Any], *, tool_call_id: str | None = None) -> None:
    """Attach a device receipt as a child of the canonical tool receipt ledger."""
    from agentplatform_extension.local_runtime.receipts import tool_receipt_from_local

    record_tool_receipt(tool_receipt_from_local(receipt, tool_call_id=tool_call_id))


def record_subagent_verification(verification: Mapping[str, Any]) -> None:
    """Record a sub-agent verification verdict in the active Run envelope."""

    _append_evidence_item("subagent_verification", verification)


class EvidenceLifecycleContributor:
    """Bind AgentPlatform projections to DeerFlow's task-scoped envelope."""

    def __init__(
        self,
        *,
        snapshots: Iterable[ResourceSnapshotRef | Mapping[str, Any]] = (),
        authorization: AuthorizationContext | None = None,
        runtime_assembly_fingerprint: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self._snapshots = tuple(snapshots)
        self._authorization = authorization
        self._runtime_assembly_fingerprint = runtime_assembly_fingerprint
        self._trace_id = trace_id

    async def on_task_start(self, app_store: ExtensionData, task_store: ExtensionData, info: TaskInfo) -> None:
        del app_store
        binding = current_run_evidence()
        if binding is None:
            if self._authorization is None:
                return
            binding = RunEvidenceBinding(
                snapshots=self._snapshots,
                authorization=self._authorization,
                runtime_assembly_fingerprint=self._runtime_assembly_fingerprint,
                trace_id=self._trace_id,
            )
        task_store.set(
            build_run_evidence_envelope(
                run_id=info.run_id,
                thread_id=info.thread_id,
                snapshots=binding.snapshots,
                authorization=binding.authorization,
                runtime_assembly_fingerprint=binding.runtime_assembly_fingerprint,
                trace_id=binding.trace_id,
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
            binding = current_run_evidence()
            task_store.set(
                replace(
                    envelope,
                    outcome=outcome,
                    tool_receipts=binding.tool_receipts if binding is not None else envelope.tool_receipts,
                    retrieval_receipts=binding.retrieval_receipts if binding is not None else envelope.retrieval_receipts,
                    subagent_verification=binding.subagent_verification if binding is not None else envelope.subagent_verification,
                    artifact_receipts=binding.artifact_receipts if binding is not None else envelope.artifact_receipts,
                )
            )


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
    retrieval_receipts: Sequence[Mapping[str, Any]] = (),
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
        retrieval_receipts=tuple(dict(item) for item in retrieval_receipts),
        subagent_verification=tuple(dict(item) for item in subagent_verification),
        artifact_receipts=tuple(dict(item) for item in artifact_receipts),
    )
