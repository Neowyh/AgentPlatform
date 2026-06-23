"""Comprehensive tests for JsonlRunEventStore.

Targets 98%+ line coverage of
backend/packages/harness/ideer/runtime/events/store/jsonl.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ideer.runtime.events.store.jsonl import _SAFE_ID_PATTERN, JsonlRunEventStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_base(tmp_path: Path) -> Path:
    """Provide a fresh temp directory for each test."""
    return tmp_path / "ideer_data"


@pytest.fixture
def store(tmp_base: Path) -> JsonlRunEventStore:
    """Create a store backed by a temp directory."""
    return JsonlRunEventStore(base_dir=tmp_base)


@pytest.fixture
def populated_store(tmp_base: Path) -> JsonlRunEventStore:
    """Create a store pre-populated with sample events across two runs."""
    s = JsonlRunEventStore(base_dir=tmp_base)
    return s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    thread_id: str = "t1",
    run_id: str = "r1",
    event_type: str = "message",
    category: str = "message",
    content: str = "hello",
    seq: int = 1,
) -> dict:
    return {
        "thread_id": thread_id,
        "run_id": run_id,
        "event_type": event_type,
        "category": category,
        "content": content,
        "metadata": {},
        "seq": seq,
        "created_at": "2025-01-01T00:00:00+00:00",
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# ===================================================================
# __init__
# ===================================================================


class TestInit:
    def test_default_base_dir(self):
        store = JsonlRunEventStore()
        assert store._base_dir == Path(".ideer")
        assert store._seq_counters == {}

    def test_custom_base_dir_str(self, tmp_base: Path):
        store = JsonlRunEventStore(base_dir=str(tmp_base))
        assert store._base_dir == tmp_base
        assert store._seq_counters == {}

    def test_custom_base_dir_path(self, tmp_base: Path):
        store = JsonlRunEventStore(base_dir=tmp_base)
        assert store._base_dir == tmp_base

    def test_init_logs_info(self, tmp_base: Path, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="ideer.runtime.events.store.jsonl"):
            JsonlRunEventStore(base_dir=tmp_base)
        assert "JsonlRunEventStore initialized" in caplog.text
        assert "single-process only" in caplog.text


# ===================================================================
# _validate_id (static method)
# ===================================================================


class TestValidateId:
    def test_valid_alphanumeric(self):
        assert JsonlRunEventStore._validate_id("abc123", "id") == "abc123"

    def test_valid_with_dash(self):
        assert JsonlRunEventStore._validate_id("my-id", "id") == "my-id"

    def test_valid_with_underscore(self):
        assert JsonlRunEventStore._validate_id("my_id", "id") == "my_id"

    def test_valid_mixed(self):
        assert JsonlRunEventStore._validate_id("Run-01_v2", "id") == "Run-01_v2"

    def test_invalid_empty(self):
        with pytest.raises(ValueError, match="Invalid test_id"):
            JsonlRunEventStore._validate_id("", "test_id")

    def test_invalid_with_slash(self):
        with pytest.raises(ValueError, match="Invalid test_id"):
            JsonlRunEventStore._validate_id("bad/id", "test_id")

    def test_invalid_with_space(self):
        with pytest.raises(ValueError, match="Invalid test_id"):
            JsonlRunEventStore._validate_id("bad id", "test_id")

    def test_invalid_with_dot(self):
        with pytest.raises(ValueError, match="Invalid test_id"):
            JsonlRunEventStore._validate_id("bad.id", "test_id")

    def test_invalid_with_special_chars(self):
        with pytest.raises(ValueError, match="must be alphanumeric"):
            JsonlRunEventStore._validate_id("id@#$", "test_id")


# ===================================================================
# _SAFE_ID_PATTERN
# ===================================================================


class TestSafeIdPattern:
    def test_pattern_matches_valid(self):
        assert _SAFE_ID_PATTERN.match("abc-123_XYZ")

    def test_pattern_rejects_invalid(self):
        assert not _SAFE_ID_PATTERN.match("abc/123")


# ===================================================================
# _thread_dir / _run_file
# ===================================================================


class TestPathHelpers:
    def test_thread_dir(self, store: JsonlRunEventStore):
        result = store._thread_dir("t1")
        assert result == store._base_dir / "threads" / "t1" / "runs"

    def test_run_file(self, store: JsonlRunEventStore):
        result = store._run_file("t1", "r1")
        assert result == store._base_dir / "threads" / "t1" / "runs" / "r1.jsonl"

    def test_run_file_validates_run_id(self, store: JsonlRunEventStore):
        with pytest.raises(ValueError, match="Invalid run_id"):
            store._run_file("t1", "bad/id")

    def test_thread_dir_validates_thread_id(self, store: JsonlRunEventStore):
        with pytest.raises(ValueError, match="Invalid thread_id"):
            store._thread_dir("bad/id")


# ===================================================================
# _next_seq
# ===================================================================


class TestNextSeq:
    def test_first_call_returns_1(self, store: JsonlRunEventStore):
        assert store._next_seq("t1") == 1

    def test_increments(self, store: JsonlRunEventStore):
        store._next_seq("t1")
        assert store._next_seq("t1") == 2
        assert store._next_seq("t1") == 3

    def test_independent_threads(self, store: JsonlRunEventStore):
        assert store._next_seq("t1") == 1
        assert store._next_seq("t2") == 1
        assert store._next_seq("t1") == 2


# ===================================================================
# _ensure_seq_loaded
# ===================================================================


class TestEnsureSeqLoaded:
    def test_noop_if_already_cached(self, store: JsonlRunEventStore):
        store._seq_counters["t1"] = 42
        store._ensure_seq_loaded("t1")
        assert store._seq_counters["t1"] == 42

    def test_loads_from_existing_files(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        _write_jsonl(run_dir / "r1.jsonl", [_make_event(seq=5)])
        _write_jsonl(run_dir / "r2.jsonl", [_make_event(seq=10)])

        store._ensure_seq_loaded("t1")
        assert store._seq_counters["t1"] == 10

    def test_no_files_sets_zero(self, store: JsonlRunEventStore):
        store._ensure_seq_loaded("nonexistent")
        assert store._seq_counters["nonexistent"] == 0

    def test_skips_malformed_json(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        # Write a file with a valid line and a malformed line
        with open(run_dir / "r1.jsonl", "w") as f:
            f.write(json.dumps(_make_event(seq=7)) + "\n")
            f.write("NOT VALID JSON\n")

        store._ensure_seq_loaded("t1")
        assert store._seq_counters["t1"] == 7

    def test_empty_file(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        (run_dir / "r1.jsonl").write_text("")

        store._ensure_seq_loaded("t1")
        assert store._seq_counters["t1"] == 0

    def test_file_with_only_whitespace(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        (run_dir / "r1.jsonl").write_text("   \n  \n")

        store._ensure_seq_loaded("t1")
        assert store._seq_counters["t1"] == 0


# ===================================================================
# _write_record
# ===================================================================


class TestWriteRecord:
    def test_creates_file_and_dir(self, store: JsonlRunEventStore, tmp_base: Path):
        record = _make_event()
        store._write_record(record)
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        assert path.exists()

    def test_writes_valid_jsonl(self, store: JsonlRunEventStore, tmp_base: Path):
        record = _make_event(content="test content")
        store._write_record(record)
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["content"] == "test content"
        assert parsed["seq"] == 1

    def test_appends_multiple_records(self, store: JsonlRunEventStore, tmp_base: Path):
        store._write_record(_make_event(seq=1))
        store._write_record(_make_event(seq=2))
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_ensure_ascii_false(self, store: JsonlRunEventStore, tmp_base: Path):
        record = _make_event(content="Hello")
        store._write_record(record)
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        text = path.read_text()
        assert "Hello" in text

    def test_default_str_serialization(self, store: JsonlRunEventStore, tmp_base: Path):
        """Ensure non-serializable objects use str() fallback."""
        record = _make_event()
        record["created_at"] = datetime(2025, 1, 1, tzinfo=UTC)
        store._write_record(record)
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        parsed = json.loads(path.read_text().strip())
        assert "2025-01-01" in parsed["created_at"]


# ===================================================================
# _read_thread_events
# ===================================================================


class TestReadThreadEvents:
    def test_returns_empty_for_missing_dir(self, store: JsonlRunEventStore):
        assert store._read_thread_events("nonexistent") == []

    def test_reads_and_sorts_events(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        _write_jsonl(run_dir / "r1.jsonl", [_make_event(seq=3)])
        _write_jsonl(run_dir / "r2.jsonl", [_make_event(seq=1)])

        events = store._read_thread_events("t1")
        assert len(events) == 2
        assert events[0]["seq"] == 1
        assert events[1]["seq"] == 3

    def test_skips_malformed_lines(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        with open(run_dir / "r1.jsonl", "w") as f:
            f.write(json.dumps(_make_event(seq=1)) + "\n")
            f.write("INVALID JSON\n")
            f.write(json.dumps(_make_event(seq=2)) + "\n")

        events = store._read_thread_events("t1")
        assert len(events) == 2

    def test_skips_empty_lines(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        with open(run_dir / "r1.jsonl", "w") as f:
            f.write(json.dumps(_make_event(seq=1)) + "\n")
            f.write("\n")
            f.write(json.dumps(_make_event(seq=2)) + "\n")

        events = store._read_thread_events("t1")
        assert len(events) == 2

    def test_reads_multiple_run_files_sorted(self, store: JsonlRunEventStore, tmp_base: Path):
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        _write_jsonl(run_dir / "a.jsonl", [_make_event(seq=5)])
        _write_jsonl(run_dir / "b.jsonl", [_make_event(seq=2)])

        events = store._read_thread_events("t1")
        assert events[0]["seq"] == 2
        assert events[1]["seq"] == 5


# ===================================================================
# _read_run_events
# ===================================================================


class TestReadRunEvents:
    def test_returns_empty_for_missing_file(self, store: JsonlRunEventStore):
        assert store._read_run_events("t1", "r1") == []

    def test_reads_events_from_file(self, store: JsonlRunEventStore, tmp_base: Path):
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        _write_jsonl(path, [_make_event(seq=2), _make_event(seq=1)])

        events = store._read_run_events("t1", "r1")
        assert len(events) == 2
        assert events[0]["seq"] == 1
        assert events[1]["seq"] == 2

    def test_skips_malformed_lines(self, store: JsonlRunEventStore, tmp_base: Path):
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        path.parent.mkdir(parents=True)
        with open(path, "w") as f:
            f.write("NOT JSON\n")
            f.write(json.dumps(_make_event(seq=1)) + "\n")

        events = store._read_run_events("t1", "r1")
        assert len(events) == 1

    def test_skips_empty_lines(self, store: JsonlRunEventStore, tmp_base: Path):
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        path.parent.mkdir(parents=True)
        with open(path, "w") as f:
            f.write(json.dumps(_make_event(seq=1)) + "\n")
            f.write("\n")
            f.write(json.dumps(_make_event(seq=2)) + "\n")

        events = store._read_run_events("t1", "r1")
        assert len(events) == 2


# ===================================================================
# put (async)
# ===================================================================


class TestPut:
    @pytest.mark.asyncio
    async def test_basic_put(self, store: JsonlRunEventStore):
        record = await store.put(
            thread_id="t1",
            run_id="r1",
            event_type="message",
            category="message",
            content="hello",
        )
        assert record["thread_id"] == "t1"
        assert record["run_id"] == "r1"
        assert record["event_type"] == "message"
        assert record["category"] == "message"
        assert record["content"] == "hello"
        assert record["seq"] == 1
        assert record["metadata"] == {}

    @pytest.mark.asyncio
    async def test_put_auto_increments_seq(self, store: JsonlRunEventStore):
        r1 = await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        r2 = await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        assert r1["seq"] == 1
        assert r2["seq"] == 2

    @pytest.mark.asyncio
    async def test_put_with_metadata(self, store: JsonlRunEventStore):
        record = await store.put(
            thread_id="t1",
            run_id="r1",
            event_type="msg",
            category="message",
            metadata={"key": "value"},
        )
        assert record["metadata"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_put_with_custom_created_at(self, store: JsonlRunEventStore):
        record = await store.put(
            thread_id="t1",
            run_id="r1",
            event_type="msg",
            category="message",
            created_at="2025-06-01T12:00:00Z",
        )
        assert record["created_at"] == "2025-06-01T12:00:00Z"

    @pytest.mark.asyncio
    async def test_put_generates_created_at_when_not_provided(self, store: JsonlRunEventStore):
        record = await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        assert record["created_at"] is not None
        assert "T" in record["created_at"]

    @pytest.mark.asyncio
    async def test_put_default_content_empty(self, store: JsonlRunEventStore):
        record = await store.put(thread_id="t1", run_id="r1", event_type="msg", category="trace")
        assert record["content"] == ""

    @pytest.mark.asyncio
    async def test_put_default_metadata_empty_dict(self, store: JsonlRunEventStore):
        record = await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        assert record["metadata"] == {}

    @pytest.mark.asyncio
    async def test_put_persists_to_file(self, store: JsonlRunEventStore, tmp_base: Path):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message", content="persist")
        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        assert path.exists()
        parsed = json.loads(path.read_text().strip())
        assert parsed["content"] == "persist"


# ===================================================================
# put_batch (async)
# ===================================================================


class TestPutBatch:
    @pytest.mark.asyncio
    async def test_empty_batch(self, store: JsonlRunEventStore):
        result = await store.put_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_writes_all(self, store: JsonlRunEventStore):
        events = [
            {"thread_id": "t1", "run_id": "r1", "event_type": "msg", "category": "message", "content": "a"},
            {"thread_id": "t1", "run_id": "r1", "event_type": "msg", "category": "message", "content": "b"},
            {"thread_id": "t1", "run_id": "r1", "event_type": "msg", "category": "message", "content": "c"},
        ]
        results = await store.put_batch(events)
        assert len(results) == 3
        assert [r["seq"] for r in results] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_batch_returns_complete_records(self, store: JsonlRunEventStore):
        events = [
            {"thread_id": "t1", "run_id": "r1", "event_type": "msg", "category": "message", "content": "x"},
        ]
        results = await store.put_batch(events)
        assert results[0]["content"] == "x"
        assert "created_at" in results[0]


# ===================================================================
# list_messages (async)
# ===================================================================


class TestListMessages:
    async def _populate(self, store: JsonlRunEventStore):
        """Helper: write a mix of message and trace events."""
        for i in range(1, 6):
            await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message", content=f"m{i}")
        await store.put(thread_id="t1", run_id="r1", event_type="trace", category="trace", content="not a message")

    @pytest.mark.asyncio
    async def test_returns_only_messages(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages("t1")
        assert all(m["category"] == "message" for m in msgs)
        assert len(msgs) == 5

    @pytest.mark.asyncio
    async def test_default_limit(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages("t1")
        assert len(msgs) <= 50

    @pytest.mark.asyncio
    async def test_custom_limit(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages("t1", limit=2)
        assert len(msgs) == 2
        # Should be the last 2 (limit applies to tail)
        assert msgs[0]["content"] == "m4"
        assert msgs[1]["content"] == "m5"

    @pytest.mark.asyncio
    async def test_before_seq(self, store: JsonlRunEventStore):
        await self._populate(store)
        # Messages with seq < 4, take last `limit` of those
        msgs = await store.list_messages("t1", before_seq=4)
        assert all(m["seq"] < 4 for m in msgs)
        assert len(msgs) == 3  # seq 1,2,3

    @pytest.mark.asyncio
    async def test_before_seq_with_limit(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages("t1", before_seq=5, limit=2)
        assert len(msgs) == 2
        # Should be last 2 of seq < 5 -> seq 3,4
        assert msgs[0]["seq"] == 3
        assert msgs[1]["seq"] == 4

    @pytest.mark.asyncio
    async def test_after_seq(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages("t1", after_seq=2)
        assert all(m["seq"] > 2 for m in msgs)
        assert len(msgs) == 3  # seq 3,4,5

    @pytest.mark.asyncio
    async def test_after_seq_with_limit(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages("t1", after_seq=2, limit=1)
        assert len(msgs) == 1
        assert msgs[0]["seq"] == 3

    @pytest.mark.asyncio
    async def test_empty_thread(self, store: JsonlRunEventStore):
        msgs = await store.list_messages("nonexistent")
        assert msgs == []

    @pytest.mark.asyncio
    async def test_limit_larger_than_available(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message", content="only")
        msgs = await store.list_messages("t1", limit=100)
        assert len(msgs) == 1


# ===================================================================
# list_events (async)
# ===================================================================


class TestListEvents:
    async def _populate(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="start", category="lifecycle")
        await store.put(thread_id="t1", run_id="r1", event_type="message", category="message")
        await store.put(thread_id="t1", run_id="r1", event_type="end", category="lifecycle")

    @pytest.mark.asyncio
    async def test_returns_all_events(self, store: JsonlRunEventStore):
        await self._populate(store)
        events = await store.list_events("t1", "r1")
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_filter_by_event_types(self, store: JsonlRunEventStore):
        await self._populate(store)
        events = await store.list_events("t1", "r1", event_types=["start", "end"])
        assert len(events) == 2
        assert all(e["event_type"] in ("start", "end") for e in events)

    @pytest.mark.asyncio
    async def test_filter_no_match(self, store: JsonlRunEventStore):
        await self._populate(store)
        events = await store.list_events("t1", "r1", event_types=["nonexistent"])
        assert events == []

    @pytest.mark.asyncio
    async def test_limit(self, store: JsonlRunEventStore):
        await self._populate(store)
        events = await store.list_events("t1", "r1", limit=2)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_missing_run(self, store: JsonlRunEventStore):
        events = await store.list_events("t1", "nonexistent")
        assert events == []

    @pytest.mark.asyncio
    async def test_event_types_none_returns_all(self, store: JsonlRunEventStore):
        await self._populate(store)
        events = await store.list_events("t1", "r1", event_types=None)
        assert len(events) == 3


# ===================================================================
# list_messages_by_run (async)
# ===================================================================


class TestListMessagesByRun:
    async def _populate(self, store: JsonlRunEventStore):
        for i in range(1, 6):
            await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message", content=f"m{i}")
        await store.put(thread_id="t1", run_id="r1", event_type="trace", category="trace", content="skip")

    @pytest.mark.asyncio
    async def test_returns_only_messages(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1")
        assert len(msgs) == 5
        assert all(m["category"] == "message" for m in msgs)

    @pytest.mark.asyncio
    async def test_before_seq(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1", before_seq=3)
        assert all(m["seq"] < 3 for m in msgs)
        assert len(msgs) == 2

    @pytest.mark.asyncio
    async def test_after_seq(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1", after_seq=3)
        assert all(m["seq"] > 3 for m in msgs)
        assert len(msgs) == 2  # seq 4,5

    @pytest.mark.asyncio
    async def test_after_seq_with_limit(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1", after_seq=2, limit=1)
        assert len(msgs) == 1
        assert msgs[0]["seq"] == 3

    @pytest.mark.asyncio
    async def test_before_and_after_seq(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1", before_seq=5, after_seq=1)
        assert all(1 < m["seq"] < 5 for m in msgs)
        assert len(msgs) == 3  # seq 2,3,4

    @pytest.mark.asyncio
    async def test_after_seq_takes_head(self, store: JsonlRunEventStore):
        """When after_seq is set, we take the first `limit` items (head)."""
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1", after_seq=1, limit=2)
        assert len(msgs) == 2
        assert msgs[0]["seq"] == 2
        assert msgs[1]["seq"] == 3

    @pytest.mark.asyncio
    async def test_no_filters_returns_tail_or_all(self, store: JsonlRunEventStore):
        """Without after_seq, returns last `limit` items (tail) or all if under limit."""
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1")
        assert len(msgs) == 5  # all fit in default limit=50

    @pytest.mark.asyncio
    async def test_no_filters_with_small_limit(self, store: JsonlRunEventStore):
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1", limit=2)
        assert len(msgs) == 2
        # Should be last 2: seq 4,5
        assert msgs[0]["seq"] == 4
        assert msgs[1]["seq"] == 5

    @pytest.mark.asyncio
    async def test_empty_run(self, store: JsonlRunEventStore):
        msgs = await store.list_messages_by_run("t1", "nonexistent")
        assert msgs == []

    @pytest.mark.asyncio
    async def test_after_seq_returns_all_if_under_limit(self, store: JsonlRunEventStore):
        """When after_seq is set, returns first `limit` items; check boundary."""
        await self._populate(store)
        msgs = await store.list_messages_by_run("t1", "r1", after_seq=0, limit=100)
        assert len(msgs) == 5


# ===================================================================
# count_messages (async)
# ===================================================================


class TestCountMessages:
    @pytest.mark.asyncio
    async def test_count_zero(self, store: JsonlRunEventStore):
        count = await store.count_messages("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_only_messages(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.put(thread_id="t1", run_id="r1", event_type="trace", category="trace")
        count = await store.count_messages("t1")
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_across_runs(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.put(thread_id="t1", run_id="r2", event_type="msg", category="message")
        count = await store.count_messages("t1")
        assert count == 2


# ===================================================================
# delete_by_thread (async)
# ===================================================================


class TestDeleteByThread:
    @pytest.mark.asyncio
    async def test_delete_existing_thread(self, store: JsonlRunEventStore, tmp_base: Path):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.put(thread_id="t1", run_id="r2", event_type="msg", category="message")

        thread_dir = tmp_base / "threads" / "t1" / "runs"
        assert thread_dir.exists()

        count = await store.delete_by_thread("t1")
        assert count == 2
        assert not thread_dir.exists() or not any(thread_dir.glob("*.jsonl"))

    @pytest.mark.asyncio
    async def test_delete_clears_seq_counter(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        assert "t1" in store._seq_counters
        await store.delete_by_thread("t1")
        assert "t1" not in store._seq_counters

    @pytest.mark.asyncio
    async def test_delete_nonexistent_thread(self, store: JsonlRunEventStore):
        count = await store.delete_by_thread("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_only_affects_target_thread(self, store: JsonlRunEventStore, tmp_base: Path):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.put(thread_id="t2", run_id="r1", event_type="msg", category="message")

        await store.delete_by_thread("t1")

        t2_dir = tmp_base / "threads" / "t2" / "runs"
        assert t2_dir.exists()
        assert len(list(t2_dir.glob("*.jsonl"))) == 1


# ===================================================================
# delete_by_run (async)
# ===================================================================


class TestDeleteByRun:
    @pytest.mark.asyncio
    async def test_delete_existing_run(self, store: JsonlRunEventStore, tmp_base: Path):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")

        count = await store.delete_by_run("t1", "r1")
        assert count == 2

        path = tmp_base / "threads" / "t1" / "runs" / "r1.jsonl"
        assert not path.exists()

    @pytest.mark.asyncio
    async def test_delete_preserves_other_runs(self, store: JsonlRunEventStore, tmp_base: Path):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.put(thread_id="t1", run_id="r2", event_type="msg", category="message")

        count = await store.delete_by_run("t1", "r1")
        assert count == 1

        r2_path = tmp_base / "threads" / "t1" / "runs" / "r2.jsonl"
        assert r2_path.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_run(self, store: JsonlRunEventStore):
        count = await store.delete_by_run("t1", "nonexistent")
        assert count == 0


# ===================================================================
# Integration / round-trip tests
# ===================================================================


class TestIntegration:
    @pytest.mark.asyncio
    async def test_put_then_list_messages_roundtrip(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message", content="hi")
        msgs = await store.list_messages("t1")
        assert len(msgs) == 1
        assert msgs[0]["content"] == "hi"

    @pytest.mark.asyncio
    async def test_put_then_list_events_roundtrip(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="start", category="lifecycle")
        events = await store.list_events("t1", "r1")
        assert len(events) == 1
        assert events[0]["event_type"] == "start"

    @pytest.mark.asyncio
    async def test_put_then_count(self, store: JsonlRunEventStore):
        for i in range(10):
            await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        assert await store.count_messages("t1") == 10

    @pytest.mark.asyncio
    async def test_put_then_delete_then_verify(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.delete_by_run("t1", "r1")
        assert await store.count_messages("t1") == 0

    @pytest.mark.asyncio
    async def test_seq_across_multiple_runs(self, store: JsonlRunEventStore):
        """Seq should be global per thread, not per run."""
        r1 = await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        r2 = await store.put(thread_id="t1", run_id="r2", event_type="msg", category="message")
        assert r1["seq"] == 1
        assert r2["seq"] == 2

    @pytest.mark.asyncio
    async def test_seq_loaded_from_disk_on_late_init(self, tmp_base: Path):
        """If the store is created after files exist, seq should load correctly."""
        # Simulate existing data
        run_dir = tmp_base / "threads" / "t1" / "runs"
        run_dir.mkdir(parents=True)
        _write_jsonl(run_dir / "r1.jsonl", [_make_event(seq=7)])

        # New store instance should pick up seq=7
        store = JsonlRunEventStore(base_dir=tmp_base)
        record = await store.put(thread_id="t1", run_id="r2", event_type="msg", category="message")
        assert record["seq"] == 8

    @pytest.mark.asyncio
    async def test_delete_thread_then_put_reuses_seq_space(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message")
        await store.delete_by_thread("t1")
        # After delete, seq counter is cleared; new put starts fresh
        record = await store.put(thread_id="t1", run_id="r2", event_type="msg", category="message")
        assert record["seq"] == 1

    @pytest.mark.asyncio
    async def test_list_messages_by_run_filters_correctly(self, store: JsonlRunEventStore):
        await store.put(thread_id="t1", run_id="r1", event_type="msg", category="message", content="r1-msg")
        await store.put(thread_id="t1", run_id="r2", event_type="msg", category="message", content="r2-msg")

        r1_msgs = await store.list_messages_by_run("t1", "r1")
        assert len(r1_msgs) == 1
        assert r1_msgs[0]["content"] == "r1-msg"

        r2_msgs = await store.list_messages_by_run("t1", "r2")
        assert len(r2_msgs) == 1
        assert r2_msgs[0]["content"] == "r2-msg"
