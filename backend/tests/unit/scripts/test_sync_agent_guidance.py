from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "sync_agent_guidance.py"
SPEC = importlib.util.spec_from_file_location("sync_agent_guidance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _git_init(root: Path) -> None:
    _git(root, "init", "-q")


def test_check_reports_missing_mismatched_and_orphan_mirrors(tmp_path: Path, capsys) -> None:
    _git_init(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"root\r\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"different\n")
    nested = tmp_path / "new" / "nested"
    nested.mkdir(parents=True)
    (nested / "AGENTS.md").write_bytes("规则\n".encode())
    orphan = tmp_path / "orphan"
    orphan.mkdir()
    (orphan / "CLAUDE.md").write_bytes(b"orphan\n")

    result = sync.main(["--check", "--repo-root", str(tmp_path)])

    output = capsys.readouterr().out
    assert result == 1
    assert "missing CLAUDE.md" in output
    assert "content differs" in output
    assert "orphan CLAUDE.md" in output


def test_write_generates_byte_identical_mirrors_in_new_directories(tmp_path: Path) -> None:
    _git_init(tmp_path)
    source = tmp_path / "new" / "nested" / "AGENTS.md"
    source.parent.mkdir(parents=True)
    source.write_bytes("规则\r\nsecond line\r".encode())

    assert sync.main(["--write", "--repo-root", str(tmp_path)]) == 0

    mirror = source.with_name("CLAUDE.md")
    assert mirror.is_file()
    assert mirror.read_bytes() == source.read_bytes()
    assert sync.main(["--check", "--repo-root", str(tmp_path)]) == 0


def test_revision_check_uses_revision_files_not_worktree(tmp_path: Path, capsys) -> None:
    _git_init(tmp_path)
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "AGENTS.md").write_bytes(b"committed\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"committed\n")
    _git(tmp_path, "add", "AGENTS.md", "CLAUDE.md")
    _git(tmp_path, "commit", "-qm", "guidance")
    (tmp_path / "AGENTS.md").write_bytes(b"working tree differs\n")

    result = sync.main(["--check", "--revision", "HEAD", "--repo-root", str(tmp_path)])

    output = capsys.readouterr().out
    assert result == 0
    assert "content differs" not in output


def test_write_preserves_orphan_mirrors_and_reports_them(tmp_path: Path, capsys) -> None:
    _git_init(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"source\n")
    orphan = tmp_path / "orphan" / "CLAUDE.md"
    orphan.parent.mkdir()
    orphan.write_bytes(b"unknown content\n")

    assert sync.main(["--write", "--repo-root", str(tmp_path)]) == 1

    assert orphan.read_bytes() == b"unknown content\n"
    assert "orphan CLAUDE.md" in capsys.readouterr().out


def test_write_rejects_invalid_utf8_without_replacing_existing_mirror(tmp_path: Path) -> None:
    _git_init(tmp_path)
    source = tmp_path / "AGENTS.md"
    source.write_bytes(b"\xff")
    mirror = tmp_path / "CLAUDE.md"
    mirror.write_bytes(b"keep me")

    assert sync.main(["--write", "--repo-root", str(tmp_path)]) == 1

    assert mirror.read_bytes() == b"keep me"


def test_move_and_delete_require_both_guidance_files(tmp_path: Path) -> None:
    _git_init(tmp_path)
    old = tmp_path / "old"
    old.mkdir()
    (old / "AGENTS.md").write_text("rule\n")
    assert sync.main(["--write", "--repo-root", str(tmp_path)]) == 0
    new = tmp_path / "new"
    new.mkdir()
    (old / "AGENTS.md").rename(new / "AGENTS.md")
    assert sync.main(["--check", "--repo-root", str(tmp_path)]) == 1
    (old / "CLAUDE.md").rename(new / "CLAUDE.md")
    assert sync.main(["--check", "--repo-root", str(tmp_path)]) == 0
    (new / "AGENTS.md").unlink()
    assert sync.main(["--check", "--repo-root", str(tmp_path)]) == 1
    (new / "CLAUDE.md").unlink()
    assert sync.main(["--check", "--repo-root", str(tmp_path)]) == 0


def test_write_rejects_symlink_without_changing_target(tmp_path: Path) -> None:
    _git_init(tmp_path)
    (tmp_path / "AGENTS.md").write_text("new rule\n")
    target = tmp_path / "target.md"
    target.write_text("keep target\n")
    (tmp_path / "CLAUDE.md").symlink_to(target)
    assert sync.main(["--write", "--repo-root", str(tmp_path)]) == 1
    assert target.read_text() == "keep target\n"
