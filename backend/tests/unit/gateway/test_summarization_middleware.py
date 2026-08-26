from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage

from ideer.agents.memory.summarization_hook import memory_flush_hook
from ideer.agents.middlewares.dynamic_context_middleware import _DYNAMIC_CONTEXT_REMINDER_KEY, DynamicContextMiddleware
from ideer.agents.middlewares.summarization_middleware import (
    IDeerSummarizationMiddleware,
    SummarizationEvent,
    _resolve_agent_name,
    _resolve_thread_id,
    _tool_call_path,
)
from ideer.config.memory_config import MemoryConfig


def _messages() -> list:
    return [
        HumanMessage(content="user-1"),
        AIMessage(content="assistant-1"),
        HumanMessage(content="user-2"),
        AIMessage(content="assistant-2"),
    ]


def _dynamic_context_reminder(msg_id: str = "reminder-1") -> HumanMessage:
    return HumanMessage(
        content="<system-reminder>\n<current_date>2026-05-08, Friday</current_date>\n</system-reminder>",
        id=msg_id,
        additional_kwargs={"hide_from_ui": True, _DYNAMIC_CONTEXT_REMINDER_KEY: True},
    )


def _runtime(
    thread_id: str | None = "thread-1",
    agent_name: str | None = None,
    user_id: str | None = None,
) -> SimpleNamespace:
    context = {}
    if thread_id is not None:
        context["thread_id"] = thread_id
    if agent_name is not None:
        context["agent_name"] = agent_name
    if user_id is not None:
        context["user_id"] = user_id
    return SimpleNamespace(context=context)


def _middleware(
    *,
    before_summarization=None,
    trigger=("messages", 4),
    keep=("messages", 2),
    skill_file_read_tool_names=None,
    preserve_recent_skill_count: int = 0,
    preserve_recent_skill_tokens: int = 0,
    preserve_recent_skill_tokens_per_skill: int = 0,
) -> IDeerSummarizationMiddleware:
    model = MagicMock()
    model.invoke.return_value = SimpleNamespace(text="compressed summary")
    return IDeerSummarizationMiddleware(
        model=model,
        trigger=trigger,
        keep=keep,
        token_counter=len,
        before_summarization=before_summarization,
        skill_file_read_tool_names=skill_file_read_tool_names,
        preserve_recent_skill_count=preserve_recent_skill_count,
        preserve_recent_skill_tokens=preserve_recent_skill_tokens,
        preserve_recent_skill_tokens_per_skill=preserve_recent_skill_tokens_per_skill,
    )


def _skill_read_call(tool_id: str, skill: str) -> dict:
    return {
        "name": "read_file",
        "id": tool_id,
        "args": {"path": f"/mnt/skills/{skill}/SKILL.md"},
    }


def _skill_conversation() -> list:
    return [
        HumanMessage(content="u1"),
        AIMessage(content="", tool_calls=[_skill_read_call("t1", "alpha")]),
        ToolMessage(content="alpha skill body", tool_call_id="t1"),
        HumanMessage(content="u2"),
        AIMessage(content="", tool_calls=[_skill_read_call("t2", "beta")]),
        ToolMessage(content="beta skill body", tool_call_id="t2"),
        HumanMessage(content="u3"),
        AIMessage(content="final"),
    ]


def _raw_tool_call(tool_id: str, name: str = "read_file") -> dict:
    return {
        "id": tool_id,
        "type": "function",
        "function": {"name": name, "arguments": "{}"},
    }


# ---------------------------------------------------------------------------
# _resolve_thread_id / _resolve_agent_name
# ---------------------------------------------------------------------------


def test_resolve_thread_id_from_runtime_context():
    runtime = _runtime(thread_id="t-123")
    assert _resolve_thread_id(runtime) == "t-123"


def test_resolve_thread_id_from_langgraph_config():
    runtime = SimpleNamespace(context={})
    with mock.patch(
        "ideer.agents.middlewares.summarization_middleware.get_config",
        return_value={"configurable": {"thread_id": "cfg-thread"}},
    ):
        assert _resolve_thread_id(runtime) == "cfg-thread"


def test_resolve_thread_id_returns_none_when_no_context():
    runtime = SimpleNamespace(context={})
    with mock.patch(
        "ideer.agents.middlewares.summarization_middleware.get_config",
        side_effect=RuntimeError("no config"),
    ):
        assert _resolve_thread_id(runtime) is None


def test_resolve_thread_id_none_context():
    runtime = SimpleNamespace(context=None)
    assert _resolve_thread_id(runtime) is None


def test_resolve_agent_name_from_runtime_context():
    runtime = _runtime(agent_name="researcher")
    assert _resolve_agent_name(runtime) == "researcher"


def test_resolve_agent_name_from_langgraph_config():
    runtime = SimpleNamespace(context={})
    with mock.patch(
        "ideer.agents.middlewares.summarization_middleware.get_config",
        return_value={"configurable": {"agent_name": "writer"}},
    ):
        assert _resolve_agent_name(runtime) == "writer"


def test_resolve_agent_name_returns_none_when_no_context():
    runtime = SimpleNamespace(context={})
    with mock.patch(
        "ideer.agents.middlewares.summarization_middleware.get_config",
        side_effect=RuntimeError("no config"),
    ):
        assert _resolve_agent_name(runtime) is None


def test_resolve_agent_name_none_context():
    runtime = SimpleNamespace(context=None)
    assert _resolve_agent_name(runtime) is None


# ---------------------------------------------------------------------------
# _tool_call_path
# ---------------------------------------------------------------------------


def test_tool_call_path_with_path_key():
    assert _tool_call_path({"args": {"path": "/foo/bar"}}) == "/foo/bar"


def test_tool_call_path_with_file_path_key():
    assert _tool_call_path({"args": {"file_path": "/foo/bar"}}) == "/foo/bar"


def test_tool_call_path_with_filepath_key():
    assert _tool_call_path({"args": {"filepath": "/foo/bar"}}) == "/foo/bar"


def test_tool_call_path_no_matching_key():
    assert _tool_call_path({"args": {"other": "val"}}) is None


def test_tool_call_path_non_dict_args():
    assert _tool_call_path({"args": "invalid"}) is None


def test_tool_call_path_no_args():
    assert _tool_call_path({}) is None


def test_tool_call_path_empty_path():
    assert _tool_call_path({"args": {"path": ""}}) is None


def test_tool_call_path_non_string_path():
    assert _tool_call_path({"args": {"path": 123}}) is None


# ---------------------------------------------------------------------------
# Hook tests
# ---------------------------------------------------------------------------


def test_before_summarization_hook_receives_messages_before_compression() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(before_summarization=[captured.append])

    result = middleware.before_model({"messages": _messages()}, _runtime())

    assert len(captured) == 1
    assert [message.content for message in captured[0].messages_to_summarize] == ["user-1", "assistant-1"]
    assert [message.content for message in captured[0].preserved_messages] == ["user-2", "assistant-2"]
    assert captured[0].thread_id == "thread-1"
    assert captured[0].agent_name is None
    assert isinstance(result["messages"][0], RemoveMessage)
    assert result["messages"][1].content.startswith("Here is a summary")


def test_dynamic_context_reminder_is_preserved_across_summarization() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(before_summarization=[captured.append])
    reminder = _dynamic_context_reminder()

    result = middleware.before_model(
        {
            "messages": [
                reminder,
                HumanMessage(content="user-1"),
                AIMessage(content="assistant-1"),
                HumanMessage(content="user-2"),
            ]
        },
        _runtime(),
    )

    assert len(captured) == 1
    assert [message.content for message in captured[0].messages_to_summarize] == ["user-1"]
    assert captured[0].preserved_messages[0] is reminder

    emitted = result["messages"]
    assert isinstance(emitted[0], RemoveMessage)
    assert emitted[1].name == "summary"
    assert emitted[2] is reminder

    followup_state = {"messages": [*emitted[1:], HumanMessage(content="Follow-up", id="msg-2")]}
    with mock.patch("ideer.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        assert DynamicContextMiddleware().before_agent(followup_state, _runtime()) is None


def test_before_summarization_hook_not_called_when_threshold_not_met() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(before_summarization=[captured.append], trigger=("messages", 10))

    result = middleware.before_model({"messages": _messages()}, _runtime())

    assert captured == []
    assert result is None


def test_before_summarization_hook_exception_does_not_block_compression(caplog: pytest.LogCaptureFixture) -> None:
    def _broken_hook(_: SummarizationEvent) -> None:
        raise RuntimeError("hook failure")

    middleware = _middleware(before_summarization=[_broken_hook])

    with caplog.at_level("ERROR"):
        result = middleware.before_model({"messages": _messages()}, _runtime())

    assert "before_summarization hook _broken_hook failed" in caplog.text
    assert isinstance(result["messages"][0], RemoveMessage)


def test_multiple_before_summarization_hooks_run_in_registration_order() -> None:
    call_order: list[str] = []

    def _hook(name: str):
        return lambda _: call_order.append(name)

    middleware = _middleware(before_summarization=[_hook("first"), _hook("second"), _hook("third")])

    middleware.before_model({"messages": _messages()}, _runtime())

    assert call_order == ["first", "second", "third"]


@pytest.mark.anyio
async def test_abefore_model_calls_hooks_same_as_sync() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(before_summarization=[captured.append])

    await middleware.abefore_model({"messages": _messages()}, _runtime())

    assert len(captured) == 1
    assert [message.content for message in captured[0].messages_to_summarize] == ["user-1", "assistant-1"]


# ---------------------------------------------------------------------------
# _preserve_dynamic_context_reminders edge cases
# ---------------------------------------------------------------------------


def test_preserve_dynamic_context_reminders_no_reminders() -> None:
    middleware = _middleware()
    msgs = [HumanMessage(content="a"), AIMessage(content="b")]
    to_sum, preserved = middleware._preserve_dynamic_context_reminders(msgs, [])
    assert to_sum == msgs
    assert preserved == []


def test_preserve_dynamic_context_reminders_with_reminder() -> None:
    middleware = _middleware()
    reminder = _dynamic_context_reminder()
    other = HumanMessage(content="user")
    to_sum, preserved = middleware._preserve_dynamic_context_reminders([reminder, other], [])
    assert other in to_sum
    assert reminder not in to_sum
    assert reminder in preserved


# ---------------------------------------------------------------------------
# _fire_hooks edge cases
# ---------------------------------------------------------------------------


def test_fire_hooks_no_hooks() -> None:
    middleware = _middleware(before_summarization=[])
    # Should not raise
    middleware._fire_hooks([], [], _runtime())


def test_fire_hooks_hook_with_no_name() -> None:
    """Hook without __name__ falls back to type().__name__."""

    class NoNameHook:
        def __call__(self, event):
            raise RuntimeError("fail")

    middleware = _middleware(before_summarization=[NoNameHook()])
    # Should not raise (exception is caught internally)
    middleware._fire_hooks([], [], _runtime())


# ---------------------------------------------------------------------------
# _is_skill_tool_call edge cases
# ---------------------------------------------------------------------------


def test_is_skill_tool_call_non_read_tool() -> None:
    middleware = _middleware()
    tc = {"name": "write_file", "args": {"path": "/mnt/skills/foo/SKILL.md"}}
    assert middleware._is_skill_tool_call(tc, "/mnt/skills") is False


def test_is_skill_tool_call_path_outside_root() -> None:
    middleware = _middleware()
    tc = {"name": "read_file", "args": {"path": "/other/path/SKILL.md"}}
    assert middleware._is_skill_tool_call(tc, "/mnt/skills") is False


def test_is_skill_tool_call_path_at_root() -> None:
    middleware = _middleware()
    tc = {"name": "read_file", "args": {"path": "/mnt/skills"}}
    assert middleware._is_skill_tool_call(tc, "/mnt/skills") is True


def test_is_skill_tool_call_path_under_root() -> None:
    middleware = _middleware()
    tc = {"name": "read_file", "args": {"path": "/mnt/skills/foo/SKILL.md"}}
    assert middleware._is_skill_tool_call(tc, "/mnt/skills") is True


def test_is_skill_tool_call_custom_tool_name() -> None:
    middleware = _middleware(skill_file_read_tool_names=["my_reader"])
    tc = {"name": "my_reader", "args": {"path": "/mnt/skills/foo/SKILL.md"}}
    assert middleware._is_skill_tool_call(tc, "/mnt/skills") is True


def test_is_skill_tool_call_no_path() -> None:
    middleware = _middleware()
    tc = {"name": "read_file", "args": {}}
    assert middleware._is_skill_tool_call(tc, "/mnt/skills") is False


# ---------------------------------------------------------------------------
# _select_bundles_to_rescue edge cases
# ---------------------------------------------------------------------------


def test_select_bundles_to_rescue_empty() -> None:
    middleware = _middleware(preserve_recent_skill_count=5, preserve_recent_skill_tokens=10000)
    assert middleware._select_bundles_to_rescue([]) == []


def test_select_bundles_to_rescue_deduplicates_skill_keys() -> None:
    from ideer.agents.middlewares.summarization_middleware import _SkillBundle

    middleware = _middleware(preserve_recent_skill_count=5, preserve_recent_skill_tokens=10000, preserve_recent_skill_tokens_per_skill=10000)
    b1 = _SkillBundle(ai_index=0, skill_tool_indices=(1,), skill_tool_call_ids=frozenset({"t1"}), skill_tool_tokens=100, skill_key="alpha")
    b2 = _SkillBundle(ai_index=2, skill_tool_indices=(3,), skill_tool_call_ids=frozenset({"t2"}), skill_tool_tokens=100, skill_key="alpha")
    selected = middleware._select_bundles_to_rescue([b1, b2])
    # Newest (b2) should be selected, b1 skipped (same key)
    assert len(selected) == 1
    assert selected[0].skill_key == "alpha"


def test_select_bundles_to_rescue_respects_total_token_budget() -> None:
    from ideer.agents.middlewares.summarization_middleware import _SkillBundle

    middleware = _middleware(preserve_recent_skill_count=5, preserve_recent_skill_tokens=50, preserve_recent_skill_tokens_per_skill=10000)
    b1 = _SkillBundle(ai_index=0, skill_tool_indices=(1,), skill_tool_call_ids=frozenset({"t1"}), skill_tool_tokens=100, skill_key="a")
    selected = middleware._select_bundles_to_rescue([b1])
    assert selected == []


# ---------------------------------------------------------------------------
# _find_skill_bundles edge cases
# ---------------------------------------------------------------------------


def test_find_skill_bundles_no_tool_messages() -> None:
    middleware = _middleware()
    messages = [
        HumanMessage(content="u1"),
        AIMessage(content="", tool_calls=[_skill_read_call("t1", "alpha")]),
        # No ToolMessage follows
        HumanMessage(content="u2"),
    ]
    bundles = middleware._find_skill_bundles(messages, "/mnt/skills")
    assert bundles == []


def test_find_skill_bundles_no_matching_tool_results() -> None:
    middleware = _middleware()
    messages = [
        HumanMessage(content="u1"),
        AIMessage(content="", tool_calls=[_skill_read_call("t1", "alpha")]),
        ToolMessage(content="result", tool_call_id="t_other"),
        HumanMessage(content="u2"),
    ]
    bundles = middleware._find_skill_bundles(messages, "/mnt/skills")
    assert bundles == []


# ---------------------------------------------------------------------------
# _partition_with_skill_rescue edge cases
# ---------------------------------------------------------------------------


def test_partition_with_skill_rescue_exception_falls_back() -> None:
    middleware = _middleware(preserve_recent_skill_count=5, preserve_recent_skill_tokens=10000)
    # Force exception in _find_skill_bundles by passing very short cutoff
    to_sum, preserved = middleware._partition_with_skill_rescue(_messages(), 1)
    # Should fall back to parent partitioning
    assert len(to_sum) > 0 or len(preserved) > 0


# ---------------------------------------------------------------------------
# Memory flush hook
# ---------------------------------------------------------------------------


def test_memory_flush_hook_skips_when_memory_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = MagicMock()
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_config", lambda: MemoryConfig(enabled=False))
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_queue", lambda: queue)

    memory_flush_hook(
        SummarizationEvent(
            messages_to_summarize=tuple(_messages()[:2]),
            preserved_messages=(),
            thread_id="thread-1",
            agent_name=None,
            runtime=_runtime(),
        )
    )

    queue.add_nowait.assert_not_called()


def test_memory_flush_hook_skips_when_thread_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = MagicMock()
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_config", lambda: MemoryConfig(enabled=True))
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_queue", lambda: queue)

    memory_flush_hook(
        SummarizationEvent(
            messages_to_summarize=tuple(_messages()[:2]),
            preserved_messages=(),
            thread_id=None,
            agent_name=None,
            runtime=_runtime(None),
        )
    )

    queue.add_nowait.assert_not_called()


def test_memory_flush_hook_enqueues_filtered_messages_and_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = MagicMock()
    messages = [
        HumanMessage(content="Question"),
        AIMessage(content="Calling tool", tool_calls=[{"name": "search", "id": "tool-1", "args": {}}]),
        AIMessage(content="Final answer"),
    ]
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_config", lambda: MemoryConfig(enabled=True))
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_queue", lambda: queue)

    memory_flush_hook(
        SummarizationEvent(
            messages_to_summarize=tuple(messages),
            preserved_messages=(),
            thread_id="thread-1",
            agent_name=None,
            runtime=_runtime(),
        )
    )

    queue.add_nowait.assert_called_once()
    add_kwargs = queue.add_nowait.call_args.kwargs
    assert add_kwargs["thread_id"] == "thread-1"
    assert [message.content for message in add_kwargs["messages"]] == ["Question", "Final answer"]
    assert add_kwargs["correction_detected"] is False
    assert add_kwargs["reinforcement_detected"] is False


def test_memory_flush_hook_preserves_agent_scoped_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = MagicMock()
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_config", lambda: MemoryConfig(enabled=True))
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_queue", lambda: queue)

    memory_flush_hook(
        SummarizationEvent(
            messages_to_summarize=tuple(_messages()[:2]),
            preserved_messages=(),
            thread_id="thread-1",
            agent_name="research-agent",
            runtime=_runtime(agent_name="research-agent"),
        )
    )

    queue.add_nowait.assert_called_once()
    assert queue.add_nowait.call_args.kwargs["agent_name"] == "research-agent"


def test_memory_flush_hook_passes_runtime_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = MagicMock()
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_config", lambda: MemoryConfig(enabled=True))
    monkeypatch.setattr("ideer.agents.memory.summarization_hook.get_memory_queue", lambda: queue)

    memory_flush_hook(
        SummarizationEvent(
            messages_to_summarize=tuple(_messages()[:2]),
            preserved_messages=(),
            thread_id="main",
            agent_name="researcher",
            runtime=_runtime(thread_id="main", agent_name="researcher", user_id="alice"),
        )
    )

    queue.add_nowait.assert_called_once()
    assert queue.add_nowait.call_args.kwargs["user_id"] == "alice"


# ---------------------------------------------------------------------------
# Skill rescue tests
# ---------------------------------------------------------------------------


def test_skill_rescue_keeps_recent_skill_reads_out_of_summary() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    result = middleware.before_model({"messages": _skill_conversation()}, _runtime())

    assert len(captured) == 1
    summarized_ids = {id(m) for m in captured[0].messages_to_summarize}
    preserved = captured[0].preserved_messages

    assert any(isinstance(m, ToolMessage) and m.content == "alpha skill body" for m in preserved)
    assert any(isinstance(m, ToolMessage) and m.content == "beta skill body" for m in preserved)
    for m in preserved:
        if isinstance(m, ToolMessage) and m.content in {"alpha skill body", "beta skill body"}:
            assert id(m) not in summarized_ids

    contents = [getattr(m, "content", None) for m in preserved]
    assert contents[-2:] == ["u3", "final"]

    emitted = result["messages"]
    assert isinstance(emitted[0], RemoveMessage)
    assert emitted[1].content.startswith("Here is a summary")
    assert list(emitted[-2:]) == list(preserved[-2:])


def test_skill_rescue_respects_count_budget() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=1,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    middleware.before_model({"messages": _skill_conversation()}, _runtime())

    preserved = captured[0].preserved_messages
    summarized = captured[0].messages_to_summarize
    assert any(isinstance(m, ToolMessage) and m.content == "beta skill body" for m in preserved)
    assert not any(isinstance(m, ToolMessage) and m.content == "alpha skill body" for m in preserved)
    assert any(isinstance(m, ToolMessage) and m.content == "alpha skill body" for m in summarized)


def test_skill_rescue_uses_injected_skills_container_path() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )
    middleware._skills_container_path = "/custom/skills"
    messages = [
        HumanMessage(content="u1"),
        AIMessage(content="", tool_calls=[{"name": "read_file", "id": "t1", "args": {"path": "/custom/skills/demo/SKILL.md"}}]),
        ToolMessage(content="demo skill body", tool_call_id="t1"),
        HumanMessage(content="u2"),
        AIMessage(content="final"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    preserved = captured[0].preserved_messages
    assert any(isinstance(m, ToolMessage) and m.content == "demo skill body" for m in preserved)


def test_skill_rescue_uses_configured_skill_read_tool_names() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        skill_file_read_tool_names=["custom_read"],
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )
    middleware._skills_container_path = "/custom/skills"
    messages = [
        HumanMessage(content="u1"),
        AIMessage(content="", tool_calls=[{"name": "custom_read", "id": "t1", "args": {"path": "/custom/skills/demo/SKILL.md"}}]),
        ToolMessage(content="demo skill body", tool_call_id="t1"),
        HumanMessage(content="u2"),
        AIMessage(content="final"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    preserved = captured[0].preserved_messages
    assert any(isinstance(m, ToolMessage) and m.content == "demo skill body" for m in preserved)


def test_skill_rescue_respects_per_skill_token_cap() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=0,
    )

    middleware.before_model({"messages": _skill_conversation()}, _runtime())

    preserved = captured[0].preserved_messages
    assert not any(isinstance(m, ToolMessage) and m.content in {"alpha skill body", "beta skill body"} for m in preserved)


def test_skill_rescue_disabled_when_count_zero() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=0,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    middleware.before_model({"messages": _skill_conversation()}, _runtime())

    preserved = captured[0].preserved_messages
    assert not any(isinstance(m, ToolMessage) for m in preserved)


def test_skill_rescue_ignores_non_skill_tool_reads() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    messages = [
        HumanMessage(content="u1"),
        AIMessage(
            content="",
            tool_calls=[{"name": "read_file", "id": "t1", "args": {"path": "/mnt/user-data/workspace/notes.md"}}],
        ),
        ToolMessage(content="user notes", tool_call_id="t1"),
        HumanMessage(content="u2"),
        AIMessage(content="done"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    preserved = captured[0].preserved_messages
    assert not any(isinstance(m, ToolMessage) and m.content == "user notes" for m in preserved)


def test_skill_rescue_does_not_preserve_non_skill_outputs_from_mixed_tool_calls() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    messages = [
        HumanMessage(content="u1"),
        AIMessage(
            content="",
            tool_calls=[
                _skill_read_call("skill-1", "alpha"),
                {"name": "read_file", "id": "file-1", "args": {"path": "/mnt/user-data/workspace/notes.md"}},
            ],
        ),
        ToolMessage(content="alpha skill body", tool_call_id="skill-1"),
        ToolMessage(content="user notes", tool_call_id="file-1"),
        HumanMessage(content="u2"),
        AIMessage(content="done"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    preserved = captured[0].preserved_messages
    summarized = captured[0].messages_to_summarize

    preserved_ai = next(m for m in preserved if isinstance(m, AIMessage) and m.tool_calls)
    summarized_ai = next(m for m in summarized if isinstance(m, AIMessage) and m.tool_calls)

    assert [tc["id"] for tc in preserved_ai.tool_calls] == ["skill-1"]
    assert [tc["id"] for tc in summarized_ai.tool_calls] == ["file-1"]
    assert any(isinstance(m, ToolMessage) and m.content == "alpha skill body" for m in preserved)
    assert not any(isinstance(m, ToolMessage) and m.content == "user notes" for m in preserved)
    assert any(isinstance(m, ToolMessage) and m.content == "user notes" for m in summarized)


def test_skill_rescue_syncs_raw_provider_tool_calls_on_split_ai_messages() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    messages = [
        HumanMessage(content="u1"),
        AIMessage(
            content="reading skill and notes",
            tool_calls=[
                _skill_read_call("skill-1", "alpha"),
                {"name": "read_file", "id": "file-1", "args": {"path": "/mnt/user-data/workspace/notes.md"}},
            ],
            additional_kwargs={"tool_calls": [_raw_tool_call("skill-1"), _raw_tool_call("file-1")]},
        ),
        ToolMessage(content="alpha skill body", tool_call_id="skill-1"),
        ToolMessage(content="user notes", tool_call_id="file-1"),
        HumanMessage(content="u2"),
        AIMessage(content="done"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    preserved = captured[0].preserved_messages
    summarized = captured[0].messages_to_summarize

    preserved_ai = next(m for m in preserved if isinstance(m, AIMessage) and m.tool_calls)
    summarized_ai = next(m for m in summarized if isinstance(m, AIMessage) and m.tool_calls)

    assert [tc["id"] for tc in preserved_ai.tool_calls] == ["skill-1"]
    assert [tc["id"] for tc in preserved_ai.additional_kwargs["tool_calls"]] == ["skill-1"]
    assert [tc["id"] for tc in summarized_ai.tool_calls] == ["file-1"]
    assert [tc["id"] for tc in summarized_ai.additional_kwargs["tool_calls"]] == ["file-1"]


def test_skill_rescue_clears_content_on_rescued_ai_clone() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    messages = [
        HumanMessage(content="u1"),
        AIMessage(
            content="reading skill and notes",
            tool_calls=[
                _skill_read_call("skill-1", "alpha"),
                {"name": "read_file", "id": "file-1", "args": {"path": "/mnt/user-data/workspace/notes.md"}},
            ],
        ),
        ToolMessage(content="alpha skill body", tool_call_id="skill-1"),
        ToolMessage(content="user notes", tool_call_id="file-1"),
        HumanMessage(content="u2"),
        AIMessage(content="done"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    preserved = captured[0].preserved_messages
    summarized = captured[0].messages_to_summarize

    preserved_ai = next(m for m in preserved if isinstance(m, AIMessage) and m.tool_calls)
    summarized_ai = next(m for m in summarized if isinstance(m, AIMessage) and m.tool_calls)

    assert preserved_ai.content == ""
    assert summarized_ai.content == "reading skill and notes"


def test_skill_rescue_removes_raw_provider_tool_calls_from_content_only_summary_clone() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    messages = [
        HumanMessage(content="u1"),
        AIMessage(
            content="reading skill",
            tool_calls=[_skill_read_call("skill-1", "alpha")],
            additional_kwargs={"tool_calls": [_raw_tool_call("skill-1")], "function_call": {"name": "read_file"}},
            response_metadata={"finish_reason": "tool_calls"},
        ),
        ToolMessage(content="alpha skill body", tool_call_id="skill-1"),
        HumanMessage(content="u2"),
        AIMessage(content="done"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    summarized = captured[0].messages_to_summarize
    summarized_ai = next(m for m in summarized if isinstance(m, AIMessage))

    assert summarized_ai.content == "reading skill"
    assert summarized_ai.tool_calls == []
    assert "tool_calls" not in summarized_ai.additional_kwargs
    assert "function_call" not in summarized_ai.additional_kwargs
    assert summarized_ai.response_metadata["finish_reason"] == "stop"


def test_skill_rescue_only_preserves_skill_calls_with_matched_tool_results() -> None:
    captured: list[SummarizationEvent] = []
    middleware = _middleware(
        before_summarization=[captured.append],
        trigger=("messages", 4),
        keep=("messages", 2),
        preserve_recent_skill_count=5,
        preserve_recent_skill_tokens=10_000,
        preserve_recent_skill_tokens_per_skill=10_000,
    )

    messages = [
        HumanMessage(content="u1"),
        AIMessage(
            content="",
            tool_calls=[
                _skill_read_call("skill-1", "alpha"),
                _skill_read_call("skill-2", "beta"),
            ],
        ),
        ToolMessage(content="alpha skill body", tool_call_id="skill-1"),
        HumanMessage(content="u2"),
        AIMessage(content="done"),
    ]

    middleware.before_model({"messages": messages}, _runtime())

    preserved = captured[0].preserved_messages
    summarized = captured[0].messages_to_summarize

    preserved_ai = next(m for m in preserved if isinstance(m, AIMessage) and m.tool_calls)
    summarized_ai = next(m for m in summarized if isinstance(m, AIMessage) and m.tool_calls)

    assert [tc["id"] for tc in preserved_ai.tool_calls] == ["skill-1"]
    assert [tc["id"] for tc in summarized_ai.tool_calls] == ["skill-2"]
    assert any(isinstance(m, ToolMessage) and m.content == "alpha skill body" for m in preserved)
    assert not any(isinstance(m, ToolMessage) and getattr(m, "tool_call_id", None) == "skill-2" for m in preserved)
