"""Release tags cannot bypass product provenance and version records."""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "scripts/check_product_release.sh"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_product_release_requires_branch_and_committed_record(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "verify_versions.sh").write_text("exit 0\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    git(tmp_path, "tag", "ideer-1.0.0")
    command = ["bash", str(SCRIPT), "ideer-1.0.0"]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "product/offline-" in result.stderr
    git(tmp_path, "branch", "product/offline-1.x")
    git(tmp_path, "update-ref", "refs/remotes/origin/product/offline-1.x", "HEAD")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Missing committed" in result.stderr
    record = tmp_path / "docs/releases/ideer-1.0.0.md"
    record.parent.mkdir(parents=True)
    record.write_text("upstream_baseline: deadbeef\nproduct_branch: product/offline-1.x\nverification_command: bash scripts/run-test-lane.sh core-full\nverification_result: passed\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "record")
    git(tmp_path, "tag", "-f", "ideer-1.0.0")
    git(tmp_path, "update-ref", "refs/remotes/origin/product/offline-1.x", "HEAD")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "upstream baseline" in result.stderr
    baseline = git(tmp_path, "rev-parse", "HEAD")
    record.write_text(record.read_text().replace("deadbeef", baseline))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "valid baseline")
    git(tmp_path, "tag", "-f", "ideer-1.0.0")
    git(tmp_path, "update-ref", "refs/remotes/origin/product/offline-1.x", "HEAD")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = subprocess.run(["bash", str(SCRIPT), "v1.0.0"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "ideer-VERSION" in result.stderr
