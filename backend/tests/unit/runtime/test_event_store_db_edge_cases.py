"""Additional tests for events/store/db.py — coverage gaps."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from ideer.runtime.events.store.db import DbRunEventStore

# ---------------------------------------------------------------------------
# _truncate_trace
# ---------------------------------------------------------------------------


class TestTruncateTrace:
    def test_non_trace_category_not_truncated(self):
        store = DbRunEventStore.__new__(DbRunEventStore)
        store._max_trace_content = 10
        content = "x" * 100
        result, meta = store._truncate_trace("message", content, None)
        assert result == content
        assert meta == {}

    def test_trace_content_under_limit(self):
        store = DbRunEventStore.__new__(DbRunEventStore)
        store._max_trace_content = 100
        content = "short"
        result, meta = store._truncate_trace("trace", content, None)
        assert result == "short"

    def test_trace_content_over_limit_truncated(self):
        store = DbRunEventStore.__new__(DbRunEventStore)
        store._max_trace_content = 10
        content = "x" * 100
        result, meta = store._truncate_trace("trace", content, None)
        assert len(result) == 10
        assert meta.get("content_truncated") is True
        assert meta["original_byte_length"] == 100

    def test_trace_dict_content_serialized_and_truncated(self):
        store = DbRunEventStore.__new__(DbRunEventStore)
        store._max_trace_content = 20
        content = {"key": "x" * 100}
        result, meta = store._truncate_trace("trace", content, None)
        assert isinstance(result, str)
        assert len(result) <= 20

    def test_trace_with_existing_metadata(self):
        store = DbRunEventStore.__new__(DbRunEventStore)
        store._max_trace_content = 1000
        result, meta = store._truncate_trace("trace", "short", {"existing": True})
        assert meta["existing"] is True

    def test_trace_content_exact_limit(self):
        store = DbRunEventStore.__new__(DbRunEventStore)
        store._max_trace_content = 10
        content = "x" * 10
        result, meta = store._truncate_trace("trace", content, None)
        assert result == content
        assert meta.get("content_truncated") is not True


# ---------------------------------------------------------------------------
# _content_to_db
# ---------------------------------------------------------------------------


class TestContentToDb:
    def test_string_content(self):
        db_content, meta = DbRunEventStore._content_to_db("hello", None)
        assert db_content == "hello"
        assert meta == {}

    def test_dict_content(self):
        db_content, meta = DbRunEventStore._content_to_db({"key": "val"}, None)
        parsed = json.loads(db_content)
        assert parsed == {"key": "val"}
        assert meta["content_is_json"] is True
        assert meta["content_is_dict"] is True

    def test_list_content(self):
        db_content, meta = DbRunEventStore._content_to_db([1, 2, 3], None)
        parsed = json.loads(db_content)
        assert parsed == [1, 2, 3]
        assert meta["content_is_json"] is True
        assert "content_is_dict" not in meta

    def test_with_existing_metadata(self):
        db_content, meta = DbRunEventStore._content_to_db({"a": 1}, {"extra": True})
        assert meta["extra"] is True
        assert meta["content_is_json"] is True

    def test_none_metadata(self):
        db_content, meta = DbRunEventStore._content_to_db("text", None)
        assert meta == {}


# ---------------------------------------------------------------------------
# _row_to_dict
# ---------------------------------------------------------------------------


class TestRowToDict:
    def test_basic_row(self):
        row = MagicMock()
        row.to_dict.return_value = {
            "id": 1,
            "thread_id": "t1",
            "run_id": "r1",
            "event_type": "test",
            "category": "trace",
            "content": "hello",
            "event_metadata": {"key": "val"},
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "seq": 1,
        }
        result = DbRunEventStore._row_to_dict(row)
        assert "id" not in result
        assert result["metadata"] == {"key": "val"}
        assert result["content"] == "hello"

    def test_json_content_with_metadata_flag(self):
        row = MagicMock()
        row.to_dict.return_value = {
            "id": 1,
            "thread_id": "t1",
            "run_id": "r1",
            "event_type": "test",
            "category": "message",
            "content": '{"key": "val"}',
            "event_metadata": {"content_is_json": True, "content_is_dict": True},
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "seq": 1,
        }
        result = DbRunEventStore._row_to_dict(row)
        assert result["content"] == {"key": "val"}

    def test_json_content_parse_failure_keeps_raw(self):
        row = MagicMock()
        row.to_dict.return_value = {
            "id": 1,
            "thread_id": "t1",
            "run_id": "r1",
            "event_type": "test",
            "category": "message",
            "content": "not valid json {",
            "event_metadata": {"content_is_json": True},
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "seq": 1,
        }
        result = DbRunEventStore._row_to_dict(row)
        assert result["content"] == "not valid json {"


# ---------------------------------------------------------------------------
# _user_id_from_context
# ---------------------------------------------------------------------------


class TestUserIdFromContext:
    def test_no_user_returns_none(self):
        with patch("ideer.runtime.events.store.db.get_current_user", return_value=None):
            assert DbRunEventStore._user_id_from_context() is None

    def test_with_user_returns_str_id(self):
        user = MagicMock()
        user.id = "test-uuid-123"
        with patch("ideer.runtime.events.store.db.get_current_user", return_value=user):
            assert DbRunEventStore._user_id_from_context() == "test-uuid-123"


# ---------------------------------------------------------------------------
# _max_seq_for_thread — non-postgres path
# ---------------------------------------------------------------------------


class TestMaxSeqForThread:
    @pytest.mark.anyio
    async def test_non_postgres_uses_for_update(self):
        class FakeBind:
            dialect = MagicMock()
            dialect.name = "sqlite"

        class FakeSession:
            def get_bind(self):
                return FakeBind()

            async def scalar(self, stmt):
                return 42

        session = FakeSession()
        max_seq = await DbRunEventStore._max_seq_for_thread(session, "thread-1")
        assert max_seq == 42

    @pytest.mark.anyio
    async def test_unknown_dialect_uses_for_update(self):
        class FakeBind:
            dialect = MagicMock()
            dialect.name = "mysql"

        class FakeSession:
            def get_bind(self):
                return FakeBind()

            async def scalar(self, stmt):
                return 10

        session = FakeSession()
        max_seq = await DbRunEventStore._max_seq_for_thread(session, "thread-1")
        assert max_seq == 10

    @pytest.mark.anyio
    async def test_no_bind_uses_for_update(self):
        class FakeSession:
            def get_bind(self):
                return None

            async def scalar(self, stmt):
                return 5

        session = FakeSession()
        max_seq = await DbRunEventStore._max_seq_for_thread(session, "thread-1")
        assert max_seq == 5
