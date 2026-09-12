import asyncio
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.file_service import LocalFileService
from core.files import LocalFileStore, RootConfig
from core.protocol import MessageType, public_key_text, sign_envelope, verify_envelope
from core.python import LocalPythonService
from core.transport import LocalRuntimeClient


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


def test_python_task_round_trip_returns_bounded_result_and_receipt(
    tmp_path: Path,
) -> None:
    server_key = Ed25519PrivateKey.generate()
    client = LocalRuntimeClient(
        server_url="ws://unused",
        device_id="device-1",
        session_token="token",
        private_key=Ed25519PrivateKey.generate(),
        session_id="session-1",
        python_service=LocalPythonService(
            LocalFileStore([RootConfig("/projects", tmp_path)])
        ),
    )
    client.connection = FakeConnection()
    payload = {
        "operation": "local.python",
        "working_root": "/projects",
        "script": "print('API_KEY=super-secret')",
        "environment": [],
        "run_id": "run-1",
    }
    task = sign_envelope(
        private_key=server_key,
        message_type=MessageType.TASK,
        device_id="device-1",
        session_id="session-1",
        task_id="task-python",
        payload=payload,
    )
    verified_task = verify_envelope(
        task,
        server_public_key=public_key_text(server_key),
        expected_device_id="device-1",
        expected_session_id="session-1",
    )

    async def run_with_consent():
        await client._handle_task(verified_task)
        consent_message = json.loads(client.connection.sent[-1])
        assert consent_message["type"] == MessageType.CONSENT_REQUIRED
        decision = sign_envelope(
            private_key=server_key,
            message_type=MessageType.CONSENT_DECISION,
            device_id="device-1",
            session_id="session-1",
            task_id="task-python",
            payload={
                "approved": True,
                "actor_id": "alice",
                "request_hash": consent_message["payload"]["request_hash"],
            },
        )
        await client._handle_consent_decision(
            verify_envelope(
                decision,
                server_public_key=public_key_text(server_key),
                expected_device_id="device-1",
                expected_session_id="session-1",
            )
        )

    asyncio.run(run_with_consent())

    result = json.loads(client.connection.sent[-1])
    assert result["type"] == MessageType.TASK_RESULT
    assert result["payload"]["result"]["stdout"] == "API_KEY=[REDACTED]\n"
    assert result["payload"]["receipt"]["capability"] == "local.python"
    progress = [
        json.loads(message)
        for message in client.connection.sent
        if json.loads(message)["type"] == MessageType.TASK_PROGRESS
    ]
    assert any(
        message["payload"].get("output") == "API_KEY=[REDACTED]\n"
        for message in progress
    )


def test_cancelled_consent_cannot_be_revived_by_a_late_approval(tmp_path: Path) -> None:
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
        "content": "must-not-write",
        "run_id": "run-1",
    }
    task = sign_envelope(
        private_key=server_key,
        message_type=MessageType.TASK,
        device_id="device-1",
        session_id="session-1",
        task_id="task-cancel-consent",
        payload=payload,
    )
    verified_task = verify_envelope(
        task,
        server_public_key=public_key_text(server_key),
        expected_device_id="device-1",
        expected_session_id="session-1",
    )

    async def cancel_then_approve() -> None:
        await client._handle_task(verified_task)
        request = client._pending_consents["task-cancel-consent"]
        await client._handle_task_cancel("task-cancel-consent")
        decision = sign_envelope(
            private_key=server_key,
            message_type=MessageType.CONSENT_DECISION,
            device_id="device-1",
            session_id="session-1",
            task_id="task-cancel-consent",
            payload={
                "approved": True,
                "actor_id": "alice",
                "request_hash": request.request_hash,
            },
        )
        await client._handle_consent_decision(
            verify_envelope(
                decision,
                server_public_key=public_key_text(server_key),
                expected_device_id="device-1",
                expected_session_id="session-1",
            )
        )

    asyncio.run(cancel_then_approve())
    assert not (tmp_path / "a.txt").exists()


def test_cancel_during_approved_python_execution_returns_cancelled_receipt(
    tmp_path: Path,
) -> None:
    server_key = Ed25519PrivateKey.generate()
    client = LocalRuntimeClient(
        server_url="ws://unused",
        device_id="device-1",
        session_token="token",
        private_key=Ed25519PrivateKey.generate(),
        session_id="session-1",
        python_service=LocalPythonService(
            LocalFileStore([RootConfig("/projects", tmp_path)])
        ),
    )
    client.connection = FakeConnection()
    payload = {
        "operation": "local.python",
        "working_root": "/projects",
        "script": "import time; time.sleep(30)",
        "environment": [],
        "run_id": "run-1",
    }
    task = sign_envelope(
        private_key=server_key,
        message_type=MessageType.TASK,
        device_id="device-1",
        session_id="session-1",
        task_id="task-cancel-python",
        payload=payload,
    )
    verified_task = verify_envelope(
        task,
        server_public_key=public_key_text(server_key),
        expected_device_id="device-1",
        expected_session_id="session-1",
    )

    async def run_and_cancel() -> None:
        await client._handle_task(verified_task)
        request = client._pending_consents["task-cancel-python"]
        client._cancelled_tasks.discard("task-cancel-python")
        decision = sign_envelope(
            private_key=server_key,
            message_type=MessageType.CONSENT_DECISION,
            device_id="device-1",
            session_id="session-1",
            task_id="task-cancel-python",
            payload={
                "approved": True,
                "actor_id": "alice",
                "request_hash": request.request_hash,
            },
        )
        await client._handle_consent_decision(
            verify_envelope(
                decision,
                server_public_key=public_key_text(server_key),
                expected_device_id="device-1",
                expected_session_id="session-1",
            ),
            background=True,
        )
        running = client._running_tasks["task-cancel-python"]
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)

    asyncio.run(run_and_cancel())
    result = json.loads(client.connection.sent[-1])
    assert result["type"] == MessageType.TASK_RESULT
    assert result["payload"]["receipt"]["status"] == "cancelled"
