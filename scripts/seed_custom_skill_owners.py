#!/usr/bin/env python3
"""Assign bundled custom skills to a super admin as private resources.

The gateway already reconciles ``skills/custom/`` metadata at startup
(``app.gateway.app._reconcile_resource_metadata``), but on the first boot no
admin exists yet so the scan is skipped.  This host-side helper performs the
same backfill after the admin account has been created during an offline
deployment.

Stdlib-only (sqlite3), idempotent: existing metadata rows are never touched.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

RESOURCE_TYPE = "skill"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _skill_names(skills_dir: Path) -> list[str]:
    if not skills_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in skills_dir.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )


def resolve_super_admin_id(db_path: Path) -> str | None:
    """Return the first active super admin user id, or None when absent."""
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT id FROM users_ext WHERE role='super_admin' AND disabled=0 LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0]) if row else None


def seed_skill_owners(db_path: Path, skills_dir: Path, owner_id: str) -> dict:
    """Upsert private resource_metadata for every bundled custom skill."""
    names = _skill_names(skills_dir)
    added: list[str] = []
    skipped: list[str] = []
    now = _now()

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            for name in names:
                existing = conn.execute(
                    "SELECT 1 FROM resource_metadata WHERE resource_type=? AND resource_id=?",
                    (RESOURCE_TYPE, name),
                ).fetchone()
                if existing:
                    skipped.append(name)
                    continue
                conn.execute(
                    """
                    INSERT INTO resource_metadata (
                        id, resource_type, resource_id, owner_id, department_id,
                        visibility, imported_from, version, is_favorited,
                        created_at, updated_at
                    ) VALUES (?, 'skill', ?, ?, NULL, 'private', NULL, 1, 0, ?, ?)
                    """,
                    (uuid.uuid4().hex, name, owner_id, now, now),
                )
                added.append(name)
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"failed to seed skill metadata in {db_path}: {exc}"
        ) from exc
    finally:
        conn.close()

    return {
        "added": added,
        "skipped": skipped,
        "skills_dir": str(skills_dir),
        "owner_id": owner_id,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assign bundled custom skills to a super admin as private resources.",
    )
    parser.add_argument(
        "--db", required=True, help="Path to the runtime SQLite database (ideer.db)."
    )
    parser.add_argument(
        "--skills-dir",
        default=None,
        help="Path to the bundled skills/custom directory (defaults to <bundle>/skills/custom).",
    )
    parser.add_argument(
        "--owner",
        default=None,
        help="Super admin user id; defaults to the first active super admin in the database.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    db_path = Path(args.db).resolve()
    if not db_path.is_file():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        return 1

    skills_dir = (
        Path(args.skills_dir).resolve()
        if args.skills_dir
        else Path(__file__).resolve().parents[1] / "skills" / "custom"
    )

    owner_id = args.owner or resolve_super_admin_id(db_path)
    if not owner_id:
        print(
            f"Error: no active super admin found in {db_path}; pass --owner explicitly.",
            file=sys.stderr,
        )
        return 1

    try:
        result = seed_skill_owners(db_path, skills_dir, owner_id)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Skills dir : {result['skills_dir']}")
    print(f"Owner      : {result['owner_id']}")
    print(f"Skills added: {', '.join(result['added']) or '(none)'}")
    print(f"Skills skipped: {', '.join(result['skipped']) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
