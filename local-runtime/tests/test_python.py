import asyncio
from pathlib import Path

from core.python import PythonExecutor, PythonTaskStatus


def test_python_executor_success_and_bounded_output(tmp_path: Path) -> None:
    result = asyncio.run(
        PythonExecutor(max_output_bytes=16).run(
            "print('hello')", working_root=tmp_path, timeout=5
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
