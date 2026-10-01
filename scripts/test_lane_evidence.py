#!/usr/bin/env python3
"""Write a small, secret-safe record of a test lane execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEPENDENCY_CONFIG_PATHS = (
    "backend/uv.lock",
    "backend/pyproject.toml",
    "frontend/pnpm-lock.yaml",
    "frontend/package.json",
    "frontend/vitest.config.ts",
    "frontend/rstest.config.ts",
    "frontend/playwright.config.ts",
    "frontend/next.config.ts",
    "pyproject.toml",
    "pytest.ini",
    "config.yaml",
    "extensions_config.json",
)
RECORDED_ENVIRONMENT = (
    "CI",
    "GITHUB_ACTIONS",
    "RUNNER_OS",
    "TEST_LANE_SHARDS",
    "TEST_LANE_SHARD_INDEX",
    "TEST_LANE_COVERAGE",
    "TEST_PREFLIGHT_STRICT",
    "SKIP_ENV_VALIDATION",
    "NODE_VERSION",
    "PNPM_VERSION",
    "UV_VERSION",
    "UV_CACHE_DIR",
    "TEST_PNPM_HOME",
)
CREDENTIAL_PRESENCE = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "DEER_FLOW_RUN_LIVE_TESTS",
)


def _digest(chunks: list[bytes]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(len(chunk).to_bytes(8, "big"))
        digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root)


def _version(command: str, args: tuple[str, ...]) -> str | None:
    executable = shutil.which(command)
    if executable is None:
        return None
    result = subprocess.run([executable, *args], capture_output=True, text=True, check=False)
    if result.returncode:
        return None
    return (result.stdout or result.stderr).strip().splitlines()[0]


def workspace_fingerprint(root: Path) -> tuple[str, str]:
    """Hash the candidate diff plus every untracked, non-ignored file."""

    try:
        chunks = [_git(root, "diff", "--binary", "HEAD", "--")]
        untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
        for raw_path in sorted(path for path in untracked.split(b"\0") if path):
            path = raw_path.decode("utf-8", errors="surrogateescape")
            candidate = root / path
            content = os.fsencode(os.readlink(candidate)) if candidate.is_symlink() else candidate.read_bytes()
            chunks.extend((raw_path, content))
        return _digest(chunks), "git-diff-and-untracked"
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Source archives have no Git metadata; fingerprint the visible tree.
        chunks = []
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file() or any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in candidate.relative_to(root).parts):
                continue
            relative = candidate.relative_to(root).as_posix().encode()
            content = os.fsencode(os.readlink(candidate)) if candidate.is_symlink() else candidate.read_bytes()
            chunks.extend((relative, content))
        return _digest(chunks), "visible-source-tree-no-git"


def dependency_fingerprint(root: Path) -> str:
    chunks: list[bytes] = []
    for relative in DEPENDENCY_CONFIG_PATHS:
        path = root / relative
        chunks.append(relative.encode())
        chunks.append(path.read_bytes() if path.is_file() else b"<missing>")
    return _digest(chunks)


def build_context(root: Path, lane: str, command: str) -> dict[str, Any]:
    root = root.resolve()
    fingerprint, fingerprint_source = workspace_fingerprint(root)
    try:
        candidate_commit = _git(root, "rev-parse", "HEAD").decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        candidate_commit = None
    environment = {
        "python": platform.python_version(),
        "node": _version("node", ("--version",)),
        "pnpm": _version("pnpm", ("--version",)),
        "uv": _version("uv", ("--version",)),
        "platform": platform.platform(),
        **{name: os.environ[name] for name in RECORDED_ENVIRONMENT if name in os.environ},
        "credential_presence": {name: bool(os.environ.get(name)) for name in CREDENTIAL_PRESENCE},
    }
    return {
        "lane": lane,
        "command": command,
        "candidate_commit": candidate_commit,
        "diff_fingerprint_sha256": fingerprint,
        "fingerprint_source": fingerprint_source,
        "dependency_config_fingerprint_sha256": dependency_fingerprint(root),
        "environment": environment,
        "started_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 -- supports Python 3.8
    }


def write_start(root: Path, output: Path, lane: str, command: str) -> None:
    output.write_text(
        json.dumps(build_context(root, lane, command), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_completion(output: Path, status: int, seconds: int, outcome: str) -> None:
    record = json.loads(output.read_text(encoding="utf-8"))
    record["finished_at"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017 -- supports Python 3.8
    record["status"] = status
    record["outcome"] = outcome
    record["duration_seconds"] = seconds
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--command", default="")
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--status", type=int, default=0)
    parser.add_argument("--seconds", type=int, default=0)
    parser.add_argument("--outcome", default="passed")
    args = parser.parse_args()
    if args.complete:
        write_completion(args.output, args.status, args.seconds, args.outcome)
    else:
        write_start(args.root, args.output, args.lane, args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
