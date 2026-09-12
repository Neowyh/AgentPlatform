"""Replay-safe local consent decisions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
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
    db_path: str | Path | None = None

    def __post_init__(self) -> None:
        if self.db_path is None:
            return
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS approvals (capability TEXT NOT NULL, request_hash TEXT NOT NULL, PRIMARY KEY (capability, request_hash))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS always_allowed (capability TEXT PRIMARY KEY)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS consent_audit (capability TEXT, request_hash TEXT, decision TEXT, actor_id TEXT, decided_at TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS pending_consents (capability TEXT NOT NULL, request_hash TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            self._approved.update(
                db.execute("SELECT capability, request_hash FROM approvals").fetchall()
            )
            self._always_allowed.update(
                row[0] for row in db.execute("SELECT capability FROM always_allowed")
            )
            self.audit.extend(
                {
                    "capability": row[0],
                    "request_hash": row[1],
                    "decision": row[2],
                    "actor_id": row[3],
                    "decided_at": row[4],
                }
                for row in db.execute(
                    "SELECT capability, request_hash, decision, actor_id, decided_at FROM consent_audit ORDER BY rowid"
                )
            )

    def _persist(self, capability: str, digest: str, approved: bool) -> None:
        if self.db_path is None:
            return
        with sqlite3.connect(self.db_path) as db:
            if approved:
                db.execute(
                    "INSERT OR REPLACE INTO approvals VALUES (?, ?)",
                    (capability, digest),
                )
            else:
                db.execute(
                    "DELETE FROM approvals WHERE capability = ? AND request_hash = ?",
                    (capability, digest),
                )

    def approve(
        self,
        capability: str,
        digest: str,
        *,
        actor_id: str = "local-user",
        decided_at: str | None = None,
    ) -> None:
        self._approved.add((capability, digest))
        self._persist(capability, digest, True)
        self._remove_pending(digest)
        self.audit.append(
            self._audit_entry(capability, digest, "approved", actor_id, decided_at)
        )
        self._persist_audit(self.audit[-1])

    def deny(
        self,
        capability: str,
        digest: str,
        *,
        actor_id: str = "local-user",
        decided_at: str | None = None,
    ) -> None:
        self._approved.discard((capability, digest))
        self._persist(capability, digest, False)
        self._remove_pending(digest)
        self.audit.append(
            self._audit_entry(capability, digest, "denied", actor_id, decided_at)
        )
        self._persist_audit(self.audit[-1])

    def _persist_audit(self, entry: dict[str, str]) -> None:
        if self.db_path is not None:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT INTO consent_audit VALUES (?, ?, ?, ?, ?)",
                    tuple(
                        entry[k]
                        for k in (
                            "capability",
                            "request_hash",
                            "decision",
                            "actor_id",
                            "decided_at",
                        )
                    ),
                )

    def _remove_pending(self, digest: str) -> None:
        if self.db_path is not None:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    "DELETE FROM pending_consents WHERE request_hash = ?", (digest,)
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
        if self.db_path is not None:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT OR REPLACE INTO always_allowed VALUES (?)", (capability,)
                )

    def consume(self, capability: str, digest: str) -> bool:
        if capability in self._always_allowed:
            return True
        key = (capability, digest)
        if key not in self._approved:
            return False
        self._approved.remove(key)
        self._persist(capability, digest, False)
        return True


class ConsentExchange:
    """The device-to-user consent round trip at the local runtime boundary."""

    def __init__(self, store: ConsentStore) -> None:
        self.store = store

    def create_request(
        self, capability: str, payload: dict[str, Any]
    ) -> ConsentRequest:
        digest = request_hash(payload)
        if self.store.db_path is not None:
            with sqlite3.connect(self.store.db_path) as db:
                db.execute(
                    "INSERT OR REPLACE INTO pending_consents VALUES (?, ?, ?)",
                    (
                        capability,
                        digest,
                        json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    ),
                )
        return ConsentRequest(capability, dict(payload), digest)

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
