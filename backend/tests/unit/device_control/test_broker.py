import json
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.device_control.broker import DeviceBroker, DeviceConnection, TaskStatus
from app.device_control.protocol import MessageType, TaskEnvelope, payload_digest, sign_envelope


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_signed_echo_task_has_ack_progress_result_receipt_lifecycle() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    socket = FakeWebSocket()
    connection = DeviceConnection("device-1", "session-1", "token", device_key.public_key(), socket)
    await broker.attach(connection)
    record = await broker.send_echo_task(device_id="device-1", run_id="run-1", tool_call_id="tool-1", value="hello")
    assert record.status == TaskStatus.SENT
    task = TaskEnvelope.model_validate_json(socket.sent[-1])
    task.verify(public_key=broker.server_private_key.public_key(), expected_device_id="device-1", expected_session_id="session-1")

    for message_type, payload, expected in (
        (MessageType.TASK_ACK, {"accepted": True}, TaskStatus.ACKED),
        (MessageType.TASK_PROGRESS, {"fraction": 1.0}, TaskStatus.PROGRESS),
        (MessageType.TASK_RESULT, {"receipt": {"status": "completed", "task_id": record.task_id}}, TaskStatus.COMPLETED),
    ):
        message = sign_envelope(
            private_key=device_key,
            message_type=message_type,
            device_id="device-1",
            session_id="session-1",
            task_id=record.task_id,
            payload=payload,
        )
        updated = await broker.receive(connection, message)
        assert updated is not None
        assert updated.status == expected
    assert record.receipt == {"status": "completed", "task_id": record.task_id}


@pytest.mark.asyncio
async def test_offline_task_and_cancel_are_explicit_and_no_system_command_is_run() -> None:
    broker = DeviceBroker()
    offline = await broker.send_echo_task(device_id="missing", run_id="run-1", tool_call_id="tool-1", value="safe")
    assert offline.status == TaskStatus.DEVICE_OFFLINE
    assert offline.expires_at is not None

    device_key = Ed25519PrivateKey.generate()
    socket = FakeWebSocket()
    connection = DeviceConnection("device-2", "session-2", "token", device_key.public_key(), socket)
    await broker.attach(connection)
    record = await broker.send_echo_task(device_id="device-2", run_id="run-2", tool_call_id="tool-2", value="echo only")
    cancelled = await broker.cancel_task(record.task_id)
    assert cancelled.status == TaskStatus.CANCELLED
    cancel_message = json.loads(socket.sent[-1])
    assert cancel_message["type"] == MessageType.TASK_CANCEL
    assert "command" not in cancel_message["payload"]

    expired = await broker.send_echo_task(
        device_id="device-2",
        run_id="run-expired",
        tool_call_id="tool-expired",
        value="echo only",
        expires_in=timedelta(seconds=-1),
    )
    assert broker.get_task(expired.task_id).status == TaskStatus.EXPIRED


@pytest.mark.asyncio
async def test_capability_update_is_stored_without_a_task_id() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection("device-cap", "session-cap", "token", device_key.public_key(), FakeWebSocket())
    await broker.attach(connection)

    message = sign_envelope(
        private_key=device_key,
        message_type=MessageType.CAPABILITY_UPDATE,
        device_id="device-cap",
        session_id="session-cap",
        payload={"capabilities": ["local.files.read"]},
    )
    assert await broker.receive(connection, message) is None
    assert connection.capabilities == {"local.files.read"}


@pytest.mark.asyncio
async def test_consent_required_is_recorded_and_decision_is_forwarded() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    socket = FakeWebSocket()
    connection = DeviceConnection("device-consent", "session-consent", "token", device_key.public_key(), socket)
    await broker.attach(connection)
    record = await broker.send_task(
        device_id="device-consent",
        operation="local.files.write",
        path="/projects/a.txt",
        run_id="run-consent",
        tool_call_id="tool-consent",
        payload_extra={"content": "approved"},
    )
    request = sign_envelope(
        private_key=device_key,
        message_type=MessageType.CONSENT_REQUIRED,
        device_id=connection.device_id,
        session_id=connection.session_id,
        task_id=record.task_id,
        payload={
            "capability": "local.files.write",
            "payload": record.payload,
            "request_hash": payload_digest(record.payload),
        },
    )

    updated = await broker.receive(connection, request)
    assert updated is record
    assert record.status is TaskStatus.CONSENT_REQUIRED
    assert record.consent_request["request_hash"] == payload_digest(record.payload)

    await broker.send_consent_decision(record.task_id, approved=True, actor_id="alice")
    decision = json.loads(socket.sent[-1])
    assert decision["type"] == MessageType.CONSENT_DECISION
    assert decision["payload"] == {
        "approved": True,
        "actor_id": "alice",
        "request_hash": payload_digest(record.payload),
    }
