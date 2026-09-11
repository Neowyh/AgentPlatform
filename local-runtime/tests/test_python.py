import asyncio
import hashlib
from pathlib import Path

import pytest
from core.artifacts import MemoryArtifactUploader
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
