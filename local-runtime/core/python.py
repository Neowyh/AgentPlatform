"""Constrained local Python execution with bounded output and cancellation."""

from __future__ import annotations

import asyncio
import ctypes
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .artifacts import ArtifactUploader
from .consent import ConsentStore, request_hash
from .files import LocalFileStore
from .policy import LocalPolicy, PolicyDecision
from .receipts import LocalExecutionReceipt, content_hash


class _WindowsJob:
    """Job Object that makes descendant cleanup a kernel-enforced property."""

    def __init__(self, pid: int) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows Job Objects are unavailable")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32 = kernel32
        self._handle = kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        try:
            class _BasicLimit(ctypes.Structure):
                _fields_ = [
                    ("per_process_user_time", ctypes.c_ulonglong),
                    ("per_job_user_time", ctypes.c_ulonglong),
                    ("limit_flags", ctypes.c_uint32),
                    ("min_working_set", ctypes.c_size_t),
                    ("max_working_set", ctypes.c_size_t),
                    ("active_process_limit", ctypes.c_uint32),
                    ("affinity", ctypes.c_size_t),
                    ("priority", ctypes.c_uint32),
                    ("scheduling_class", ctypes.c_uint32),
                ]

            class _IoCounters(ctypes.Structure):
                _fields_ = [("values", ctypes.c_ulonglong * 6)]

            class _ExtendedLimit(ctypes.Structure):
                _fields_ = [("basic", _BasicLimit), ("io", _IoCounters),
                            ("process_memory", ctypes.c_size_t),
                            ("job_memory", ctypes.c_size_t)]

            limits = _ExtendedLimit()
            # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000),
            # JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9.
            limits.basic.limit_flags = 0x2000
            if not kernel32.SetInformationJobObject(
                self._handle,
                9,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                raise OSError(
                    ctypes.get_last_error(), "SetInformationJobObject failed"
                )
            if not kernel32.AssignProcessToJobObject(self._handle, pid):
                raise OSError(
                    ctypes.get_last_error(), "AssignProcessToJobObject failed"
                )
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


class PythonTaskStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    UPLOAD_DENIED = "upload_denied"


@dataclass(frozen=True)
class PythonResult:
    status: PythonTaskStatus
    exit_code: int | None
    stdout: str
    stderr: str
    artifact_refs: tuple[str, ...] = ()
    stdout_hash: str | None = None
    stderr_hash: str | None = None
    stdout_log_path: str | None = None
    stderr_log_path: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    runtime_version: str | None = None
    receipt: LocalExecutionReceipt | None = None
    artifact_error: str | None = None


class _StreamingRedactor:
    """Redact credentials without exposing values split across output chunks."""

    _pattern = re.compile(
        r"(?i)(api[_-]?key|secret|token|password)(\s*[=:]\s*)[^\s,;]+"
    )

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, text: str, *, final: bool = False) -> str:
        self._pending += text
        redacted = self._pattern.sub(r"\1\2[REDACTED]", self._pending)
        if final:
            self._pending = ""
            return redacted
        keep = min(128, len(redacted))
        emitted, self._pending = redacted[:-keep], redacted[-keep:]
        return emitted


class LocalPythonService:
    """Policy and root-gated facade around :class:`PythonExecutor`."""

    def __init__(
        self,
        files: LocalFileStore,
        *,
        policy: LocalPolicy | None = None,
        consent: ConsentStore | None = None,
        uploader: ArtifactUploader | None = None,
        executor: PythonExecutor | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.files = files
        self.policy = policy or LocalPolicy()
        self.consent = consent or ConsentStore()
        self.uploader = uploader
        self.executor = executor or PythonExecutor()
        self.environment = dict(environment or {})

    async def execute(
        self,
        payload: dict[str, object],
        *,
        consent: bool = False,
        on_output: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> PythonResult | PolicyDecision:
        self._validate_payload(payload)
        digest = request_hash(payload)
        consent_granted = consent or self.consent.consume("local.python", digest)
        decision = self.policy.authorize(
            "local.python",
            payload,
            consent=consent_granted,
        )
        if decision is not PolicyDecision.ALLOW:
            return decision
        environment_names = [str(name) for name in payload.get("environment", [])]
        safe_environment_names = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        unavailable = {
            name
            for name in environment_names
            if name not in self.environment and name not in safe_environment_names
        }
        if unavailable:
            raise ValueError("environment reference is unavailable")
        working_root = self.files.resolve(str(payload["working_root"]))
        result = await self.executor.run(
            str(payload["script"]),
            working_root=working_root,
            args=[str(arg) for arg in payload.get("args", [])],
            timeout=float(payload.get("timeout", 30)),
            environment={
                name: self.environment[name]
                for name in payload.get("environment", [])
                if name in self.environment
            },
            on_output=on_output,
        )
        artifact_error: str | None = None
        if result.status is PythonTaskStatus.COMPLETED and payload.get(
            "expected_outputs"
        ):
            upload_decision = self.policy.authorize(
                "local.artifacts.upload", payload, consent=consent_granted
            )
            if upload_decision is not PolicyDecision.ALLOW:
                artifact_error = "artifact upload denied by local policy"
                result = replace(result, status=PythonTaskStatus.UPLOAD_DENIED)
            elif self.uploader is None:
                artifact_error = "artifact uploader is unavailable"
                result = replace(result, status=PythonTaskStatus.UPLOAD_DENIED)
        if (
            result.status is PythonTaskStatus.COMPLETED
            and self.uploader is not None
            and payload.get("expected_outputs")
        ):
            refs = []
            for logical_path in payload.get("expected_outputs", []):
                path = self.files.resolve(str(logical_path))
                refs.append(
                    self.uploader.upload(
                        path.name, self.files.read_bytes(str(logical_path))
                    )
                )
            result = replace(result, artifact_refs=tuple(refs))
        receipt = LocalExecutionReceipt(
            run_id=str(payload.get("run_id", "")),
            task_id=str(payload.get("task_id", "")),
            capability="local.python",
            policy_decision=PolicyDecision.ALLOW.value,
            status=(artifact_error and "upload_denied") or result.status.value,
            payload_hash=digest,
            result_hash=content_hash(
                {
                    "status": result.status.value,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            ),
            consent_decision="approved" if consent_granted else None,
            stdout_hash=result.stdout_hash,
            stderr_hash=result.stderr_hash,
            stdout_log_path=result.stdout_log_path,
            stderr_log_path=result.stderr_log_path,
            artifact_refs=result.artifact_refs,
            runtime_version=result.runtime_version,
            exit_code=result.exit_code,
            started_at=result.started_at,
            finished_at=result.finished_at,
        )
        return replace(result, receipt=receipt, artifact_error=artifact_error)

    @staticmethod
    def _validate_payload(payload: dict[str, object]) -> None:
        if not isinstance(payload.get("working_root"), str):
            raise TypeError("working_root is required")
        if not isinstance(payload.get("script"), str):
            raise TypeError("script is required")
        if payload.get("runtime", "python") not in {"python", "python3"}:
            raise ValueError("unsupported Python runtime")
        for field in ("args", "expected_outputs"):
            value = payload.get(field, [])
            if not isinstance(value, list) or any(
                not isinstance(item, str) for item in value
            ):
                raise ValueError(f"{field} must be a list of strings")
        environment = payload.get("environment", [])
        if not isinstance(environment, list) or any(
            not isinstance(name, str) for name in environment
        ):
            raise ValueError("environment references must be a list of names")


class PythonExecutor:
    def __init__(
        self,
        *,
        max_output_bytes: int = 64 * 1024,
        max_output_rate_bytes: int = 64 * 1024,
    ) -> None:
        self.max_output_bytes = max_output_bytes
        self.max_output_rate_bytes = max_output_rate_bytes

    async def run(
        self,
        script: str,
        *,
        working_root: Path,
        args: list[str] | None = None,
        timeout: float = 30,
        environment: Mapping[str, str] | None = None,
        on_output: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> PythonResult:
        if not working_root.is_dir():
            raise ValueError("working_root must be a directory")
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        }
        for name, value in (environment or {}).items():
            if not name or "=" in name or "\x00" in name or "\x00" in value:
                raise ValueError("environment references must be valid names")
            env[name] = value
        process_options = {
            "cwd": working_root,
            "env": env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True
        started_at = datetime.now(UTC)
        with (
            tempfile.NamedTemporaryFile(
                mode="w+b", prefix="local-python-stdout-", delete=False
            ) as stdout_file,
            tempfile.NamedTemporaryFile(
                mode="w+b", prefix="local-python-stderr-", delete=False
            ) as stderr_file,
        ):
            process_options["stdout"] = stdout_file
            process_options["stderr"] = stderr_file
            process = subprocess.Popen(  # noqa: ASYNC220
                [sys.executable, "-I", "-c", script, *(args or [])],
                **process_options,
            )
            job = None
            if os.name == "nt":
                try:
                    job = _WindowsJob(process.pid)
                except Exception:
                    self._terminate(process)
                    await self._wait_until_exited(process)
                    raise RuntimeError("reliable Windows process cleanup unavailable")
            try:
                deadline = asyncio.get_running_loop().time() + timeout
                output_offsets = {"stdout": 0, "stderr": 0}
                redactors = {
                    "stdout": _StreamingRedactor(),
                    "stderr": _StreamingRedactor(),
                }
                output_window_started = asyncio.get_running_loop().time()
                output_window_bytes = {"stdout": 0, "stderr": 0}
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise TimeoutError
                    if on_output is not None:
                        for stream, output_file in (
                            ("stdout", stdout_file),
                            ("stderr", stderr_file),
                        ):
                            chunk, output_offsets[stream] = self._read_output_delta(
                                output_file.name, output_offsets[stream]
                            )
                            if not chunk:
                                continue
                            now = asyncio.get_running_loop().time()
                            if now - output_window_started >= 1:
                                output_window_started = now
                                output_window_bytes = {"stdout": 0, "stderr": 0}
                            available = max(
                                0,
                                self.max_output_rate_bytes
                                - output_window_bytes[stream],
                            )
                            visible = redactors[stream].feed(
                                chunk.decode("utf-8", errors="replace")
                            )
                            if available and visible:
                                visible = visible[:available]
                                await on_output(stream, visible)
                                output_window_bytes[stream] += len(
                                    visible.encode("utf-8")
                                )
                    if process.poll() is not None:
                        break
                    await asyncio.sleep(min(0.05, remaining))
                status = (
                    PythonTaskStatus.COMPLETED
                    if process.returncode == 0
                    else PythonTaskStatus.FAILED
                )
            except TimeoutError:
                self._terminate(process)
                await self._wait_until_exited(process)
                status = PythonTaskStatus.TIMED_OUT
            except asyncio.CancelledError:
                self._terminate(process)
                await self._wait_until_exited(process)
                status = PythonTaskStatus.CANCELLED
            if on_output is not None:
                for stream, redactor in redactors.items():
                    tail = redactor.feed("", final=True)
                    available = max(
                        0, self.max_output_rate_bytes - output_window_bytes[stream]
                    )
                    if tail and available:
                        visible = tail[:available]
                        await on_output(stream, visible)
                        output_window_bytes[stream] += len(visible.encode("utf-8"))
            stdout, stdout_hash = self._summarize_log(stdout_file.name)
            stderr, stderr_hash = self._summarize_log(stderr_file.name)
            if job is not None:
                job.close()
        finished_at = datetime.now(UTC)
        if status is PythonTaskStatus.TIMED_OUT:
            stderr = "execution timed out"
        elif status is PythonTaskStatus.CANCELLED:
            stderr = "execution cancelled"
        return PythonResult(
            status,
            process.returncode
            if status not in {PythonTaskStatus.TIMED_OUT, PythonTaskStatus.CANCELLED}
            else None,
            stdout,
            stderr,
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            stdout_log_path=stdout_file.name,
            stderr_log_path=stderr_file.name,
            started_at=started_at,
            finished_at=finished_at,
            runtime_version=sys.version.split()[0],
        )

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if os.name != "nt" and process.pid is not None:
            try:
                os.killpg(process.pid, 9)
                return
            except ProcessLookupError:
                return
        if os.name == "nt" and process.pid is not None:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
            return
        process.kill()

    @staticmethod
    async def _wait_until_exited(process: subprocess.Popen[bytes]) -> None:
        while process.poll() is None:
            await asyncio.sleep(0.01)

    @staticmethod
    def _read_output_delta(path: str, offset: int) -> tuple[bytes, int]:
        with open(path, "rb") as output_file:
            output_file.seek(offset)
            chunk = output_file.read()
        return chunk, offset + len(chunk)

    @staticmethod
    def _redact(output: str) -> str:
        return re.sub(
            r"(?i)(api[_-]?key|secret|token|password)(\s*[=:]\s*)[^\s,;]+",
            r"\1\2[REDACTED]",
            output,
        )

    def _summarize_log(self, path: str) -> tuple[str, str]:
        digest = hashlib.sha256()
        preview = bytearray()
        with open(path, "rb") as output_file:
            while chunk := output_file.read(64 * 1024):
                digest.update(chunk)
                if len(preview) < self.max_output_bytes:
                    preview.extend(chunk[: self.max_output_bytes - len(preview)])
        return self._redact(
            bytes(preview).decode("utf-8", errors="replace")
        ), digest.hexdigest()
