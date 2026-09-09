"""Immutable local execution receipts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "capability": self.capability,
            "policy_decision": self.policy_decision,
            "status": self.status,
            "payload_hash": self.payload_hash,
            "result_hash": self.result_hash,
        }


def content_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
