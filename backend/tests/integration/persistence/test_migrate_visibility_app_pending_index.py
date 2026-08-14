"""Tests for the visibility_applications pending index migration script.

Verifies that uq_visibility_app_pending is rebuilt keyed on
(resource_type, resource_id, applicant_id) so same-named resources owned by
different users have independent application flows.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ideer.persistence.base import Base

# ---------------------------------------------------------------------------
# Raw DDL — visibility_applications with the OLD (global) pending index
# ---------------------------------------------------------------------------

_DDL = """\
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
CREATE UNIQUE INDEX uq_visibility_app_pending
    ON visibility_applications(resource_type, resource_id)
    WHERE status = 'pending';
"""


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/test.db")
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
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    url = session.get_bind().url.render_as_string(hide_password=False).replace("sqlite://", "sqlite+aiosqlite://")
    sf = async_sessionmaker(bind=create_async_engine(url), expire_on_commit=False)
    with patch("ideer.scripts.migrate_visibility_app_pending_index.get_session_factory", return_value=sf):
        from ideer.scripts.migrate_visibility_app_pending_index import migrate_visibility_app_pending_index

        return asyncio.run(migrate_visibility_app_pending_index(dry_run=dry_run))


def _insert(session, *, app_id, applicant_id, resource_id="my-agent", status="pending"):
    session.execute(
        text(
            "INSERT INTO visibility_applications "
            "(id,resource_type,resource_id,applicant_id,current_visibility,"
            "target_visibility,status,submitted_at,version,created_at) "
            "VALUES (:id,'agent',:rid,:applicant,'private','public',:status,'2025-01-01',1,'2025-01-01')"
        ),
        {"id": app_id, "rid": resource_id, "applicant": applicant_id, "status": status},
    )
    session.commit()


# ---------------------------------------------------------------------------
# Basic migration
# ---------------------------------------------------------------------------


class TestMigration:
    def test_recreates_index(self, session):
        r = _run(session)
        assert r["action"] == "recreated"
        indexes = session.execute(text("PRAGMA index_list(visibility_applications)")).all()
        assert any(idx[1] == "uq_visibility_app_pending" for idx in indexes)

    def test_dry_run_keeps_old_index(self, session):
        """Dry-run leaves the old (global) index untouched."""
        r = _run(session, dry_run=True)
        assert r["action"] == "dry-run"
        # Old index still blocks two different applicants on the same resource
        _insert(session, app_id="a-1", applicant_id="user-1")
        with pytest.raises(Exception):
            _insert(session, app_id="a-2", applicant_id="user-2")

    def test_idempotent(self, session):
        _run(session)
        _run(session)
        indexes = session.execute(text("PRAGMA index_list(visibility_applications)")).all()
        assert len([idx for idx in indexes if idx[1] == "uq_visibility_app_pending"]) == 1

    def test_uninitialized_db_returns_skipped(self):
        with patch("ideer.scripts.migrate_visibility_app_pending_index.get_session_factory", return_value=None):
            from ideer.scripts.migrate_visibility_app_pending_index import migrate_visibility_app_pending_index

            assert asyncio.run(migrate_visibility_app_pending_index())["action"] == "skipped"


# ---------------------------------------------------------------------------
# Behavior of the new index
# ---------------------------------------------------------------------------


class TestNewIndexBehavior:
    def test_different_applicants_same_resource_allowed(self, session):
        """After migration, two owners of same-named resources can each have
        their own pending application."""
        _run(session)
        _insert(session, app_id="a-1", applicant_id="user-1")
        _insert(session, app_id="a-2", applicant_id="user-2")
        rows = session.execute(text("SELECT applicant_id FROM visibility_applications ORDER BY applicant_id")).scalars().all()
        assert rows == ["user-1", "user-2"]

    def test_same_applicant_duplicate_rejected(self, session):
        """The same applicant still cannot hold two pending applications for
        the same resource."""
        _run(session)
        _insert(session, app_id="a-1", applicant_id="user-1")
        with pytest.raises(Exception):
            _insert(session, app_id="a-2", applicant_id="user-1")

    def test_approved_does_not_conflict(self, session):
        """A non-pending application does not count toward the unique index."""
        _run(session)
        _insert(session, app_id="a-1", applicant_id="user-1", status="approved")
        _insert(session, app_id="a-2", applicant_id="user-1")
        assert session.execute(text("SELECT count(*) FROM visibility_applications")).scalar() == 2
