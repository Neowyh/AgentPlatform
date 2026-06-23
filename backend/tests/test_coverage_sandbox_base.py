"""Coverage tests for ideer.sandbox.sandbox (abstract base class)."""

from __future__ import annotations

import pytest

from ideer.sandbox.sandbox import Sandbox
from ideer.sandbox.search import GrepMatch

# ===========================================================================
# Concrete implementation for testing the ABC
# ===========================================================================


class ConcreteSandbox(Sandbox):
    def execute_command(self, command: str) -> str:
        return f"exec: {command}"

    def read_file(self, path: str) -> str:
        return f"content of {path}"

    def download_file(self, path: str) -> bytes:
        return f"bytes of {path}".encode()

    def list_dir(self, path: str, max_depth: int = 2) -> list[str]:
        return [f"{path}/file1.txt", f"{path}/dir/"]

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        pass

    def glob(self, path: str, pattern: str, *, include_dirs: bool = False, max_results: int = 200) -> tuple[list[str], bool]:
        return [f"{path}/match.py"], False

    def grep(
        self,
        path: str,
        pattern: str,
        *,
        glob: str | None = None,
        literal: bool = False,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> tuple[list[GrepMatch], bool]:
        return [GrepMatch(path=f"{path}/file.py", line_number=1, line="match")], False

    def update_file(self, path: str, content: bytes) -> None:
        pass


# ===========================================================================
# Test cases
# ===========================================================================


class TestSandboxABC:
    def test_id_property(self):
        sandbox = ConcreteSandbox(id="test-id")
        assert sandbox.id == "test-id"

    def test_execute_command(self):
        sandbox = ConcreteSandbox(id="test")
        result = sandbox.execute_command("ls -la")
        assert result == "exec: ls -la"

    def test_read_file(self):
        sandbox = ConcreteSandbox(id="test")
        result = sandbox.read_file("/tmp/test.txt")
        assert "test.txt" in result

    def test_download_file(self):
        sandbox = ConcreteSandbox(id="test")
        result = sandbox.download_file("/tmp/test.bin")
        assert isinstance(result, bytes)

    def test_list_dir(self):
        sandbox = ConcreteSandbox(id="test")
        result = sandbox.list_dir("/tmp")
        assert len(result) == 2

    def test_write_file(self):
        sandbox = ConcreteSandbox(id="test")
        sandbox.write_file("/tmp/test.txt", "content")  # should not raise

    def test_glob(self):
        sandbox = ConcreteSandbox(id="test")
        matches, truncated = sandbox.glob("/tmp", "*.py")
        assert len(matches) == 1
        assert truncated is False

    def test_grep(self):
        sandbox = ConcreteSandbox(id="test")
        matches, truncated = sandbox.grep("/tmp", "pattern")
        assert len(matches) == 1
        assert truncated is False

    def test_update_file(self):
        sandbox = ConcreteSandbox(id="test")
        sandbox.update_file("/tmp/test.bin", b"binary")  # should not raise

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            Sandbox(id="test")


# ===========================================================================
# SandboxWithoutId — default id behavior
# ===========================================================================


class TestSandboxDefaultId:
    def test_id_set_in_constructor(self):
        sandbox = ConcreteSandbox(id="custom-id")
        assert sandbox.id == "custom-id"

    def test_different_instances_independent(self):
        s1 = ConcreteSandbox(id="first")
        s2 = ConcreteSandbox(id="second")
        assert s1.id != s2.id
