from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from core.file_service import LocalFileService
from core.files import LocalFileStore, RootConfig
from core.transport import LocalRuntimeClient


def test_list_and_read_are_the_only_exposed_file_operations(tmp_path: Path) -> None:
    service = LocalFileService(LocalFileStore([RootConfig("/projects", tmp_path)]))
    (tmp_path / "a.txt").write_text("read me")

    assert service.execute("local.files.list", {"path": "/projects"}).value == ["/projects/a.txt"]
    assert service.execute("local.files.read", {"path": "/projects/a.txt"}).value == "read me"


def test_write_is_not_an_exposed_file_operation(tmp_path: Path) -> None:
    service = LocalFileService(LocalFileStore([RootConfig("/projects", tmp_path)]))

    try:
        service.execute("local.files.write", {"path": "/projects/a.txt", "content": "blocked"})
    except ValueError as exc:
        assert str(exc) == "unsupported local file capability"
    else:
        raise AssertionError("write must not be exposed by the MVP service")

    assert not (tmp_path / "a.txt").exists()


def test_file_task_does_not_require_consent_argument(tmp_path: Path) -> None:
    service = LocalFileService(LocalFileStore([RootConfig("/projects", tmp_path)]))
    (tmp_path / "a.txt").write_text("read me")

    assert service.execute("local.files.read", {"path": "/projects/a.txt"}).value == "read me"


def test_runtime_reports_file_capabilities_when_file_service_is_enabled(tmp_path: Path) -> None:
    service = LocalFileService(LocalFileStore([RootConfig("/projects", tmp_path)]))
    client = LocalRuntimeClient(
        server_url="ws://localhost",
        device_id="device",
        session_token="token",
        private_key=Ed25519PrivateKey.generate(),
        file_service=service,
    )

    assert set(client.capabilities) >= {"local.files.list", "local.files.read"}
