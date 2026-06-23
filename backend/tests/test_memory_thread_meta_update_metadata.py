"""Tests for MemoryThreadMetaStore — covering update_metadata success path (lines 124-128).

Lines 124-128 are the success path of update_metadata():
    merged = dict(record.get("metadata") or {})
    merged.update(metadata)
    record["metadata"] = merged
    record["updated_at"] = now_iso()
    await self._store.aput(THREADS_NS, thread_id, record)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ideer.persistence.thread_meta.memory import MemoryThreadMetaStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(key: str, value: dict) -> MagicMock:
    """Create a mock store item with .key and .value attributes."""
    item = MagicMock()
    item.key = key
    item.value = value
    return item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_metadata_success():
    """Lines 124-128: update_metadata merges and writes back."""
    store = AsyncMock()
    record = {
        "thread_id": "t-1",
        "user_id": "u-1",
        "metadata": {"existing_key": "old_value"},
        "updated_at": "2025-01-01T00:00:00Z",
    }
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    await mts.update_metadata("t-1", {"new_key": "new_value", "existing_key": "updated"}, user_id="u-1")

    store.aput.assert_awaited_once()
    call_args = store.aput.call_args
    saved = call_args[0][2]
    assert saved["metadata"]["new_key"] == "new_value"
    assert saved["metadata"]["existing_key"] == "updated"
    assert saved["updated_at"] != "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_update_metadata_no_existing_metadata():
    """Lines 124-128: update_metadata when record has no metadata key (or None)."""
    store = AsyncMock()
    record = {
        "thread_id": "t-1",
        "user_id": "u-1",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    await mts.update_metadata("t-1", {"key": "value"}, user_id="u-1")

    store.aput.assert_awaited_once()
    call_args = store.aput.call_args
    saved = call_args[0][2]
    assert saved["metadata"] == {"key": "value"}


@pytest.mark.asyncio
async def test_update_metadata_record_not_found():
    """update_metadata is a no-op when record is not found."""
    store = AsyncMock()
    store.aget.return_value = None

    mts = MemoryThreadMetaStore(store)
    await mts.update_metadata("t-missing", {"key": "value"}, user_id="u-1")

    store.aput.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_success():
    """Test create method with various parameter combinations."""
    store = AsyncMock()

    mts = MemoryThreadMetaStore(store)
    result = await mts.create(
        "t-1",
        assistant_id="asst-1",
        user_id="u-1",
        display_name="My Thread",
        metadata={"key": "val"},
    )

    store.aput.assert_awaited_once()
    assert result["thread_id"] == "t-1"
    assert result["assistant_id"] == "asst-1"
    assert result["user_id"] == "u-1"
    assert result["display_name"] == "My Thread"
    assert result["status"] == "idle"
    assert result["metadata"] == {"key": "val"}
    assert result["values"] == {}
    assert "created_at" in result
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_create_with_defaults():
    """Test create method with minimal parameters (defaults)."""
    store = AsyncMock()

    mts = MemoryThreadMetaStore(store)
    result = await mts.create("t-1", user_id="u-1")

    assert result["assistant_id"] is None
    assert result["display_name"] is None
    assert result["metadata"] == {}


@pytest.mark.asyncio
async def test_get_success():
    """Test get method returns record when found and user matches."""
    store = AsyncMock()
    record = {"thread_id": "t-1", "user_id": "u-1", "display_name": "test"}
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    result = await mts.get("t-1", user_id="u-1")

    assert result is not None
    assert result["thread_id"] == "t-1"
    assert result["display_name"] == "test"


@pytest.mark.asyncio
async def test_search_returns_items():
    """Test search method converts items to dicts."""
    store = AsyncMock()
    item1 = _make_item(
        "t-1",
        {
            "user_id": "u-1",
            "status": "idle",
            "display_name": "Thread 1",
            "assistant_id": "asst-1",
            "metadata": {},
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
        },
    )
    item2 = _make_item(
        "t-2",
        {
            "user_id": "u-1",
            "status": "active",
            "display_name": "Thread 2",
            "assistant_id": None,
            "metadata": {"k": "v"},
            "created_at": "2025-01-03T00:00:00Z",
            "updated_at": "2025-01-04T00:00:00Z",
        },
    )
    store.asearch.return_value = [item1, item2]

    mts = MemoryThreadMetaStore(store)
    results = await mts.search(user_id="u-1")

    assert len(results) == 2
    assert results[0]["thread_id"] == "t-1"
    assert results[0]["display_name"] == "Thread 1"
    assert results[1]["thread_id"] == "t-2"
    assert results[1]["metadata"] == {"k": "v"}
