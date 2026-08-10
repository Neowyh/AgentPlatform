"""Tests for scripts/seed_custom_skill_owners.py."""

from __future__ import annotations

import ast
import importlib.util
import sqlite3
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "seed_custom_skill_owners.py"
SPEC = importlib.util.spec_from_file_location("seed_custom_skill_owners", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
seed_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed_script)


def _make_db(path: Path, *, admin_id: str = "admin-1") -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE users_ext (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE resource_metadata (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                department_id TEXT,
                visibility TEXT NOT NULL DEFAULT 'private',
                imported_from TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                is_favorited INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(resource_type, resource_id, owner_id)
            );
            """
        )
        conn.execute(
            "INSERT INTO users_ext (id, role, disabled) VALUES (?, 'super_admin', 0)",
            (admin_id,),
        )


def _make_skills_dir(path: Path, *names: str) -> Path:
    for name in names:
        (path / name).mkdir(parents=True)
    return path


def _load_meta(db_path: Path, skill_name: str) -> tuple | None:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT resource_id, owner_id, visibility FROM resource_metadata WHERE resource_type='skill' AND resource_id=?",
            (skill_name,),
        ).fetchone()


def test_seed_assigns_private_owner_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "ideer.db"
    _make_db(db_path, admin_id="admin-1")
    skills_dir = _make_skills_dir(tmp_path / "skills", "fault-zeroing", "srs-writing", "officecli")

    first = seed_script.seed_skill_owners(db_path, skills_dir, "admin-1")
    assert first["added"] == ["fault-zeroing", "officecli", "srs-writing"]
    assert first["skipped"] == []

    for name in ("fault-zeroing", "srs-writing", "officecli"):
        assert _load_meta(db_path, name) == (name, "admin-1", "private")

    second = seed_script.seed_skill_owners(db_path, skills_dir, "admin-1")
    assert second["added"] == []
    assert second["skipped"] == ["fault-zeroing", "officecli", "srs-writing"]

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM resource_metadata").fetchone()[0]
    assert count == 3


def test_seed_skips_dot_dirs_and_missing_skills_dir(tmp_path: Path) -> None:
    db_path = tmp_path / "ideer.db"
    _make_db(db_path, admin_id="admin-1")
    skills_dir = _make_skills_dir(tmp_path / "skills", ".hidden", "real-skill")

    result = seed_script.seed_skill_owners(db_path, skills_dir, "admin-1")

    assert result["added"] == ["real-skill"]
    assert ".hidden" not in [row[0] for row in result["added"] + result["skipped"]]

    empty = seed_script.seed_skill_owners(db_path, tmp_path / "no-such-dir", "admin-1")
    assert empty["added"] == []


def test_resolve_super_admin_id_returns_first_active(tmp_path: Path) -> None:
    db_path = tmp_path / "ideer.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users_ext (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.executemany(
            "INSERT INTO users_ext (id, role, disabled) VALUES (?, ?, ?)",
            [
                ("disabled-admin", "super_admin", 1),
                ("active-admin", "super_admin", 0),
                ("regular", "user", 0),
            ],
        )

    assert seed_script.resolve_super_admin_id(db_path) == "active-admin"


def test_resolve_super_admin_id_returns_none_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "ideer.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users_ext (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute("INSERT INTO users_ext (id, role, disabled) VALUES ('u1', 'user', 0)")

    assert seed_script.resolve_super_admin_id(db_path) is None
    assert seed_script.resolve_super_admin_id(tmp_path / "missing.db") is None


def test_main_fails_without_admin_or_db(tmp_path: Path) -> None:
    missing_db = tmp_path / "missing.db"
    assert seed_script.main(["--db", str(missing_db), "--skills-dir", str(tmp_path / "skills")]) == 1

    db_no_admin = tmp_path / "no-admin.db"
    with sqlite3.connect(db_no_admin) as conn:
        conn.execute("CREATE TABLE users_ext (id TEXT PRIMARY KEY, role TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0)")
    assert seed_script.main(["--db", str(db_no_admin), "--skills-dir", str(tmp_path / "skills")]) == 1


def test_main_seeds_with_default_owner_resolution(tmp_path: Path) -> None:
    db_path = tmp_path / "ideer.db"
    _make_db(db_path, admin_id="admin-1")
    skills_dir = _make_skills_dir(tmp_path / "skills", "fault-zeroing")

    assert seed_script.main(["--db", str(db_path), "--skills-dir", str(skills_dir)]) == 0
    assert _load_meta(db_path, "fault-zeroing") == ("fault-zeroing", "admin-1", "private")


def test_seed_script_uses_only_standard_library_imports_for_offline_deploy_hosts() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported_modules = {alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(node.module.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)

    assert imported_modules <= {"__future__", "argparse", "sqlite3", "sys", "uuid", "datetime", "pathlib"}
