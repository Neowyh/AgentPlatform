from datetime import UTC, datetime, timedelta

import pytest

from app.device_control.models import DeviceStatus
from app.device_control.pairing import (
    PairingError,
    consume_pairing_code,
    hash_secret,
    new_pairing_code,
    validate_device_transition,
)


def test_pairing_code_is_hashed_and_single_use() -> None:
    code, digest = new_pairing_code()

    assert code
    assert digest == hash_secret(code)
    assert consume_pairing_code(digest, code, expires_at=datetime.now(UTC) + timedelta(minutes=1))

    with pytest.raises(PairingError, match="already used"):
        consume_pairing_code(digest, code, expires_at=datetime.now(UTC) + timedelta(minutes=1), consumed=True)


def test_expired_or_wrong_pairing_code_is_rejected() -> None:
    _code, digest = new_pairing_code()

    with pytest.raises(PairingError, match="expired"):
        consume_pairing_code(digest, "wrong", expires_at=datetime.now(UTC) - timedelta(seconds=1))


def test_device_lifecycle_only_allows_declared_transitions() -> None:
    validate_device_transition(DeviceStatus.PENDING, DeviceStatus.ONLINE)
    validate_device_transition(DeviceStatus.ONLINE, DeviceStatus.OFFLINE)
    validate_device_transition(DeviceStatus.OFFLINE, DeviceStatus.REVOKED)

    with pytest.raises(PairingError, match="invalid device transition"):
        validate_device_transition(DeviceStatus.REVOKED, DeviceStatus.ONLINE)
