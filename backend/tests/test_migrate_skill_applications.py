"""Tests for the skill_applications → visibility_applications migration script.

All tables are created via raw DDL to avoid SQLAlchemy MetaData collisions
and SQLite partial-index quirks (postgresql_where is ignored by SQLite).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import the migration module once at module level so its SkillApplication(Base)
# class registers on Base.metadata exactly once.  Subsequent imports are cached.
import ideer.scripts.migrate_skill_applications as _migrate_mod  # noqa: F401
from ideer.persistence.base import Base

# ---------------------------------------------------------------------------
# Raw DDL — every table the migration touches
# ---------------------------------------------------------------------------

_DDL = """\
DROP TABLE IF EXISTS skill_applications;
CREATE TABLE skill_applications (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    applicant_id TEXT NOT NULL,
    request_level TEXT NOT NULL,
    department_id TEXT,
    reason TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMP,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    review_comment TEXT
);

DROP TABLE IF EXISTS users_ext;
CREATE TABLE users_ext (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
);

DROP TABLE IF EXISTS departments;
CREATE TABLE departments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

DROP TABLE IF EXISTS resource_metadata;
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
    deleted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(resource_type, resource_id)
);

DROP TABLE IF EXISTS visibility_applications;
CREATE TABLE visibility_applications (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    applicant_id TEXT NOT NULL,
    current_visibility TEXT NOT NULL,
    target_visibility TEXT NOT NULL,
    department_id TEXT,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMP NOT NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    review_comment TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL
);
"""

_INS_SA = """\
INSERT INTO skill_applications
    (id, skill_id, skill_name, applicant_id, request_level,
     department_id, reason, status, submitted_at, reviewed_by, reviewed_at, review_comment)
VALUES
    (:id, :skill_id, :skill_name, :applicant_id, :request_level,
     :department_id, :reason, :status, :submitted_at, :reviewed_by, :reviewed_at, :review_comment)
"""


def _sa_row(**overrides):
    d = dict(
        id="sa-001",
        skill_id="skill-a",
        skill_name="Test Skill",
        applicant_id="user-1",
        request_level="public",
        department_id=None,
        reason="",
        status="pending",
        submitted_at="2025-01-01T00:00:00",
        reviewed_by=None,
        reviewed_at=None,
        review_comment=None,
    )
    d.update(overrides)
    return d


def _ins_rm(conn, *, rid="rm-1", skill_id="skill-a", vis="public"):
    conn.execute(
        text("INSERT INTO resource_metadata (id,resource_type,resource_id,owner_id,visibility,version,created_at,updated_at) VALUES (:id,'skill',:rid,'owner-1',:vis,1,'2025-01-01','2025-01-01')"),
        {"id": rid, "rid": skill_id, "vis": vis},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    # Drop all tables registered in metadata first to avoid conflicts
    Base.metadata.drop_all(eng)
    with eng.begin() as conn:
        for stmt in _DDL.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    S = sessionmaker(bind=engine, expire_on_commit=False)
    s = S()
    yield s
    s.close()


def _run(session, *, dry_run=False):
    sf = MagicMock(return_value=session)
    with patch("ideer.scripts.migrate_skill_applications.get_session_factory", return_value=sf):
        from ideer.scripts.migrate_skill_applications import migrate_skill_applications

        return migrate_skill_applications(dry_run=dry_run)


# ---------------------------------------------------------------------------
# Basic migration
# ---------------------------------------------------------------------------


class TestBasicMigration:
    def test_empty_returns_zeros(self, session):
        assert _run(session) == {"migrated": 0, "skipped": 0, "failed": 0}

    def test_single_record(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row())
        r = _run(session)
        assert r["migrated"] == 1 and r["skipped"] == 0 and r["failed"] == 0
        row = session.execute(text("SELECT * FROM visibility_applications")).mappings().one()
        assert row["resource_type"] == "skill"
        assert row["resource_id"] == "skill-a"
        assert row["applicant_id"] == "user-1"
        assert row["target_visibility"] == "public"
        assert row["current_visibility"] == "private"
        assert row["status"] == "pending"
        assert row["version"] == 1

    def test_multiple_records(self, session, engine):
        with engine.begin() as c:
            for i in range(5):
                c.execute(text(_INS_SA), _sa_row(id=f"sa-{i}", skill_id=f"sk-{i}", applicant_id=f"u-{i}"))
        assert _run(session)["migrated"] == 5
        assert session.execute(text("SELECT count(*) FROM visibility_applications")).scalar() == 5

    def test_skill_name_not_in_target(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row())
        _run(session)
        cols = [d[0] for d in session.execute(text("PRAGMA table_info(visibility_applications)")).all()]
        assert "skill_name" not in cols


# ---------------------------------------------------------------------------
# Visibility resolution
# ---------------------------------------------------------------------------


class TestVisibilityResolution:
    def test_from_resource_metadata(self, session, engine):
        with engine.begin() as c:
            _ins_rm(c, vis="public")
            c.execute(text(_INS_SA), _sa_row())
        _run(session)
        v = session.execute(text("SELECT current_visibility FROM visibility_applications")).scalar()
        assert v == "public"

    def test_fallback_to_private(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row())
        _run(session)
        assert session.execute(text("SELECT current_visibility FROM visibility_applications")).scalar() == "private"

    def test_department_visibility(self, session, engine):
        with engine.begin() as c:
            _ins_rm(c, rid="rm-2", skill_id="skill-x", vis="department")
            c.execute(text(_INS_SA), _sa_row(skill_id="skill-x", applicant_id="user-x"))
        _run(session)
        assert session.execute(text("SELECT current_visibility FROM visibility_applications")).scalar() == "department"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_skips_pending_duplicate(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row())
        assert _run(session)["migrated"] == 1
        r2 = _run(session)
        assert r2["skipped"] == 1 and r2["migrated"] == 0
        assert session.execute(text("SELECT count(*) FROM visibility_applications")).scalar() == 1

    def test_does_not_skip_approved(self, session, engine):
        """An already-approved row should not block a new pending migration."""
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row())
        # Manually insert an approved record
        session.execute(
            text(
                "INSERT INTO visibility_applications "
                "(id,resource_type,resource_id,applicant_id,current_visibility,"
                "target_visibility,status,submitted_at,version,created_at) "
                "VALUES ('va-ok','skill','skill-a','user-1','private','public','approved','2025-01-01',1,'2025-01-01')"
            )
        )
        session.commit()
        r = _run(session)
        assert r["migrated"] == 1
        assert session.execute(text("SELECT count(*) FROM visibility_applications")).scalar() == 2


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_counts_without_writing(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row())
        r = _run(session, dry_run=True)
        assert r["migrated"] == 1
        assert session.execute(text("SELECT count(*) FROM visibility_applications")).scalar() == 0


# ---------------------------------------------------------------------------
# Null / empty fields
# ---------------------------------------------------------------------------


class TestFieldDefaults:
    def test_none_reason_becomes_empty(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row(reason=None))
        _run(session)
        assert session.execute(text("SELECT reason FROM visibility_applications")).scalar() == ""

    def test_none_review_comment_becomes_empty(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row(status="approved", reviewed_by="admin-1", reviewed_at="2025-02-01T00:00:00", review_comment=None))
        _run(session)
        row = session.execute(text("SELECT review_comment, reviewed_by FROM visibility_applications")).mappings().one()
        assert row["review_comment"] == ""
        assert row["reviewed_by"] == "admin-1"

    def test_preserves_submitted_at(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row(submitted_at="2025-03-15T12:00:00"))
        _run(session)
        assert session.execute(text("SELECT submitted_at FROM visibility_applications")).scalar() is not None

    def test_preserves_department_id(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row(department_id="dept-42"))
        _run(session)
        assert session.execute(text("SELECT department_id FROM visibility_applications")).scalar() == "dept-42"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_one_failure_does_not_block_others(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row(id="sa-ok", skill_id="skill-ok"))
            c.execute(text(_INS_SA), _sa_row(id="sa-bad", skill_id="skill-bad"))

        orig = None
        with patch("ideer.scripts.migrate_skill_applications.get_session_factory", return_value=MagicMock(return_value=session)):
            from ideer.scripts.migrate_skill_applications import _resolve_current_visibility

            orig = _resolve_current_visibility

        def _boom(skill_id, sess):
            if skill_id == "skill-bad":
                raise RuntimeError("boom")
            return orig(skill_id, sess)

        with patch("ideer.scripts.migrate_skill_applications.get_session_factory", return_value=MagicMock(return_value=session)), patch("ideer.scripts.migrate_skill_applications._resolve_current_visibility", side_effect=_boom):
            from ideer.scripts.migrate_skill_applications import migrate_skill_applications

            r = migrate_skill_applications()

        assert r["migrated"] == 1
        assert r["failed"] == 1

    def test_uninitialized_db_returns_zeros(self):
        with patch("ideer.scripts.migrate_skill_applications.get_session_factory", return_value=None):
            from ideer.scripts.migrate_skill_applications import migrate_skill_applications

            assert migrate_skill_applications() == {"migrated": 0, "skipped": 0, "failed": 0}


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------


class TestDataIntegrity:
    def test_new_uuid_not_reused(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row(id="old-id"))
        _run(session)
        new_id = session.execute(text("SELECT id FROM visibility_applications")).scalar()
        assert new_id != "old-id" and len(new_id) == 36

    def test_created_at_is_set(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row())
        before = datetime.utcnow()
        _run(session)
        after = datetime.utcnow()
        created = session.execute(text("SELECT created_at FROM visibility_applications")).scalar()
        # SQLite stores as "YYYY-MM-DD HH:MM:SS"; normalize to ISO format for comparison
        created_iso = created.replace(" ", "T")[:19]
        assert before.isoformat()[:19] <= created_iso <= after.isoformat()[:19]

    def test_version_always_one(self, session, engine):
        with engine.begin() as c:
            for i in range(3):
                c.execute(text(_INS_SA), _sa_row(id=f"sa-{i}", skill_id=f"sk-{i}", applicant_id=f"u-{i}"))
        _run(session)
        versions = session.execute(text("SELECT version FROM visibility_applications")).scalars().all()
        assert all(v == 1 for v in versions)

    def test_target_matches_request_level(self, session, engine):
        with engine.begin() as c:
            c.execute(text(_INS_SA), _sa_row(request_level="department"))
        _run(session)
        assert session.execute(text("SELECT target_visibility FROM visibility_applications")).scalar() == "department"
