from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_MODULE_PATH = Path(__file__).with_name("multi_attachment_ttft.py")
_SPEC = importlib.util.spec_from_file_location("multi_attachment_ttft", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_stream_signal_ignores_user_and_empty_events() -> None:
    assert _MODULE._stream_signal(
        "messages", [{"type": "human", "content": "prompt"}, {"run_id": "r1"}], "r1"
    ) == (None, "r1")
    assert _MODULE._stream_signal(
        "messages", [{"type": "ai", "content": ""}, {"run_id": "r1"}], "r1"
    ) == (None, "r1")


def test_stream_signal_requires_current_run_and_assistant_role() -> None:
    other = [{"type": "ai", "content": "old"}, {"run_id": "old"}]
    current = [{"type": "AIMessageChunk", "content": "answer"}, {"run_id": "r1"}]
    assert _MODULE._stream_signal("messages", other, "r1") == (None, "r1")
    assert _MODULE._stream_signal("messages", current, "r1") == ("assistant", "r1")


def test_stream_signal_separates_tool_and_error_events() -> None:
    tool = [
        {"type": "tool", "content": "result", "tool_call_id": "call-1"},
        {"run_id": "r1"},
    ]
    assert _MODULE._stream_signal("messages", tool, "r1") == ("tool", "r1")
    assert _MODULE._stream_signal("error", {"message": "gateway failed"}, "r1") == (
        "error",
        "r1",
    )


def test_stream_signal_accepts_chunk_without_run_id_on_dedicated_thread() -> None:
    # The gateway's per-chunk `messages` metadata carries LangGraph routing
    # keys (langgraph_node, thread_id, ...) but no run_id; the run is pinned
    # by the leading metadata event. Such chunks must still count as tokens.
    chunk = [
        {"type": "AIMessageChunk", "content": "Hello", "additional_kwargs": {}},
        {"langgraph_node": "agent", "thread_id": "t1"},
    ]
    assert _MODULE._stream_signal("messages", chunk, "r1") == ("assistant", "r1")
    # Stale full-state replays that DO carry a mismatched run_id stay rejected.
    stale = [{"type": "ai", "content": "old"}, {"run_id": "old"}]
    assert _MODULE._stream_signal("values", stale, "r1") == (None, "r1")


def test_observe_stream_uses_monotonic_marks_for_calibration() -> None:
    ticks = iter([10.0, 10.25, 10.5])
    events = [
        ("metadata", {"run_id": "r1"}),
        (
            "messages",
            [
                {"type": "tool", "content": "working", "tool_call_id": "c1"},
                {"run_id": "r1"},
            ],
        ),
        ("messages", [{"type": "ai", "content": "answer"}, {"run_id": "r1"}]),
    ]
    observed = _MODULE._observe_stream(events, 9.5, clock=lambda: next(ticks))
    assert observed["run_to_first_sse_event_ms"] == 500.0
    assert observed["run_to_first_tool_ms"] == 750.0
    assert observed["run_to_first_token_ms"] == 1000.0


def test_ttft_acceptance_counts_exclude_out_of_scope_twenty_file_case() -> None:
    assert _MODULE.DEFAULT_COUNTS == (0, 1, 5, 10)
    parser = _MODULE._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--thread-id", "thread", "--count", "20"])
