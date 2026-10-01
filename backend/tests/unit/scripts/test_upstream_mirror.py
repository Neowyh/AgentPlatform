"""Initial mirror creation requires an explicit bootstrap, then preserves upstream SHA."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "scripts/sync_upstream_mirror.sh"


def test_missing_main_requires_explicit_bootstrap(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    (tmp_path / "file.txt").write_text("upstream")
    git("add", "file.txt")
    git("commit", "-m", "upstream")
    git("branch", "-M", "main")
    upstream_sha = git("rev-parse", "HEAD")
    upstream = tmp_path / "upstream.git"
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(tmp_path), str(upstream)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    git("remote", "add", "origin", str(origin))
    env = {**os.environ, "UPSTREAM_MIRROR_URL": str(upstream), "UPSTREAM_MIRROR_APPLY": "1"}
    result = subprocess.run(["bash", str(SCRIPT)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "explicit bootstrap" in result.stderr
    result = subprocess.run(["bash", str(SCRIPT)], cwd=tmp_path, env={**env, "UPSTREAM_MIRROR_BOOTSTRAP": "1"}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    remote_sha = subprocess.check_output(["git", "-C", str(origin), "rev-parse", "main"], text=True).strip()
    assert remote_sha == upstream_sha
