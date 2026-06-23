"""Tests for ideer.sandbox.exceptions — structured sandbox error types."""

from __future__ import annotations

from ideer.sandbox.exceptions import (
    SandboxCommandError,
    SandboxError,
    SandboxFileError,
    SandboxFileNotFoundError,
    SandboxNotFoundError,
    SandboxPermissionError,
    SandboxRuntimeError,
)


class TestSandboxError:
    def test_basic_message(self):
        err = SandboxError("something broke")
        assert str(err) == "something broke"
        assert err.message == "something broke"
        assert err.details == {}

    def test_with_details(self):
        err = SandboxError("fail", details={"key": "value", "count": 3})
        result = str(err)
        assert "fail" in result
        assert "key=value" in result
        assert "count=3" in result

    def test_details_default_none(self):
        err = SandboxError("msg")
        assert err.details == {}

    def test_details_empty_dict(self):
        err = SandboxError("msg", details={})
        assert str(err) == "msg"


class TestSandboxNotFoundError:
    def test_default_message(self):
        err = SandboxNotFoundError()
        assert err.message == "Sandbox not found"
        assert err.sandbox_id is None
        assert err.details == {}

    def test_with_sandbox_id(self):
        err = SandboxNotFoundError(sandbox_id="sb-123")
        assert err.sandbox_id == "sb-123"
        assert err.details == {"sandbox_id": "sb-123"}
        assert "sb-123" in str(err)

    def test_custom_message(self):
        err = SandboxNotFoundError("custom msg", sandbox_id="sb-456")
        assert err.message == "custom msg"
        assert err.sandbox_id == "sb-456"

    def test_inheritance(self):
        assert issubclass(SandboxNotFoundError, SandboxError)


class TestSandboxRuntimeError:
    def test_inheritance(self):
        err = SandboxRuntimeError("runtime issue")
        assert isinstance(err, SandboxError)
        assert str(err) == "runtime issue"


class TestSandboxCommandError:
    def test_basic(self):
        err = SandboxCommandError("cmd failed")
        assert err.command is None
        assert err.exit_code is None
        assert err.details == {}

    def test_with_command_and_exit_code(self):
        err = SandboxCommandError("cmd failed", command="ls -la", exit_code=1)
        assert err.command == "ls -la"
        assert err.exit_code == 1
        assert err.details["command"] == "ls -la"
        assert err.details["exit_code"] == 1

    def test_long_command_truncated(self):
        long_cmd = "a" * 200
        err = SandboxCommandError("fail", command=long_cmd)
        assert len(err.details["command"]) < 200
        assert err.details["command"].endswith("...")

    def test_command_exactly_100_chars(self):
        cmd = "a" * 100
        err = SandboxCommandError("fail", command=cmd)
        assert err.details["command"] == cmd  # no truncation at exactly 100

    def test_command_101_chars(self):
        cmd = "a" * 101
        err = SandboxCommandError("fail", command=cmd)
        assert err.details["command"].endswith("...")

    def test_inheritance(self):
        assert issubclass(SandboxCommandError, SandboxError)


class TestSandboxFileError:
    def test_basic(self):
        err = SandboxFileError("file error")
        assert err.path is None
        assert err.operation is None

    def test_with_path_and_operation(self):
        err = SandboxFileError("file error", path="/tmp/test.txt", operation="read")
        assert err.path == "/tmp/test.txt"
        assert err.operation == "read"
        assert err.details["path"] == "/tmp/test.txt"
        assert err.details["operation"] == "read"

    def test_inheritance(self):
        assert issubclass(SandboxFileError, SandboxError)


class TestSandboxPermissionError:
    def test_inheritance(self):
        assert issubclass(SandboxPermissionError, SandboxFileError)
        assert issubclass(SandboxPermissionError, SandboxError)

    def test_instance(self):
        err = SandboxPermissionError("denied", path="/etc/passwd", operation="write")
        assert err.path == "/etc/passwd"
        assert err.operation == "write"


class TestSandboxFileNotFoundError:
    def test_inheritance(self):
        assert issubclass(SandboxFileNotFoundError, SandboxFileError)
        assert issubclass(SandboxFileNotFoundError, SandboxError)

    def test_instance(self):
        err = SandboxFileNotFoundError("not found", path="/missing.txt")
        assert err.path == "/missing.txt"


class TestExceptionHierarchy:
    def test_all_subclasses_of_sandbox_error(self):
        for cls in (
            SandboxNotFoundError,
            SandboxRuntimeError,
            SandboxCommandError,
            SandboxFileError,
            SandboxPermissionError,
            SandboxFileNotFoundError,
        ):
            assert issubclass(cls, SandboxError), f"{cls.__name__} not subclass of SandboxError"
