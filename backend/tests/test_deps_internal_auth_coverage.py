"""Tests for app.gateway.deps covering lines 59-61, 66-67, 298.

Lines 59-61: Exception during run_manager.list_by_thread (logged, continues)
Lines 66-67: Exception during thread_store.update_status (logged, continues)
Line 298: User not found in get_current_user dependency
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMarkRecoveredThreadAsError:
    """Cover the except branches in _mark_latest_recovered_threads_error."""

    @pytest.mark.asyncio
    async def test_list_by_thread_raises(self, caplog):
        """Lines 59-61: exception during list_by_thread is logged and continues."""
        from app.gateway.deps import _mark_latest_recovered_threads_error

        run_manager = MagicMock()
        run_manager.list_by_thread = AsyncMock(side_effect=RuntimeError("db down"))

        record = MagicMock()
        record.thread_id = "thread-1"
        record.run_id = "run-1"

        thread_store = MagicMock()
        thread_store.update_status = AsyncMock()

        await _mark_latest_recovered_threads_error(run_manager, thread_store, [record])
        assert "Failed to find latest run" in caplog.text
        thread_store.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_status_raises(self, caplog):
        """Lines 66-67: exception during update_status is logged."""
        from app.gateway.deps import _mark_latest_recovered_threads_error

        record = MagicMock()
        record.thread_id = "thread-1"
        record.run_id = "run-1"

        latest_run = MagicMock()
        latest_run.run_id = "run-1"

        run_manager = MagicMock()
        run_manager.list_by_thread = AsyncMock(return_value=[latest_run])

        thread_store = MagicMock()
        thread_store.update_status = AsyncMock(side_effect=RuntimeError("write fail"))

        await _mark_latest_recovered_threads_error(run_manager, thread_store, [record])
        assert "Failed to mark thread" in caplog.text
