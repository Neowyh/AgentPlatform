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
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

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


@pytest.mark.asyncio
async def test_runtime_adapter_passes_ready_document_allowlist_to_async_provider() -> None:
    calls: list[dict] = []

    async def provider(query: str, *, dataset_ids: list[str], document_ids: list[str]) -> str:
        calls.append({"query": query, "dataset_ids": dataset_ids, "document_ids": document_ids})
        return "ok"

    scope = KnowledgeScope.from_bindings({"docs": "opaque-dataset"}, ready_document_ids={"opaque-dataset": ["ready-1"]})
    assert await KnowledgeRuntimeAdapter(scope, provider).search_knowledge("find it", logical_kb="docs") == "ok"
    assert calls == [{"query": "find it", "dataset_ids": ["opaque-dataset"], "document_ids": ["ready-1"]}]


@pytest.mark.asyncio
async def test_runtime_adapter_rejects_provider_without_document_filtering() -> None:
    calls: list[dict] = []

    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        calls.append({"query": query, "dataset_ids": dataset_ids})
        return "unsafe"

    scope = KnowledgeScope.from_bindings({"docs": "opaque-dataset"}, ready_document_ids={"opaque-dataset": ["ready-1"]})
    with pytest.raises(KnowledgeAccessDenied, match=KNOWLEDGE_ACCESS_DENIED):
        await KnowledgeRuntimeAdapter(scope, provider).search_knowledge("find it", logical_kb="docs")
    assert calls == []


def test_delegation_can_only_narrow_scope() -> None:
    parent = KnowledgeRuntimeContext("run-1", KnowledgeScope.from_bindings({"a": "da", "b": "db"}))
    child = parent.for_delegation(KnowledgeScope.from_bindings({"b": "db"}))
    assert child.scope.as_mapping()["bindings"] == {"b": "db"}


def test_scope_keeps_platform_ready_document_allowlist_when_delegating() -> None:
    parent = KnowledgeScope.from_bindings({"a": "da", "b": "db"}, ready_document_ids={"da": ["doc-a"]})
    child = parent.intersect(KnowledgeScope.from_bindings({"a": "da"}))

    assert child.document_ids_for("da") == ("doc-a",)
    assert child.document_ids_for("db") is None


@pytest.mark.asyncio
async def test_adapted_tool_passes_only_resolved_dataset_to_provider() -> None:
    calls: list[dict] = []

    async def provider(query: str, *, dataset_ids: list[str]) -> str:
        calls.append({"query": query, "dataset_ids": dataset_ids})
        return "ok"

    tool = type("Tool", (), {"name": "knowledge_search", "coroutine": staticmethod(provider), "description": "search"})()
    adapted = adapt_knowledge_tools([tool], KnowledgeScope.from_bindings({"docs": "opaque"}))[0]

    assert isinstance(adapted, BaseTool)
    ToolNode([adapted])
    assert await adapted.ainvoke({"query": "find", "knowledge_base": "docs"}) == "ok"
    assert calls == [{"query": "find", "dataset_ids": ["opaque"]}]
    with pytest.raises(KnowledgeAccessDenied):
        await adapted.ainvoke({"query": "find", "knowledge_base": "opaque"})
    with pytest.raises(Exception):
        await adapted.ainvoke({"query": "find", "knowledge_base": "docs", "dataset_id": "opaque"})


def test_adapted_sync_tool_passes_ready_document_allowlist_to_provider() -> None:
    calls: list[dict] = []

    def provider(query: str, *, dataset_ids: list[str], document_ids: list[str]) -> str:
        calls.append({"query": query, "dataset_ids": dataset_ids, "document_ids": document_ids})
        return "ok"

    tool = type("Tool", (), {"name": "knowledge_search", "func": staticmethod(provider), "description": "search"})()
    scope = KnowledgeScope.from_bindings({"docs": "opaque"}, ready_document_ids={"opaque": ["ready-1"]})
    adapted = adapt_knowledge_tools([tool], scope)[0]

    assert adapted.invoke({"query": "find", "knowledge_base": "docs"}) == "ok"
    assert calls == [{"query": "find", "dataset_ids": ["opaque"], "document_ids": ["ready-1"]}]


def test_adapted_tool_exposes_logical_selector_schema_without_provider_id() -> None:
    tool = type("Tool", (), {"name": "knowledge_search", "coroutine": lambda *_args, **_kwargs: None})()
    adapted = adapt_knowledge_tools([tool], KnowledgeScope.from_bindings({"docs": "opaque"}))[0]

    schema = adapted.args_schema.model_json_schema()
    assert set(schema["properties"]) == {"query", "knowledge_base"}
    assert "dataset_id" not in schema["properties"]
    assert schema["required"] == ["query", "knowledge_base"]
