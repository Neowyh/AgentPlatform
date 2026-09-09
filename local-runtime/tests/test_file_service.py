from pathlib import Path

from core.file_service import LocalFileService
from core.files import LocalFileStore, RootConfig
from core.policy import PolicyDecision


def test_write_requires_approval_and_then_executes(tmp_path: Path) -> None:
    service = LocalFileService(LocalFileStore([RootConfig("/projects", tmp_path)]))
    payload = {"path": "/projects/a.txt", "content": "approved"}
    assert service.execute("local.files.write", payload).decision is PolicyDecision.CONSENT_REQUIRED
    assert service.execute("local.files.write", payload, consent=True).value == {"written": True}
    assert (tmp_path / "a.txt").read_text() == "approved"
