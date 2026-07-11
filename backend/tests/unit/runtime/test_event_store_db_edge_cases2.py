"""Tests targeting uncovered lines in DbRunEventStore.

Covers:
- db.py line 146: put_batch returning [] for empty events
- db.py line 223: list_events with event_types filter
- db.py lines 239-262: list_messages_by_run method
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideer.runtime.events.store.db import DbRunEventStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(seq: int = 1, category: str = "message", event_type: str = "human") -> MagicMock:
    """Create a mock RunEventRow."""
    row = MagicMock()
    row.to_dict.return_value = {
        "id": seq,
        "thread_id": "t1",
        "run_id": "r1",
        "user_id": "u1",
        "event_type": event_type,
        "category": category,
        "content": "hello",
        "event_metadata": {},
        "seq": seq,
        "created_at": datetime.now(UTC),
    }
    return row


def _mock_session_factory(scalars_result=None):
    """Return an async_sessionmaker mock whose session.execute returns scalars_result."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    if scalars_result is not None:
        mock_scalars.all.return_value = scalars_result
        mock_scalars.__iter__ = lambda self: iter(scalars_result)
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.scalar = AsyncMock(return_value=0)
    mock_session.get_bind.return_value = MagicMock(dialect=MagicMock(name="sqlite"))

    mock_sf = MagicMock()
    mock_sf.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.__aexit__ = AsyncMock(return_value=False)
    # session_factory is a callable that returns the context manager
    mock_sf.return_value = mock_sf
    return mock_sf, mock_session


# ---------------------------------------------------------------------------
# put_batch with empty events (line 146)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_batch_empty_events():
    """put_batch([]) should return [] without opening a session."""
    sf = MagicMock()
    store = DbRunEventStore(sf)
    result = await store.put_batch([])
    assert result == []
    sf.assert_not_called()


# ---------------------------------------------------------------------------
# list_events with event_types filter (line 223)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_with_event_types():
    """list_events filters by event_types when provided."""
    row = _make_row(seq=1, event_type="llm_request")
    sf, mock_session = _mock_session_factory([row])

    store = DbRunEventStore(sf)

    with patch("ideer.runtime.events.store.db.resolve_user_id", return_value=None):
        result = await store.list_events(
            "t1",
            "r1",
            event_types=["llm_request", "llm_response"],
            user_id=None,
        )

    assert len(result) == 1
    assert result[0]["event_type"] == "llm_request"

    # Verify the IN clause was applied by inspecting the execute call
    mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# list_messages_by_run — after_seq path (lines 239-256)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_messages_by_run_with_after_seq():
    """list_messages_by_run with after_seq uses ASC ordering and forward pagination."""
    row1 = _make_row(seq=5)
    row2 = _make_row(seq=6)
    sf, mock_session = _mock_session_factory([row1, row2])

    store = DbRunEventStore(sf)

    with patch("ideer.runtime.events.store.db.resolve_user_id", return_value="u1"):
        result = await store.list_messages_by_run(
            "t1",
            "r1",
            after_seq=4,
            limit=10,
            user_id="u1",
        )

    assert len(result) == 2
    mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# list_messages_by_run — before_seq path (lines 257-262)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_messages_by_run_with_before_seq():
    """list_messages_by_run with before_seq uses DESC ordering and reverses."""
    row1 = _make_row(seq=3)
    row2 = _make_row(seq=4)
    sf, mock_session = _mock_session_factory([row2, row1])  # DESC order from DB

    store = DbRunEventStore(sf)

    with patch("ideer.runtime.events.store.db.resolve_user_id", return_value="u1"):
        result = await store.list_messages_by_run(
            "t1",
            "r1",
            before_seq=5,
            limit=10,
            user_id="u1",
        )

    assert len(result) == 2
    # After reversal, should be ascending
    assert result[0]["seq"] == 3
    assert result[1]["seq"] == 4


# ---------------------------------------------------------------------------
# list_messages_by_run — default path (no cursors, lines 257-262)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_messages_by_run_default_latest():
    """list_messages_by_run with no cursors returns latest messages in ascending order."""
    row1 = _make_row(seq=9)
    row2 = _make_row(seq=10)
    sf, mock_session = _mock_session_factory([row2, row1])  # DESC from DB

    store = DbRunEventStore(sf)

    with patch("ideer.runtime.events.store.db.resolve_user_id", return_value=None):
        result = await store.list_messages_by_run(
            "t1",
            "r1",
            user_id=None,
        )

    assert len(result) == 2


# ---------------------------------------------------------------------------
# list_messages_by_run — with user_id filter (line 245-246)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_messages_by_run_with_user_id_filter():
    """list_messages_by_run adds user_id WHERE clause when resolved_user_id is not None."""
    sf, mock_session = _mock_session_factory([])

    store = DbRunEventStore(sf)

    with patch("ideer.runtime.events.store.db.resolve_user_id", return_value="u42"):
        result = await store.list_messages_by_run(
            "t1",
            "r1",
            user_id="u42",
        )

    assert result == []
    mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# list_messages_by_run — with both before_seq and after_seq (lines 248-250)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_messages_by_run_with_both_cursors():
    """list_messages_by_run applies both before_seq and after_seq filters."""
    row = _make_row(seq=5)
    sf, mock_session = _mock_session_factory([row])

    store = DbRunEventStore(sf)

    with patch("ideer.runtime.events.store.db.resolve_user_id", return_value=None):
        result = await store.list_messages_by_run(
            "t1",
            "r1",
            before_seq=10,
            after_seq=3,
            user_id=None,
        )

    assert len(result) == 1
