"""Protocol serialization kept independent from the server package."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


class MessageType(StrEnum):
    HELLO = "hello"
    HEARTBEAT = "heartbeat"
    CAPABILITY_UPDATE = "capability_update"
    TASK = "task"
    TASK_ACK = "task_ack"
    TASK_PROGRESS = "task_progress"
    TASK_RESULT = "task_result"
    TASK_CANCEL = "task_cancel"
    CONSENT_REQUIRED = "consent_required"
    ERROR = "error"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def public_key_text(private_key: Ed25519PrivateKey) -> str:
    return base64.urlsafe_b64encode(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")


def new_session_id() -> str:
    return secrets.token_urlsafe(18)


def sign_envelope(
    *,
    private_key: Ed25519PrivateKey,
    message_type: MessageType,
    device_id: str,
    session_id: str,
    payload: dict[str, Any],
    task_id: str | None = None,
) -> dict[str, Any]:
    issued_at = datetime.now(UTC)
    unsigned = {
        "protocol": "1",
        "type": message_type.value,
        "message_id": str(uuid4()),
        "device_id": device_id,
        "session_id": session_id,
        "task_id": task_id,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=5)).isoformat(),
        "payload": payload,
        "payload_hash": hashlib.sha256(_canonical(payload)).hexdigest(),
    }
    signed = dict(unsigned)
    signed["signature"] = base64.urlsafe_b64encode(
        private_key.sign(_canonical(unsigned))
    ).decode("ascii")
    return signed
