"""Pure security helpers for device pairing and lifecycle transitions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

from .models import DeviceStatus


class PairingError(ValueError):
    """A pairing or device-state operation cannot be accepted."""


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_pairing_code() -> tuple[str, str]:
    code = secrets.token_urlsafe(18)
    return code, hash_secret(code)


def consume_pairing_code(
    digest: str,
    code: str,
    *,
    expires_at: datetime,
    consumed: bool = False,
) -> bool:
    now = datetime.now(UTC)
    normalized_expiry = expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
    if normalized_expiry <= now:
        raise PairingError("pairing code expired")
    if consumed:
        raise PairingError("pairing code already used")
    if not hmac.compare_digest(digest, hash_secret(code)):
        raise PairingError("pairing code invalid")
    return True


_ALLOWED_TRANSITIONS: dict[DeviceStatus, frozenset[DeviceStatus]] = {
    DeviceStatus.PENDING: frozenset({DeviceStatus.ONLINE, DeviceStatus.OFFLINE, DeviceStatus.REVOKED, DeviceStatus.BLOCKED}),
    DeviceStatus.ONLINE: frozenset({DeviceStatus.OFFLINE, DeviceStatus.REVOKED, DeviceStatus.BLOCKED, DeviceStatus.OUTDATED}),
    DeviceStatus.OFFLINE: frozenset({DeviceStatus.ONLINE, DeviceStatus.REVOKED, DeviceStatus.BLOCKED, DeviceStatus.OUTDATED}),
    DeviceStatus.OUTDATED: frozenset({DeviceStatus.ONLINE, DeviceStatus.OFFLINE, DeviceStatus.REVOKED, DeviceStatus.BLOCKED}),
    DeviceStatus.REVOKED: frozenset(),
    DeviceStatus.BLOCKED: frozenset({DeviceStatus.REVOKED}),
}


def validate_device_transition(current: DeviceStatus | str, target: DeviceStatus | str) -> None:
    current_status = DeviceStatus(current)
    target_status = DeviceStatus(target)
    if target_status not in _ALLOWED_TRANSITIONS[current_status]:
        raise PairingError(f"invalid device transition: {current_status} -> {target_status}")
