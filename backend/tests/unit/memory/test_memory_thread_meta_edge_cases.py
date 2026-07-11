"""Tests for MemoryThreadMetaStore — covering previously uncovered lines.

Targeted uncovered lines:
  - Line 35: _get_owned_record when item is None
  - Line 83: search with status filter
  - Lines 96-102: check_access when item exists but user_id mismatch
  - Lines 108-110: update_display_name success path
  - Lines 116-118: update_status success path
  - Line 134: delete success path
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
async def test_get_owned_record_item_is_none():
    """Line 35: _get_owned_record returns None when store.aget returns None."""
    store = AsyncMock()
    store.aget.return_value = None

    mts = MemoryThreadMetaStore(store)
    # user_id=None means resolved=None, which skips ownership check
    result = await mts._get_owned_record("t-1", user_id=None, method_name="test")

    assert result is None
    store.aget.assert_awaited_once_with(("threads",), "t-1")


@pytest.mark.asyncio
async def test_search_with_status_filter():
    """Line 83: search sets filter_dict["status"] when status is provided."""
    store = AsyncMock()
    store.asearch.return_value = []

    mts = MemoryThreadMetaStore(store)
    result = await mts.search(status="active", user_id="u-1")

    assert result == []
    store.asearch.assert_awaited_once_with(
        ("threads",),
        filter={"status": "active", "user_id": "u-1"},
        limit=100,
        offset=0,
    )


@pytest.mark.asyncio
async def test_check_access_item_exists_user_id_mismatch():
    """Lines 96-102: check_access returns False when record user_id != caller user_id."""
    store = AsyncMock()
    item = _make_item("t-1", {"user_id": "owner-123"})
    store.aget.return_value = item

    mts = MemoryThreadMetaStore(store)
    result = await mts.check_access("t-1", user_id="other-user")

    assert result is False


@pytest.mark.asyncio
async def test_check_access_item_exists_user_id_matches():
    """check_access returns True when record user_id matches caller user_id."""
    store = AsyncMock()
    item = _make_item("t-1", {"user_id": "owner-123"})
    store.aget.return_value = item

    mts = MemoryThreadMetaStore(store)
    result = await mts.check_access("t-1", user_id="owner-123")

    assert result is True


@pytest.mark.asyncio
async def test_check_access_item_exists_record_user_id_is_none():
    """Lines 100-101: check_access returns True when record has no user_id."""
    store = AsyncMock()
    item = _make_item("t-1", {"user_id": None})
    store.aget.return_value = item

    mts = MemoryThreadMetaStore(store)
    result = await mts.check_access("t-1", user_id="any-user")

    assert result is True


@pytest.mark.asyncio
async def test_check_access_item_not_found_require_existing_false():
    """Lines 97-98: check_access returns True when item is None and require_existing=False."""
    store = AsyncMock()
    store.aget.return_value = None

    mts = MemoryThreadMetaStore(store)
    result = await mts.check_access("t-missing", user_id="u-1", require_existing=False)

    assert result is True


@pytest.mark.asyncio
async def test_check_access_item_not_found_require_existing_true():
    """Lines 97-98: check_access returns False when item is None and require_existing=True."""
    store = AsyncMock()
    store.aget.return_value = None

    mts = MemoryThreadMetaStore(store)
    result = await mts.check_access("t-missing", user_id="u-1", require_existing=True)

    assert result is False


@pytest.mark.asyncio
async def test_update_display_name_success():
    """Lines 108-110: update_display_name writes the new name and updated_at."""
    store = AsyncMock()
    record = {
        "thread_id": "t-1",
        "user_id": "u-1",
        "display_name": "old name",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    await mts.update_display_name("t-1", "new name", user_id="u-1")

    store.aput.assert_awaited_once()
    call_args = store.aput.call_args
    saved = call_args[0][2]  # third positional arg is the record dict
    assert saved["display_name"] == "new name"
    assert saved["updated_at"] != "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_update_status_success():
    """Lines 116-118: update_status writes the new status and updated_at."""
    store = AsyncMock()
    record = {
        "thread_id": "t-1",
        "user_id": "u-1",
        "status": "idle",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    await mts.update_status("t-1", "running", user_id="u-1")

    store.aput.assert_awaited_once()
    call_args = store.aput.call_args
    saved = call_args[0][2]
    assert saved["status"] == "running"
    assert saved["updated_at"] != "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_delete_success():
    """Line 134: delete calls store.adelete when record is found."""
    store = AsyncMock()
    record = {"thread_id": "t-1", "user_id": "u-1"}
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    await mts.delete("t-1", user_id="u-1")

    store.adelete.assert_awaited_once_with(("threads",), "t-1")


@pytest.mark.asyncio
async def test_get_owned_record_user_id_mismatch():
    """Lines 37-38: _get_owned_record returns None when user_id doesn't match."""
    store = AsyncMock()
    record = {"thread_id": "t-1", "user_id": "owner-123"}
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    result = await mts._get_owned_record("t-1", user_id="other-user", method_name="test")

    assert result is None


@pytest.mark.asyncio
async def test_get_owned_record_returns_mutable_copy():
    """Lines 36, 39: _get_owned_record returns a mutable dict copy of item.value."""
    store = AsyncMock()
    record = {"thread_id": "t-1", "user_id": "u-1", "display_name": "hi"}
    store.aget.return_value = _make_item("t-1", record)

    mts = MemoryThreadMetaStore(store)
    result = await mts._get_owned_record("t-1", user_id="u-1", method_name="test")

    assert result == record
    # Verify it's a mutable copy, not the original object
    result["display_name"] = "mutated"
    assert store.aget.return_value.value["display_name"] == "hi"


@pytest.mark.asyncio
async def test_search_with_metadata_and_status_filters():
    """Lines 80-83: search applies both metadata and status filters."""
    store = AsyncMock()
    store.asearch.return_value = []

    mts = MemoryThreadMetaStore(store)
    result = await mts.search(metadata={"category": "work"}, status="active", user_id="u-1")

    assert result == []
    store.asearch.assert_awaited_once_with(
        ("threads",),
        filter={"category": "work", "status": "active", "user_id": "u-1"},
        limit=100,
        offset=0,
    )


@pytest.mark.asyncio
async def test_search_no_filters_user_id_none():
    """search passes filter=None when no filters apply and user_id is None."""
    store = AsyncMock()
    store.asearch.return_value = []

    mts = MemoryThreadMetaStore(store)
    result = await mts.search(user_id=None)

    assert result == []
    store.asearch.assert_awaited_once_with(
        ("threads",),
        filter=None,
        limit=100,
        offset=0,
    )


@pytest.mark.asyncio
async def test_delete_record_not_found():
    """delete is a no-op when record is not found."""
    store = AsyncMock()
    store.aget.return_value = None

    mts = MemoryThreadMetaStore(store)
    await mts.delete("t-missing", user_id="u-1")

    store.adelete.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_display_name_record_not_found():
    """update_display_name is a no-op when record is not found."""
    store = AsyncMock()
    store.aget.return_value = None

    mts = MemoryThreadMetaStore(store)
    await mts.update_display_name("t-missing", "new name", user_id="u-1")

    store.aput.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_status_record_not_found():
    """update_status is a no-op when record is not found."""
    store = AsyncMock()
    store.aget.return_value = None

    mts = MemoryThreadMetaStore(store)
    await mts.update_status("t-missing", "done", user_id="u-1")

    store.aput.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_with_limit_and_offset():
    """search passes limit and offset through to store."""
    store = AsyncMock()
    item1 = _make_item("t-1", {"user_id": "u-1", "status": "idle"})
    store.asearch.return_value = [item1]

    mts = MemoryThreadMetaStore(store)
    result = await mts.search(limit=10, offset=5, user_id="u-1")

    assert len(result) == 1
    store.asearch.assert_awaited_once_with(
        ("threads",),
        filter={"user_id": "u-1"},
        limit=10,
        offset=5,
    )


@pytest.mark.asyncio
async def test_item_to_dict():
    """_item_to_dict converts a store item to the expected dict format."""
    item = _make_item(
        "t-1",
        {
            "assistant_id": "asst-1",
            "user_id": "u-1",
            "display_name": "test thread",
            "status": "idle",
            "metadata": {"key": "val"},
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
        },
    )

    result = MemoryThreadMetaStore._item_to_dict(item)

    assert result["thread_id"] == "t-1"
    assert result["assistant_id"] == "asst-1"
    assert result["user_id"] == "u-1"
    assert result["display_name"] == "test thread"
    assert result["status"] == "idle"
    assert result["metadata"] == {"key": "val"}
    assert result["created_at"] == "2025-01-01T00:00:00Z"
    assert result["updated_at"] == "2025-01-02T00:00:00Z"


@pytest.mark.asyncio
async def test_item_to_dict_defaults():
    """_item_to_dict handles missing optional fields with defaults."""
    item = _make_item("t-2", {})

    result = MemoryThreadMetaStore._item_to_dict(item)

    assert result["thread_id"] == "t-2"
    assert result["status"] == "idle"
    assert result["metadata"] == {}
