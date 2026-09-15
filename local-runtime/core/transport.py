"""Outbound-only WebSocket transport for the harmless M7 echo task."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.asyncio.client import ClientConnection, connect

from .audit import AuditEntry, AuditKind, LocalAuditLog
from .consent import (
    ConsentExchange,
    ConsentRequest,
    ConsentStore,
    PendingConsent,
    request_summary,
)
from .file_service import FileTaskResult, LocalFileService
from .files import FileAccessError
from .mcp import LocalMCPService, MCPExecution
from .policy import LocalPolicy, PolicyDecision, RiskLevel
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


class ConsentDecisionError(RuntimeError):
    """The request is unknown, already answered, or not answerable here."""


class ConsentUnavailableError(RuntimeError):
    """A decision was asked for while the local runtime is not running."""


#: Seconds an unanswered on-device prompt waits before it auto-denies itself.
CONSENT_TIMEOUT_SECONDS = 300.0

#: Asks the local user about one pending request and resolves to their answer
#: (``{"approved": bool, "actor_id": str, "always": bool}``) or ``None`` when
#: nobody can answer it. Implemented by the tray; the transport never renders.
ConsentPrompt = Callable[[PendingConsent], Awaitable[dict[str, Any] | None]]


@dataclass
class _LocalConsent:
    """A consent request this device will answer itself, on the tray."""

    request: ConsentRequest
    future: asyncio.Future[Any]
    loop: asyncio.AbstractEventLoop
    requested_at: float
    task_id: str
    #: The prompt coroutine; cancelled when the request stops being answerable.
    prompt: asyncio.Future[Any] | None = None
    #: Why nobody answered (disconnect, timeout); recorded in the audit as-is.
    abandoned_reason: str | None = None


@dataclass
class _RelayedConsent:
    """A consent request forwarded to the server, pending a browser decision."""

    request: ConsentRequest
    requested_at: float


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
        mcp_service: LocalMCPService | None = None,
        audit: LocalAuditLog | None = None,
        consent_prompt: ConsentPrompt | None = None,
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
        self.mcp_service = mcp_service
        if self.mcp_service is not None:
            self.mcp_service.on_capabilities_changed = self._on_mcp_capabilities_changed
        self.connection: ClientConnection | None = None
        self.audit = audit or LocalAuditLog()
        self.consent_prompt = consent_prompt
        self.paused = False
        self.connected = False
        self._last_sent_capabilities: tuple[str, ...] | None = None
        self._relayed_consents: dict[str, _RelayedConsent] = {}
        self._local_consents: dict[str, _LocalConsent] = {}
        self._answered_consents: set[str] = set()
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._cancelled_tasks: set[str] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    # --- user controls ---------------------------------------------------

    def pause(self, *, actor_id: str = "local-user") -> None:
        """Stop accepting new tasks; in-flight work and prompts complete."""
        if self.paused:
            return
        self.paused = True
        self._record(
            AuditKind.CONTROL,
            "paused",
            actor_id=actor_id,
            detail={"accepting_tasks": False},
        )

    def resume(self, *, actor_id: str = "local-user") -> None:
        if not self.paused:
            return
        self.paused = False
        self._record(
            AuditKind.CONTROL,
            "resumed",
            actor_id=actor_id,
            detail={"accepting_tasks": True},
        )

    async def close(self, *, actor_id: str = "local-user") -> None:
        """Drop the outbound session, failing open prompts closed."""
        self._record(
            AuditKind.CONNECTION,
            "disconnecting",
            actor_id=actor_id,
            detail={"device_id": self.device_id},
        )
        await self._end_connection(actor_id=actor_id, reason="the local runtime disconnected")

    async def _end_connection(self, *, actor_id: str, reason: str) -> None:
        """Drop the socket and cancel anything still running on the old session.

        A session that has ended cannot answer a consent prompt or deliver a
        task result, so an in-flight task is stopped here rather than left to
        finish its local side effect with nowhere to report it. This is the
        teardown both an explicit :meth:`close` and a dropped connection use —
        a retry has to start from no connection at all, or it would write its
        next hello into a dead socket.
        """
        self._abandon_pending_consents(reason=reason)
        tasks = tuple(self._running_tasks.values())
        for task in tasks:
            task.cancel()
        # Nothing is awaited between reading the socket and clearing it, so a
        # session that has ended can never leave a connection object behind for
        # a retry to mistake as live.
        connection = self.connection
        self.connected = False
        self.connection = None
        try:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if connection is not None:
                await connection.close()

    async def shutdown(self, *, actor_id: str = "local-user") -> None:
        """Stop the runtime: cancel in-flight tasks, then close the session."""
        for task in tuple(self._running_tasks.values()):
            task.cancel()
        await self.close(actor_id=actor_id)

    def _abandon_pending_consents(self, *, reason: str) -> None:
        """Fail open on-device prompts closed; nothing waits on a dead session."""
        for task_id in tuple(self._local_consents):
            self._abandon_local_consent(task_id, reason=reason)
        self._relayed_consents.clear()

    def _record(
        self,
        kind: AuditKind,
        action: str,
        *,
        capability: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        digest: str | None = None,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.audit.record(
            kind,
            action,
            capability=capability,
            task_id=task_id,
            run_id=run_id,
            digest=digest,
            actor_id=actor_id,
            detail=detail,
        )

    async def connect(self) -> ClientConnection:
        """Open the device-initiated connection; the server is never dialed back."""
        connection = await connect(self.server_url)
        self.connection = connection
        return connection

    def current_capabilities(self) -> tuple[str, ...]:
        """The capability set this device would announce right now."""
        return self._current_capabilities()

    def busy(self) -> bool:
        """Whether a task or consent round trip is still in flight."""
        return bool(self._running_tasks) or bool(self._local_consents)

    def _current_capabilities(self) -> tuple[str, ...]:
        """Static capabilities plus the live ``local.mcp.*`` projection."""
        if self.mcp_service is None:
            return tuple(self.capabilities)
        merged = list(self.capabilities)
        merged.extend(
            name
            for name in self.mcp_service.supervisor.capabilities()
            if name not in merged
        )
        return tuple(merged)

    async def send_hello(self) -> None:
        if self.connection is None:
            raise RuntimeError("connect() must be called before send_hello()")
        self.session_id = self.session_id or new_session_id()
        self._last_sent_capabilities = self._current_capabilities()
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
                "capabilities": list(self._current_capabilities()),
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
        self._last_sent_capabilities = self._current_capabilities()
        message = sign_envelope(
            private_key=self.private_key,
            message_type=MessageType.CAPABILITY_UPDATE,
            device_id=self.device_id,
            session_id=self.session_id,
            payload={
                "capabilities": list(self._current_capabilities()),
                "policy_hash": self.policy_hash,
            },
        )
        await self.connection.send(
            json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        )

    async def _on_mcp_capabilities_changed(self) -> None:
        """Republish capabilities when a server reports a tool-set change."""
        if self.connection is None or self.session_id is None:
            return
        current = self._current_capabilities()
        if current != self._last_sent_capabilities:
            await self.send_capability_update()

    async def refresh_mcp_capabilities(self) -> None:
        """Re-enumerate tools from enabled servers; republish when the set changed."""
        if self.mcp_service is None:
            return
        await self.mcp_service.supervisor.refresh_all()
        await self._on_mcp_capabilities_changed()

    async def run(self) -> None:
        """Receive signed tasks and return ACK/progress/result envelopes."""
        self._loop = asyncio.get_running_loop()
        if self.connection is None:
            await self.connect()
        await self.send_hello()
        await self.send_capability_update()
        self.connected = True
        self._record(
            AuditKind.CONNECTION,
            "connected",
            detail={"server_url": self.server_url, "device_id": self.device_id},
        )
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
        try:
            await self._receive_loop()
        finally:
            # Reached on every exit: a clean close, an aborted socket and a
            # verification failure all end here. Without this the next run()
            # finds self.connection still set and "sends" hello to a socket
            # that is already gone, so the device never redials.
            if self.connection is not None:
                await self._end_connection(
                    actor_id="local-runtime",
                    reason="the session with the server ended",
                )

    async def _receive_loop(self) -> None:
        """Verify and dispatch frames until the session ends."""
        assert self.connection is not None
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

    def _task_finished(self, task_id: str, task: asyncio.Task[None]) -> None:
        self._running_tasks.pop(task_id, None)
        if not task.cancelled():
            task.exception()

    async def _handle_task_cancel(self, task_id: str) -> None:
        relayed = self._relayed_consents.pop(task_id, None)
        request = relayed.request if relayed is not None else None
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
        operation = str(envelope.payload.get("operation", ""))
        if self.paused:
            # Pause never drops a task silently: the caller gets a structured
            # denial carrying a receipt, which the broker records as DENIED.
            await self._send_error(
                task_id,
                "local runtime is paused; no new tasks are accepted",
                "DEVICE_PAUSED",
                dict(envelope.payload),
                operation,
                policy_decision=PolicyDecision.DENY.value,
                status="denied",
            )
            return
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
        self._record(
            AuditKind.TASK,
            "accepted",
            capability=operation,
            task_id=task_id,
            run_id=str(envelope.payload.get("run_id", "")),
        )
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
                    assert self.file_service is not None
                    await self._request_consent(
                        envelope,
                        dict(envelope.payload),
                        self.file_service.consent,
                    )
                    return
                if file_task.decision is not PolicyDecision.ALLOW:
                    self._record_policy_denial(operation, task_id, envelope.payload)
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
                    await self._request_consent(
                        envelope,
                        dict(envelope.payload),
                        self.python_service.consent,
                    )
                    return
                if python_result is not PolicyDecision.ALLOW and not isinstance(
                    python_result, PythonResult
                ):
                    self._record_policy_denial(operation, task_id, envelope.payload)
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
            elif operation.startswith("local.mcp."):
                if self.mcp_service is None:
                    raise RuntimeError("mcp_service is required for local MCP tasks")
                execution = await self.mcp_service.execute(
                    operation, dict(envelope.payload)
                )
                if execution is PolicyDecision.CONSENT_REQUIRED:
                    await self._request_consent(
                        envelope,
                        dict(envelope.payload),
                        self.mcp_service.consent,
                    )
                    return
                if not isinstance(execution, MCPExecution):
                    self._record_policy_denial(operation, task_id, envelope.payload)
                    await self._send_error(
                        task_id,
                        execution.value,
                        "LOCAL_POLICY_DENIED",
                        envelope.payload,
                        operation,
                        policy_decision=execution.value,
                        status="denied",
                    )
                    return
                result = execution.value
                receipt = replace(execution.receipt, task_id=task_id)
            else:
                raise ValueError("unsupported operation")
        except asyncio.CancelledError:
            self._record(
                AuditKind.TASK,
                "cancelled",
                capability=operation,
                task_id=task_id,
                run_id=str(envelope.payload.get("run_id", "")),
            )
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
        self._record_execution(receipt)
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

    def _record_policy_denial(
        self, capability: str, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Record a device-side veto, which no receipt would otherwise show."""
        self._record(
            AuditKind.POLICY,
            "denied",
            capability=capability,
            task_id=task_id,
            run_id=str(payload.get("run_id", "")),
            detail={
                "risk_level": self.policy.risk_level(capability, dict(payload)).value
            },
        )

    def _record_execution(self, receipt: LocalExecutionReceipt) -> None:
        """One audit row per finished local execution, keyed by its receipt.

        Callers record before sending the result: the local log must never lag
        a frame the network already delivered, or a user opening their history
        right after an outcome appears sees nothing.
        """
        kind = (
            AuditKind.MCP
            if receipt.capability.startswith("local.mcp.")
            else AuditKind.EXECUTION
        )
        self._record(
            kind,
            receipt.status,
            capability=receipt.capability,
            task_id=receipt.task_id,
            run_id=receipt.run_id,
            digest=receipt.payload_hash,
            detail={
                "result_hash": receipt.result_hash,
                "consent_decision": receipt.consent_decision,
                "policy_decision": receipt.policy_decision,
            },
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

    # --- consent: one request, two answering surfaces --------------------

    def _pending_view(self, task_id: str, request: ConsentRequest) -> PendingConsent:
        """The renderable form of a request, shared by the tray and the server."""
        level = self.policy.risk_level(request.capability, request.payload)
        return PendingConsent(
            task_id=task_id,
            capability=request.capability,
            payload=dict(request.payload),
            request_hash=request.request_hash,
            risk_level=level.value,
            # Level 2 is displayed but never silenceable (§9: dangerous work
            # has no "always allow" escape hatch).
            silenceable=level is not RiskLevel.LEVEL_2,
            summary=request_summary(
                request.capability, request.payload, request_hash=request.request_hash
            ),
            requested_at=time.monotonic(),
        )

    def pending_consents(self) -> tuple[PendingConsent, ...]:
        """Every request awaiting a decision, newest first."""
        entries = [
            self._pending_view(task_id, consent.request)
            for task_id, consent in self._local_consents.items()
        ]
        entries.extend(
            self._pending_view(task_id, consent.request)
            for task_id, consent in self._relayed_consents.items()
        )
        entries.sort(key=lambda item: item.requested_at, reverse=True)
        return tuple(entries)

    async def _request_consent(
        self,
        envelope: Any,
        payload: dict[str, Any],
        store: ConsentStore,
    ) -> None:
        """Ask about one task: locally when a tray is attached, else upstream.

        Both routes bind the same ``request_hash`` and settle through
        :meth:`_settle_consent`, so a tray decision and a browser decision
        authorize exactly the same bytes.
        """
        task_id = envelope.task_id or ""
        request = ConsentExchange(store).create_request(
            str(payload.get("operation", "")), payload
        )
        self._record(
            AuditKind.CONSENT,
            "required",
            capability=request.capability,
            task_id=task_id,
            run_id=str(payload.get("run_id", "")),
            digest=request.request_hash,
            detail={
                "origin": "tray" if self.consent_prompt is not None else "server",
                "summary": request_summary(request.capability, payload),
            },
        )
        if self.consent_prompt is None:
            self._relayed_consents[task_id] = _RelayedConsent(
                request, time.monotonic()
            )
            await self._send_consent_required(envelope, request)
            return
        loop = asyncio.get_running_loop()
        consent = _LocalConsent(
            request=request,
            future=loop.create_future(),
            loop=loop,
            requested_at=time.monotonic(),
            task_id=task_id,
        )
        self._local_consents[task_id] = consent
        try:
            answer = await self._await_local_consent(consent)
        finally:
            consent.prompt = None
            self._local_consents.pop(task_id, None)
        if answer is None:
            await self._deny_unanswered(envelope, request, reason=consent.abandoned_reason)
            return
        await self._settle_consent(
            envelope,
            request,
            store,
            approved=bool(answer.get("approved")),
            actor_id=str(answer.get("actor_id", "local-user")),
            always=bool(answer.get("always")),
            origin="tray",
        )

    async def _await_local_consent(
        self, consent: _LocalConsent
    ) -> dict[str, Any] | None:
        """Wait for the user, whichever way the answer arrives.

        Two channels can end the wait: the prompt surface returns an answer (a
        CLI, or a tray that decides for itself), or the UI thread calls
        :meth:`resolve_local_consent` and settles ``consent.future``. If the
        request stops being answerable — the task is cancelled, the session
        closes, the timeout expires — the caller abandons it, which cancels the
        prompt so no surface is left showing a dead request.
        """
        assert self.consent_prompt is not None
        pending = self._pending_view(consent.task_id, consent.request)
        prompt = asyncio.ensure_future(self.consent_prompt(pending))
        consent.prompt = prompt
        try:
            done, _ = await asyncio.wait(
                {prompt, consent.future},
                timeout=CONSENT_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
        except asyncio.CancelledError:
            prompt.cancel()
            raise
        if not done:
            self._abandon_local_consent(
                consent.task_id, reason="the consent request timed out"
            )
            await self._close_prompt(prompt)
            return None
        if consent.future.done() and not consent.future.cancelled():
            # The user answered, or nobody can anymore; either way the prompt
            # coroutine is no longer wanted.
            await self._close_prompt(prompt)
            return consent.future.result()
        try:
            answer = prompt.result()
        except asyncio.CancelledError:
            answer = None
        except Exception:
            # A broken prompt surface must never imply consent.
            answer = None
        return answer

    @staticmethod
    async def _close_prompt(prompt: asyncio.Future[Any]) -> None:
        """Cancel a prompt nobody is waiting on anymore, and reap its result."""
        prompt.cancel()
        try:
            await prompt
        except (asyncio.CancelledError, Exception):
            pass

    def resolve_local_consent(
        self,
        task_id: str,
        *,
        approved: bool,
        actor_id: str = "local-user",
        always: bool = False,
    ) -> None:
        """Answer a pending on-device request from the UI thread."""
        consent = self._local_consents.get(task_id)
        if consent is None:
            raise ConsentDecisionError("no local consent is pending for this task")
        if consent.future.done():
            raise ConsentDecisionError("this request was already answered")
        answer = {
            "approved": approved,
            "actor_id": actor_id,
            "always": always,
        }

        def settle() -> None:
            if not consent.future.done():
                consent.future.set_result(answer)

        try:
            consent.loop.call_soon_threadsafe(settle)
        except RuntimeError as exc:
            raise ConsentUnavailableError(
                "the local runtime is not running"
            ) from exc

    def _abandon_local_consent(self, task_id: str, *, reason: str) -> None:
        """Answer a prompt with "nobody can answer", never with implied consent."""
        consent = self._local_consents.pop(task_id, None)
        if consent is None:
            return
        consent.abandoned_reason = reason
        if not consent.future.done():
            consent.future.set_result(None)
        if consent.prompt is not None and not consent.prompt.done():
            consent.prompt.cancel()

    async def _deny_unanswered(
        self,
        envelope: Any,
        request: ConsentRequest,
        *,
        reason: str | None = None,
    ) -> None:
        """Nobody answered: fail closed and record why nobody did."""
        task_id = envelope.task_id or ""
        self._answered_consents.add(task_id)
        self._record(
            AuditKind.CONSENT,
            "unanswered",
            capability=request.capability,
            task_id=task_id,
            run_id=str(request.payload.get("run_id", "")),
            digest=request.request_hash,
            detail={
                "origin": "tray",
                "outcome": "denied",
                "reason": reason or "no local answer",
            },
        )
        if self.connection is None:
            # The session went away with the request: the local audit still
            # records the outcome, and the server learns from the disconnect.
            return
        await self._send_error(
            task_id,
            "no local consent was given",
            "DENIED",
            request.payload,
            request.capability,
            policy_decision=PolicyDecision.DENY.value,
            status="denied",
            consent_decision="denied",
        )

    async def _settle_consent(
        self,
        envelope: Any,
        request: ConsentRequest,
        store: ConsentStore,
        *,
        approved: bool,
        actor_id: str,
        always: bool = False,
        origin: str,
    ) -> None:
        """Record the decision, then run or refuse exactly what was shown."""
        task_id = envelope.task_id or ""
        self._answered_consents.add(task_id)
        exchange = ConsentExchange(store)
        exchange.decide(request, approved=approved, actor_id=actor_id)
        if approved and always:
            store.set_always_allow(request.capability)
        self._record(
            AuditKind.CONSENT,
            "always_allowed" if approved and always else "approved" if approved else "denied",
            capability=request.capability,
            task_id=task_id,
            run_id=str(request.payload.get("run_id", "")),
            digest=request.request_hash,
            actor_id=actor_id,
            detail={"origin": origin, "binds_to_payload": True},
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
        await self._execute_consented(envelope, request)

    def expire_consents(self, *, now: float | None = None) -> tuple[str, ...]:
        """Auto-deny prompts nobody answered, so nothing hangs indefinitely."""
        cutoff = (now if now is not None else time.monotonic()) - CONSENT_TIMEOUT_SECONDS
        expired = [
            task_id
            for task_id, consent in self._local_consents.items()
            if consent.requested_at <= cutoff
        ]
        for task_id in expired:
            self._abandon_local_consent(
                task_id, reason="the consent request timed out"
            )
        return tuple(expired)

    def _consent_service_store(self, capability: str) -> ConsentStore:
        if capability.startswith("local.mcp."):
            service: Any = self.mcp_service
        elif capability == "local.python":
            service = self.python_service
        else:
            service = self.file_service
        if service is None:
            raise RuntimeError("required local service is unavailable")
        return service.consent

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
        relayed = self._relayed_consents.pop(task_id, None)
        request = relayed.request if relayed is not None else None
        if request is None and task_id in self._answered_consents:
            # The tray already decided this one; its outcome is on its way to
            # the server. A late browser decision must not act twice.
            self._record(
                AuditKind.CONSENT,
                "ignored_duplicate",
                task_id=task_id,
                detail={"origin": "server"},
            )
            return
        if request is None or envelope.payload.get("request_hash") != request.request_hash:
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
        store = self._consent_service_store(request.capability)
        approved = bool(envelope.payload.get("approved", False))
        actor_id = str(envelope.payload.get("actor_id", "local-user"))
        if background:
            task = asyncio.create_task(
                self._settle_consent(
                    envelope,
                    request,
                    store,
                    approved=approved,
                    actor_id=actor_id,
                    origin="server",
                )
            )
            self._running_tasks[task_id] = task
            task.add_done_callback(
                lambda finished, current_task_id=task_id: self._task_finished(
                    current_task_id, finished
                )
            )
            await asyncio.sleep(0)
            return
        await self._settle_consent(
            envelope,
            request,
            store,
            approved=approved,
            actor_id=actor_id,
            origin="server",
        )

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
        if request.capability.startswith("local.mcp."):
            execution = await self.mcp_service.execute(
                request.capability, request.payload, consent=True
            )
            if not isinstance(execution, MCPExecution):
                decision = execution
                value = None
                receipt = None
            else:
                decision = PolicyDecision.ALLOW
                value = execution.value
                receipt = replace(execution.receipt, task_id=task_id)
        elif request.capability == "local.python":
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
        self._record_execution(receipt)
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
        if self.connection is None:
            # Nothing to report to: the session ended first. The local audit
            # carries the outcome, and the broker resolves the task by timeout.
            return
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
