"""Regression guards for deferred-tool promotion (issue #2884 semantics).

Upstream replaced the module-level ContextVar ``DeferredToolRegistry`` with a
per-agent-build design:

- ``assemble_deferred_tools`` derives ``DeferredToolSetup`` (tool_search tool,
  deferred names, catalog hash) from the MCP candidates of one build.
- ``DeferredToolFilterMiddleware(deferred_names, catalog_hash)`` hides
  still-deferred schemas and reads promotions from graph state
  (``state["promoted"]``, scoped by catalog hash).
- ``tool_search`` promotes by returning ``Command(update={"promoted": ...})``.

The invariant issue #2884 asked for — a re-entrant toolset rebuild must not
wipe an in-flight promotion — now holds structurally: promotions live in graph
state, and identical candidate catalogs hash identically, so a rebuild (e.g.
``task_tool`` spawning a subagent) can neither see nor reset them.
"""

from __future__ import annotations

from typing import Annotated, Any
from unittest.mock import MagicMock

import pytest
from langchain.agents import AgentState
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import tool as as_tool

from deerflow.agents.thread_state import PromotedTools, merge_promoted
from deerflow.tools.builtins.tool_search import assemble_deferred_tools
from deerflow.tools.mcp_metadata import tag_mcp_tool


class FakeToolCallingModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel + no-op bind_tools so create_agent works."""

    def bind_tools(  # type: ignore[override]
        self,
        tools: Any,
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> Runnable:
        return self


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@as_tool
def plain_tool(query: str) -> str:
    """A non-MCP config tool that must never be deferred."""
    return f"plain result for {query}"


@as_tool
def fake_mcp_search(query: str) -> str:
    """Pretend to search a knowledge base for the given query."""
    return f"results for {query}"


@as_tool
def fake_mcp_fetch(url: str) -> str:
    """Pretend to fetch a page at the given URL."""
    return f"content of {url}"


@as_tool
def duplicate_tool(query: str) -> str:
    """Fixture for a config tool colliding with an MCP tool."""
    return f"config result for {query}"


@as_tool("duplicate_tool")
def duplicate_tool_mcp(query: str) -> str:
    """The MCP twin that loses the name collision and is dropped."""
    return f"mcp result for {query}"


def _mcp(*tools) -> list:
    for t in tools:
        tag_mcp_tool(t)
    return list(tools)


class _PromotedState(AgentState):
    """Agent state with the production promoted-tools channel."""

    promoted: Annotated[PromotedTools | None, merge_promoted]


@pytest.fixture(autouse=True)
def _supply_env(monkeypatch: pytest.MonkeyPatch):
    """config.yaml references $OPENAI_API_KEY at parse time; supply a placeholder."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-not-used")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.invalid")


# ---------------------------------------------------------------------------
# A. Unit boundary — catalog hashing keeps rebuilds promotion-compatible
# ---------------------------------------------------------------------------


def test_reassembled_catalog_keeps_promotions_valid(monkeypatch: pytest.MonkeyPatch):
    """Identical candidate catalogs hash identically across rebuilds.

    Issue #2884's failure mode was a re-entrant ``get_available_tools`` call
    resetting a global registry. Upstream derives the deferred set from the
    candidates and scopes promotions by catalog hash, so rebuilding the same
    catalog (e.g. ``task_tool`` building a subagent's toolset) yields the same
    hash and the graph-state promotion stays valid.
    """
    candidates = [plain_tool] + _mcp(fake_mcp_search, fake_mcp_fetch)

    _, setup1 = assemble_deferred_tools(candidates, enabled=True)
    _, setup2 = assemble_deferred_tools(candidates, enabled=True)

    assert setup1.deferred_names == frozenset({"fake_mcp_search", "fake_mcp_fetch"})
    assert setup1.catalog_hash == setup2.catalog_hash
    assert setup1.catalog_hash is not None


def test_config_tool_collision_is_active_while_mcp_names_are_deferred(monkeypatch: pytest.MonkeyPatch):
    """A config tool wins a name collision without being deferred with MCP tools."""
    from deerflow.config.extensions_config import ExtensionsConfig, McpServerConfig
    from deerflow.tools.tools import get_available_tools

    config_tool = MagicMock(name="config_tool")
    config_tool.name = "duplicate_tool"
    config_tool.group = "core"
    config_tool.use = "tests:duplicate_tool"
    config_tool.requires_network = False
    config = MagicMock(
        tools=[config_tool],
        models=[],
        skill_evolution=MagicMock(enabled=False),
        tool_search=MagicMock(enabled=True),
        acp_agents={},
    )
    config.get_model_config.return_value = None
    monkeypatch.setattr("deerflow.tools.tools.get_app_config", lambda: config)
    monkeypatch.setattr("deerflow.tools.tools.resolve_variable", lambda *_args: duplicate_tool)
    monkeypatch.setattr(
        "deerflow.config.extensions_config.ExtensionsConfig.from_file",
        classmethod(
            lambda cls: ExtensionsConfig(
                mcpServers={"fake-server": McpServerConfig(type="stdio", command="echo", enabled=True)},
            )
        ),
    )
    monkeypatch.setattr(
        "deerflow.mcp.cache.get_cached_mcp_tools",
        lambda: _mcp(duplicate_tool_mcp, fake_mcp_search),
    )

    result = get_available_tools()

    assert [tool.name for tool in result if tool.name == "duplicate_tool"] == ["duplicate_tool"]
    assert next(tool for tool in result if tool.name == "duplicate_tool") is duplicate_tool

    _, setup = assemble_deferred_tools(result, enabled=True)
    assert setup.deferred_names == {"fake_mcp_search"}, "the config tool must stay active, only the MCP tool is deferred"


# ---------------------------------------------------------------------------
# B. Graph boundary — promotion becomes visible to the model on the next turn
# ---------------------------------------------------------------------------


class _RecordingModel(FakeToolCallingModel):
    """Records the tool names bound on each turn."""

    bound_tools_per_turn: list[list[str]] = []

    def bind_tools(  # type: ignore[override]
        self,
        tools: Any,
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> Runnable:
        self.bound_tools_per_turn.append([getattr(t, "name", repr(t)) for t in tools])
        return self


def _two_turn_model() -> _RecordingModel:
    return _RecordingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "tool_search",
                        "args": {"query": "select:fake_mcp_search"},
                        "id": "call_search_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "fake_mcp_search",
                        "args": {"query": "hello"},
                        "id": "call_mcp_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="all done"),
        ]
    )


def test_promoted_tool_is_visible_to_model_on_second_turn():
    """End-to-end: drive a real create_agent graph through two turns.

    Turn 1 must hide the deferred MCP schema and expose ``tool_search``; after
    ``tool_search`` promotes ``fake_mcp_search`` (a ``promoted`` graph-state
    update scoped by catalog hash), turn 2's bind_tools must include it.
    """
    from langchain.agents import create_agent

    from deerflow.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware

    candidates = [plain_tool] + _mcp(fake_mcp_search, fake_mcp_fetch)
    final_tools, setup = assemble_deferred_tools(candidates, enabled=True)
    assert {"tool_search", "plain_tool", "fake_mcp_search", "fake_mcp_fetch"} <= {t.name for t in final_tools}

    model = _two_turn_model()
    model.bound_tools_per_turn = []  # reset class-level recorder

    graph = create_agent(
        model=model,
        tools=final_tools,
        middleware=[DeferredToolFilterMiddleware(setup.deferred_names, setup.catalog_hash)],
        state_schema=_PromotedState,
        system_prompt="deferred-promotion-repro",
    )

    graph.invoke({"messages": [HumanMessage(content="use the search tool")]})

    # Turn 1: model should NOT see fake_mcp_search (it's deferred)
    turn1 = set(model.bound_tools_per_turn[0])
    assert "fake_mcp_search" not in turn1, f"Turn 1 sanity: deferred tools must be hidden from the model. Saw: {turn1!r}"
    assert "tool_search" in turn1, f"Turn 1 sanity: tool_search must be visible so the agent can discover. Saw: {turn1!r}"

    # Turn 2: AFTER tool_search promoted fake_mcp_search, the model must see it.
    assert len(model.bound_tools_per_turn) >= 2, f"Expected at least 2 model turns, got {len(model.bound_tools_per_turn)}"
    turn2 = set(model.bound_tools_per_turn[1])
    assert "fake_mcp_search" in turn2, f"tool_search promoted fake_mcp_search in turn 1, but the deferred-tool filter still hid it from the model in turn 2. Turn 2 bound tools: {turn2!r}"


def test_stale_catalog_hash_does_not_expose_promoted_tool():
    """A promotion recorded under a different catalog hash must stay hidden."""
    from langchain.agents import create_agent

    from deerflow.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware

    candidates = [plain_tool] + _mcp(fake_mcp_search, fake_mcp_fetch)
    _, setup = assemble_deferred_tools(candidates, enabled=True)
    stale_hash = ("0" * 16) if setup.catalog_hash != "0" * 16 else "f" * 16

    model = _RecordingModel(
        responses=[
            AIMessage(content=""),  # no tool call — just observe the bound tools
        ]
    )
    model.bound_tools_per_turn = []

    graph = create_agent(
        model=model,
        tools=assemble_deferred_tools(candidates, enabled=True)[0],
        middleware=[DeferredToolFilterMiddleware(setup.deferred_names, setup.catalog_hash)],
        state_schema=_PromotedState,
        system_prompt="deferred-promotion-stale-hash",
    )
    graph.invoke(
        {
            "messages": [HumanMessage(content="hello")],
            "promoted": {"catalog_hash": stale_hash, "names": ["fake_mcp_search"]},
        }
    )

    turn1 = set(model.bound_tools_per_turn[0])
    assert "fake_mcp_search" not in turn1, f"A promotion from a stale catalog must not expose the tool. Saw: {turn1!r}"
    assert "tool_search" in turn1
