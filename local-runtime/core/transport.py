"""Outbound-only WebSocket transport for the harmless M7 echo task."""

from __future__ import annotations

import json
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.asyncio.client import ClientConnection, connect

from .file_service import FileTaskResult, LocalFileService
from .files import FileAccessError
from .policy import LocalPolicy, PolicyDecision
from .protocol import (
    MessageType,
    new_session_id,
    public_key_text,
    sign_envelope,
    verify_envelope,
)
from .receipts import LocalExecutionReceipt, content_hash


class LocalRuntimeClient:
    """Connect to the Broker and execute only the protocol's echo task."""

    def __init__(
        self,
        *,
        server_url: str,
        device_id: str,
        session_token: str,
        private_key: Ed25519PrivateKey,
        session_id: str | None = None,
        protocol_version: str = "1",
        runtime_version: str = "0.1.0",
        capabilities: tuple[str, ...] | None = None,
        policy_hash: str | None = None,
        server_public_key: str | None = None,
        policy: LocalPolicy | None = None,
        file_service: LocalFileService | None = None,
    ) -> None:
        self.server_url = server_url
        self.device_id = device_id
        self.session_id = session_id
        self.session_token = session_token
        self.private_key = private_key
        self.protocol_version = protocol_version
        self.runtime_version = runtime_version
        self.capabilities = capabilities if capabilities is not None else (
            ("echo", "local.files.list", "local.files.read")
            if file_service is not None
            else ("echo",)
        )
        self.policy_hash = policy_hash
        self.server_public_key = server_public_key
        self.policy = policy or LocalPolicy()
        self.file_service = file_service
        self.connection: ClientConnection | None = None

    async def connect(self) -> ClientConnection:
        """Open the device-initiated connection; the server is never dialed back."""
        self.connection = await connect(self.server_url)
        return self.connection

    async def send_hello(self) -> None:
        if self.connection is None:
            raise RuntimeError("connect() must be called before send_hello()")
        self.session_id = self.session_id or new_session_id()
        hello = sign_envelope(
            private_key=self.private_key,
            message_type=MessageType.HELLO,
            device_id=self.device_id,
            session_id=self.session_id,
            payload={
                "session_token": self.session_token,
                "public_key": public_key_text(self.private_key),
                "protocol_version": self.protocol_version,
                "runtime_version": self.runtime_version,
                "capabilities": list(self.capabilities),
                "policy_hash": self.policy_hash,
            },
        )
        await self.connection.send(
            json.dumps(hello, ensure_ascii=False, separators=(",", ":"))
        )

    async def send_capability_update(self) -> None:
        """Publish the current device capability set to the server registry."""
        if self.connection is None or self.session_id is None:
            raise RuntimeError("connect and send_hello must be called first")
        message = sign_envelope(
            private_key=self.private_key,
            message_type=MessageType.CAPABILITY_UPDATE,
            device_id=self.device_id,
            session_id=self.session_id,
            payload={
                "capabilities": list(self.capabilities),
                "policy_hash": self.policy_hash,
            },
        )
        await self.connection.send(json.dumps(message, ensure_ascii=False, separators=(",", ":")))

    async def run(self) -> None:
        """Receive signed tasks and return ACK/progress/result envelopes."""
        if self.connection is None:
            await self.connect()
        await self.send_hello()
        await self.send_capability_update()
        assert self.connection is not None
        server_hello = json.loads(await self.connection.recv())
        configured_key = self.server_public_key or str(server_hello.get("payload", {}).get("server_public_key", ""))
        verify_envelope(
            server_hello,
            server_public_key=configured_key,
            expected_device_id=self.device_id,
            expected_session_id=self.session_id or "",
        )
        self.server_public_key = configured_key
        async for raw in self.connection:
            message = json.loads(raw)
            envelope = verify_envelope(
                message,
                server_public_key=self.server_public_key,
                expected_device_id=self.device_id,
                expected_session_id=self.session_id or "",
            )
            if envelope.type == MessageType.TASK:
                await self._handle_task(envelope)
            elif envelope.type == MessageType.TASK_CANCEL:
                return

    async def _handle_task(self, envelope) -> None:
        assert self.connection is not None
        task_id = envelope.task_id or ""
        await self.connection.send(
            json.dumps(
                sign_envelope(
                    private_key=self.private_key,
                    message_type=MessageType.TASK_ACK,
                    device_id=self.device_id,
                    session_id=self.session_id or "",
                    task_id=task_id,
                    payload={"accepted": True},
                ),
                separators=(",", ":"),
            )
        )
        operation = str(envelope.payload.get("operation", ""))
        try:
            if operation == "echo":
                result = envelope.payload.get("value")
                receipt = await self.handle_echo_task(envelope)
            elif operation in {"local.files.list", "local.files.read"}:
                file_task = self.handle_file_task(operation, dict(envelope.payload))
                if file_task.decision is not PolicyDecision.ALLOW:
                    await self._send_error(task_id, file_task.decision.value, "POLICY_DENIED", envelope.payload, operation)
                    return
                result = file_task.value
                receipt = self._file_receipt(envelope, operation, result)
            else:
                raise ValueError("unsupported operation")
        except FileAccessError as exc:
            await self._send_error(task_id, str(exc), exc.code, envelope.payload, operation)
            return
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            await self._send_error(task_id, str(exc), "INVALID_TASK", envelope.payload, operation)
            return
        await self.connection.send(json.dumps(sign_envelope(
            private_key=self.private_key, message_type=MessageType.TASK_PROGRESS,
            device_id=self.device_id, session_id=self.session_id or "", task_id=task_id,
            payload={"fraction": 1.0},
        ), separators=(",", ":")))
        await self.connection.send(json.dumps(sign_envelope(
            private_key=self.private_key, message_type=MessageType.TASK_RESULT,
            device_id=self.device_id, session_id=self.session_id or "", task_id=task_id,
            payload={"result": result, "receipt": receipt.as_dict()},
        ), separators=(",", ":")))

    def _file_receipt(self, envelope: Any, capability: str, result: Any) -> LocalExecutionReceipt:
        payload = dict(envelope.payload)
        return LocalExecutionReceipt(
            run_id=str(payload.get("run_id", "")), task_id=envelope.task_id or "",
            capability=capability, policy_decision=PolicyDecision.ALLOW.value,
            status="completed", payload_hash=content_hash(payload), result_hash=content_hash(result),
        )

    async def _send_error(self, task_id: str, message: str, code: str, payload: dict[str, Any], capability: str) -> None:
        assert self.connection is not None
        receipt = LocalExecutionReceipt(
            run_id=str(payload.get("run_id", "")), task_id=task_id, capability=capability,
            policy_decision="allow", status="failed", payload_hash=content_hash(payload),
        )
        await self.connection.send(json.dumps(sign_envelope(
            private_key=self.private_key, message_type=MessageType.ERROR,
            device_id=self.device_id, session_id=self.session_id or "", task_id=task_id,
            payload={"error_code": code, "message": message, "receipt": receipt.as_dict()},
        ), separators=(",", ":")))

    async def handle_echo_task(self, envelope: Any) -> LocalExecutionReceipt:
        """Apply Local Policy and return a receipt without executing system commands."""
        task_id = envelope.task_id or ""
        payload = dict(envelope.payload)
        decision = self.policy.authorize("echo", payload)
        status = "completed" if decision == PolicyDecision.ALLOW else decision.value
        result_hash = (
            content_hash(payload) if decision == PolicyDecision.ALLOW else None
        )
        return LocalExecutionReceipt(
            run_id=str(payload.get("run_id", "")),
            task_id=task_id,
            capability="echo",
            policy_decision=decision.value,
            status=status,
            payload_hash=content_hash(payload),
            result_hash=result_hash,
        )
    def handle_file_task(self, capability: str, payload: dict[str, Any], *, consent: bool = False) -> FileTaskResult:
        """Execute a list/read task through the configured logical-root store."""
        if capability not in {"local.files.list", "local.files.read"}:
            raise ValueError("unsupported local file capability")
        if self.file_service is None:
            raise RuntimeError("file_service is required for local file tasks")
        del consent  # File reads are Level 0 and never require a consent round trip.
        return self.file_service.execute(capability, payload)
