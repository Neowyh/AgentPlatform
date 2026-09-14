"""Outbound-only WebSocket transport for the harmless M7 echo task."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.asyncio.client import ClientConnection, connect

from .consent import ConsentExchange, ConsentRequest
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
from .python import LocalPythonService, PythonResult
from .receipts import LocalExecutionReceipt, content_hash
from .secrets import SecretStoreError


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
        python_service: LocalPythonService | None = None,
    ) -> None:
        self.server_url = server_url
        self.device_id = device_id
        self.session_id = session_id
        self.session_token = session_token
        self.private_key = private_key
        self.protocol_version = protocol_version
        self.runtime_version = runtime_version
        if capabilities is None:
            default_capabilities = ["echo"]
            if file_service is not None:
                default_capabilities.extend(
                    ("local.files.list", "local.files.read", "local.files.write")
                )
            if python_service is not None:
                default_capabilities.append("local.python")
            capabilities = tuple(default_capabilities)
        self.capabilities = capabilities
        self.policy_hash = policy_hash
        self.server_public_key = server_public_key
        self.policy = policy or LocalPolicy()
        self.file_service = file_service
        self.python_service = python_service
        self.connection: ClientConnection | None = None
        self._pending_consents: dict[str, ConsentRequest] = {}
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._cancelled_tasks: set[str] = set()

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
        await self.connection.send(
            json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        )

    async def run(self) -> None:
        """Receive signed tasks and return ACK/progress/result envelopes."""
        if self.connection is None:
            await self.connect()
        await self.send_hello()
        await self.send_capability_update()
        assert self.connection is not None
        server_hello = json.loads(await self.connection.recv())
        configured_key = self.server_public_key or str(
            server_hello.get("payload", {}).get("server_public_key", "")
        )
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
                task_id = envelope.task_id or ""
                task = asyncio.create_task(self._handle_task(envelope))
                self._running_tasks[task_id] = task
                task.add_done_callback(
                    lambda finished, current_task_id=task_id: self._task_finished(
                        current_task_id, finished
                    )
                )
            elif envelope.type == MessageType.CONSENT_DECISION:
                await self._handle_consent_decision(envelope, background=True)
            elif envelope.type == MessageType.TASK_CANCEL:
                await self._handle_task_cancel(envelope.task_id or "")

        tasks = tuple(self._running_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _task_finished(self, task_id: str, task: asyncio.Task[None]) -> None:
        self._running_tasks.pop(task_id, None)
        if not task.cancelled():
            task.exception()

    async def _handle_task_cancel(self, task_id: str) -> None:
        request = self._pending_consents.pop(task_id, None)
        if request is not None:
            self._cancelled_tasks.add(task_id)
            await self._send_error(
                task_id,
                "local task cancelled while waiting for consent",
                "CANCELLED",
                request.payload,
                request.capability,
                policy_decision=PolicyDecision.DENY.value,
                status="cancelled",
            )
        task = self._running_tasks.get(task_id)
        if task is not None:
            task.cancel()

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
                    await self._send_error(
                        task_id,
                        file_task.decision.value,
                        "POLICY_DENIED",
                        envelope.payload,
                        operation,
                    )
                    return
                result = file_task.value
                receipt = self._file_receipt(envelope, operation, result)
            elif operation == "local.files.write":
                file_task = self.handle_file_task(operation, dict(envelope.payload))
                if file_task.decision is PolicyDecision.CONSENT_REQUIRED:
                    if self.file_service is None:
                        raise RuntimeError(
                            "file_service is required for local file tasks"
                        )
                    request = ConsentExchange(self.file_service.consent).create_request(
                        operation, dict(envelope.payload)
                    )
                    self._pending_consents[task_id] = request
                    await self._send_consent_required(envelope, request)
                    return
                if file_task.decision is not PolicyDecision.ALLOW:
                    await self._send_error(
                        task_id,
                        file_task.decision.value,
                        "LOCAL_POLICY_DENIED",
                        envelope.payload,
                        operation,
                        policy_decision=file_task.decision.value,
                        status="denied",
                    )
                    return
                result = file_task.value
                receipt = self._file_receipt(
                    envelope, operation, result, consent_decision="always_allow"
                )
            elif operation == "local.python":
                if self.python_service is None:
                    raise RuntimeError(
                        "python_service is required for local Python tasks"
                    )
                python_result = await self.python_service.execute(
                    dict(envelope.payload),
                    on_output=lambda stream, output: self._send_python_output(
                        task_id, stream, output
                    ),
                )
                if python_result is PolicyDecision.CONSENT_REQUIRED:
                    request = ConsentExchange(
                        self.python_service.consent
                    ).create_request(operation, dict(envelope.payload))
                    self._pending_consents[task_id] = request
                    await self._send_consent_required(envelope, request)
                    return
                if python_result is not PolicyDecision.ALLOW and not isinstance(
                    python_result, PythonResult
                ):
                    await self._send_error(
                        task_id,
                        python_result.value,
                        "LOCAL_POLICY_DENIED",
                        envelope.payload,
                        operation,
                        policy_decision=python_result.value,
                        status="denied",
                    )
                    return
                assert isinstance(python_result, PythonResult)
                result = self._python_result_value(python_result)
                receipt = python_result.receipt
                if receipt is None:
                    raise RuntimeError(
                        "local Python execution did not produce a receipt"
                    )
                receipt = replace(receipt, task_id=task_id)
            else:
                raise ValueError("unsupported operation")
        except asyncio.CancelledError:
            await self._send_error(
                task_id,
                "local task cancelled",
                "CANCELLED",
                envelope.payload,
                operation,
                policy_decision=PolicyDecision.ALLOW.value,
                status="cancelled",
            )
            raise
        except FileAccessError as exc:
            await self._send_error(
                task_id, str(exc), exc.code, envelope.payload, operation
            )
            return
        except SecretStoreError as exc:
            # A secret reference or its backend failed: the task fails with a
            # stable code; there is no plaintext fallback path.
            await self._send_error(
                task_id, str(exc), exc.code, envelope.payload, operation
            )
            return
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            await self._send_error(
                task_id, str(exc), "INVALID_TASK", envelope.payload, operation
            )
            return
        await self.connection.send(
            json.dumps(
                sign_envelope(
                    private_key=self.private_key,
                    message_type=MessageType.TASK_PROGRESS,
                    device_id=self.device_id,
                    session_id=self.session_id or "",
                    task_id=task_id,
                    payload={"fraction": 1.0},
                ),
                separators=(",", ":"),
            )
        )
        await self.connection.send(
            json.dumps(
                sign_envelope(
                    private_key=self.private_key,
                    message_type=MessageType.TASK_RESULT,
                    device_id=self.device_id,
                    session_id=self.session_id or "",
                    task_id=task_id,
                    payload={"result": result, "receipt": receipt.as_dict()},
                ),
                separators=(",", ":"),
            )
        )

    def _file_receipt(
        self,
        envelope: Any,
        capability: str,
        result: Any,
        *,
        consent_decision: str | None = None,
        payload: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> LocalExecutionReceipt:
        payload = dict(envelope.payload if payload is None else payload)
        return LocalExecutionReceipt(
            run_id=str(payload.get("run_id", "")),
            task_id=task_id or envelope.task_id or "",
            capability=capability,
            policy_decision=PolicyDecision.ALLOW.value,
            status="completed",
            payload_hash=content_hash(payload),
            result_hash=content_hash(result),
            consent_decision=consent_decision,
        )

    @staticmethod
    def _python_result_value(result: PythonResult) -> dict[str, Any]:
        return {
            "status": result.status.value,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "artifact_refs": list(result.artifact_refs),
            "artifact_error": result.artifact_error,
        }

    async def _send_consent_required(
        self, envelope: Any, request: ConsentRequest
    ) -> None:
        assert self.connection is not None
        await self.connection.send(
            json.dumps(
                sign_envelope(
                    private_key=self.private_key,
                    message_type=MessageType.CONSENT_REQUIRED,
                    device_id=self.device_id,
                    session_id=self.session_id or "",
                    task_id=envelope.task_id,
                    payload={
                        "capability": request.capability,
                        "payload": request.payload,
                        "request_hash": request.request_hash,
                    },
                ),
                separators=(",", ":"),
            )
        )

    async def _handle_consent_decision(self, envelope: Any, *, background: bool = False) -> None:
        task_id = envelope.task_id or ""
        if task_id in self._cancelled_tasks:
            return
        request = self._pending_consents.pop(task_id, None)
        if (
            request is None
            or envelope.payload.get("request_hash") != request.request_hash
        ):
            await self._send_error(
                task_id,
                "consent request does not match",
                "CONSENT_MISMATCH",
                envelope.payload,
                request.capability if request else "local.files.write",
                policy_decision=PolicyDecision.DENY.value,
                status="denied",
            )
            return
        if request.capability == "local.python":
            service = self.python_service
        else:
            service = self.file_service
        if service is None:
            raise RuntimeError("required local service is unavailable")
        approved = bool(envelope.payload.get("approved", False))
        exchange = ConsentExchange(service.consent)
        exchange.decide(
            request,
            approved=approved,
            actor_id=str(envelope.payload.get("actor_id", "local-user")),
        )
        if not approved or not exchange.authorize(request, request.payload):
            await self._send_error(
                task_id,
                "local consent denied",
                "DENIED",
                request.payload,
                request.capability,
                policy_decision=PolicyDecision.DENY.value,
                status="denied",
                consent_decision="denied",
            )
            return
        if background:
            task = asyncio.create_task(self._execute_consented(envelope, request))
            self._running_tasks[task_id] = task
            task.add_done_callback(
                lambda finished, current_task_id=task_id: self._task_finished(
                    current_task_id, finished
                )
            )
            await asyncio.sleep(0)
            return
        await self._execute_consented(envelope, request)

    async def _execute_consented(self, envelope: Any, request: ConsentRequest) -> None:
        try:
            await self._execute_consented_inner(envelope, request)
        except asyncio.CancelledError:
            await self._send_error(
                envelope.task_id or "",
                "local task cancelled",
                "CANCELLED",
                request.payload,
                request.capability,
                policy_decision=PolicyDecision.ALLOW.value,
                status="cancelled",
                consent_decision="approved",
            )

    async def _execute_consented_inner(self, envelope: Any, request: ConsentRequest) -> None:
        task_id = envelope.task_id or ""
        if request.capability == "local.python":
            python_result = await self.python_service.execute(
                request.payload,
                consent=True,
                on_output=lambda stream, output: self._send_python_output(
                    task_id, stream, output
                ),
            )
            if not isinstance(python_result, PythonResult):
                decision = python_result
                value = None
            else:
                decision = PolicyDecision.ALLOW
                value = self._python_result_value(python_result)
                receipt = python_result.receipt
                if receipt is not None:
                    receipt = replace(receipt, task_id=task_id)
        else:
            file_task = self.file_service.execute(
                request.capability, request.payload, consent=True
            )
            decision = file_task.decision
            value = file_task.value
            receipt = self._file_receipt(
                envelope,
                request.capability,
                value,
                consent_decision="approved",
                payload=request.payload,
                task_id=task_id,
            )
        if decision is not PolicyDecision.ALLOW:
            await self._send_error(
                task_id,
                decision.value,
                "LOCAL_POLICY_DENIED",
                request.payload,
                request.capability,
                policy_decision=decision.value,
                status="denied",
                consent_decision="approved",
            )
            return
        if receipt is None:
            raise RuntimeError("local execution did not produce a receipt")
        await self.connection.send(
            json.dumps(
                sign_envelope(
                    private_key=self.private_key,
                    message_type=MessageType.TASK_RESULT,
                    device_id=self.device_id,
                    session_id=self.session_id or "",
                    task_id=task_id,
                    payload={
                        "result": value,
                        "receipt": receipt.as_dict(),
                    },
                ),
                separators=(",", ":"),
            )
        )

    async def _send_error(
        self,
        task_id: str,
        message: str,
        code: str,
        payload: dict[str, Any],
        capability: str,
        *,
        policy_decision: str = "allow",
        status: str = "failed",
        consent_decision: str | None = None,
    ) -> None:
        assert self.connection is not None
        receipt = LocalExecutionReceipt(
            run_id=str(payload.get("run_id", "")),
            task_id=task_id,
            capability=capability,
            policy_decision=policy_decision,
            status=status,
            payload_hash=content_hash(payload),
            consent_decision=consent_decision,
        )
        await self.connection.send(
            json.dumps(
                sign_envelope(
                    private_key=self.private_key,
                    message_type=MessageType.ERROR,
                    device_id=self.device_id,
                    session_id=self.session_id or "",
                    task_id=task_id,
                    payload={
                        "error_code": code,
                        "message": message,
                        "receipt": receipt.as_dict(),
                    },
                ),
                separators=(",", ":"),
            )
        )

    async def _send_python_output(self, task_id: str, stream: str, output: str) -> None:
        assert self.connection is not None
        await self.connection.send(
            json.dumps(
                sign_envelope(
                    private_key=self.private_key,
                    message_type=MessageType.TASK_PROGRESS,
                    device_id=self.device_id,
                    session_id=self.session_id or "",
                    task_id=task_id,
                    payload={"fraction": 0.0, "stream": stream, "output": output},
                ),
                separators=(",", ":"),
            )
        )

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

    def handle_file_task(
        self, capability: str, payload: dict[str, Any], *, consent: bool = False
    ) -> FileTaskResult:
        """Execute a list/read task through the configured logical-root store."""
        if capability not in {
            "local.files.list",
            "local.files.read",
            "local.files.write",
        }:
            raise ValueError("unsupported local file capability")
        if self.file_service is None:
            raise RuntimeError("file_service is required for local file tasks")
        return self.file_service.execute(capability, payload, consent=consent)
