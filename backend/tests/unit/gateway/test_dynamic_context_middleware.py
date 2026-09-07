"""Tests for DynamicContextMiddleware.

Upstream contract: framework-owned data (current date) rides a SystemMessage
<system-reminder>; user-owned memory rides a separate hidden HumanMessage; the
original user message is re-issued with a ``{id}__user`` ID suffix. Injection
happens once per session (and again on midnight crossing), targeting the LAST
user turn when a prior injection was missed.
"""

from types import SimpleNamespace
from unittest import mock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from deerflow.agents.middlewares.dynamic_context_middleware import (
    _DYNAMIC_CONTEXT_REMINDER_KEY,
    _REMINDER_DATE_KEY,
    DynamicContextMiddleware,
)

_SYSTEM_REMINDER_TAG = "<system-reminder>"


def _make_middleware(**kwargs) -> DynamicContextMiddleware:
    return DynamicContextMiddleware(**kwargs)


def _fake_runtime():
    return SimpleNamespace(context={})


def _reminder_msg(content: str, msg_id: str, date: str | None = None) -> SystemMessage:
    """Build a reminder SystemMessage the way the middleware produces it."""
    kwargs = {"hide_from_ui": True, _DYNAMIC_CONTEXT_REMINDER_KEY: True}
    if date is not None:
        kwargs[_REMINDER_DATE_KEY] = date
    return SystemMessage(content=content, id=msg_id, additional_kwargs=kwargs)


# ---------------------------------------------------------------------------
# Basic injection
# ---------------------------------------------------------------------------


def test_injects_system_reminder_into_first_human_message():
    mw = _make_middleware()
    state = {"messages": [HumanMessage(content="Hello", id="msg-1")]}

    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""), mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is not None
    updated_msgs = result["messages"]
    assert len(updated_msgs) == 2

    reminder_msg = updated_msgs[0]
    assert isinstance(reminder_msg, SystemMessage)
    assert reminder_msg.id == "msg-1"  # takes the original ID (position swap)
    assert reminder_msg.additional_kwargs.get(_DYNAMIC_CONTEXT_REMINDER_KEY) is True
    assert _SYSTEM_REMINDER_TAG in reminder_msg.content
    assert "<current_date>2026-05-08, Friday</current_date>" in reminder_msg.content
    assert "Hello" not in reminder_msg.content  # reminder only — no user text

    user_msg = updated_msgs[1]
    assert isinstance(user_msg, HumanMessage)
    assert user_msg.id == "msg-1__user"  # derived ID
    assert user_msg.content == "Hello"


def test_memory_included_when_present():
    """Memory is user-owned: it rides a separate hidden HumanMessage, never the
    framework-authority SystemMessage (OWASP LLM01 role separation)."""
    mw = _make_middleware()
    state = {"messages": [HumanMessage(content="Hi", id="msg-1")]}

    with (
        mock.patch(
            "deerflow.agents.lead_agent.prompt._get_memory_context",
            return_value="<memory>\nUser prefers Python.\n</memory>",
        ),
        mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt,
    ):
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    msgs = result["messages"]
    # [SystemMessage(date reminder), HumanMessage(memory), HumanMessage(query)]
    assert isinstance(msgs[0], SystemMessage)
    assert "User prefers Python." not in msgs[0].content
    assert "<current_date>2026-05-08, Friday</current_date>" in msgs[0].content
    memory_msg = msgs[1]
    assert isinstance(memory_msg, HumanMessage)
    assert memory_msg.id == "msg-1__memory"
    assert "User prefers Python." in memory_msg.content
    assert memory_msg.additional_kwargs.get("hide_from_ui") is True
    assert msgs[2].content == "Hi"
    assert msgs[2].id == "msg-1__user"


# ---------------------------------------------------------------------------
# Frozen-snapshot: no re-injection within a session
# ---------------------------------------------------------------------------


def test_skips_injection_if_already_present():
    """Second turn: reminder already present with the same date → no update."""
    mw = _make_middleware()
    reminder_content = "<system-reminder>\n<current_date>2026-05-08, Friday</current_date>\n</system-reminder>"
    state = {
        "messages": [
            _reminder_msg(reminder_content, "msg-1", date="2026-05-08, Friday"),
            HumanMessage(content="Hello", id="msg-1__user"),
            AIMessage(content="Hi there"),
            HumanMessage(content="Follow-up", id="msg-2"),
        ]
    }

    with mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is None  # no update needed


def test_injects_into_last_user_message_when_no_prior_injection():
    """The fallback path targets the LAST user turn: the ID-swap's {id}__user copy
    is appended by add_messages, so attaching to an earlier message would move the
    stale prompt ahead of the current question."""
    mw = _make_middleware()
    state = {
        "messages": [
            HumanMessage(content="First", id="msg-1"),
            AIMessage(content="Reply"),
            HumanMessage(content="Second", id="msg-2"),
        ]
    }

    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""), mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is not None
    msgs = result["messages"]
    # Only the two injected messages are returned (reminder + original last query)
    assert len(msgs) == 2
    assert msgs[0].id == "msg-2"  # reminder takes the targeted message's ID
    assert msgs[0].additional_kwargs.get(_DYNAMIC_CONTEXT_REMINDER_KEY) is True
    assert _SYSTEM_REMINDER_TAG in msgs[0].content
    assert msgs[1].id == "msg-2__user"  # original content with derived ID
    assert msgs[1].content == "Second"
    # "First" (msg-1) is not in the returned update — it is left unchanged
    assert all(m.id != "msg-1" for m in msgs)


def test_summary_human_message_is_not_used_as_injection_target():
    """After summarization, the synthetic summary HumanMessage is not a user turn."""
    mw = _make_middleware()
    state = {
        "messages": [
            HumanMessage(content="Here is a summary of the conversation to date:\n\n...", id="summary-1", name="summary"),
            AIMessage(content="Earlier reply"),
            HumanMessage(content="Follow-up", id="msg-2"),
        ]
    }

    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""), mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is not None
    msgs = result["messages"]
    assert len(msgs) == 2
    assert msgs[0].id == "msg-2"
    assert msgs[0].additional_kwargs.get(_DYNAMIC_CONTEXT_REMINDER_KEY) is True
    assert msgs[1].id == "msg-2__user"
    assert msgs[1].content == "Follow-up"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_messages_returns_none():
    mw = _make_middleware()
    result = mw.before_agent({"messages": []}, _fake_runtime())
    assert result is None


def test_no_human_message_returns_none():
    mw = _make_middleware()
    state = {"messages": [AIMessage(content="assistant only")]}
    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""):
        result = mw.before_agent(state, _fake_runtime())
    assert result is None


def test_list_content_message_handled_as_separate_reminder():
    """List-content (e.g. multi-modal) messages remain intact; reminder is a separate message."""
    mw = _make_middleware()
    original_content = [{"type": "text", "text": "Hello"}]
    state = {"messages": [HumanMessage(content=original_content, id="msg-1")]}

    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""), mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is not None
    msgs = result["messages"]
    assert len(msgs) == 2
    # Reminder is a plain string message with the flag set
    assert isinstance(msgs[0].content, str)
    assert msgs[0].additional_kwargs.get(_DYNAMIC_CONTEXT_REMINDER_KEY) is True
    assert _SYSTEM_REMINDER_TAG in msgs[0].content
    # Original list-content message is untouched
    assert msgs[1].content == original_content


def test_reminder_uses_original_id_user_message_uses_derived_id():
    """Reminder takes original ID (position swap); user message gets {id}__user."""
    mw = _make_middleware()
    original_id = "original-id-abc"
    state = {"messages": [HumanMessage(content="Hello", id=original_id)]}

    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""), mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    assert result["messages"][0].id == original_id
    assert result["messages"][1].id == f"{original_id}__user"


def test_message_without_id_gets_stable_uuid():
    """If the original HumanMessage has no ID, a UUID is generated and used consistently."""
    mw = _make_middleware()
    state = {"messages": [HumanMessage(content="Hello", id=None)]}

    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""), mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is not None
    reminder_id = result["messages"][0].id
    user_id = result["messages"][1].id
    assert reminder_id is not None
    assert reminder_id != "None"
    assert user_id == f"{reminder_id}__user"


def test_user_message_containing_system_reminder_tag_does_not_prevent_injection():
    """A user message containing '<system-reminder>' must not be mistaken for a reminder."""
    mw = _make_middleware()
    state = {
        "messages": [
            HumanMessage(content="What is <system-reminder>?", id="msg-1"),
        ]
    }

    with mock.patch("deerflow.agents.lead_agent.prompt._get_memory_context", return_value=""), mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-08, Friday"
        result = mw.before_agent(state, _fake_runtime())

    # Injection must happen — the user message does NOT carry the reminder flag
    assert result is not None
    assert result["messages"][0].additional_kwargs.get(_DYNAMIC_CONTEXT_REMINDER_KEY) is True


# ---------------------------------------------------------------------------
# Midnight crossing
# ---------------------------------------------------------------------------


def test_midnight_crossing_injects_date_update_as_separate_message():
    """When the date has changed, a separate date-update reminder is injected before
    the current turn's HumanMessage using the ID-swap technique."""
    mw = _make_middleware()
    reminder_content = "<system-reminder>\n<current_date>2026-05-08, Friday</current_date>\n</system-reminder>"
    state = {
        "messages": [
            _reminder_msg(reminder_content, "msg-1"),
            HumanMessage(content="Hello", id="msg-1__user"),
            AIMessage(content="Response"),
            HumanMessage(content="Good morning", id="msg-2"),
        ]
    }

    with mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-09, Saturday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is not None
    msgs = result["messages"]
    assert len(msgs) == 2

    # Date-update reminder takes the current message's ID
    assert msgs[0].id == "msg-2"
    assert msgs[0].additional_kwargs.get(_DYNAMIC_CONTEXT_REMINDER_KEY) is True
    assert _SYSTEM_REMINDER_TAG in msgs[0].content
    assert "<current_date>2026-05-09, Saturday</current_date>" in msgs[0].content
    assert "Good morning" not in msgs[0].content  # reminder only

    # Original user text appended with derived ID
    assert msgs[1].id == "msg-2__user"
    assert msgs[1].content == "Good morning"


def test_midnight_crossing_id_swap():
    """Date-update reminder uses original ID; user message uses {id}__user."""
    mw = _make_middleware()
    reminder_content = "<system-reminder>\n<current_date>2026-05-08, Friday</current_date>\n</system-reminder>"
    state = {
        "messages": [
            _reminder_msg(reminder_content, "msg-1"),
            HumanMessage(content="Next day message", id="msg-2"),
        ]
    }

    with mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-09, Saturday"
        result = mw.before_agent(state, _fake_runtime())

    assert result["messages"][0].id == "msg-2"
    assert result["messages"][1].id == "msg-2__user"


def test_no_second_midnight_injection_once_date_updated():
    """After a midnight update is persisted, the same-day path skips re-injection."""
    mw = _make_middleware()
    state = {
        "messages": [
            _reminder_msg(
                "<system-reminder>\n<current_date>2026-05-08, Friday</current_date>\n</system-reminder>",
                "msg-1",
                date="2026-05-08, Friday",
            ),
            HumanMessage(content="Hello", id="msg-1__user"),
            AIMessage(content="Response"),
            _reminder_msg(
                "<system-reminder>\n<current_date>2026-05-09, Saturday</current_date>\n</system-reminder>",
                "msg-2",
                date="2026-05-09, Saturday",
            ),
            HumanMessage(content="Good morning", id="msg-2__user"),
            AIMessage(content="Good morning!"),
            HumanMessage(content="Third turn", id="msg-3"),
        ]
    }

    with mock.patch("deerflow.agents.middlewares.dynamic_context_middleware.datetime") as mock_dt:
        mock_dt.now.return_value.strftime.return_value = "2026-05-09, Saturday"
        result = mw.before_agent(state, _fake_runtime())

    assert result is None  # same day as last injected date → no update
