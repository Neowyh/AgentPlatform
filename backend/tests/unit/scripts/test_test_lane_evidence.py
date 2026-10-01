import json
import subprocess
from pathlib import Path

from test_lane_evidence import build_context, write_completion


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_evidence_fingerprint_tracks_uncommitted_and_untracked_candidate(tmp_path: Path, monkeypatch) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-qm", "base")

    monkeypatch.setenv("OPENAI_API_KEY", "never-write-this-value")
    before = build_context(tmp_path, "backend-standard", "bash scripts/run-test-lane.sh backend-standard")
    (tmp_path / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (tmp_path / "new.txt").write_text("new candidate file\n", encoding="utf-8")
    after = build_context(tmp_path, "backend-standard", "bash scripts/run-test-lane.sh backend-standard")

    assert before["candidate_commit"] == after["candidate_commit"]
    assert before["diff_fingerprint_sha256"] != after["diff_fingerprint_sha256"]
    encoded = json.dumps(after)
    assert "never-write-this-value" not in encoded
    assert after["environment"]["credential_presence"]["OPENAI_API_KEY"] is True


def test_completion_records_final_status_and_duration(tmp_path: Path) -> None:
    output = tmp_path / "lane.json"
    output.write_text('{"lane":"backend-standard"}\n', encoding="utf-8")

    write_completion(output, 124, 600, "cancelled")

    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["status"] == 124
    assert record["outcome"] == "cancelled"
    assert record["duration_seconds"] == 600
    assert record["finished_at"]


def test_source_archive_records_context_without_git_metadata(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("safe: true\n", encoding="utf-8")

    context = build_context(tmp_path, "local-runtime", "pytest")

    assert context["candidate_commit"] is None
    assert context["fingerprint_source"] == "visible-source-tree-no-git"
    assert context["diff_fingerprint_sha256"]
    assert "node" in context["environment"]
    assert "pnpm" in context["environment"]
