"""Extra coverage tests for queue.py missed lines.

Targets: 75, 102, 148-151, 178, 204-206, 223-224, 242-243, 256-257, 272-275, 284-287
"""

from unittest.mock import MagicMock, patch

from ideer.agents.memory.queue import (
    MemoryUpdateQueue,
    get_memory_queue,
    reset_memory_queue,
)
from ideer.config.memory_config import MemoryConfig


def _memory_config(**overrides):
    config = MemoryConfig()
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


# --- Line 75: add() with disabled config ---


def test_add_returns_early_when_disabled():
    """Line 75: add() does nothing when memory is disabled."""
    queue = MemoryUpdateQueue()
    with patch("ideer.agents.memory.queue.get_memory_config", return_value=_memory_config(enabled=False)):
        queue.add(thread_id="t1", messages=["msg"])
    assert queue.pending_count == 0


# --- Line 102: add_nowait() with disabled config ---


def test_add_nowait_returns_early_when_disabled():
    """Line 102: add_nowait() does nothing when memory is disabled."""
    queue = MemoryUpdateQueue()
    with patch("ideer.agents.memory.queue.get_memory_config", return_value=_memory_config(enabled=False)):
        queue.add_nowait(thread_id="t1", messages=["msg"])
    assert queue.pending_count == 0


# --- Line 178: _process_queue with empty queue ---


def test_process_queue_returns_early_when_empty():
    """Line 178: _process_queue returns early when queue is empty."""
    queue = MemoryUpdateQueue()
    queue._queue = []
    # Should not raise
    queue._process_queue()


# --- Lines 204-206: _process_queue with exception during update ---


def test_process_queue_continues_on_updater_exception():
    """Lines 204-206: _process_queue continues processing after updater exception."""
    from ideer.agents.memory.queue import ConversationContext

    queue = MemoryUpdateQueue()
    queue._queue = [
        ConversationContext(thread_id="t1", messages=["msg1"]),
        ConversationContext(thread_id="t2", messages=["msg2"]),
    ]

    mock_updater = MagicMock()
    mock_updater.update_memory.side_effect = [RuntimeError("boom"), True]

    with (
        patch("ideer.agents.memory.updater.MemoryUpdater", return_value=mock_updater),
        patch("ideer.agents.memory.queue.time.sleep"),
    ):
        queue._process_queue()

    assert mock_updater.update_memory.call_count == 2
    assert queue._processing is False


# --- Lines 223-224: flush() with timer is None ---


def test_flush_when_timer_is_none():
    """Lines 223-224: flush() works when timer is None."""
    queue = MemoryUpdateQueue()
    queue._timer = None
    queue._queue = []
    # Should not raise
    queue.flush()
    assert queue._processing is False


# --- Lines 242-243: clear() resets processing flag ---


def test_clear_resets_processing_flag():
    """Lines 242-243: clear() resets _processing to False."""
    queue = MemoryUpdateQueue()
    queue._processing = True
    queue._timer = MagicMock()
    queue.clear()
    assert queue._processing is False
    assert queue.pending_count == 0


# --- Lines 256-257: pending_count and is_processing properties ---


def test_pending_count_and_is_processing():
    """Lines 256-257: Properties return correct values."""
    queue = MemoryUpdateQueue()
    assert queue.pending_count == 0
    assert queue.is_processing is False

    queue._processing = True
    assert queue.is_processing is True


# --- Lines 272-275: get_memory_queue ---


def test_get_memory_queue_returns_singleton():
    """Lines 272-275: get_memory_queue returns a singleton."""
    import ideer.agents.memory.queue as queue_mod

    old = queue_mod._memory_queue
    queue_mod._memory_queue = None
    try:
        q1 = get_memory_queue()
        q2 = get_memory_queue()
        assert q1 is q2
        assert isinstance(q1, MemoryUpdateQueue)
    finally:
        queue_mod._memory_queue = old


# --- Lines 284-287: reset_memory_queue ---


def test_reset_memory_queue_clears_singleton():
    """Lines 284-287: reset_memory_queue clears the singleton."""
    import ideer.agents.memory.queue as queue_mod

    old = queue_mod._memory_queue
    try:
        get_memory_queue()
        assert queue_mod._memory_queue is not None
        reset_memory_queue()
        assert queue_mod._memory_queue is None
    finally:
        queue_mod._memory_queue = old


def test_reset_memory_queue_handles_none_singleton():
    """Lines 284-287: reset_memory_queue handles None singleton gracefully."""
    import ideer.agents.memory.queue as queue_mod

    old = queue_mod._memory_queue
    queue_mod._memory_queue = None
    try:
        reset_memory_queue()
        assert queue_mod._memory_queue is None
    finally:
        queue_mod._memory_queue = old


# --- add with user_id ---


def test_add_preserves_user_id_in_context():
    """add() stores user_id in ConversationContext."""
    queue = MemoryUpdateQueue()
    with (
        patch("ideer.agents.memory.queue.get_memory_config", return_value=_memory_config(enabled=True)),
        patch.object(queue, "_reset_timer"),
    ):
        queue.add(thread_id="t1", messages=["msg"], user_id="user-42")
    assert queue._queue[0].user_id == "user-42"


# --- _reset_timer direct coverage ---


def test_reset_timer_sets_timer():
    """_reset_timer calls _schedule_timer with debounce_seconds."""
    queue = MemoryUpdateQueue()
    with (
        patch("ideer.agents.memory.queue.get_memory_config", return_value=_memory_config(debounce_seconds=15)),
        patch.object(queue, "_schedule_timer") as mock_schedule,
    ):
        queue._reset_timer()
    mock_schedule.assert_called_once_with(15)


# --- _process_queue with failed update (not exception) ---


def test_process_queue_logs_warning_on_failed_update():
    """_process_queue logs warning when update returns False."""
    from ideer.agents.memory.queue import ConversationContext

    queue = MemoryUpdateQueue()
    queue._queue = [
        ConversationContext(thread_id="t1", messages=["msg1"]),
    ]

    mock_updater = MagicMock()
    mock_updater.update_memory.return_value = False

    with patch("ideer.agents.memory.updater.MemoryUpdater", return_value=mock_updater):
        queue._process_queue()

    assert queue._processing is False


# --- flush with timer not None ---


def test_flush_cancels_timer_and_processes():
    """flush() cancels existing timer and processes queue."""
    queue = MemoryUpdateQueue()
    mock_timer = MagicMock()
    queue._timer = mock_timer
    queue._queue = []

    queue.flush()

    mock_timer.cancel.assert_called_once()
    assert queue._timer is None
    assert queue._processing is False
