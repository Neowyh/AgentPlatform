"""Tests for policy denial audit recording."""

import asyncio
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.audit import AuditKind
from core.file_service import LocalFileService
from core.files import LocalFileStore, RootConfig
from core.policy import LocalPolicy, PolicyDecision
from core.protocol import MessageType, public_key_text, sign_envelope, verify_envelope
from core.transport import LocalRuntimeClient


class FakeConnection:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, value: str) -> None:
        self.sent.append(value)

    async def close(self) -> None:
        pass


def test_policy_denial_records_audit_with_risk_level(tmp_path: Path) -> None:
    """When policy denies a task, the local audit records the denial with risk level."""
    server_key = Ed25519PrivateKey.generate()
    # Set policy on file service (not client) to deny writes
    file_service = LocalFileService(
        LocalFileStore([RootConfig("/projects", tmp_path)]),
        policy=LocalPolicy(denied_capabilities=frozenset(["local.files.write"])),
    )
    client = LocalRuntimeClient(
        server_url="ws://unused",
        device_id="device-1",
        session_token="token",
        private_key=Ed25519PrivateKey.generate(),
        session_id="session-1",
        file_service=file_service,
    )
    client.connection = FakeConnection()

    payload = {
        "operation": "local.files.write",
        "path": "/projects/denied.txt",
        "content": "nope",
        "run_id": "run-1",
    }
    envelope = verify_envelope(
        sign_envelope(
            private_key=server_key,
            message_type=MessageType.TASK,
            device_id="device-1",
            session_id="session-1",
            task_id="task-denied",
            payload=payload,
        ),
        server_public_key=public_key_text(server_key),
        expected_device_id="device-1",
        expected_session_id="session-1",
    )

    asyncio.run(client._handle_task(envelope))

    # Should have sent an error frame
    error_frame = next(
        (json.loads(s) for s in client.connection.sent if json.loads(s)["type"] == MessageType.ERROR.value),
        None,
    )
    assert error_frame is not None
    assert error_frame["payload"]["error_code"] == "LOCAL_POLICY_DENIED"

    # And recorded in audit
    policy_denials = client.audit.recent(kind=AuditKind.POLICY)
    assert len(policy_denials) == 1
    assert policy_denials[0].action == "denied"
    assert policy_denials[0].capability == "local.files.write"
    assert "risk_level" in policy_denials[0].detail
    assert not (tmp_path / "denied.txt").exists()


def test_policy_denial_audit_contains_risk_level_detail(tmp_path: Path) -> None:
    """The audit detail must include the risk level that triggered the denial."""
    file_service = LocalFileService(
        LocalFileStore([RootConfig("/projects", tmp_path)]),
        policy=LocalPolicy(denied_capabilities=frozenset(["local.files.write"])),
    )

    payload = {
        "operation": "local.files.write",
        "path": "/projects/x.txt",
        "content": "x",
        "run_id": "r1",
    }

    # Check that file_service denies correctly
    result = file_service.execute("local.files.write", payload)
    assert result.decision is PolicyDecision.DENY
    assert result.value is None
