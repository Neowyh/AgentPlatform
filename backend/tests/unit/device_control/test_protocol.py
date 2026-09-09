from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.device_control.protocol import MessageType, ProtocolError, sign_envelope


def test_signed_envelope_rejects_tamper_replay_expiry_and_session_mismatch() -> None:
    private_key = Ed25519PrivateKey.generate()
    envelope = sign_envelope(
        private_key=private_key,
        message_type=MessageType.TASK,
        device_id="device-1",
        session_id="session-1",
        task_id="task-1",
        payload={"operation": "echo", "value": "safe"},
    )
    seen_tasks: set[str] = set()
    seen_messages: set[str] = set()
    envelope.verify(
        public_key=private_key.public_key(),
        expected_device_id="device-1",
        expected_session_id="session-1",
        seen_task_ids=seen_tasks,
        seen_message_ids=seen_messages,
    )

    with pytest.raises(ProtocolError, match="already been received"):
        envelope.verify(
            public_key=private_key.public_key(),
            expected_device_id="device-1",
            expected_session_id="session-1",
            seen_task_ids=seen_tasks,
            seen_message_ids=seen_messages,
        )

    tampered = envelope.model_copy(update={"payload": {"operation": "echo", "value": "changed"}})
    with pytest.raises(ProtocolError, match="hash"):
        tampered.verify(public_key=private_key.public_key(), expected_device_id="device-1", expected_session_id="session-1")

    with pytest.raises(ProtocolError, match="session"):
        envelope.verify(public_key=private_key.public_key(), expected_device_id="device-1", expected_session_id="other-session")

    expired = sign_envelope(
        private_key=private_key,
        message_type=MessageType.TASK,
        device_id="device-1",
        session_id="session-1",
        task_id="task-2",
        payload={},
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(ProtocolError, match="expired"):
        expired.verify(public_key=private_key.public_key(), expected_device_id="device-1", expected_session_id="session-1")
