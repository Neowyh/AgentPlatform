"""Server-side gate: only `local:<name>` references cross the device boundary.

Drives the real Local Runtime client against the DeviceBroker so the recorded
task payload, result, receipt, and error paths are the ones the server would
actually persist. The Local plan Phase 7 gate requires that none of them carry
secret plaintext.
"""

import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.device_control.broker import DeviceBroker, DeviceConnection, TaskStatus
from app.device_control.protocol import TaskEnvelope

sys.path.insert(0, str(Path(__file__).parents[4] / "local-runtime"))
from core.files import LocalFileStore, RootConfig  # noqa: E402
from core.policy import LocalPolicy  # noqa: E402
from core.protocol import MessageType, verify_envelope  # noqa: E402
from core.python import LocalPythonService  # noqa: E402
from core.secrets import InMemorySecretStore, SecretResolver  # noqa: E402
from core.transport import LocalRuntimeClient  # noqa: E402

TOKEN = "ghp_servergate-secret-token-value-1"


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


class FakeRuntimeConnection:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, value: str) -> None:
        self.sent.append(value)


def _client(server_public_key: str, device_key: Ed25519PrivateKey, tmp_path: Path) -> LocalRuntimeClient:
    return LocalRuntimeClient(
        server_url="ws://unused",
        device_id="device-1",
        session_token="token",
        private_key=device_key,
        session_id="session-1",
        server_public_key=server_public_key,
        python_service=LocalPythonService(
            LocalFileStore([RootConfig("/projects", tmp_path)]),
            policy=LocalPolicy(always_allow_capabilities=frozenset({"local.python"})),
            secrets=SecretResolver(_store()),
        ),
        policy=LocalPolicy(always_allow_capabilities=frozenset({"local.python"})),
    )


def _store() -> InMemorySecretStore:
    store = InMemorySecretStore()
    store.set("git.company", TOKEN)
    return store


def _payload() -> dict[str, object]:
    return {
        "working_root": "/projects",
        "script": "import os; print(os.environ['GIT_TOKEN'])",
        "environment": [],
        "secrets": {"GIT_TOKEN": "local:git.company"},
    }


def _server_material(record) -> str:
    return json.dumps(
        {
            "payload": record.payload,
            "result": record.result,
            "receipt": record.receipt,
            "error": record.error,
            "consent_request": record.consent_request,
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_broker_records_only_references_and_redacted_output(tmp_path: Path) -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    socket = FakeWebSocket()
    connection = DeviceConnection("device-1", "session-1", "token", device_key.public_key(), socket)
    await broker.attach(connection)

    client = _client(broker.server_public_key, device_key, tmp_path)
    client.connection = FakeRuntimeConnection()
    record = await broker.send_task(
        device_id="device-1",
        operation="local.python",
        path=None,
        run_id="run-1",
        tool_call_id="tool-1",
        payload_extra=_payload(),
    )
    assert record.status == TaskStatus.SENT

    verified = verify_envelope(
        json.loads(socket.sent[-1]),
        server_public_key=broker.server_public_key,
        expected_device_id="device-1",
        expected_session_id="session-1",
    )
    await client._handle_task(verified)

    result_envelope = TaskEnvelope.model_validate_json(client.connection.sent[-1])
    updated = await broker.receive(connection, result_envelope)

    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.payload["secrets"] == {"GIT_TOKEN": "local:git.company"}
    assert updated.result["stdout"].strip() == "[REDACTED]"
    server_material = _server_material(updated)
    assert TOKEN not in server_material
    assert updated.receipt is not None
    assert updated.receipt["stdout_hash"]
    assert updated.receipt["capability"] == "local.python"


@pytest.mark.asyncio
async def test_broker_records_structured_failure_for_missing_reference(
    tmp_path: Path,
) -> None:
    broker = DeviceBroker()
    device_key = Ed25519PrivateKey.generate()
    socket = FakeWebSocket()
    connection = DeviceConnection("device-1", "session-1", "token", device_key.public_key(), socket)
    await broker.attach(connection)

    client = _client(broker.server_public_key, device_key, tmp_path)
    client.connection = FakeRuntimeConnection()
    store = InMemorySecretStore()
    client.python_service.secrets = SecretResolver(store)  # reference now missing
    record = await broker.send_task(
        device_id="device-1",
        operation="local.python",
        path=None,
        run_id="run-1",
        tool_call_id="tool-1",
        payload_extra=_payload(),
    )
    assert record.status == TaskStatus.SENT

    verified = verify_envelope(
        json.loads(socket.sent[-1]),
        server_public_key=broker.server_public_key,
        expected_device_id="device-1",
        expected_session_id="session-1",
    )
    await client._handle_task(verified)

    error_envelope = TaskEnvelope.model_validate_json(client.connection.sent[-1])
    assert error_envelope.type == MessageType.ERROR
    updated = await broker.receive(connection, error_envelope)

    assert updated is not None
    assert updated.status == TaskStatus.FAILED
    assert updated.error_code == "SECRET_REF_NOT_FOUND"
    assert "git.company" in (updated.error or "")
    assert "local:git.company" in json.dumps(updated.payload)
    server_material = _server_material(updated)
    assert TOKEN not in server_material
    assert updated.receipt is not None
    assert updated.receipt["status"] == "failed"
