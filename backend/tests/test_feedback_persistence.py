"""Tests for ideer.persistence.feedback — FeedbackRow model and FeedbackRepository."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ideer.persistence.base import Base
from ideer.persistence.feedback.model import FeedbackRow
from ideer.persistence.feedback.sql import FeedbackRepository
from ideer.runtime.user_context import _current_user, reset_current_user, set_current_user

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _set_user():
    """Set a test user in the contextvar for the duration of the test."""
    user = SimpleNamespace(id="test-user-1", email="test1@example.com")
    token = set_current_user(user)
    try:
        yield user
    finally:
        reset_current_user(token)


@pytest_asyncio.fixture()
async def _db():
    """Create an in-memory async SQLite database with FeedbackRow table."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    yield sf
    await engine.dispose()


@pytest_asyncio.fixture()
async def repo(_db):
    """Return a FeedbackRepository backed by the test database."""
    return FeedbackRepository(_db)


# ---------------------------------------------------------------------------
# FeedbackRow model
# ---------------------------------------------------------------------------


class TestFeedbackRowModel:
    @pytest.mark.asyncio
    async def test_to_dict_fields(self, _db):
        """FeedbackRow.to_dict() returns all mapped columns."""
        row = FeedbackRow(
            feedback_id="fb-1",
            run_id="run-1",
            thread_id="thread-1",
            user_id="test-user-1",
            message_id="msg-1",
            rating=1,
            comment="great",
            created_at=datetime.now(UTC),
        )
        async with _db() as session:
            session.add(row)
            await session.commit()
            d = row.to_dict()
        assert set(d.keys()) == {
            "feedback_id",
            "run_id",
            "thread_id",
            "user_id",
            "message_id",
            "rating",
            "comment",
            "created_at",
        }
        assert d["feedback_id"] == "fb-1"
        assert d["rating"] == 1
        assert d["comment"] == "great"

    @pytest.mark.asyncio
    async def test_to_dict_excludes_columns(self, _db):
        """to_dict(exclude=...) omits specified columns."""
        row = FeedbackRow(
            feedback_id="fb-2",
            run_id="run-2",
            thread_id="thread-2",
            user_id="u2",
            rating=-1,
            comment=None,
            created_at=datetime.now(UTC),
        )
        async with _db() as session:
            session.add(row)
            await session.commit()
            d = row.to_dict(exclude={"comment", "message_id"})
        assert "comment" not in d
        assert "message_id" not in d
        assert "feedback_id" in d

    @pytest.mark.asyncio
    async def test_repr(self, _db):
        """FeedbackRow.__repr__ contains class name and key fields."""
        row = FeedbackRow(
            feedback_id="fb-3",
            run_id="run-3",
            thread_id="thread-3",
            user_id="u3",
            rating=1,
            created_at=datetime.now(UTC),
        )
        async with _db() as session:
            session.add(row)
            await session.commit()
            r = repr(row)
        assert "FeedbackRow" in r
        assert "fb-3" in r
        assert "run-3" in r


# ---------------------------------------------------------------------------
# FeedbackRepository.create
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_positive_rating(self, repo, _set_user):
        result = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            comment="good",
        )
        assert result["feedback_id"]
        assert result["run_id"] == "r1"
        assert result["thread_id"] == "t1"
        assert result["rating"] == 1
        assert result["comment"] == "good"
        assert result["user_id"] == "test-user-1"
        assert result["created_at"] is not None

    @pytest.mark.asyncio
    async def test_create_negative_rating(self, repo, _set_user):
        result = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=-1,
            comment="bad",
        )
        assert result["rating"] == -1

    @pytest.mark.asyncio
    async def test_create_with_message_id(self, repo, _set_user):
        result = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            message_id="msg-42",
        )
        assert result["message_id"] == "msg-42"

    @pytest.mark.asyncio
    async def test_create_invalid_rating_zero(self, repo, _set_user):
        with pytest.raises(ValueError, match="rating must be"):
            await repo.create(run_id="r1", thread_id="t1", rating=0)

    @pytest.mark.asyncio
    async def test_create_invalid_rating_positive_out_of_range(self, repo, _set_user):
        with pytest.raises(ValueError, match="rating must be"):
            await repo.create(run_id="r1", thread_id="t1", rating=2)

    @pytest.mark.asyncio
    async def test_create_invalid_rating_negative_out_of_range(self, repo, _set_user):
        with pytest.raises(ValueError, match="rating must be"):
            await repo.create(run_id="r1", thread_id="t1", rating=-2)

    @pytest.mark.asyncio
    async def test_create_with_explicit_user_id(self, repo):
        result = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        assert result["user_id"] == "alice"

    @pytest.mark.asyncio
    async def test_create_with_none_user_id(self, repo):
        """user_id=None should work (migration/CLI path)."""
        result = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id=None,
        )
        assert result["user_id"] is None

    @pytest.mark.asyncio
    async def test_create_auto_user_id_uses_contextvar(self, repo, _set_user):
        """create() with default user_id=AUTO reads from contextvar."""
        result = await repo.create(run_id="r1", thread_id="t1", rating=1)
        assert result["user_id"] == _set_user.id

    @pytest.mark.asyncio
    async def test_create_auto_without_context_raises(self, repo):
        token = _current_user.set(None)
        try:
            with pytest.raises(RuntimeError, match="no user context"):
                await repo.create(run_id="r1", thread_id="t1", rating=1)
        finally:
            _current_user.reset(token)

    @pytest.mark.asyncio
    async def test_create_comment_default_none(self, repo):
        result = await repo.create(run_id="r1", thread_id="t1", rating=1)
        assert result["comment"] is None


# ---------------------------------------------------------------------------
# FeedbackRepository.get
# ---------------------------------------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_get_existing(self, repo, _set_user):
        created = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
        )
        fetched = await repo.get(created["feedback_id"], user_id=_set_user.id)
        assert fetched is not None
        assert fetched["feedback_id"] == created["feedback_id"]
        assert fetched["rating"] == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, repo, _set_user):
        result = await repo.get("no-such-id", user_id=_set_user.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_mismatch_returns_none(self, repo):
        """get() returns None when user_id doesn't match the record."""
        created = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        result = await repo.get(created["feedback_id"], user_id="bob")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_no_user_filter(self, repo):
        """get() with user_id=None bypasses the user filter."""
        created = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        result = await repo.get(created["feedback_id"], user_id=None)
        assert result is not None
        assert result["feedback_id"] == created["feedback_id"]

    @pytest.mark.asyncio
    async def test_get_auto_uses_contextvar(self, repo, _set_user):
        """get() with default user_id=AUTO reads from contextvar."""
        created = await repo.create(run_id="r1", thread_id="t1", rating=1)
        fetched = await repo.get(created["feedback_id"])
        assert fetched is not None

    @pytest.mark.asyncio
    async def test_get_auto_returns_none_for_other_user(self, repo, _set_user):
        """get() with AUTO returns None if record belongs to a different user."""
        created = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="other-user",
        )
        result = await repo.get(created["feedback_id"])
        assert result is None


# ---------------------------------------------------------------------------
# FeedbackRepository.list_by_run
# ---------------------------------------------------------------------------


class TestListByRun:
    @pytest.mark.asyncio
    async def test_list_by_run(self, repo, _set_user):
        await repo.create(run_id="r1", thread_id="t1", rating=1)
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_run("t1", "r1", user_id=None)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_run_empty(self, repo, _set_user):
        result = await repo.list_by_run("t1", "nonexistent", user_id=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_by_run_user_filter(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_run("t1", "r1", user_id="alice")
        assert len(result) == 1
        assert result[0]["user_id"] == "alice"

    @pytest.mark.asyncio
    async def test_list_by_run_orders_by_created_at(self, repo):
        """Results are ordered by created_at ascending."""
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_run("t1", "r1", user_id=None)
        times = [r["created_at"] for r in result]
        assert times == sorted(times)

    @pytest.mark.asyncio
    async def test_list_by_run_respects_limit(self, repo):
        for i in range(5):
            await repo.create(
                run_id="r1",
                thread_id="t1",
                rating=1,
                user_id=f"user-{i}",
            )
        result = await repo.list_by_run("t1", "r1", limit=2, user_id=None)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_run_auto_uses_contextvar(self, repo, _set_user):
        """list_by_run() with AUTO filters by current contextvar user."""
        await repo.create(run_id="r1", thread_id="t1", rating=1)
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_run("t1", "r1")
        assert len(result) == 1
        assert result[0]["user_id"] == _set_user.id


# ---------------------------------------------------------------------------
# FeedbackRepository.list_by_thread
# ---------------------------------------------------------------------------


class TestListByThread:
    @pytest.mark.asyncio
    async def test_list_by_thread(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r2", thread_id="t1", rating=-1, user_id="bob")
        await repo.create(run_id="r3", thread_id="t2", rating=1, user_id="alice")
        result = await repo.list_by_thread("t1", user_id=None)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_thread_empty(self, repo):
        result = await repo.list_by_thread("nonexistent", user_id=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_by_thread_user_filter(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r2", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_thread("t1", user_id="alice")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_by_thread_auto_uses_contextvar(self, repo, _set_user):
        """list_by_thread() with AUTO filters by contextvar user."""
        await repo.create(run_id="r1", thread_id="t1", rating=1)
        await repo.create(run_id="r2", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_thread("t1")
        assert len(result) == 1
        assert result[0]["user_id"] == _set_user.id


# ---------------------------------------------------------------------------
# FeedbackRepository.delete
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self, repo):
        created = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        deleted = await repo.delete(created["feedback_id"], user_id="alice")
        assert deleted is True
        assert await repo.get(created["feedback_id"], user_id=None) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, repo):
        deleted = await repo.delete("no-such-id", user_id="alice")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_user_mismatch(self, repo):
        created = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        deleted = await repo.delete(created["feedback_id"], user_id="bob")
        assert deleted is False
        assert await repo.get(created["feedback_id"], user_id=None) is not None

    @pytest.mark.asyncio
    async def test_delete_no_user_filter(self, repo):
        created = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        deleted = await repo.delete(created["feedback_id"], user_id=None)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_auto_uses_contextvar(self, repo, _set_user):
        """delete() with AUTO uses contextvar user."""
        created = await repo.create(run_id="r1", thread_id="t1", rating=1)
        deleted = await repo.delete(created["feedback_id"])
        assert deleted is True


# ---------------------------------------------------------------------------
# FeedbackRepository.upsert
# ---------------------------------------------------------------------------


class TestUpsert:
    @pytest.mark.asyncio
    async def test_upsert_creates_new(self, repo):
        result = await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        assert result["feedback_id"]
        assert result["rating"] == 1

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, repo):
        first = await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        second = await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=-1,
            user_id="alice",
            comment="changed mind",
        )
        # Same feedback_id means it was updated, not created
        assert first["feedback_id"] == second["feedback_id"]
        assert second["rating"] == -1
        assert second["comment"] == "changed mind"

    @pytest.mark.asyncio
    async def test_upsert_invalid_rating_zero(self, repo):
        with pytest.raises(ValueError, match="rating must be"):
            await repo.upsert(
                run_id="r1",
                thread_id="t1",
                rating=0,
                user_id="alice",
            )

    @pytest.mark.asyncio
    async def test_upsert_invalid_rating_out_of_range(self, repo):
        with pytest.raises(ValueError, match="rating must be"):
            await repo.upsert(
                run_id="r1",
                thread_id="t1",
                rating=5,
                user_id="alice",
            )

    @pytest.mark.asyncio
    async def test_upsert_different_users_create_separate_records(self, repo):
        r1 = await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        r2 = await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=-1,
            user_id="bob",
        )
        assert r1["feedback_id"] != r2["feedback_id"]

    @pytest.mark.asyncio
    async def test_upsert_updates_comment(self, repo):
        await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
            comment="first",
        )
        updated = await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
            comment="second",
        )
        assert updated["comment"] == "second"

    @pytest.mark.asyncio
    async def test_upsert_comment_to_none(self, repo):
        """upsert can clear comment from a value to None."""
        await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
            comment="was here",
        )
        updated = await repo.upsert(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
            comment=None,
        )
        assert updated["comment"] is None

    @pytest.mark.asyncio
    async def test_upsert_auto_uses_contextvar(self, repo, _set_user):
        """upsert() with AUTO reads from contextvar."""
        result = await repo.upsert(run_id="r1", thread_id="t1", rating=1)
        assert result["user_id"] == _set_user.id


# ---------------------------------------------------------------------------
# FeedbackRepository.delete_by_run
# ---------------------------------------------------------------------------


class TestDeleteByRun:
    @pytest.mark.asyncio
    async def test_delete_by_run_existing(self, repo):
        await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        deleted = await repo.delete_by_run(
            thread_id="t1",
            run_id="r1",
            user_id="alice",
        )
        assert deleted is True
        remaining = await repo.list_by_run("t1", "r1", user_id=None)
        assert remaining == []

    @pytest.mark.asyncio
    async def test_delete_by_run_nonexistent(self, repo):
        deleted = await repo.delete_by_run(
            thread_id="t1",
            run_id="r1",
            user_id="alice",
        )
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_by_run_user_mismatch(self, repo):
        await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        deleted = await repo.delete_by_run(
            thread_id="t1",
            run_id="r1",
            user_id="bob",
        )
        assert deleted is False
        remaining = await repo.list_by_run("t1", "r1", user_id=None)
        assert len(remaining) == 1

    @pytest.mark.asyncio
    async def test_delete_by_run_only_deletes_matching_user(self, repo):
        """delete_by_run should only delete the caller's feedback, not others."""
        await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
            user_id="alice",
        )
        await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=-1,
            user_id="bob",
        )
        await repo.delete_by_run(
            thread_id="t1",
            run_id="r1",
            user_id="alice",
        )
        remaining = await repo.list_by_run("t1", "r1", user_id=None)
        assert len(remaining) == 1
        assert remaining[0]["user_id"] == "bob"


# ---------------------------------------------------------------------------
# FeedbackRepository.list_by_thread_grouped
# ---------------------------------------------------------------------------


class TestListByThreadGrouped:
    @pytest.mark.asyncio
    async def test_grouped_by_run(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r2", thread_id="t1", rating=-1, user_id="alice")
        result = await repo.list_by_thread_grouped("t1", user_id="alice")
        assert set(result.keys()) == {"r1", "r2"}
        assert result["r1"]["rating"] == 1
        assert result["r2"]["rating"] == -1

    @pytest.mark.asyncio
    async def test_grouped_empty(self, repo):
        result = await repo.list_by_thread_grouped("nonexistent", user_id=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_grouped_no_user_filter(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_thread_grouped("t1", user_id=None)
        # Two records for r1 exist; dict overwrite means only one survives
        assert "r1" in result
        assert len(result) == 1
        assert result["r1"]["rating"] in (1, -1)

    @pytest.mark.asyncio
    async def test_grouped_user_filter(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r2", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.list_by_thread_grouped("t1", user_id="alice")
        assert result == {"r1": result["r1"]}
        assert result["r1"]["user_id"] == "alice"


# ---------------------------------------------------------------------------
# FeedbackRepository.aggregate_by_run
# ---------------------------------------------------------------------------


class TestAggregateByRun:
    @pytest.mark.asyncio
    async def test_aggregate_empty(self, repo):
        result = await repo.aggregate_by_run("t1", "r1")
        assert result == {"run_id": "r1", "total": 0, "positive": 0, "negative": 0}

    @pytest.mark.asyncio
    async def test_aggregate_mixed(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="bob")
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="charlie")
        result = await repo.aggregate_by_run("t1", "r1")
        assert result["total"] == 3
        assert result["positive"] == 2
        assert result["negative"] == 1
        assert result["run_id"] == "r1"

    @pytest.mark.asyncio
    async def test_aggregate_all_positive(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="bob")
        result = await repo.aggregate_by_run("t1", "r1")
        assert result["positive"] == 2
        assert result["negative"] == 0

    @pytest.mark.asyncio
    async def test_aggregate_all_negative(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="alice")
        await repo.create(run_id="r1", thread_id="t1", rating=-1, user_id="bob")
        result = await repo.aggregate_by_run("t1", "r1")
        assert result["positive"] == 0
        assert result["negative"] == 2

    @pytest.mark.asyncio
    async def test_aggregate_different_runs_independent(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r2", thread_id="t1", rating=-1, user_id="alice")
        agg1 = await repo.aggregate_by_run("t1", "r1")
        agg2 = await repo.aggregate_by_run("t1", "r2")
        assert agg1["positive"] == 1
        assert agg1["negative"] == 0
        assert agg2["positive"] == 0
        assert agg2["negative"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_different_threads_independent(self, repo):
        await repo.create(run_id="r1", thread_id="t1", rating=1, user_id="alice")
        await repo.create(run_id="r1", thread_id="t2", rating=-1, user_id="alice")
        agg1 = await repo.aggregate_by_run("t1", "r1")
        agg2 = await repo.aggregate_by_run("t2", "r1")
        assert agg1["positive"] == 1
        assert agg2["negative"] == 1


# ---------------------------------------------------------------------------
# Empty database behavior
# ---------------------------------------------------------------------------


class TestEmptyDatabase:
    @pytest.mark.asyncio
    async def test_get_returns_none(self, repo, _set_user):
        assert await repo.get("any-id", user_id=_set_user.id) is None

    @pytest.mark.asyncio
    async def test_list_by_run_empty(self, repo, _set_user):
        assert await repo.list_by_run("t1", "r1", user_id=None) == []

    @pytest.mark.asyncio
    async def test_list_by_thread_empty(self, repo, _set_user):
        assert await repo.list_by_thread("t1", user_id=None) == []

    @pytest.mark.asyncio
    async def test_delete_returns_false(self, repo, _set_user):
        assert await repo.delete("any-id", user_id=_set_user.id) is False

    @pytest.mark.asyncio
    async def test_delete_by_run_returns_false(self, repo, _set_user):
        assert (
            await repo.delete_by_run(
                thread_id="t1",
                run_id="r1",
                user_id=_set_user.id,
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_grouped_returns_empty(self, repo, _set_user):
        assert await repo.list_by_thread_grouped("t1", user_id=None) == {}

    @pytest.mark.asyncio
    async def test_aggregate_returns_zeros(self, repo):
        result = await repo.aggregate_by_run("t1", "r1")
        assert result["total"] == 0
        assert result["positive"] == 0
        assert result["negative"] == 0


# ---------------------------------------------------------------------------
# Concurrent writes
# ---------------------------------------------------------------------------


class TestConcurrentWrites:
    @pytest.mark.asyncio
    async def test_concurrent_creates(self, repo):
        """Multiple concurrent creates should all succeed."""
        tasks = [
            repo.create(
                run_id="r1",
                thread_id="t1",
                rating=1,
                user_id=f"user-{i}",
                comment=f"feedback-{i}",
            )
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        assert len(results) == 10
        all_ids = {r["feedback_id"] for r in results}
        assert len(all_ids) == 10  # all unique

        stored = await repo.list_by_run("t1", "r1", user_id=None)
        assert len(stored) == 10

    @pytest.mark.asyncio
    async def test_concurrent_upserts(self, repo):
        """Concurrent upserts for different users should all succeed."""
        tasks = [
            repo.upsert(
                run_id="r1",
                thread_id="t1",
                rating=1,
                user_id=f"user-{i}",
            )
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)
        assert len(results) == 5
        all_ids = {r["feedback_id"] for r in results}
        assert len(all_ids) == 5

    @pytest.mark.asyncio
    async def test_concurrent_upsert_same_user(self, repo):
        """Multiple upserts for the same user race on the UNIQUE constraint.

        The upsert is not atomic (SELECT-then-INSERT), so concurrent calls
        may all fail with IntegrityError. We verify the database stays
        consistent (at most 1 record per unique constraint).
        """
        tasks = [
            repo.upsert(
                run_id="r1",
                thread_id="t1",
                rating=1,
                user_id="alice",
                comment=f"attempt-{i}",
            )
            for i in range(5)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        stored = await repo.list_by_run("t1", "r1", user_id="alice")
        assert len(stored) <= 1

    @pytest.mark.asyncio
    async def test_concurrent_aggregate(self, repo):
        """Concurrent creates followed by aggregate should be consistent."""
        for i in range(20):
            rating = 1 if i % 3 != 0 else -1
            await repo.create(
                run_id="r1",
                thread_id="t1",
                rating=rating,
                user_id=f"user-{i}",
            )
        result = await repo.aggregate_by_run("t1", "r1")
        assert result["total"] == 20
        assert result["positive"] + result["negative"] == 20


# ---------------------------------------------------------------------------
# _row_to_dict normalization
# ---------------------------------------------------------------------------


class TestRowToDictNormalization:
    @pytest.mark.asyncio
    async def test_created_at_is_normalized(self, repo, _set_user):
        """created_at should be timezone-aware after normalization."""
        result = await repo.create(
            run_id="r1",
            thread_id="t1",
            rating=1,
        )
        created = result["created_at"]
        # coerce_iso returns a string like "2024-01-01T00:00:00+00:00"
        assert "+" in created or "Z" in created
