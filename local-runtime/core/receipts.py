"""Immutable local execution receipts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class LocalExecutionReceipt:
    run_id: str
    task_id: str
    capability: str
    policy_decision: str
    status: str
    payload_hash: str
    result_hash: str | None = None
    policy_version: str = "1"
    consent_decision: str | None = None
    stdout_hash: str | None = None
    stderr_hash: str | None = None
    artifact_refs: tuple[str, ...] = ()
    runtime_version: str | None = None
    exit_code: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def request_hash(self) -> str:
        """Protocol name for the M7-compatible payload hash."""
        return self.payload_hash

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "capability": self.capability,
            "policy_decision": self.policy_decision,
            "status": self.status,
            "payload_hash": self.payload_hash,
            "request_hash": self.request_hash,
            "result_hash": self.result_hash,
            "policy_version": self.policy_version,
            "consent_decision": self.consent_decision,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "artifact_refs": list(self.artifact_refs),
            "runtime_version": self.runtime_version,
            "exit_code": self.exit_code,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


def content_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
