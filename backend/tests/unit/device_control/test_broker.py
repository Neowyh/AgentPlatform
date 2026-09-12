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


@pytest.mark.asyncio
async def test_failed_local_execution_receipt_marks_task_failed() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection("device-python", "session-python", "token", device_key.public_key(), FakeWebSocket())
    await broker.attach(connection)
    record = await broker.send_task(
        device_id="device-python",
        operation="local.python",
        path="/projects",
        run_id="run-python",
        tool_call_id="tool-python",
        payload_extra={
            "working_root": "/projects",
            "script": "raise SystemExit(3)",
        },
    )

    message = sign_envelope(
        private_key=device_key,
        message_type=MessageType.TASK_RESULT,
        device_id=connection.device_id,
        session_id=connection.session_id,
        task_id=record.task_id,
        payload={"receipt": {"status": "failed", "exit_code": 3}},
    )

    updated = await broker.receive(connection, message)

    assert updated is record
    assert record.status is TaskStatus.FAILED
    assert record.error_code == "FAILED"


@pytest.mark.asyncio
async def test_cancelled_local_execution_receipt_preserves_cancelled_status() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection("device-cancel", "session-cancel", "token", device_key.public_key(), FakeWebSocket())
    await broker.attach(connection)
    record = await broker.send_task(
        device_id="device-cancel",
        operation="local.python",
        path="/projects",
        run_id="run-cancel",
        tool_call_id="tool-cancel",
        payload_extra={"working_root": "/projects", "script": "pass"},
    )

    message = sign_envelope(
        private_key=device_key,
        message_type=MessageType.TASK_RESULT,
        device_id=connection.device_id,
        session_id=connection.session_id,
        task_id=record.task_id,
        payload={"receipt": {"status": "cancelled"}},
    )

    updated = await broker.receive(connection, message)

    assert updated is record
    assert record.status is TaskStatus.CANCELLED
    assert record.error_code == "CANCELLED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("receipt_status", "expected_status", "expected_code"),
    [
        ("denied", TaskStatus.DENIED, "DENIED"),
        ("timed_out", TaskStatus.TIMED_OUT, "TIMED_OUT"),
    ],
)
async def test_device_terminal_receipts_preserve_distinct_denied_and_timeout_states(receipt_status: str, expected_status: TaskStatus, expected_code: str) -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection("device-terminal", "session-terminal", "token", device_key.public_key(), FakeWebSocket())
    await broker.attach(connection)
    record = await broker.send_echo_task(device_id=connection.device_id, run_id="run-terminal", tool_call_id="tool-terminal", value="x")

    message = sign_envelope(
        private_key=device_key,
        message_type=MessageType.TASK_RESULT,
        device_id=connection.device_id,
        session_id=connection.session_id,
        task_id=record.task_id,
        payload={"receipt": {"status": receipt_status}},
    )

    await broker.receive(connection, message)

    assert record.status is expected_status
    assert record.error_code == expected_code


@pytest.mark.asyncio
async def test_terminal_task_ignores_late_ack_progress_and_result() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection("device-late", "session-late", "token", device_key.public_key(), FakeWebSocket())
    await broker.attach(connection)
    record = await broker.send_echo_task(device_id=connection.device_id, run_id="run-late", tool_call_id="tool-late", value="x")

    completed = sign_envelope(
        private_key=device_key,
        message_type=MessageType.TASK_RESULT,
        device_id=connection.device_id,
        session_id=connection.session_id,
        task_id=record.task_id,
        payload={"result": "first", "receipt": {"status": "completed"}},
    )
    await broker.receive(connection, completed)

    for message_type, payload in (
        (MessageType.TASK_ACK, {"accepted": True}),
        (MessageType.TASK_PROGRESS, {"fraction": 1.0}),
        (MessageType.TASK_RESULT, {"result": "late", "receipt": {"status": "failed"}}),
    ):
        message = sign_envelope(
            private_key=device_key,
            message_type=message_type,
            device_id=connection.device_id,
            session_id=connection.session_id,
            task_id=record.task_id,
            payload=payload,
        )
        assert await broker.receive(connection, message) is record

    assert record.status is TaskStatus.COMPLETED
    assert record.result == "first"


@pytest.mark.asyncio
async def test_error_receipt_preserves_denied_status() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection("device-error-denied", "session-error-denied", "token", device_key.public_key(), FakeWebSocket())
    await broker.attach(connection)
    record = await broker.send_echo_task(device_id=connection.device_id, run_id="run-error-denied", tool_call_id="tool-error-denied", value="x")
    message = sign_envelope(
        private_key=device_key,
        message_type=MessageType.ERROR,
        device_id=connection.device_id,
        session_id=connection.session_id,
        task_id=record.task_id,
        payload={
            "error_code": "LOCAL_POLICY_DENIED",
            "message": "local policy denied",
            "receipt": {"status": "denied"},
        },
    )

    await broker.receive(connection, message)

    assert record.status is TaskStatus.DENIED


@pytest.mark.asyncio
async def test_connected_device_without_requested_capability_rejects_local_task() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection("device-capability", "session-capability", "token", device_key.public_key(), FakeWebSocket(), capabilities=frozenset({"local.files.read"}))
    await broker.attach(connection)

    record = await broker.send_task(
        device_id=connection.device_id,
        operation="local.python",
        path="/projects",
        run_id="run-capability",
        tool_call_id="tool-capability",
    )

    assert record.status is TaskStatus.FAILED
    assert record.error_code == "CAPABILITY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_authorization_snapshot_is_checked_before_task_delivery() -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    connection = DeviceConnection(
        "device-snapshot",
        "session-snapshot",
        "token",
        device_key.public_key(),
        FakeWebSocket(),
        capabilities=frozenset({"local.python"}),
    )
    await broker.attach(connection)
    record = await broker.send_task(
        device_id=connection.device_id,
        operation="local.python",
        path="/projects/a.py",
        run_id="run",
        tool_call_id="call",
        authorization_snapshot={
            "device_id": "other-device",
            "effective_capabilities": ["local.python"],
        },
    )
    assert record.status is TaskStatus.DENIED
    assert record.error_code == "AUTHORIZATION_SNAPSHOT_INVALID"
