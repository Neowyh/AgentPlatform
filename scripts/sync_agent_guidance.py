#!/usr/bin/env python3
"""Generate or verify CLAUDE.md mirrors of AGENTS.md guidance files."""

from __future__ import annotations

import argparse
import stat
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

GUIDANCE_NAMES = {"AGENTS.md", "CLAUDE.md"}


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _safe_relative_path(raw: bytes) -> PurePosixPath:
    path = PurePosixPath(raw.decode("utf-8", errors="strict"))
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"unsafe guidance path: {path}")
    return path


def _worktree_paths(root: Path) -> set[PurePosixPath]:
    output = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return {path for raw in output.split(b"\0") if raw for path in [_safe_relative_path(raw)] if path.name in GUIDANCE_NAMES}


def _revision_modes(root: Path, revision: str) -> dict[PurePosixPath, str]:
    output = _git(root, "ls-tree", "-r", "-z", revision)
    modes: dict[PurePosixPath, str] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode = metadata.split(b" ", 1)[0].decode("ascii")
        path = _safe_relative_path(raw_path)
        if path.name in GUIDANCE_NAMES:
            modes[path] = mode
    return modes


def _read_regular_file(path: Path) -> bytes:
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise RuntimeError(f"guidance path is not a regular file: {path}")
    data = path.read_bytes()
    data.decode("utf-8", errors="strict")
    return data


def _revision_files(root: Path, revision: str) -> dict[PurePosixPath, bytes]:
    modes = _revision_modes(root, revision)
    files: dict[PurePosixPath, bytes] = {}
    for path, mode in modes.items():
        if mode not in {"100644", "100755"}:
            raise RuntimeError(f"guidance path is not a regular file in {revision}: {path}")
        data = _git(root, "show", f"{revision}:{path.as_posix()}")
        data.decode("utf-8", errors="strict")
        files[path] = data
    return files


def _worktree_files(root: Path) -> dict[PurePosixPath, bytes]:
    files: dict[PurePosixPath, bytes] = {}
    for relative in sorted(_worktree_paths(root)):
        path = root / Path(relative.as_posix())
        if path.exists() or path.is_symlink():
            files[relative] = _read_regular_file(path)
    return files


def _findings(files: dict[PurePosixPath, bytes]) -> list[str]:
    findings: list[str] = []
    for path in sorted(files):
        if path.name != "AGENTS.md":
            continue
        mirror = path.with_name("CLAUDE.md")
        if mirror not in files:
            findings.append(f"missing CLAUDE.md for {path}")
        elif files[mirror] != files[path]:
            findings.append(f"content differs: {path} and {mirror}")
    for path in sorted(files):
        if path.name == "CLAUDE.md" and path.with_name("AGENTS.md") not in files:
            findings.append(f"orphan CLAUDE.md: {path}")
    return findings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="write CLAUDE.md mirrors")
    action.add_argument("--check", action="store_true", help="verify guidance pairs")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--revision", help="check files from this Git revision")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.revision and not args.check:
        parser.error("--revision is only valid with --check")
    root = args.repo_root.resolve()
    try:
        if args.revision:
            files = _revision_files(root, args.revision)
        else:
            files = _worktree_files(root)
        if args.write:
            sources = [(path, data) for path, data in files.items() if path.name == "AGENTS.md"]
            for relative, data in sources:
                target = root / Path(relative.with_name("CLAUDE.md").as_posix())
                if target.exists() or target.is_symlink():
                    _read_regular_file(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            files = _worktree_files(root)
        findings = _findings(files)
    except (OSError, RuntimeError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for finding in findings:
        print(f"ERROR: {finding}")
    if findings:
        return 1
    mode = f"revision {args.revision}" if args.revision else "working tree"
    print(f"Agent guidance sync check passed ({mode}; {sum(p.name == 'AGENTS.md' for p in files)} pairs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
