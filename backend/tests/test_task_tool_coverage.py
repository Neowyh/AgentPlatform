"""Tests targeting uncovered error paths in task_tool.py.

Each test maps to specific uncovered lines identified by coverage analysis:
  - Line 64: _await_subagent_terminal returns None when result is None
  - Line 68: _await_subagent_terminal returns None after poll exhaustion
  - Line 77: _deferred_cleanup_subagent_task returns when result is None
  - Lines 79-80: _deferred_cleanup_subagent_task cleans up on terminal result
  - Line 94: _log_cleanup_failure logs error when task raised an exception
  - Line 136: _iter_runtime_callbacks returns [] for None callbacks
  - Line 143: _iter_runtime_callbacks skips None callback in iteration
  - Line 146: _iter_runtime_callbacks skips duplicate callback
  - Line 183: _report_subagent_usage returns early when usage_reported is True
  - Lines 194-195: _report_subagent_usage catches and logs exceptions
  - Line 210: _merge_skill_allowlists returns child when parent is None
  - Line 295: task_tool reads thread_id from config.configurable
  - Lines 368-371: task_tool handles task disappearing from background tasks
"""

import asyncio
import importlib
from enum import Enum
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

task_tool_module = importlib.import_module("ideer.tools.builtins.task_tool")


# ---------------------------------------------------------------------------
# Shared helpers (mirrored from test_task_tool_core_logic for isolation)
# ---------------------------------------------------------------------------


class FakeSubagentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


def _make_runtime(*, app_config=None, thread_id="thread-1", metadata=None):
    context = {}
    if thread_id is not None:
        context["thread_id"] = thread_id
    if app_config is not None:
        context["app_config"] = app_config
    return SimpleNamespace(
        state={
            "sandbox": {"sandbox_id": "local"},
            "thread_data": {"workspace_path": "/tmp/workspace"},
        },
        context=context,
        config={"metadata": metadata or {}},
    )


def _make_subagent_config(name="general-purpose"):
    from ideer.subagents.config import SubagentConfig

    return SubagentConfig(
        name=name,
        description="General helper",
        system_prompt="Base system prompt",
        max_turns=50,
        timeout_seconds=10,
    )


def _make_result(
    status,
    *,
    ai_messages=None,
    result=None,
    error=None,
    token_usage_records=None,
    usage_reported=False,
):
    return SimpleNamespace(
        status=status,
        ai_messages=ai_messages or [],
        result=result,
        error=error,
        token_usage_records=token_usage_records or [],
        usage_reported=usage_reported,
    )


async def _no_sleep(_: float) -> None:
    return None


def _run_task_tool(**kwargs):
    coroutine = getattr(task_tool_module.task_tool, "coroutine", None)
    if coroutine is not None:
        return asyncio.run(coroutine(**kwargs))
    return task_tool_module.task_tool.func(**kwargs)


# ===========================================================================
# _await_subagent_terminal  (lines 64, 68)
# ===========================================================================


class TestAwaitSubagentTerminal:
    """Coverage for _await_subagent_terminal error/edge paths."""

    @pytest.mark.asyncio
    async def test_returns_none_when_result_is_none(self, monkeypatch):
        """Line 64: get_background_task_result returns None immediately."""
        monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: None)
        result = await task_tool_module._await_subagent_terminal("task-x", max_polls=5)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_after_poll_exhaustion(self, monkeypatch):
        """Line 68: all polls exhausted while task keeps running."""
        monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
        running = _make_result(FakeSubagentStatus.RUNNING, ai_messages=[])
        monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: running)
        monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
        result = await task_tool_module._await_subagent_terminal("task-x", max_polls=3)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_terminal_result_when_found(self, monkeypatch):
        """Line 65-66: _is_subagent_terminal returns True, loop exits early."""
        monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
        # First poll returns RUNNING, second poll returns COMPLETED
        polls = iter(
            [
                _make_result(FakeSubagentStatus.RUNNING, ai_messages=[]),
                _make_result(FakeSubagentStatus.COMPLETED, result="done"),
            ]
        )
        monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: next(polls))
        monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
        result = await task_tool_module._await_subagent_terminal("task-x", max_polls=10)
        assert result is not None
        assert result.status == FakeSubagentStatus.COMPLETED
        assert result.result == "done"


# ===========================================================================
# _deferred_cleanup_subagent_task  (lines 77, 79-80)
# ===========================================================================


class TestDeferredCleanupSubagentTask:
    """Coverage for _deferred_cleanup_subagent_task edge paths."""

    @pytest.mark.asyncio
    async def test_returns_when_result_is_none(self, monkeypatch):
        """Line 77: result is None means the entry was already removed."""
        monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: None)
        # Should return without error
        await task_tool_module._deferred_cleanup_subagent_task("task-y", "trace-1", max_polls=10)

    @pytest.mark.asyncio
    async def test_cleans_up_on_terminal_result(self, monkeypatch):
        """Lines 79-80: terminal result triggers immediate cleanup and return."""
        monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
        terminal = _make_result(FakeSubagentStatus.COMPLETED, result="done")
        cleanup_calls = []
        monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: terminal)
        monkeypatch.setattr(
            task_tool_module,
            "cleanup_background_task",
            lambda tid: cleanup_calls.append(tid),
        )

        await task_tool_module._deferred_cleanup_subagent_task("task-y", "trace-1", max_polls=10)
        assert cleanup_calls == ["task-y"]

    @pytest.mark.asyncio
    async def test_returns_after_max_polls_for_non_terminal(self, monkeypatch):
        """Lines 81-85: poll count exceeded without reaching terminal state."""
        monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
        running = _make_result(FakeSubagentStatus.RUNNING, ai_messages=[])
        monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: running)
        monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)

        # Should return after max_polls without hanging
        await task_tool_module._deferred_cleanup_subagent_task("task-y", "trace-1", max_polls=2)


# ===========================================================================
# _log_cleanup_failure  (line 94)
# ===========================================================================


class TestLogCleanupFailure:
    """Coverage for _log_cleanup_failure when task raised an exception."""

    def test_logs_error_when_exception_exists(self, monkeypatch):
        """Line 94: cleanup task finished with an exception."""
        exc = RuntimeError("boom")
        mock_task = MagicMock()
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = exc

        log_messages = []
        monkeypatch.setattr(
            task_tool_module.logger,
            "error",
            lambda msg: log_messages.append(msg),
        )

        task_tool_module._log_cleanup_failure(mock_task, trace_id="t1", task_id="task-z")
        assert len(log_messages) == 1
        assert "task-z" in log_messages[0]
        assert "boom" in log_messages[0]

    def test_noop_when_cancelled(self):
        """Line 89-90: cancelled task does nothing."""
        mock_task = MagicMock()
        mock_task.cancelled.return_value = True
        # Should not raise or call exception()
        task_tool_module._log_cleanup_failure(mock_task, trace_id="t1", task_id="task-z")


# ===========================================================================
# _iter_runtime_callbacks  (lines 136, 143, 146)
# ===========================================================================


class TestIterRuntimeCallbacks:
    """Coverage for _iter_runtime_callbacks edge paths."""

    def test_returns_empty_list_for_none(self):
        """Line 136: callbacks is None -> return []."""
        assert task_tool_module._iter_runtime_callbacks(None) == []

    def test_skips_none_callback_in_list(self):
        """Line 143: a None entry inside the callback list is skipped."""
        handler = MagicMock(name="real_handler")
        result = task_tool_module._iter_runtime_callbacks([None, handler])
        assert handler in result
        assert None not in result

    def test_skips_duplicate_callback(self):
        """Line 146: same callback object appearing twice is only added once."""
        handler = MagicMock(name="dup_handler")
        result = task_tool_module._iter_runtime_callbacks([handler, handler])
        assert result.count(handler) == 1

    def test_deduplicates_across_handlers_and_iterable(self):
        """Same callback found via .handlers attr and direct iteration is deduped."""
        handler = MagicMock(name="shared")
        mgr = SimpleNamespace(handlers=[handler])
        result = task_tool_module._iter_runtime_callbacks([mgr, handler])
        assert result.count(handler) == 1


# ===========================================================================
# _report_subagent_usage  (lines 183, 194-195)
# ===========================================================================


class TestReportSubagentUsage:
    """Coverage for _report_subagent_usage edge paths."""

    def test_returns_early_when_usage_already_reported(self):
        """Line 183: usage_reported=True -> skip immediately."""
        result = _make_result(
            FakeSubagentStatus.COMPLETED,
            token_usage_records=[{"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}],
            usage_reported=True,
        )
        runtime = SimpleNamespace(config={"callbacks": None})
        # Should not raise or attempt to find a recorder
        task_tool_module._report_subagent_usage(runtime, result)

    def test_catches_and_logs_exception_from_recorder(self, monkeypatch):
        """Lines 194-195: exception during recording is caught and logged."""
        failing_recorder = MagicMock()
        failing_recorder.record_external_llm_usage_records.side_effect = RuntimeError("recorder broken")

        result = _make_result(
            FakeSubagentStatus.COMPLETED,
            token_usage_records=[{"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}],
            usage_reported=False,
        )
        runtime = SimpleNamespace(config={"callbacks": [failing_recorder]})

        warn_messages = []
        monkeypatch.setattr(
            task_tool_module.logger,
            "warning",
            lambda msg, **kw: warn_messages.append(msg),
        )

        # Should not raise; the exception is caught internally
        task_tool_module._report_subagent_usage(runtime, result)

        assert len(warn_messages) == 1
        assert "token usage" in warn_messages[0].lower()
        # usage_reported should remain False since the recorder failed
        assert result.usage_reported is False


# ===========================================================================
# _merge_skill_allowlists  (line 210)
# ===========================================================================


class TestMergeSkillAllowlists:
    """Coverage for _merge_skill_allowlists edge paths."""

    def test_returns_child_when_parent_is_none(self):
        """Line 210: parent=None -> return child as-is."""
        child = ["skill-a", "skill-b"]
        assert task_tool_module._merge_skill_allowlists(None, child) is child

    def test_returns_copy_of_parent_when_child_is_none(self):
        """Line 212: child=None -> return list(parent)."""
        parent = ["skill-a", "skill-b"]
        result = task_tool_module._merge_skill_allowlists(parent, None)
        assert result == ["skill-a", "skill-b"]
        assert result is not parent  # should be a copy

    def test_intersects_when_both_provided(self):
        """Lines 214-215: intersection logic."""
        result = task_tool_module._merge_skill_allowlists(["a", "b", "c"], ["b", "c", "d"])
        assert sorted(result) == ["b", "c"]


# ===========================================================================
# task_tool: thread_id fallback via configurable (line 295)
# ===========================================================================


class TestTaskToolThreadIdFallback:
    """Coverage for task_tool reading thread_id from config.configurable."""

    def test_reads_thread_id_from_configurable(self, monkeypatch):
        """Line 295: thread_id is None in context, falls back to configurable."""
        config = _make_subagent_config()
        events = []
        captured = {}

        class DummyExecutor:
            def __init__(self, **kwargs):
                captured["executor_kwargs"] = kwargs

            def execute_async(self, prompt, task_id=None):
                return task_id or "generated-task-id"

        runtime = SimpleNamespace(
            state={"sandbox": {"sandbox_id": "local"}, "thread_data": {}},
            context={},  # No thread_id in context
            config={
                "metadata": {"trace_id": "trace-fallback"},
                "configurable": {"thread_id": "from-configurable"},
            },
        )

        monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
        monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
        monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
        monkeypatch.setattr(
            task_tool_module,
            "get_background_task_result",
            lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="ok"),
        )
        monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
        monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
        monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [])
        monkeypatch.setattr(
            task_tool_module,
            "get_app_config",
            lambda: SimpleNamespace(models=[SimpleNamespace(name="test-model")]),
        )

        output = _run_task_tool(
            runtime=runtime,
            description="test",
            prompt="fallback thread id",
            subagent_type="general-purpose",
            tool_call_id="tc-configurable",
        )

        assert output == "Task Succeeded. Result: ok"
        assert captured["executor_kwargs"]["thread_id"] == "from-configurable"


# ===========================================================================
# task_tool: task disappears from background tasks (lines 368-371)
# ===========================================================================


class TestTaskToolTaskDisappeared:
    """Coverage for task_tool when get_background_task_result returns None mid-loop."""

    def test_returns_error_when_task_disappears(self, monkeypatch):
        """Lines 368-371: result is None during polling -> error return."""
        config = _make_subagent_config()
        events = []
        cleanup_calls = []
        call_count = 0

        def get_result_always_none(_tid):
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
        monkeypatch.setattr(
            task_tool_module,
            "SubagentExecutor",
            type(
                "DummyExecutor",
                (),
                {
                    "__init__": lambda self, **kwargs: None,
                    "execute_async": lambda self, prompt, task_id=None: task_id,
                },
            ),
        )
        monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
        monkeypatch.setattr(task_tool_module, "get_background_task_result", get_result_always_none)
        monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
        monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
        monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [])
        monkeypatch.setattr(
            task_tool_module,
            "get_app_config",
            lambda: SimpleNamespace(models=[SimpleNamespace(name="test-model")]),
        )
        monkeypatch.setattr(
            task_tool_module,
            "cleanup_background_task",
            lambda tid: cleanup_calls.append(tid),
        )

        output = _run_task_tool(
            runtime=_make_runtime(),
            description="test",
            prompt="disappearing task",
            subagent_type="general-purpose",
            tool_call_id="tc-disappear",
        )

        assert "disappeared" in output.lower()
        assert "tc-disappear" in output
        # Verify error event was emitted
        error_events = [e for e in events if e.get("type") == "task_failed"]
        assert len(error_events) == 1
        assert "disappeared" in error_events[0]["error"].lower()
        # Verify cleanup was called
        assert cleanup_calls == ["tc-disappear"]
