import asyncio
import hashlib
from pathlib import Path

import pytest

from core.artifacts import (
    ArtifactUploadError,
    FileArtifactUploader,
    MemoryArtifactUploader,
    SingleUseUploadGrant,
)
from core.consent import ConsentStore, request_hash
from core.files import LocalFileStore, RootConfig
from core.policy import LocalPolicy, PolicyDecision
from core.python import LocalPythonService, PythonExecutor, PythonTaskStatus


def test_python_executor_success_and_bounded_output(tmp_path: Path) -> None:
    result = asyncio.run(
        PythonExecutor(max_output_bytes=16).run(
            "print('hello')", working_root=tmp_path, timeout=30
        )
    )
    assert result.status is PythonTaskStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "hello\n"


def test_python_executor_timeout(tmp_path: Path) -> None:
    result = asyncio.run(
        PythonExecutor().run(
            "import time; time.sleep(10)", working_root=tmp_path, timeout=0.05
        )
    )
    assert result.status is PythonTaskStatus.TIMED_OUT


def test_python_executor_nonzero_exit_is_failed_with_exit_code(tmp_path: Path) -> None:
    result = asyncio.run(
        PythonExecutor().run(
            "import sys; print('bad', file=sys.stderr); sys.exit(3)",
            working_root=tmp_path,
            timeout=30,
        )
    )

    assert result.status is PythonTaskStatus.FAILED
    assert result.exit_code == 3
    assert result.stderr == "bad\n"


def test_python_executor_bounds_output_without_retaining_the_full_stream(
    tmp_path: Path,
) -> None:
    result = asyncio.run(
        PythonExecutor(max_output_bytes=32).run(
            "print('x' * 1000000)", working_root=tmp_path, timeout=30
        )
    )

    assert len(result.stdout.encode()) <= 32
    assert (
        result.stdout_hash
        == hashlib.sha256(("x" * 1000000 + "\n").encode()).hexdigest()
    )


def test_local_python_requires_hash_bound_consent_and_returns_receipt(
    tmp_path: Path,
) -> None:
    payload = {
        "working_root": "/projects",
        "runtime": "python",
        "script": "print('hello')",
        "args": [],
        "expected_outputs": [],
        "environment": [],
    }
    consent = ConsentStore()
    service = LocalPythonService(
        LocalFileStore([RootConfig("/projects", tmp_path)]), consent=consent
    )

    async def run_with_consent():
        assert await service.execute(payload) is PolicyDecision.CONSENT_REQUIRED
        consent.approve("local.python", request_hash(payload), actor_id="alice")
        return await service.execute(payload)

    result = asyncio.run(run_with_consent())

    assert result.status is PythonTaskStatus.COMPLETED
    assert result.receipt is not None
    assert result.receipt.request_hash == request_hash(payload)
    assert result.receipt.consent_decision == "approved"
    assert result.receipt.stdout_hash == result.stdout_hash
    assert result.receipt.exit_code == 0
    assert result.receipt.started_at is not None
    assert result.receipt.finished_at is not None
    assert result.receipt.stdout_log_path is not None
    assert Path(result.receipt.stdout_log_path).read_text() == "hello\n"
    stderr_log_path = result.receipt.stderr_log_path
    result.receipt.cleanup_local_logs()
    assert not Path(result.receipt.stdout_log_path).exists()
    assert stderr_log_path is not None
    assert not Path(stderr_log_path).exists()


def test_local_python_uploads_only_explicit_expected_outputs(tmp_path: Path) -> None:
    payload = {
        "working_root": "/projects",
        "script": "open('result.txt', 'w').write('artifact')",
        "expected_outputs": ["/projects/result.txt"],
        "environment": [],
        "timeout": 60,
    }
    consent = ConsentStore()
    consent.approve("local.python", request_hash(payload))
    uploader = MemoryArtifactUploader()
    service = LocalPythonService(
        LocalFileStore([RootConfig("/projects", tmp_path)]),
        consent=consent,
        uploader=uploader,
    )

    result = asyncio.run(service.execute(payload))

    assert result.status is PythonTaskStatus.COMPLETED
    assert result.artifact_refs == (
        "local://" + hashlib.sha256(b"artifact").hexdigest() + "/result.txt",
    )
    assert list(uploader.items.values()) == [b"artifact"]


def test_file_artifact_uploader_is_durable_idempotent_and_bounded(
    tmp_path: Path,
) -> None:
    uploader = FileArtifactUploader(tmp_path / "artifacts", max_bytes=4)
    assert uploader.upload("result.txt", b"data").startswith("local://")
    assert uploader.upload("result.txt", b"data") == uploader.upload(
        "result.txt", b"data"
    )
    with pytest.raises(ArtifactUploadError):
        uploader.upload("result.txt", b"too large")
    with pytest.raises(ArtifactUploadError):
        uploader.upload("../escape.txt", b"x")


def test_upload_grant_is_bound_to_run_task_thread_and_single_use() -> None:
    grant = SingleUseUploadGrant("run", "task", "thread", "result.txt")
    assert grant.consume(
        run_id="run", task_id="task", thread_id="thread", name="result.txt"
    )
    with pytest.raises(ArtifactUploadError):
        grant.consume(
            run_id="run", task_id="task", thread_id="thread", name="result.txt"
        )


def test_local_python_accepts_environment_references_but_not_plaintext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCAL_RUNTIME_TEST_VALUE", "visible")
    files = LocalFileStore([RootConfig("/projects", tmp_path)])
    service = LocalPythonService(
        files, environment={"LOCAL_RUNTIME_TEST_VALUE": "visible"}
    )
    payload = {
        "working_root": "/projects",
        "script": "import os; print(os.environ['LOCAL_RUNTIME_TEST_VALUE'])",
        "environment": ["LOCAL_RUNTIME_TEST_VALUE"],
    }
    service.consent.approve("local.python", request_hash(payload))

    result = asyncio.run(service.execute(payload))

    assert result.stdout == "visible\n"
    with pytest.raises(ValueError, match="environment references"):
        asyncio.run(
            service.execute(
                {**payload, "environment": {"TOKEN": "plaintext"}}, consent=True
            )
        )


def test_local_python_reports_upload_policy_rejection(tmp_path: Path) -> None:
    payload = {
        "working_root": "/projects",
        "script": "open('result.txt', 'w').write('artifact')",
        "expected_outputs": ["/projects/result.txt"],
        "environment": [],
    }
    consent = ConsentStore()
    consent.approve("local.python", request_hash(payload))
    service = LocalPythonService(
        LocalFileStore([RootConfig("/projects", tmp_path)]),
        policy=LocalPolicy(denied_capabilities=frozenset({"local.artifacts.upload"})),
        consent=consent,
        uploader=MemoryArtifactUploader(),
    )

    result = asyncio.run(service.execute(payload))

    assert result.status is PythonTaskStatus.UPLOAD_DENIED
    assert result.artifact_error == "artifact upload denied by local policy"
    assert result.receipt is not None
    assert result.receipt.status == "upload_denied"


def test_python_executor_cancellation_returns_cancelled(tmp_path: Path) -> None:
    async def run_and_cancel() -> None:
        task = asyncio.create_task(
            PythonExecutor().run(
                "import time; time.sleep(30)", working_root=tmp_path, timeout=30
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        result = await task
        assert result.status is PythonTaskStatus.CANCELLED

    asyncio.run(run_and_cancel())


def test_python_executor_cancellation_cleans_up_child_processes(
    tmp_path: Path,
) -> None:
    async def run_and_cancel() -> None:
        task = asyncio.create_task(
            PythonExecutor().run(
                """
import subprocess
import sys
import time

subprocess.Popen([
    sys.executable,
    '-c',
    "import pathlib, time; time.sleep(0.3); pathlib.Path('child-alive').write_text('leaked')",
])
time.sleep(30)
""",
                working_root=tmp_path,
                timeout=30,
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        result = await task
        assert result.status is PythonTaskStatus.CANCELLED

    asyncio.run(run_and_cancel())
    assert not (tmp_path / "child-alive").exists()


def test_python_executor_streams_rate_limited_redacted_output(
    tmp_path: Path,
) -> None:
    async def run_with_output() -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []

        async def on_output(stream: str, chunk: str) -> None:
            events.append((stream, chunk))

        result = await PythonExecutor(max_output_rate_bytes=1024).run(
            "print('API_KEY=super-secret')",
            working_root=tmp_path,
            on_output=on_output,
        )

        assert result.stdout == "API_KEY=[REDACTED]\n"
        assert events == [("stdout", "API_KEY=[REDACTED]\n")]
        return events

    asyncio.run(run_with_output())


def test_python_executor_limits_streamed_output_rate(tmp_path: Path) -> None:
    async def run_with_output() -> int:
        emitted = 0

        async def on_output(_stream: str, chunk: str) -> None:
            nonlocal emitted
            emitted += len(chunk.encode())

        await PythonExecutor(max_output_rate_bytes=128).run(
            "print('x' * 4096)",
            working_root=tmp_path,
            on_output=on_output,
        )
        return emitted

    assert asyncio.run(run_with_output()) <= 128


def test_python_executor_redacts_sensitive_value_split_across_chunks(
    tmp_path: Path,
) -> None:
    async def run_with_output() -> str:
        chunks: list[str] = []

        async def on_output(_stream: str, chunk: str) -> None:
            chunks.append(chunk)

        await PythonExecutor().run(
            "import sys; sys.stdout.write('API_KEY=sec'); sys.stdout.flush(); sys.stdout.write('ret-value\\n'); sys.stdout.flush()",
            working_root=tmp_path,
            on_output=on_output,
        )
        return "".join(chunks)

    output = asyncio.run(run_with_output())
    assert "secret-value" not in output
    assert "API_KEY=[REDACTED]" in output
