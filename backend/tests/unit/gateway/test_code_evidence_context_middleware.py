"""Enterprise code-evidence package context middleware.

The gateway freezes a server-derived code-evidence summary into the run context
(``code_package_id`` + ``code_evidence_manifest``; see app/gateway/run_preparation.py).
The runtime must tell the lead agent that the package was expanded server-side,
at a fixed virtual root, with the trusted counts — the agent must not ask the
user to unzip anything and must not treat the original ZIP as readable source.

This used to live inside the legacy ideer DynamicContextMiddleware; upstream
owns that middleware now, so the enterprise concern is a separate middleware
contributed through the config-declared ``extensions.middlewares`` surface.
"""

from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agentplatform.code_evidence_context_middleware import (
    CODE_EVIDENCE_REMINDER_KEY,
    CodeEvidenceContextMiddleware,
)


def _runtime(manifest=None, package_id="pkg-123"):
    context = {}
    if package_id is not None:
        context["code_package_id"] = package_id
    if manifest is not None:
        context["code_evidence_manifest"] = manifest
    return SimpleNamespace(context=context)


def _manifest():
    return {
        "original_filename": "src.zip",
        "accepted_count": 3,
        "excluded_count": 2,
        "rejected_count": 1,
    }


def test_injects_trusted_summary_reminder_on_first_turn():
    mw = CodeEvidenceContextMiddleware()
    state = {"messages": [HumanMessage(content="分析代码", id="msg-1")]}
    result = mw.before_agent(state, _runtime(_manifest()))

    assert result is not None
    (reminder,) = result["messages"]
    assert isinstance(reminder, SystemMessage)
    assert reminder.additional_kwargs.get("hide_from_ui") is True
    assert reminder.additional_kwargs.get(CODE_EVIDENCE_REMINDER_KEY) == "pkg-123"
    content = reminder.content
    assert "服务端已安全展开代码包" in content
    assert "/mnt/user-data/code-evidence/pkg-123/source" in content
    assert "src.zip" in content
    assert "已接收文件：3 个；已排除：2 项；已拒绝：1 项" in content
    assert "不要要求用户本地解压" in content


def test_skips_when_no_package_in_context():
    mw = CodeEvidenceContextMiddleware()
    state = {"messages": [HumanMessage(content="hello", id="msg-1")]}
    assert mw.before_agent(state, _runtime(package_id=None)) is None


def test_skips_when_manifest_is_not_a_dict():
    mw = CodeEvidenceContextMiddleware()
    state = {"messages": [HumanMessage(content="hello", id="msg-1")]}
    assert mw.before_agent(state, _runtime(manifest="bogus")) is None


def test_injects_once_per_package_across_turns():
    """The reminder persists via checkpoint, so later turns must not duplicate it."""
    mw = CodeEvidenceContextMiddleware()
    reminder = SystemMessage(
        content="<code-evidence-package>…</code-evidence-package>",
        additional_kwargs={"hide_from_ui": True, CODE_EVIDENCE_REMINDER_KEY: "pkg-123"},
    )
    state = {
        "messages": [
            HumanMessage(content="分析代码", id="msg-1"),
            reminder,
            AIMessage(content="done"),
            HumanMessage(content="再看一遍", id="msg-2"),
        ]
    }
    assert mw.before_agent(state, _runtime(_manifest())) is None


def test_reinjects_for_a_different_package():
    mw = CodeEvidenceContextMiddleware()
    stale = SystemMessage(
        content="<code-evidence-package>…</code-evidence-package>",
        additional_kwargs={"hide_from_ui": True, CODE_EVIDENCE_REMINDER_KEY: "pkg-old"},
    )
    state = {"messages": [HumanMessage(content="继续", id="msg-2"), stale]}
    result = mw.before_agent(state, _runtime(_manifest(), package_id="pkg-new"))
    assert result is not None
    (reminder,) = result["messages"]
    assert reminder.additional_kwargs.get(CODE_EVIDENCE_REMINDER_KEY) == "pkg-new"


def test_no_messages_returns_none():
    mw = CodeEvidenceContextMiddleware()
    assert mw.before_agent({"messages": []}, _runtime(_manifest())) is None
