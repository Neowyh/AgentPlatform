#!/usr/bin/env python3
"""Create and compare deterministic source manifests for offline bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git",
    "dist",
    "backend/.venv",
    "backend/.ideer",
    "backend/.pytest_cache",
    "backend/.ruff_cache",
    "frontend/node_modules",
    "frontend/.next",
    "frontend/.cache",
    "frontend/.env",
    "frontend/test-results",
    "frontend/playwright-report",
    "frontend/tsconfig.tsbuildinfo",
    "node_modules",
    "logs",
}


def _excluded(path: str) -> bool:
    return any(path == item or path.startswith(item + "/") for item in DEFAULT_EXCLUDES)


def _digest(path: Path) -> str:
    if path.is_symlink():
        return "sha256:" + hashlib.sha256(os.readlink(path).encode()).hexdigest()
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def snapshot(root: Path, includes: list[str] | None = None, all_skills: bool = False, excluded_skills: set[str] | None = None) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir() or _excluded(rel) or rel.endswith((".pyc", ".log")):
            continue
        if includes and not any(rel == item or rel.startswith(item.rstrip("/") + "/") for item in includes):
            continue
        if rel.startswith("resources/skills/"):
            skill = rel.split("/", 2)[1]
            if excluded_skills and skill in excluded_skills:
                continue
            listed = root / "bundled-skills.txt"
            if not all_skills and listed.is_file():
                names = {line.split("#", 1)[0].strip() for line in listed.read_text(encoding="utf-8").splitlines() if line.split("#", 1)[0].strip()}
                if skill not in names:
                    continue
        files[rel] = _digest(path)
    return files


def load_files(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("source_files", data.get("files", {}))


def write_snapshot(root: Path, output: Path, includes: list[str], all_skills: bool, excluded_skills: set[str]) -> None:
    data = {"format": 1, "source_roots": includes, "all_skills": all_skills, "excluded_skills": sorted(excluded_skills), "source_files": snapshot(root, includes, all_skills, excluded_skills)}
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_delta(root: Path, base: Path, manifest: Path, archive: Path, deleted: Path, includes: list[str], all_skills: bool, excluded_skills: set[str]) -> None:
    old = load_files(base)
    current = snapshot(root, includes, all_skills, excluded_skills)
    changed = [name for name, digest in current.items() if old.get(name) != digest]
    removed = sorted(set(old) - set(current))
    data = {
        "format": 1,
        "source_roots": includes,
        "all_skills": all_skills,
        "excluded_skills": sorted(excluded_skills),
        "source_files": current,
        "changed_files": sorted(changed),
        "deleted_files": removed,
    }
    manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    deleted.write_text("".join(f"{name}\n" for name in removed), encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tar:
        for name in changed:
            tar.add(root / name, arcname=name, recursive=False)


def verify_root(root: Path, manifest: Path) -> None:
    expected = load_files(manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    actual = snapshot(root, data.get("source_roots", []), data.get("all_skills", False), set(data.get("excluded_skills", [])))
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        changed = sorted(name for name in set(expected) & set(actual) if expected[name] != actual[name])
        extra = sorted(set(actual) - set(expected))
        raise SystemExit(f"source baseline mismatch (missing={missing[:3]}, changed={changed[:3]}, extra={extra[:3]})")


def apply_delta(root: Path, archive: Path, deleted: Path, manifest: Path) -> None:
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.delta-", dir=root.parent))
    try:
        shutil.copytree(root, staging, dirs_exist_ok=True, symlinks=True)
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                name = Path(member.name)
                if name.is_absolute() or ".." in name.parts or not member.isfile() and not member.issym():
                    raise SystemExit(f"unsafe delta archive member: {member.name}")
            tar.extractall(staging, filter="data")
        for line in deleted.read_text(encoding="utf-8").splitlines():
            name = Path(line)
            if name.is_absolute() or ".." in name.parts:
                raise SystemExit(f"unsafe deleted path: {line}")
            target = staging / name
            if target.is_file() or target.is_symlink():
                target.unlink()
        verify_root(staging, manifest)
        backup = root.with_name(f".{root.name}.before-delta")
        if backup.exists():
            shutil.rmtree(backup)
        os.replace(root, backup)
        try:
            os.replace(staging, root)
        except Exception:
            os.replace(backup, root)
            raise
        shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def fingerprint(root: Path, prefixes: list[str]) -> str:
    entries: list[str] = []
    for prefix in prefixes:
        path = root / prefix
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = [p for p in path.rglob("*") if p.is_file()]
        else:
            candidates = []
        for candidate in candidates:
            rel = candidate.relative_to(root).as_posix()
            entries.append(f"{rel}\0{_digest(candidate)}")
    return "sha256:" + hashlib.sha256("\n".join(sorted(set(entries))).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--root", type=Path, required=True)
    snap.add_argument("--output", type=Path, required=True)
    snap.add_argument("--include", action="append", default=[])
    snap.add_argument("--all-skills", action="store_true")
    snap.add_argument("--exclude-skill", action="append", default=[])
    delta = sub.add_parser("delta")
    delta.add_argument("--root", type=Path, required=True)
    delta.add_argument("--base", type=Path, required=True)
    delta.add_argument("--manifest", type=Path, required=True)
    delta.add_argument("--archive", type=Path, required=True)
    delta.add_argument("--deleted", type=Path, required=True)
    delta.add_argument("--include", action="append", default=[])
    delta.add_argument("--all-skills", action="store_true")
    delta.add_argument("--exclude-skill", action="append", default=[])
    fp = sub.add_parser("fingerprint")
    fp.add_argument("--root", type=Path, required=True)
    fp.add_argument("prefixes", nargs="+")
    verify = sub.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--root", type=Path, required=True)
    apply.add_argument("--archive", type=Path, required=True)
    apply.add_argument("--deleted", type=Path, required=True)
    apply.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        write_snapshot(args.root, args.output, args.include, args.all_skills, set(args.exclude_skill))
    elif args.command == "delta":
        write_delta(args.root, args.base, args.manifest, args.archive, args.deleted, args.include, args.all_skills, set(args.exclude_skill))
    elif args.command == "fingerprint":
        print(fingerprint(args.root, args.prefixes))
    elif args.command == "verify":
        verify_root(args.root, args.manifest)
    else:
        apply_delta(args.root, args.archive, args.deleted, args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
