from __future__ import annotations

import sqlite3
from pathlib import Path

from audit_runtime_data import build_report


def _make_database(path: Path, *, user_id: str, run_id: str, content_hash: str) -> None:
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE);
            CREATE TABLE runs (run_id TEXT PRIMARY KEY);
            CREATE TABLE checkpoints (
                thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
            CREATE TABLE resources (
                id TEXT PRIMARY KEY, storage_kind TEXT, type TEXT
            );
            CREATE TABLE resource_versions (
                resource_id TEXT, version INTEGER, content_hash TEXT, storage_key TEXT,
                PRIMARY KEY (resource_id, version)
            );
            CREATE TABLE alembic_version (version_num TEXT);
            """
        )
        connection.execute("INSERT INTO users VALUES (?, ?)", (user_id, "operator@example.test"))
        connection.execute("INSERT INTO runs VALUES (?)", (run_id,))
        connection.execute("INSERT INTO checkpoints VALUES (?, ?, ?)", (run_id, "", f"checkpoint-{run_id}"))
        connection.execute("INSERT INTO resources VALUES (?, 'filesystem', 'skill')", ("resource-1",))
        connection.execute(
            "INSERT INTO resource_versions VALUES (?, 1, ?, 'skills/resource-1/versions/1')",
            ("resource-1", content_hash),
        )
        connection.execute("INSERT INTO alembic_version VALUES ('test_revision')")


def test_build_report_identifies_data_conflicts_without_disclosing_identity(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    old_root = repo_root / "backend" / ".ideer"
    new_root = repo_root / "backend" / ".deer-flow"
    relative_resource = Path("resources/skills/resource-1/versions/1/SKILL.md")
    old_resource = old_root / relative_resource
    new_resource = new_root / relative_resource
    old_resource.parent.mkdir(parents=True)
    new_resource.parent.mkdir(parents=True)
    old_resource.write_text("old version", encoding="utf-8")
    new_resource.write_text("new version", encoding="utf-8")

    _make_database(old_root / "data" / "deerflow.db", user_id="old-user", run_id="old-run", content_hash="old-hash")
    _make_database(new_root / "data" / "deerflow.db", user_id="new-user", run_id="new-run", content_hash="new-hash")

    report = build_report(repo_root)

    assert report["read_only"] is True
    assert len(report["databases"]) == 2
    comparison = report["pairwise_comparisons"][0]
    assert comparison["shared_run_ids"] == 0
    assert comparison["left_only_run_ids"] == 1
    assert comparison["right_only_run_ids"] == 1
    assert comparison["resource_version_hash_conflicts"] == 1
    assert comparison["shared_user_emails"] == 1
    assert comparison["shared_user_emails_with_different_ids"] == 1
    assert comparison["different_shared_resource_files"] == 1
    assert "operator@example.test" not in str(report)
    assert "old-user" not in str(report)
    assert "new-user" not in str(report)
