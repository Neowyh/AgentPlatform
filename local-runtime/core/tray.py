"""The user-facing control surface: connection state, consent, and local audit.

The controller is deliberately headless. Everything a Tray needs — status, the
pending-consent queue, decisions, settings edits, audit queries — is an ordinary
method call on this object, so the whole control surface is testable without a
display server, and a thin UI (tkinter today, anything else later) only has to
render :class:`TrayStatus` and call back into it. Packaging the app is M12
(Local 方案 §22, §23).

The runtime loop runs on its own thread, which is what a desktop tray needs
anyway: the UI thread answers consent with :meth:`TrayController.decide` while
the loop thread is blocked waiting for that answer. Consent therefore completes
on this machine without a browser round trip (baseline §24), and every decision
is written to the local audit log either way.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

from .audit import AuditEntry, AuditKind, LocalAuditLog
from .consent import ConsentStore, PendingConsent
from .file_service import LocalFileService
from .files import LocalFileStore
from .mcp import LocalMCPService, MCPSupervisor, load_mcp_specs
from .policy import RiskLevel
from .python import LocalPythonService
from .secrets import (
    InMemorySecretStore,
    SecretBackendUnavailable,
    SecretResolver,
    SecretStoreError,
    create_default_secret_store,
)
from .settings import CapabilityRule, RuntimeSettings, load_settings
from .transport import ConsentDecisionError, LocalRuntimeClient

#: Reconnect delay after a dropped session, doubling up to a cap: a tray that
#: hammers a downed intranet makes the outage worse than the outage does.
RECONNECT_BACKOFF_SECONDS = 1.0
MAX_RECONNECT_BACKOFF_SECONDS = 30.0


class TrayError(RuntimeError):
    """A control-surface call could not be honoured."""


@dataclass(frozen=True)
class TrayStatus:
    """What the icon, its tooltip, and the status panel show (Local 方案 §23)."""

    connection: str
    server_url: str
    user_name: str
    device_name: str
    device_id: str
    runtime_version: str
    paused: bool
    allowed_roots: tuple[str, ...]
    capabilities: tuple[str, ...]
    mcp_servers: tuple[tuple[str, str], ...]
    pending_consents: int
    recent_execution: str
    audit_entries: int
    audit_integrity: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "connection": self.connection,
            "server_url": self.server_url,
            "user_name": self.user_name,
            "device_name": self.device_name,
            "device_id": self.device_id,
            "runtime_version": self.runtime_version,
            "paused": self.paused,
            "allowed_roots": list(self.allowed_roots),
            "capabilities": list(self.capabilities),
            "mcp_servers": [
                {"name": name, "state": state} for name, state in self.mcp_servers
            ],
            "pending_consents": self.pending_consents,
            "recent_execution": self.recent_execution,
            "audit_entries": self.audit_entries,
            "audit_integrity": self.audit_integrity,
        }


@dataclass
class TrayController:
    """Owns the runtime client, the consent queue, and the local audit log."""

    settings: RuntimeSettings
    private_key: Ed25519PrivateKey
    audit: LocalAuditLog | None = None
    consent_store_path: str | Path | None = None
    #: Server key captured at pairing. When set, the device verifies the broker
    #: against it instead of accepting the one offered in the HELLO reply.
    server_public_key: str | None = None

    def __post_init__(self) -> None:
        if self.audit is None:
            self.audit = LocalAuditLog(db_path=self.settings.audit_db_path or None)
        # One approval store for every service: an "always allow" or a denial
        # is per capability, so a shared store cannot leak a decision from one
        # capability to another, and it survives a restart as a unit.
        self.consent = ConsentStore(
            db_path=self.consent_store_path or self._default_consent_path()
        )
        self.secrets = _build_secret_resolver(self.settings, self._note_secret_use)
        self.mcp_service = _build_mcp_service(self.settings, self.secrets, self.consent)
        self.client = LocalRuntimeClient(
            server_url=self.settings.websocket_url(),
            device_id=self.settings.device_id,
            session_token=self.settings.session_token,
            private_key=self.private_key,
            server_public_key=self.server_public_key,
            runtime_version=self.settings.runtime_version,
            policy=self.settings.policy(),
            policy_hash=self.settings.policy_hash(),
            file_service=_build_file_service(self.settings, self.consent),
            python_service=_build_python_service(
                self.settings, self.secrets, self.consent
            ),
            mcp_service=self.mcp_service,
            audit=self.audit,
            consent_prompt=self._prompt,
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._serve_task: asyncio.Task[None] | None = None
        self._stopping = False
        # start/stop/disconnect are called from UI callbacks, which are not
        # ordered against each other; the lock makes "is a session owned?" a
        # single question with one answer per call.
        self._lifecycle = threading.Lock()
        self._last_audit_seq = 0

    def _default_consent_path(self) -> str | None:
        if not self.settings.audit_db_path:
            return None
        return str(Path(self.settings.audit_db_path).with_name("consent.db"))

    # --- runtime loop ----------------------------------------------------

    def start(self) -> None:
        """Run the client on its own thread; returns once the loop is live.

        The thread exists because consent does: the UI thread must be able to
        answer a request while the runtime thread is parked waiting for it.
        """
        def runner() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            loop.call_soon(ready.set)
            try:
                self._serve_task = loop.create_task(self._supervise())
                loop.run_until_complete(self._serve_task)
            except asyncio.CancelledError:
                pass  # stop()/disconnect() ended the session deliberately
            finally:
                _drain_pending(loop)
                loop.close()
                self._loop = None

        # One critical section for the whole handoff: _stopping is cleared and
        # both the thread and its loop are published before the lock is
        # released, so a teardown either sees a live session or sees none, and
        # a stop landing mid-start can never be undone by this call.
        with self._lifecycle:
            if self._thread is not None:
                raise TrayError("the tray controller is already started")
            self._stopping = False
            ready = threading.Event()
            self._thread = threading.Thread(
                target=runner, name="ideer-local-runtime", daemon=True
            )
            self._thread.start()
            if not ready.wait(timeout=5):
                # The thread exists but its loop never came up: stopping is
                # already set, so a runner that wakes late will not dial.
                raise TrayError("the runtime loop did not start")

    async def _supervise(self) -> None:
        """Keep the session up until :meth:`stop`, backing off between attempts."""
        backoff = RECONNECT_BACKOFF_SECONDS
        if self.mcp_service is not None:
            await self.mcp_service.supervisor.start_all()
        try:
            while not self._stopping:
                try:
                    await self.client.run()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - any failure means retry
                    # Not just OSError: a dropped websocket surfaces as
                    # ConnectionClosed, which is not an OSError, so a
                    # supervisor that caught only OSError would let the loop
                    # thread die under an icon that still reads "connected".
                    # SystemExit and KeyboardInterrupt are not Exception
                    # subclasses, so a real shutdown still stops the retry.
                    self.audit.record(
                        AuditKind.CONNECTION,
                        "connection_failed",
                        detail={"error": f"{type(exc).__name__}: {exc}"},
                    )
                if self._stopping:
                    break
                self.audit.record(
                    AuditKind.CONNECTION,
                    "reconnecting",
                    detail={"in_seconds": backoff},
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_RECONNECT_BACKOFF_SECONDS)
        finally:
            if self.mcp_service is not None:
                await self.mcp_service.supervisor.stop_all()

    def stop(self) -> None:
        """Stop the loop thread; open prompts are failed closed, not dropped."""
        self._teardown(actor_id="local-runtime")

    def _teardown(self, *, actor_id: str) -> bool:
        """End the session and join the loop thread; False if none was running.

        Cancel is issued from the loop itself, never from this thread: the
        runtime may be mid-dial, where closing a connection that does not exist
        yet would leave the thread waiting on a socket forever.
        """
        with self._lifecycle:
            thread, loop = self._thread, self._loop
            if thread is None or loop is None:
                return False
            self._stopping = True
        try:
            asyncio.run_coroutine_threadsafe(
                self._end_session(actor_id=actor_id), loop
            )
        except RuntimeError:
            # The loop closed on its own rather than being asked to stop, so
            # there is nothing to cancel on it; joining is all that is left.
            pass
        thread.join(timeout=10)
        with self._lifecycle:
            # Cleared either way: leaving a session on record would strand the
            # user on an icon they can neither reconnect nor explain.
            self._thread = None
            self._serve_task = None
        return True

    async def _end_session(self, *, actor_id: str) -> None:
        """Close the session, then end the supervise loop.

        Shutdown runs first so in-flight work is cancelled and open prompts
        fail closed, each outcome audited before the loop stops. The serve task
        is cancelled rather than awaited: awaiting it from inside itself would
        run the cancellation cleanup under a loop that is already ending, and
        the socket would close half-finished.
        """
        task = self._serve_task
        await self.client.shutdown(actor_id=actor_id)
        if task is not None:
            task.cancel()

    # --- display ---------------------------------------------------------

    def status(self) -> TrayStatus:
        client = self.client
        if self._thread is None:
            connection = "offline"
        elif not client.connected:
            connection = "connecting"
        elif client.paused:
            connection = "paused"
        else:
            connection = "connected"
        servers: tuple[tuple[str, str], ...] = ()
        if client.mcp_service is not None:
            supervisor = client.mcp_service.supervisor
            servers = tuple(
                (name, supervisor.state_of(name))
                for name in supervisor.server_names()
            )
        recent = self.audit.recent(limit=1, kind=AuditKind.EXECUTION)
        integrity = self.audit.verify()
        return TrayStatus(
            connection=connection,
            server_url=self.settings.server_url,
            user_name=self.settings.user_name,
            device_name=self.settings.device_name,
            device_id=self.settings.device_id,
            runtime_version=self.settings.runtime_version,
            paused=client.paused,
            allowed_roots=tuple(root.logical_root for root in self.settings.file_roots()),
            capabilities=client.current_capabilities(),
            mcp_servers=servers,
            pending_consents=len(client.pending_consents()),
            recent_execution=(
                f"{recent[0].capability} → {recent[0].action}" if recent else ""
            ),
            audit_entries=integrity.entries,
            audit_integrity="ok" if integrity.ok else integrity.problem or "broken",
        )

    # --- controls --------------------------------------------------------

    def pause(self, *, actor_id: str = "local-user") -> None:
        """Stop taking new work; in-flight tasks and open prompts complete.

        Pause never loses a task: the runtime answers each one with a
        structured ``DEVICE_PAUSED`` denial and a receipt, which the broker
        records — the same semantics the server's own pause path gives.
        """
        self.client.pause(actor_id=actor_id)

    def resume(self, *, actor_id: str = "local-user") -> None:
        self.client.resume(actor_id=actor_id)

    def disconnect(self, *, actor_id: str = "local-user") -> None:
        """Close the outbound session and stop reconnecting.

        Open prompts fail closed on the way out, and the server marks the
        device offline when the socket drops.
        """
        # Same teardown as a full stop; the tray itself keeps running, so what
        # the user sees afterwards is an offline icon, not a dead process.
        if not self._teardown(actor_id=actor_id):
            self.audit.record(
                AuditKind.CONTROL,
                "disconnect_requested",
                actor_id=actor_id,
                detail={"device_id": self.settings.device_id, "running": False},
            )

    def reconnect(self) -> None:
        """Re-open the session after a disconnect; pairing credentials are reused.

        Refused while anything is still attached: the pair credentials and the
        session token are good for a second socket, so a second ``start()``
        would be a duplicate device session rather than a resume.
        """
        with self._lifecycle:
            if self._thread is not None:
                raise TrayError("the tray controller is already running")
        self.start()

    # --- consent ---------------------------------------------------------

    def pending_consents(self) -> tuple[PendingConsent, ...]:
        return self.client.pending_consents()

    def decide(
        self,
        request: PendingConsent,
        *,
        approved: bool,
        actor_id: str = "local-user",
        always: bool = False,
    ) -> None:
        """Answer one request from the UI thread.

        ``always`` records an always-allow rule for that capability, and is
        refused for Level 2 work: a dangerous operation can never be moved out
        of the ask-first path (Local 方案 §9). Both outcomes are audited by the
        transport, which also binds the decision to the exact request hash shown.
        """
        if always and not request.silenceable:
            raise TrayError("a level 2 request cannot be always-allowed")
        try:
            self.client.resolve_local_consent(
                request.task_id, approved=approved, actor_id=actor_id, always=always
            )
        except ConsentDecisionError as exc:
            raise TrayError(str(exc)) from exc

    async def _prompt(self, request: PendingConsent) -> dict[str, Any] | None:
        """Keep an on-device request visible until it stops being answerable.

        The tray never answers through this coroutine: the UI thread calls
        :meth:`decide`, which settles the transport's own future, and the
        transport then cancels this task. Parking is therefore the honest
        behaviour — returning early would either imply a decision or hang the
        task past the point where the user could still answer it.
        """
        await asyncio.Event().wait()

    def risk_level(self, capability: str, payload: dict[str, Any]) -> RiskLevel:
        return self.client.policy.risk_level(capability, payload)

    # --- audit queries ---------------------------------------------------

    def audit_recent(
        self, *, limit: int = 50, kind: AuditKind | None = None
    ) -> list[AuditEntry]:
        return self.audit.recent(limit=limit, kind=kind)

    def audit_new_since(self) -> list[AuditEntry]:
        """Entries appended since the last call: what a live view must append."""
        entries = self.audit.since(self._last_audit_seq)
        if entries:
            self._last_audit_seq = entries[-1].seq
        return entries

    def audit_page(
        self,
        *,
        limit: int = 50,
        kinds: tuple[AuditKind, ...] = (),
        capability: str | None = None,
    ) -> list[AuditEntry]:
        return self.audit.filter(kinds=kinds, capability=capability, limit=limit)

    def clear_audit(self, *, actor_id: str = "local-user") -> dict[str, Any]:
        """Clear the visible history; the clear itself stays on record."""
        self._last_audit_seq = 0
        return self.audit.clear(actor_id=actor_id)

    def audit_integrity(self) -> str:
        result = self.audit.verify()
        return "ok" if result.ok else result.problem or "broken"

    # --- settings --------------------------------------------------------

    def save_settings(self) -> Path:
        """Write the current configuration and re-point the running client at it.

        A policy change takes effect on the next task without a restart, and the
        new hash is republished with the next capability update so the server
        can tell the device's policy moved.
        """
        if not self.settings.config_path:
            raise TrayError("no settings file is configured")
        self.apply_policy()
        self.audit.record(
            AuditKind.CONFIG,
            "saved",
            detail={"policy_hash": self.settings.policy_hash()},
        )
        return self.settings.save(self.settings.config_path)

    def apply_policy(self) -> None:
        """Push the current grading into every layer that enforces it.

        The client gates dispatch and each service re-checks before acting; if
        only one of them were updated, a rule change would half-apply.
        """
        policy = self.settings.policy()
        self.client.policy = policy
        self.client.policy_hash = self.settings.policy_hash()
        for service in (
            self.client.file_service,
            self.client.python_service,
            self.client.mcp_service,
        ):
            if service is not None:
                service.policy = policy

    def set_rule(self, capability: str, rule: CapabilityRule) -> None:
        """Grade one capability; the §9 tiers are the user's to choose."""
        self.settings.set_rule(capability, rule)
        self.apply_policy()
        self.audit.record(
            AuditKind.CONFIG,
            "rule_changed",
            capability=capability,
            detail={"rule": rule.value},
        )

    def set_risk_level(self, capability: str, level: RiskLevel) -> None:
        self.settings.set_risk_level(capability, level)
        self.apply_policy()
        self.audit.record(
            AuditKind.CONFIG,
            "risk_level_changed",
            capability=capability,
            detail={"risk_level": level.value},
        )

    def add_root(self, logical_root: str, physical_root: str | Path) -> None:
        """Widen or replace one allowed root and rebuild the store it feeds."""
        self.settings.add_root(logical_root, physical_root)
        self._rebuild_file_services()
        self.audit.record(
            AuditKind.CONFIG,
            "root_added",
            detail={"logical_root": logical_root},
        )

    def remove_root(self, logical_root: str) -> None:
        self.settings.remove_root(logical_root)
        self._rebuild_file_services()
        self.audit.record(
            AuditKind.CONFIG,
            "root_removed",
            detail={"logical_root": logical_root},
        )

    def _rebuild_file_services(self) -> None:
        store = LocalFileStore(self.settings.file_roots())
        if self.client.file_service is not None:
            self.client.file_service.files = store
        if self.client.python_service is not None:
            self.client.python_service.files = store

    # --- secrets (names and references only) -----------------------------

    def secret_names(self) -> tuple[str, ...]:
        """Configured secret names; the values never reach this process's view."""
        if self.secrets is None:
            return ()
        try:
            return self.secrets.store.names()
        except SecretStoreError:
            return ()

    def store_secret(self, name: str, value: str) -> None:
        """Put one credential in the OS store; nothing here keeps a copy.

        The tray only ever handles the name; a task references the value as
        ``local:<name>``, so plaintext stays out of settings, audit and wire.
        """
        if self.secrets is None:
            raise TrayError("no secure secret store is available on this device")
        self.secrets.store.set(name, value)
        self.audit.record(AuditKind.SECRET, "stored", detail={"ref": f"local:{name}"})

    def delete_secret(self, name: str) -> None:
        if self.secrets is None:
            raise TrayError("no secure secret store is available on this device")
        self.secrets.store.delete(name)
        self.audit.record(AuditKind.SECRET, "deleted", detail={"ref": f"local:{name}"})

    def secret_usage(self) -> list[AuditEntry]:
        return self.audit.filter(kinds=(AuditKind.SECRET,), limit=0)

    def _note_secret_use(self, names: tuple[str, ...]) -> None:
        for name in names:
            self.audit.record(
                AuditKind.SECRET,
                "resolved",
                detail={"ref": f"local:{name}"},
            )


def load_controller(
    path: str | Path,
    *,
    private_key: Ed25519PrivateKey | None = None,
    audit: LocalAuditLog | None = None,
) -> TrayController:
    """Build a controller from a settings file; a missing file is a fresh device."""
    settings = load_settings(path)
    settings.config_path = str(path)
    key_path = Path(path).with_name("runtime-key")
    private_key = private_key or _load_or_create_key(key_path)
    return TrayController(
        settings=settings,
        private_key=private_key,
        audit=audit,
        consent_store_path=Path(path).with_name("consent.db"),
    )


def _load_or_create_key(path: Path) -> Ed25519PrivateKey:
    """Read the device signing key, creating one on first run.

    The server pins the public key captured at pairing, so this file must
    outlive restarts: losing it means re-pairing, not a silent new identity.
    It is written unreadable to anyone but the user because it signs every
    frame this device sends.
    """
    if path.exists():
        try:
            key = load_pem_private_key(path.read_bytes(), password=None)
        except (ValueError, TypeError, OSError) as exc:
            raise TrayError(f"the device key at {path} could not be read") from exc
        if not isinstance(key, Ed25519PrivateKey):
            raise TrayError(f"{path} is not an Ed25519 key")
        return key
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    _write_private_key(path, key)
    return key


def _write_private_key(path: Path, key: Ed25519PrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
    )
    path.chmod(0o600)


def _drain_pending(loop: asyncio.AbstractEventLoop) -> None:
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))


def _build_secret_resolver(
    settings: RuntimeSettings, on_use: Any
) -> SecretResolver | None:
    """Resolve references locally; a missing OS backend degrades to no secrets."""
    if settings.secret_backend == "memory":
        return SecretResolver(InMemorySecretStore(), on_use=on_use)
    try:
        return SecretResolver(create_default_secret_store(), on_use=on_use)
    except SecretBackendUnavailable:
        return None


def _build_file_service(
    settings: RuntimeSettings, consent: ConsentStore
) -> LocalFileService | None:
    roots = settings.file_roots()
    if not roots:
        return None
    return LocalFileService(
        LocalFileStore(roots), policy=settings.policy(), consent=consent
    )


def _build_python_service(
    settings: RuntimeSettings, secrets: SecretResolver | None, consent: ConsentStore
) -> LocalPythonService | None:
    roots = settings.file_roots()
    if not roots:
        return None
    return LocalPythonService(
        LocalFileStore(roots),
        policy=settings.policy(),
        consent=consent,
        secrets=secrets,
    )


def _build_mcp_service(
    settings: RuntimeSettings,
    secrets: SecretResolver | None,
    consent: ConsentStore,
) -> LocalMCPService | None:
    if not settings.mcp_config_path:
        return None
    lookup = secrets.name_lookup() if secrets is not None else None
    supervisor = MCPSupervisor(
        load_mcp_specs(settings.mcp_config_path), secret_resolver=lookup
    )
    return LocalMCPService(
        supervisor, policy=settings.policy(), consent=consent
    )
