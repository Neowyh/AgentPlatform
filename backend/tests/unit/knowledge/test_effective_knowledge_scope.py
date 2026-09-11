from __future__ import annotations

import pytest
from agentplatform_extension.knowledge.context import KnowledgeRuntimeContext
from agentplatform_extension.knowledge.runtime_adapter import (
    KNOWLEDGE_ACCESS_DENIED,
    KnowledgeAccessDenied,
    KnowledgeRuntimeAdapter,
    adapt_knowledge_tools,
)
from agentplatform_extension.knowledge.scope import KnowledgeScope

from app.agentplatform.knowledge.scope import calculate_effective_knowledge_scope


def test_effective_scope_is_the_intersection_of_all_vetoes() -> None:
    assert calculate_effective_knowledge_scope(
        {"public-docs": "dataset-public", "private-docs": "dataset-private", "hidden": "dataset-hidden"},
        caller_allowed={"public-docs", "private-docs"},
        workflow_allowed={"private-docs", "dataset-private"},
        runtime_allowed={"private-docs"},
        deployment_allowed={"dataset-private"},
    ) == {"private-docs": "dataset-private"}


def test_scope_is_fail_closed_for_unbound_and_empty_restrictions() -> None:
    assert calculate_effective_knowledge_scope({"unbound": None, "bound": "d"}) == {"bound": "d"}
    assert calculate_effective_knowledge_scope({"bound": "d"}, caller_allowed=()) == {}


@pytest.mark.asyncio
async def test_runtime_adapter_resolves_logical_selector_and_rejects_raw_ids() -> None:
    calls: list[dict] = []

    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        calls.append({"query": query, "dataset_ids": dataset_ids})
        return "ok"

    adapter = KnowledgeRuntimeAdapter(KnowledgeScope.from_bindings({"docs": "opaque-dataset"}), provider)
    assert await adapter.search_knowledge("find it", logical_kb="docs") == "ok"
    assert calls == [{"query": "find it", "dataset_ids": ["opaque-dataset"]}]
    with pytest.raises(KnowledgeAccessDenied, match=KNOWLEDGE_ACCESS_DENIED):
        await adapter.search_knowledge("find it", dataset_id="opaque-dataset")
    with pytest.raises(KnowledgeAccessDenied):
        await adapter.search_knowledge("find it", logical_kb="other")


def test_delegation_can_only_narrow_scope() -> None:
    parent = KnowledgeRuntimeContext("run-1", KnowledgeScope.from_bindings({"a": "da", "b": "db"}))
    child = parent.for_delegation(KnowledgeScope.from_bindings({"b": "db"}))
    assert child.scope.as_mapping()["bindings"] == {"b": "db"}


@pytest.mark.asyncio
async def test_adapted_tool_passes_only_resolved_dataset_to_provider() -> None:
    calls: list[dict] = []

    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        calls.append({"query": query, "dataset_ids": dataset_ids})
        return "ok"

    tool = type("Tool", (), {"name": "knowledge_search", "coroutine": staticmethod(provider), "description": "search"})()
    adapted = adapt_knowledge_tools([tool], KnowledgeScope.from_bindings({"docs": "opaque"}))[0]

    assert await adapted.ainvoke({"query": "find", "knowledge_base": "docs"}) == "ok"
    assert calls == [{"query": "find", "dataset_ids": ["opaque"]}]
    with pytest.raises(KnowledgeAccessDenied):
        await adapted.ainvoke({"query": "find", "knowledge_base": "opaque"})


def test_adapted_tool_exposes_logical_selector_schema_without_provider_id() -> None:
    tool = type("Tool", (), {"name": "knowledge_search", "coroutine": lambda *_args, **_kwargs: None})()
    adapted = adapt_knowledge_tools([tool], KnowledgeScope.from_bindings({"docs": "opaque"}))[0]

    schema = adapted.args_schema.model_json_schema()
    assert set(schema["properties"]) == {"query", "knowledge_base"}
    assert "dataset_id" not in schema["properties"]
    assert schema["required"] == ["query", "knowledge_base"]
