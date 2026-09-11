import asyncio
import json
from pathlib import Path

from core.file_service import LocalFileService
from core.files import LocalFileStore, RootConfig
from core.protocol import MessageType, public_key_text, sign_envelope, verify_envelope
from core.transport import LocalRuntimeClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class FakeConnection:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, value: str) -> None:
        self.sent.append(value)


def test_write_task_round_trip_waits_for_matching_consent(tmp_path: Path) -> None:
    server_key = Ed25519PrivateKey.generate()
    client = LocalRuntimeClient(
        server_url="ws://unused",
        device_id="device-1",
        session_token="token",
        private_key=Ed25519PrivateKey.generate(),
        session_id="session-1",
        file_service=LocalFileService(
            LocalFileStore([RootConfig("/projects", tmp_path)])
        ),
    )
    client.connection = FakeConnection()
    payload = {
        "operation": "local.files.write",
        "path": "/projects/a.txt",
        "content": "approved",
        "run_id": "run-1",
    }
    task = sign_envelope(
        private_key=server_key,
        message_type=MessageType.TASK,
        device_id="device-1",
        session_id="session-1",
        task_id="task-1",
        payload=payload,
    )

    verified_task = verify_envelope(
        task,
        server_public_key=public_key_text(server_key),
        expected_device_id="device-1",
        expected_session_id="session-1",
    )
    asyncio.run(client._handle_task(verified_task))
    consent_message = json.loads(client.connection.sent[-1])
    assert consent_message["type"] == MessageType.CONSENT_REQUIRED
    assert not (tmp_path / "a.txt").exists()

    decision = sign_envelope(
        private_key=server_key,
        message_type=MessageType.CONSENT_DECISION,
        device_id="device-1",
        session_id="session-1",
        task_id="task-1",
        payload={
            "approved": True,
            "actor_id": "alice",
            "request_hash": consent_message["payload"]["request_hash"],
        },
    )
    verified_decision = verify_envelope(
        decision,
        server_public_key=public_key_text(server_key),
        expected_device_id="device-1",
        expected_session_id="session-1",
    )
    asyncio.run(client._handle_consent_decision(verified_decision))

    result = json.loads(client.connection.sent[-1])
    assert result["type"] == MessageType.TASK_RESULT
    assert (tmp_path / "a.txt").read_text() == "approved"
    assert result["payload"]["receipt"]["consent_decision"] == "approved"
