"""Adapters from local execution receipts to the canonical tool evidence ledger."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def tool_receipt_from_local(receipt: Mapping[str, Any], *, tool_call_id: str | None = None) -> dict[str, Any]:
    value = dict(receipt)
    value.update({"tool_name": value.get("capability", "local.unknown"), "receipt_kind": "local_execution"})
    if tool_call_id is not None:
        value["tool_call_id"] = tool_call_id
    return {
        "tool_name": value["tool_name"],
        "receipt_kind": "tool",
        "tool_call_id": value.get("tool_call_id"),
        "local_execution_receipt": value,
    }


@dataclass(frozen=True, slots=True)
class LocalExecutionReceipt:
    """Stable, caller-safe evidence returned by a device execution."""

    capability: str
    request_hash: str
    policy_version: str
    consent_decision: str
    status: str
    started_at: datetime | str
    finished_at: datetime | str
    runtime_version: str
    exit_code: int | None = None
    stdout_hash: str | None = None
    stderr_hash: str | None = None
    artifact_handles: tuple[str, ...] = ()

    def as_mapping(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "request_hash": self.request_hash,
            "policy_version": self.policy_version,
            "consent_decision": self.consent_decision,
            "status": self.status,
            "started_at": self.started_at.isoformat() if isinstance(self.started_at, datetime) else self.started_at,
            "finished_at": self.finished_at.isoformat() if isinstance(self.finished_at, datetime) else self.finished_at,
            "runtime_version": self.runtime_version,
            "exit_code": self.exit_code,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "artifact_handles": list(self.artifact_handles),
        }
