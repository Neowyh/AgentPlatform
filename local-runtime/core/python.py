"""Constrained local Python execution with bounded output and cancellation."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .artifacts import ArtifactUploader
from .consent import ConsentStore, request_hash
from .files import LocalFileStore
from .policy import LocalPolicy, PolicyDecision


class PythonTaskStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class PythonResult:
    status: PythonTaskStatus
    exit_code: int | None
    stdout: str
    stderr: str
    artifact_refs: tuple[str, ...] = ()


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
    ) -> None:
        self.files = files
        self.policy = policy or LocalPolicy()
        self.consent = consent or ConsentStore()
        self.uploader = uploader
        self.executor = executor or PythonExecutor()

    async def execute(
        self, payload: dict[str, object], *, consent: bool = False
    ) -> PythonResult | PolicyDecision:
        digest = request_hash(payload)
        decision = self.policy.authorize(
            "local.python",
            payload,
            consent=consent or self.consent.consume("local.python", digest),
        )
        if decision is not PolicyDecision.ALLOW:
            return decision
        working_root = self.files.resolve(str(payload["working_root"]))
        result = await self.executor.run(
            str(payload["script"]),
            working_root=working_root,
            args=[str(arg) for arg in payload.get("args", [])],
            timeout=float(payload.get("timeout", 30)),
        )
        if self.uploader is not None and result.status is PythonTaskStatus.COMPLETED:
            refs = []
            for logical_path in payload.get("expected_outputs", []):
                path = self.files.resolve(str(logical_path))
                refs.append(self.uploader.upload(path.name, path.read_bytes()))
            result = PythonResult(
                result.status,
                result.exit_code,
                result.stdout,
                result.stderr,
                tuple(refs),
            )
        return result


class PythonExecutor:
    def __init__(self, *, max_output_bytes: int = 64 * 1024) -> None:
        self.max_output_bytes = max_output_bytes

    async def run(
        self,
        script: str,
        *,
        working_root: Path,
        args: list[str] | None = None,
        timeout: float = 30,
    ) -> PythonResult:
        if not working_root.is_dir():
            raise ValueError("working_root must be a directory")
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        }
        process_options = {
            "cwd": working_root,
            "env": env,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            script,
            *(args or []),
            **process_options,
        )
        assert process.stdout is not None and process.stderr is not None
        stdout_task = asyncio.create_task(self._read_bounded(process.stdout))
        stderr_task = asyncio.create_task(self._read_bounded(process.stderr))
        try:
            await asyncio.wait_for(process.wait(), timeout)
            status = (
                PythonTaskStatus.COMPLETED
                if process.returncode == 0
                else PythonTaskStatus.FAILED
            )
        except asyncio.TimeoutError:
            self._terminate(process)
            await process.wait()
            status = PythonTaskStatus.TIMED_OUT
        except asyncio.CancelledError:
            self._terminate(process)
            await process.wait()
            status = PythonTaskStatus.CANCELLED
        stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
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
        )

    @staticmethod
    def _terminate(process: asyncio.subprocess.Process) -> None:
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

    async def _read_bounded(self, stream: asyncio.StreamReader) -> str:
        chunks: list[bytes] = []
        remaining = self.max_output_bytes
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            if remaining > 0:
                kept = chunk[:remaining]
                chunks.append(kept)
                remaining -= len(kept)
        return b"".join(chunks).decode("utf-8", errors="replace")
