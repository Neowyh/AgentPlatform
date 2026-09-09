"""Replay-safe local consent decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def request_hash(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ConsentRequest:
    capability: str
    payload: dict[str, Any]
    request_hash: str


@dataclass
class ConsentStore:
    _approved: set[tuple[str, str]] = field(default_factory=set)
    _always_allowed: set[str] = field(default_factory=set)
    audit: list[dict[str, str]] = field(default_factory=list)

    def approve(
        self,
        capability: str,
        digest: str,
        *,
        actor_id: str = "local-user",
        decided_at: str | None = None,
    ) -> None:
        self._approved.add((capability, digest))
        self.audit.append(
            self._audit_entry(capability, digest, "approved", actor_id, decided_at)
        )

    def deny(
        self,
        capability: str,
        digest: str,
        *,
        actor_id: str = "local-user",
        decided_at: str | None = None,
    ) -> None:
        self._approved.discard((capability, digest))
        self.audit.append(
            self._audit_entry(capability, digest, "denied", actor_id, decided_at)
        )

    @staticmethod
    def _audit_entry(
        capability: str,
        digest: str,
        decision: str,
        actor_id: str,
        decided_at: str | None,
    ) -> dict[str, str]:
        from datetime import UTC, datetime

        return {
            "capability": capability,
            "request_hash": digest,
            "decision": decision,
            "actor_id": actor_id,
            "decided_at": decided_at or datetime.now(UTC).isoformat(),
        }

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


class ConsentExchange:
    """The device-to-user consent round trip at the local runtime boundary."""

    def __init__(self, store: ConsentStore) -> None:
        self.store = store

    def create_request(
        self, capability: str, payload: dict[str, Any]
    ) -> ConsentRequest:
        return ConsentRequest(capability, dict(payload), request_hash(payload))

    def decide(
        self,
        request: ConsentRequest,
        *,
        approved: bool,
        actor_id: str,
        decided_at: str | None = None,
    ) -> None:
        if approved:
            self.store.approve(
                request.capability,
                request.request_hash,
                actor_id=actor_id,
                decided_at=decided_at,
            )
        else:
            self.store.deny(
                request.capability,
                request.request_hash,
                actor_id=actor_id,
                decided_at=decided_at,
            )

    def authorize(self, request: ConsentRequest, payload: dict[str, Any]) -> bool:
        if request_hash(payload) != request.request_hash:
            return False
        return self.store.consume(request.capability, request.request_hash)
