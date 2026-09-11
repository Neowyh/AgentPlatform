"""In-process outbound device broker for the signed M7 echo task."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .protocol import (
    MessageType,
    ProtocolError,
    TaskEnvelope,
    payload_digest,
    public_key_text,
    sign_envelope,
)


class WebSocketLike(Protocol):
    async def send_text(self, data: str) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class TaskStatus(StrEnum):
    CREATED = "created"
    SENT = "sent"
    ACKED = "acked"
    CONSENT_REQUIRED = "consent_required"
    PROGRESS = "progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEVICE_OFFLINE = "device_offline"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class DeviceConnection:
    device_id: str
    session_id: str
    session_token: str
    public_key: Ed25519PublicKey
    websocket: WebSocketLike
    tasks_allowed: bool = True
    capabilities: frozenset[str] = field(default_factory=frozenset)
    seen_task_ids: set[str] = field(default_factory=set)
    seen_message_ids: set[str] = field(default_factory=set)


@dataclass
class TaskRecord:
    task_id: str
    device_id: str
    session_id: str
    run_id: str
    tool_call_id: str
    payload: dict[str, Any]
    expires_at: datetime
    status: TaskStatus = TaskStatus.CREATED
    receipt: dict[str, Any] | None = None
    result: Any = None
    error: str | None = None
    error_code: str | None = None
    consent_request: dict[str, Any] | None = None


class DeviceBroker:
    """Register only device-initiated connections and route signed envelopes."""

    def __init__(self, *, server_private_key: Ed25519PrivateKey | None = None) -> None:
        self.server_private_key = server_private_key or Ed25519PrivateKey.generate()
        self.connections: dict[str, DeviceConnection] = {}
        self.tasks: dict[str, TaskRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def server_public_key(self) -> str:
        return public_key_text(self.server_private_key.public_key())

    async def attach(self, connection: DeviceConnection) -> TaskEnvelope:
        async with self._lock:
            previous = self.connections.get(connection.device_id)
            if previous is not None and previous.session_id != connection.session_id:
                await previous.websocket.close(code=4001, reason="session superseded")
            self.connections[connection.device_id] = connection
        hello = sign_envelope(
            private_key=self.server_private_key,
            message_type=MessageType.HELLO,
            device_id=connection.device_id,
            session_id=connection.session_id,
            payload={"server_public_key": self.server_public_key, "protocol_version": "1"},
        )
        await connection.websocket.send_text(hello.model_dump_json(by_alias=True))
        return hello

    async def detach(self, device_id: str, session_id: str) -> None:
        async with self._lock:
            connection = self.connections.get(device_id)
            if connection is not None and connection.session_id == session_id:
                self.connections.pop(device_id, None)
            now = datetime.now(UTC)
            for task in self.tasks.values():
                if task.device_id == device_id and task.session_id == session_id and task.status in {TaskStatus.CREATED, TaskStatus.SENT, TaskStatus.ACKED, TaskStatus.CONSENT_REQUIRED, TaskStatus.PROGRESS}:
                    task.status = TaskStatus.DEVICE_OFFLINE
                    task.error = "device disconnected before task completion"
                    task.expires_at = max(task.expires_at, now + timedelta(seconds=1))

    async def send_echo_task(
        self,
        *,
        device_id: str,
        run_id: str,
        tool_call_id: str,
        value: Any,
        expires_in: timedelta = timedelta(minutes=5),
    ) -> TaskRecord:
        return await self.send_task(
            device_id=device_id,
            operation="echo",
            path=value,
            run_id=run_id,
            tool_call_id=tool_call_id,
            expires_in=expires_in,
            payload_extra={"value": value},
        )

    async def send_task(
        self,
        *,
        device_id: str,
        operation: str,
        path: Any,
        run_id: str,
        tool_call_id: str,
        expires_in: timedelta = timedelta(minutes=5),
        payload_extra: dict[str, Any] | None = None,
    ) -> TaskRecord:
        connection = self.connections.get(device_id)
        now = datetime.now(UTC)
        task_id = str(uuid4())
        expires_at = now + expires_in
        payload = {"operation": operation, "path": path, "run_id": run_id, "tool_call_id": tool_call_id}
        if payload_extra:
            payload.update(payload_extra)
        record = TaskRecord(task_id, device_id, connection.session_id if connection else "", run_id, tool_call_id, payload, expires_at)
        self.tasks[task_id] = record
        if connection is None:
            record.status = TaskStatus.DEVICE_OFFLINE
            record.error = "no outbound device session is connected"
            return record
        if not connection.tasks_allowed:
            record.status = TaskStatus.FAILED
            record.error = "device protocol is outdated"
            return record
        envelope = sign_envelope(
            private_key=self.server_private_key,
            message_type=MessageType.TASK,
            device_id=device_id,
            session_id=connection.session_id,
            task_id=task_id,
            payload=payload,
            expires_at=expires_at,
        )
        await connection.websocket.send_text(envelope.model_dump_json(by_alias=True))
        record.status = TaskStatus.SENT
        return record

    async def cancel_task(self, task_id: str) -> TaskRecord:
        record = self._task(task_id)
        if record.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.DEVICE_OFFLINE, TaskStatus.EXPIRED}:
            return record
        record.status = TaskStatus.CANCELLED
        connection = self.connections.get(record.device_id)
        if connection is not None and connection.session_id == record.session_id:
            envelope = sign_envelope(
                private_key=self.server_private_key,
                message_type=MessageType.TASK_CANCEL,
                device_id=record.device_id,
                session_id=record.session_id,
                task_id=record.task_id,
                payload={"reason": "cancelled by caller"},
            )
            await connection.websocket.send_text(envelope.model_dump_json(by_alias=True))
        return record

    async def send_consent_decision(self, task_id: str, *, approved: bool, actor_id: str) -> TaskRecord:
        record = self._task(task_id)
        if record.status is not TaskStatus.CONSENT_REQUIRED:
            raise ProtocolError("CONSENT_NOT_PENDING", "task is not waiting for consent")
        connection = self.connections.get(record.device_id)
        if connection is None or connection.session_id != record.session_id:
            record.status = TaskStatus.DEVICE_OFFLINE
            record.error = "no outbound device session is connected"
            return record
        request_hash = str((record.consent_request or {}).get("request_hash", ""))
        envelope = sign_envelope(
            private_key=self.server_private_key,
            message_type=MessageType.CONSENT_DECISION,
            device_id=record.device_id,
            session_id=record.session_id,
            task_id=record.task_id,
            payload={
                "approved": approved,
                "actor_id": actor_id,
                "request_hash": request_hash,
            },
            expires_at=record.expires_at,
        )
        await connection.websocket.send_text(envelope.model_dump_json(by_alias=True))
        return record

    async def receive(self, connection: DeviceConnection, envelope: TaskEnvelope) -> TaskRecord | None:
        envelope.verify(
            public_key=connection.public_key,
            expected_device_id=connection.device_id,
            expected_session_id=connection.session_id,
            seen_task_ids=connection.seen_task_ids,
            seen_message_ids=connection.seen_message_ids,
        )
        if envelope.type == MessageType.HEARTBEAT:
            return None
        if envelope.type == MessageType.CAPABILITY_UPDATE:
            values = envelope.payload.get("capabilities", ())
            if not isinstance(values, (list, tuple, set)):
                raise ProtocolError("CAPABILITIES_INVALID", "capability update is invalid")
            connection.capabilities = frozenset(str(value) for value in values)
            return None
        if envelope.task_id is None:
            raise ProtocolError("TASK_ID_REQUIRED", "task lifecycle messages require task_id")
        record = self._task(envelope.task_id)
        self._expire_if_needed(record)
        if record.status == TaskStatus.EXPIRED:
            raise ProtocolError("TASK_EXPIRED", "task envelope expired before completion")
        if record.device_id != connection.device_id or record.session_id != connection.session_id:
            raise ProtocolError("SESSION_MISMATCH", "task belongs to another device session")
        if envelope.type == MessageType.TASK_ACK:
            record.status = TaskStatus.ACKED
        elif envelope.type == MessageType.CONSENT_REQUIRED:
            request_payload = envelope.payload.get("payload")
            request_hash = envelope.payload.get("request_hash")
            if not isinstance(request_payload, dict) or not isinstance(request_hash, str) or request_hash != payload_digest(request_payload) or request_payload != record.payload:
                raise ProtocolError(
                    "CONSENT_HASH_MISMATCH",
                    "consent request does not match the task payload",
                )
            record.status = TaskStatus.CONSENT_REQUIRED
            record.consent_request = dict(envelope.payload)
        elif envelope.type == MessageType.TASK_PROGRESS:
            record.status = TaskStatus.PROGRESS
        elif envelope.type == MessageType.TASK_RESULT:
            record.status = TaskStatus.COMPLETED
            record.result = envelope.payload.get("result")
            record.receipt = envelope.payload.get("receipt") or envelope.payload
        elif envelope.type == MessageType.ERROR:
            record.status = TaskStatus.FAILED
            record.error_code = str(envelope.payload.get("error_code", "DEVICE_ERROR"))
            record.error = str(envelope.payload.get("message", "device reported an error"))
            record.receipt = envelope.payload.get("receipt")
        else:
            raise ProtocolError("MESSAGE_UNEXPECTED", f"unexpected device message: {envelope.type}")
        return record

    def _task(self, task_id: str) -> TaskRecord:
        record = self.tasks.get(task_id)
        if record is None:
            raise ProtocolError("TASK_NOT_FOUND", "task id is unknown")
        return record

    def get_task(self, task_id: str) -> TaskRecord:
        record = self._task(task_id)
        self._expire_if_needed(record)
        return record

    @staticmethod
    def _expire_if_needed(record: TaskRecord) -> None:
        if record.status in {TaskStatus.CREATED, TaskStatus.SENT, TaskStatus.ACKED, TaskStatus.PROGRESS} and record.expires_at <= datetime.now(UTC):
            record.status = TaskStatus.EXPIRED
            record.error = "task delivery or execution deadline elapsed"


_broker = DeviceBroker()


def get_device_broker() -> DeviceBroker:
    return _broker
