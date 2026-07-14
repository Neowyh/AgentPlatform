from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from reconcile_user_state import audit_user_state, delete_from_manifest


def _database(path: Path) -> Path:
    database = path / "ideer.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE users (id TEXT PRIMARY KEY);
            CREATE TABLE users_ext (id TEXT PRIMARY KEY);
            CREATE TABLE resource_metadata (owner_id TEXT);
            CREATE TABLE threads_meta (user_id TEXT);
            CREATE TABLE runs (user_id TEXT, status TEXT);
            CREATE TABLE run_events (user_id TEXT);
            CREATE TABLE feedback (user_id TEXT);
            CREATE TABLE visibility_applications (
                applicant_id TEXT,
                reviewed_by TEXT
            );
            """
        )
        connection.execute("INSERT INTO users VALUES ('valid-user')")
        connection.execute("INSERT INTO users_ext VALUES ('valid-user')")
    return database


def _write_user(users_root: Path, user_id: str, content: str = "data") -> Path:
    user_dir = users_root / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "state.txt").write_text(content, encoding="utf-8")
    return user_dir


def test_audit_is_read_only_and_classifies_directory_subjects(tmp_path):
    users_root = tmp_path / "users"
    database = _database(tmp_path)
    _write_user(users_root, "valid-user")
    _write_user(users_root, "default")
    _write_user(users_root, "test-user-autouse")
    _write_user(users_root, "orphan-user")
    before = {path.relative_to(users_root): path.stat().st_mtime_ns for path in users_root.rglob("*")}

    manifest = audit_user_state(users_root=users_root, database=database)

    after = {path.relative_to(users_root): path.stat().st_mtime_ns for path in users_root.rglob("*")}
    entries = {entry["user_id"]: entry for entry in manifest["directories"]}
    assert before == after
    assert entries["valid-user"]["classification"] == "database_user"
    assert entries["default"]["classification"] == "reserved_system_subject"
    assert entries["test-user-autouse"]["classification"] == "test_pollution"
    assert entries["orphan-user"]["classification"] == "orphan"
    assert set(manifest["delete_candidates"]) == {"test-user-autouse", "orphan-user"}


def test_delete_removes_only_unchanged_unreferenced_candidates(tmp_path):
    users_root = tmp_path / "users"
    database = _database(tmp_path)
    orphan = _write_user(users_root, "orphan-user")
    manifest = audit_user_state(users_root=users_root, database=database)

    report = delete_from_manifest(manifest, yes=True)

    assert not orphan.exists()
    assert report["results"] == [pytest.approx({"user_id": "orphan-user", "result": "deleted"})]


def test_delete_requires_explicit_reserved_subject_and_detects_changes(tmp_path):
    users_root = tmp_path / "users"
    database = _database(tmp_path)
    default = _write_user(users_root, "default")
    orphan = _write_user(users_root, "orphan-user")
    manifest = audit_user_state(users_root=users_root, database=database)
    (orphan / "new.txt").write_text("changed", encoding="utf-8")

    report = delete_from_manifest(manifest, include_reserved={"default"}, yes=True)

    results = {entry["user_id"]: entry for entry in report["results"]}
    assert not default.exists()
    assert orphan.exists()
    assert results["default"]["result"] == "deleted"
    assert results["orphan-user"]["result"] == "skipped"
    assert results["orphan-user"]["reason"] == "content_changed"


def test_delete_skips_new_database_reference_and_symlink(tmp_path):
    users_root = tmp_path / "users"
    database = _database(tmp_path)
    referenced = _write_user(users_root, "referenced-later")
    manifest = audit_user_state(users_root=users_root, database=database)
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO threads_meta VALUES ('referenced-later')")

    outside = tmp_path / "outside"
    outside.mkdir()
    link = users_root / "linked-user"
    link.symlink_to(outside, target_is_directory=True)
    linked_manifest = audit_user_state(users_root=users_root, database=database)

    report = delete_from_manifest(manifest, yes=True)
    linked_report = delete_from_manifest(linked_manifest, yes=True)

    assert referenced.exists()
    assert report["results"][0]["reason"] == "database_reference"
    linked_result = next(item for item in linked_report["results"] if item["user_id"] == "linked-user")
    assert linked_result["reason"] == "symbolic_link"
    assert outside.exists()


def test_manifest_can_be_serialized_for_two_step_operation(tmp_path):
    users_root = tmp_path / "users"
    database = _database(tmp_path)
    _write_user(users_root, "orphan-user")

    manifest = audit_user_state(users_root=users_root, database=database)

    assert json.loads(json.dumps(manifest))["schema_version"] == 1
