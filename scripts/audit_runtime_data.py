#!/usr/bin/env python3
"""Read-only inventory of legacy and DeerFlow runtime data directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

_TABLE_KEYS = {
    "runs": ("run_id",),
    "checkpoints": ("thread_id", "checkpoint_ns", "checkpoint_id"),
    "resources": ("id",),
    "resource_versions": ("resource_id", "version"),
}


def _open_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _rows_by_key(connection: sqlite3.Connection, table: str, columns: tuple[str, ...]) -> dict[tuple[Any, ...], Any]:
    names = _table_names(connection)
    if table not in names:
        return {}
    available = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
    if not set(columns).issubset(available):
        return {}
    selected = ", ".join(f'"{column}"' for column in columns)
    if table == "resource_versions":
        query = f'SELECT {selected}, content_hash FROM "{table}"'
        return {(row[0], row[1]): row[2] for row in connection.execute(query)}
    return {tuple(row): None for row in connection.execute(f'SELECT {selected} FROM "{table}"')}


def _database_inventory(path: Path, state_root: Path) -> dict[str, Any]:
    connection = _open_readonly(path)
    try:
        tables = _table_names(connection)
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in ("runs", "checkpoints", "resources", "resource_versions", "users") if table in tables}
        revisions = {}
        for table in ("alembic_version", "deerflow_alembic_version"):
            if table in tables:
                revisions[table] = [row[0] for row in connection.execute(f'SELECT version_num FROM "{table}"')]

        storage_rows = []
        if {"resources", "resource_versions"}.issubset(tables):
            columns = {row[1] for row in connection.execute('PRAGMA table_info("resources")')}
            if {"id", "storage_kind", "type"}.issubset(columns):
                storage_rows = connection.execute(
                    "SELECT v.storage_key FROM resource_versions v JOIN resources r ON r.id = v.resource_id WHERE r.storage_kind = 'filesystem' AND r.type != 'workflow' AND v.storage_key IS NOT NULL AND v.storage_key != ''"
                ).fetchall()
        missing_resource_paths = sum(not (state_root / "resources" / row[0]).is_dir() for row in storage_rows)

        users = {}
        if "users" in tables:
            user_columns = {row[1] for row in connection.execute('PRAGMA table_info("users")')}
            if {"id", "email"}.issubset(user_columns):
                for user_id, email in connection.execute('SELECT id, email FROM "users"'):
                    email_key = hashlib.sha256(email.strip().casefold().encode("utf-8")).hexdigest()
                    users[email_key] = user_id
        return {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "table_count": len(tables),
            "counts": counts,
            "migration_revisions": revisions,
            "user_email_keys": users,
            "resource_storage_keys": _rows_by_key(connection, "resource_versions", ("resource_id", "version")),
            "run_ids": set(_rows_by_key(connection, "runs", _TABLE_KEYS["runs"])),
            "checkpoint_keys": set(_rows_by_key(connection, "checkpoints", _TABLE_KEYS["checkpoints"])),
            "resource_ids": set(_rows_by_key(connection, "resources", _TABLE_KEYS["resources"])),
            "missing_resource_paths": missing_resource_paths,
            "checked_resource_paths": len(storage_rows),
        }
    finally:
        connection.close()


def _file_inventory(root: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    resources: dict[str, str] = {}
    file_count = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        file_count += 1
        relative = path.relative_to(root)
        counts[relative.parts[0]] += 1
        if relative.parts[0] == "resources":
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            resources[relative.as_posix()] = digest.hexdigest()
    return {"path": str(root.resolve()), "file_count": file_count, "top_level_file_counts": dict(sorted(counts.items())), "resource_hashes": resources}


def _pairwise(left: dict[str, Any], right: dict[str, Any]) -> dict[str, int]:
    left_versions = left["resource_storage_keys"]
    right_versions = right["resource_storage_keys"]
    shared_versions = left_versions.keys() & right_versions.keys()
    left_emails = left["user_email_keys"]
    right_emails = right["user_email_keys"]
    shared_emails = left_emails.keys() & right_emails.keys()
    left_files = left["_files"]["resource_hashes"]
    right_files = right["_files"]["resource_hashes"]
    shared_files = left_files.keys() & right_files.keys()
    return {
        "shared_run_ids": len(left["run_ids"] & right["run_ids"]),
        "left_only_run_ids": len(left["run_ids"] - right["run_ids"]),
        "right_only_run_ids": len(right["run_ids"] - left["run_ids"]),
        "shared_checkpoints": len(left["checkpoint_keys"] & right["checkpoint_keys"]),
        "left_only_checkpoints": len(left["checkpoint_keys"] - right["checkpoint_keys"]),
        "right_only_checkpoints": len(right["checkpoint_keys"] - left["checkpoint_keys"]),
        "shared_resource_ids": len(left["resource_ids"] & right["resource_ids"]),
        "shared_resource_versions": len(shared_versions),
        "resource_version_hash_conflicts": sum(left_versions[key] != right_versions[key] for key in shared_versions),
        "shared_user_emails": len(shared_emails),
        "shared_user_emails_with_different_ids": sum(left_emails[key] != right_emails[key] for key in shared_emails),
        "shared_resource_files": len(shared_files),
        "identical_shared_resource_files": sum(left_files[key] == right_files[key] for key in shared_files),
        "different_shared_resource_files": sum(left_files[key] != right_files[key] for key in shared_files),
    }


def build_report(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    state_roots = [repo_root / "backend" / ".ideer", repo_root / "backend" / ".deer-flow"]
    files = {str(root): _file_inventory(root) if root.is_dir() else {"path": str(root), "file_count": 0, "top_level_file_counts": {}, "resource_hashes": {}} for root in state_roots}
    databases = []
    for root in state_roots:
        for path in sorted((root / "data").glob("*.db")) if root.is_dir() else ():
            info = _database_inventory(path, root)
            info["_files"] = files[str(root)]
            databases.append(info)

    comparisons = []
    for left_index, left in enumerate(databases):
        for right in databases[left_index + 1 :]:
            comparisons.append({"left": left["path"], "right": right["path"], **_pairwise(left, right)})

    for database in databases:
        database.pop("user_email_keys", None)
        database.pop("resource_storage_keys", None)
        database.pop("run_ids", None)
        database.pop("checkpoint_keys", None)
        database.pop("resource_ids", None)
        database.pop("_files", None)
    for report in files.values():
        report.pop("resource_hashes", None)

    return {"repo_root": str(repo_root), "read_only": True, "state_roots": list(files.values()), "databases": databases, "pairwise_comparisons": comparisons}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="print the complete sanitized JSON report")
    args = parser.parse_args()
    report = build_report(args.repo_root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Runtime data roots: {len(report['state_roots'])}")
        for root in report["state_roots"]:
            print(f"  {root['path']}: {root['file_count']} files")
        print(f"SQLite databases: {len(report['databases'])}")
        for database in report["databases"]:
            counts = ", ".join(f"{key}={value}" for key, value in sorted(database["counts"].items()))
            print(f"  {database['path']}: {counts}; missing resource paths={database['missing_resource_paths']}/{database['checked_resource_paths']}")
        for item in report["pairwise_comparisons"]:
            print(f"  compare {Path(item['left']).name} ↔ {Path(item['right']).name}: {item['resource_version_hash_conflicts']} resource-version hash conflicts; {item['shared_user_emails_with_different_ids']} email identity conflicts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
