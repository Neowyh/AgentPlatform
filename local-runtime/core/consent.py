"""Replay-safe local consent decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


def request_hash(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class ConsentStore:
    _approved: set[tuple[str, str]] = field(default_factory=set)
    _always_allowed: set[str] = field(default_factory=set)
    audit: list[dict[str, str]] = field(default_factory=list)

    def approve(self, capability: str, digest: str) -> None:
        self._approved.add((capability, digest))
        self.audit.append(
            {"capability": capability, "request_hash": digest, "decision": "approved"}
        )

    def deny(self, capability: str, digest: str) -> None:
        self.audit.append(
            {"capability": capability, "request_hash": digest, "decision": "denied"}
        )

    def set_always_allow(self, capability: str) -> None:
        self._always_allowed.add(capability)

    def consume(self, capability: str, digest: str) -> bool:
        if capability in self._always_allowed:
            return True
        key = (capability, digest)
        if key not in self._approved:
            return False
        self._approved.remove(key)
        return True
