#!/usr/bin/env python3
"""Audit and permanently remove unreferenced per-user state directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESERVED_SUBJECTS = {"default"}
REFERENCE_COLUMNS = {
    "users": ("id",),
    "users_ext": ("id",),
    "resource_metadata": ("owner_id",),
    "threads_meta": ("user_id",),
    "runs": ("user_id",),
    "run_events": ("user_id",),
    "feedback": ("user_id",),
    "visibility_applications": ("applicant_id", "reviewed_by"),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _references(connection: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for table, candidates in REFERENCE_COLUMNS.items():
        columns = _table_columns(connection, table)
        for column in candidates:
            if column not in columns:
                continue
            count = connection.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = ?',
                (user_id,),
            ).fetchone()[0]
            if count:
                found.append({"table": table, "column": column, "count": count})
    return found


def _directory_snapshot(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files: list[dict[str, Any]] = []
    size = 0
    if path.is_symlink():
        target = os.readlink(path)
        digest.update(f"symlink\0{target}".encode())
        return {"digest": digest.hexdigest(), "size_bytes": 0, "files": [], "symbolic_link": True}

    for item in sorted(path.rglob("*"), key=lambda candidate: candidate.relative_to(path).as_posix()):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            target = os.readlink(item)
            digest.update(f"symlink\0{relative}\0{target}".encode())
            files.append({"path": relative, "type": "symlink", "target": target})
        elif item.is_file():
            file_hash = hashlib.sha256()
            with item.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    file_hash.update(chunk)
            file_size = item.stat().st_size
            size += file_size
            digest.update(f"file\0{relative}\0{file_size}\0{file_hash.hexdigest()}".encode())
            files.append({"path": relative, "type": "file", "size_bytes": file_size, "sha256": file_hash.hexdigest()})
        elif item.is_dir():
            digest.update(f"directory\0{relative}".encode())
    return {"digest": digest.hexdigest(), "size_bytes": size, "files": files, "symbolic_link": False}


def _classification(user_id: str, auth_ids: set[str], rbac_ids: set[str], references: list[dict[str, Any]]) -> str:
    if user_id in RESERVED_SUBJECTS:
        return "reserved_system_subject"
    if user_id in auth_ids and user_id in rbac_ids:
        return "database_user"
    if user_id in auth_ids or user_id in rbac_ids or references:
        return "inconsistent_database_subject"
    if user_id == "test-user-autouse" or user_id == "user-1" or user_id.startswith("test-"):
        return "test_pollution"
    return "orphan"


def audit_user_state(*, users_root: Path, database: Path) -> dict[str, Any]:
    """Return a read-only manifest of database subjects and disk directories."""
    users_root = users_root.resolve()
    database = database.resolve()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        auth_ids = {str(row[0]) for row in connection.execute("SELECT id FROM users")}
        rbac_ids = {str(row[0]) for row in connection.execute("SELECT id FROM users_ext")}
        directories: list[dict[str, Any]] = []
        if users_root.exists():
            for path in sorted(users_root.iterdir(), key=lambda candidate: candidate.name):
                if not path.is_dir() and not path.is_symlink():
                    continue
                refs = _references(connection, path.name)
                snapshot = _directory_snapshot(path)
                classification = _classification(path.name, auth_ids, rbac_ids, refs)
                directories.append(
                    {
                        "user_id": path.name,
                        "path": str(path),
                        "classification": classification,
                        "references": refs,
                        **snapshot,
                    }
                )

    candidates = [entry["user_id"] for entry in directories if entry["classification"] in {"orphan", "test_pollution"} and not entry["references"]]
    return {
        "schema_version": 1,
        "generated_at": _now(),
        "users_root": str(users_root),
        "database": str(database),
        "database_users": sorted(auth_ids & rbac_ids),
        "auth_only_users": sorted(auth_ids - rbac_ids),
        "rbac_only_users": sorted(rbac_ids - auth_ids),
        "directories": directories,
        "delete_candidates": candidates,
    }


def _safe_direct_child(users_root: Path, path: Path) -> bool:
    return path.parent == users_root and path.name not in {"", ".", ".."}


def delete_from_manifest(
    manifest: dict[str, Any],
    *,
    include_reserved: set[str] | None = None,
    yes: bool = False,
) -> dict[str, Any]:
    """Delete manifest candidates after revalidating every safety condition."""
    if not yes:
        raise ValueError("permanent deletion requires explicit confirmation")
    include_reserved = include_reserved or set()
    if not include_reserved <= RESERVED_SUBJECTS:
        raise ValueError("unknown reserved subject requested")

    users_root = Path(manifest["users_root"]).resolve()
    database = Path(manifest["database"]).resolve()
    selected = set(manifest.get("delete_candidates", [])) | include_reserved
    entries = {entry["user_id"]: entry for entry in manifest.get("directories", [])}
    results: list[dict[str, str]] = []

    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        for user_id in sorted(selected):
            entry = entries.get(user_id)
            if entry is None:
                results.append({"user_id": user_id, "result": "skipped", "reason": "not_in_manifest"})
                continue
            path = Path(entry["path"])
            if path.is_symlink():
                results.append({"user_id": user_id, "result": "skipped", "reason": "symbolic_link"})
                continue
            resolved = path.resolve()
            if not _safe_direct_child(users_root, resolved) or resolved.name != user_id:
                results.append({"user_id": user_id, "result": "skipped", "reason": "outside_users_root"})
                continue
            if not resolved.exists():
                results.append({"user_id": user_id, "result": "skipped", "reason": "already_absent"})
                continue
            if _references(connection, user_id):
                results.append({"user_id": user_id, "result": "skipped", "reason": "database_reference"})
                continue
            if _directory_snapshot(resolved)["digest"] != entry["digest"]:
                results.append({"user_id": user_id, "result": "skipped", "reason": "content_changed"})
                continue
            shutil.rmtree(resolved)
            results.append({"user_id": user_id, "result": "deleted"})

    return {
        "schema_version": 1,
        "generated_at": _now(),
        "manifest_generated_at": manifest.get("generated_at"),
        "irreversible": True,
        "results": results,
    }


def _runtime_locations() -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parents[1]
    state_root = Path(os.environ.get("IDEER_HOME", repo_root / "backend" / ".ideer")).resolve()
    database = Path(os.environ.get("IDEER_DATABASE_PATH", state_root / "data" / "ideer.db")).resolve()
    return state_root / "users", database


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit_parser = commands.add_parser("audit", help="write a read-only user-state manifest")
    audit_parser.add_argument("--output", type=Path, required=True)
    delete_parser = commands.add_parser("delete", help="permanently delete manifest candidates")
    delete_parser.add_argument("--manifest", type=Path, required=True)
    delete_parser.add_argument("--include-reserved", action="append", default=[])
    delete_parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    if args.command == "audit":
        users_root, database = _runtime_locations()
        manifest = audit_user_state(users_root=users_root, database=database)
        _write_json(args.output, manifest)
        print(json.dumps({"output": str(args.output), "delete_candidates": manifest["delete_candidates"]}, ensure_ascii=False))
        return 0

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not args.yes:
        answer = input("Permanently delete the selected user state directories? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Deletion cancelled.", file=sys.stderr)
            return 2
    report = delete_from_manifest(manifest, include_reserved=set(args.include_reserved), yes=True)
    report_path = args.manifest.with_name(f"{args.manifest.stem}.delete-report.json")
    _write_json(report_path, report)
    print(json.dumps({"report": str(report_path), "results": report["results"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
