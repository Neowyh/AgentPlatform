"""Tool-boundary enforcement for logical knowledge selectors."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from agentplatform_extension.knowledge.scope import KnowledgeScope

KNOWLEDGE_ACCESS_DENIED = "KNOWLEDGE_ACCESS_DENIED"


class KnowledgeAccessDenied(PermissionError):
    """Raised when a Run requests a knowledge source outside its scope."""

    code = KNOWLEDGE_ACCESS_DENIED


class KnowledgeSearchInput(BaseModel):
    """Model-facing arguments for a run-scoped knowledge search."""

    query: str = Field(min_length=1)
    knowledge_base: str = Field(min_length=1, description="Logical knowledge base selector")
    model_config = ConfigDict(extra="forbid")


class KnowledgeRuntimeAdapter:
    """Resolve logical KB selectors and enforce the frozen dataset allowlist."""

    def __init__(self, scope: KnowledgeScope, search: Callable[..., Any]) -> None:
        self.scope = scope
        self.search = search

    async def search_knowledge(self, query: str, *, logical_kb: str | None = None, dataset_id: str | None = None) -> Any:
        if dataset_id is not None or logical_kb is None:
            raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED)
        try:
            resolved = self.scope.resolve(logical_kb)
        except KeyError as exc:
            raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED) from exc
        if _accepts_dataset_ids(self.search):
            result = self.search(query, dataset_ids=[resolved])
        else:
            result = _search_legacy_ragflow(self.search, query, resolved)
        return await result if inspect.isawaitable(result) else result


def _accepts_dataset_ids(search: Callable[..., Any]) -> bool:
    try:
        parameters = inspect.signature(search).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(parameter.name == "dataset_ids" or parameter.kind is parameter.VAR_KEYWORD for parameter in parameters)


async def _search_legacy_ragflow(search: Callable[..., Any], query: str, dataset_id: str) -> Any:
    """Use the unmodified provider implementation while retaining its helpers."""

    if "ragflow" not in getattr(search, "__module__", "").lower():
        raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED)
    from deerflow.community.ragflow import tools as provider

    settings, error = provider._settings_or_error()
    if settings is None:
        return error or "Error: Invalid RAGFlow settings for knowledge_search; check config.yaml."
    client = provider._build_client(settings)
    try:
        scoped_settings = settings.model_copy(update={"datasets": [dataset_id]})
        datasets, resolution_error = await provider._resolve_datasets(client, scoped_settings)
        if resolution_error is not None:
            return resolution_error
        if not datasets:
            return "Error: No RAGFlow datasets could be resolved; check knowledge_search in config.yaml."
        groups = provider._group_searchable_datasets(datasets)
        if not groups:
            return provider._NO_RELEVANT_CONTENT
        result = await provider._retrieve_dataset_groups(client, settings, query, groups)
        names_by_id = {dataset.dataset_id: dataset.name for dataset in datasets}
        formatted = provider.format_retrieval_result(
            result,
            dataset_names_by_id=names_by_id,
            max_chars_per_chunk=settings.max_chars_per_chunk,
            max_total_chars=settings.max_total_chars,
        )
        return provider._redact_api_key(formatted, provider._api_key(settings))
    except Exception as exc:
        return provider._tool_error(exc, settings)


def adapt_knowledge_tools(tools: list[Any], scope: KnowledgeScope) -> list[Any]:
    """Replace a provider knowledge tool with a scope-enforcing wrapper."""
    adapted: list[Any] = []
    for tool in tools:
        if getattr(tool, "name", None) != "knowledge_search":
            adapted.append(tool)
            continue
        if not scope.bindings:
            continue
        original = tool

        async def _async_search(query: str, knowledge_base: str) -> Any:
            provider = getattr(original, "coroutine", None)
            if provider is None:
                raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED)
            try:
                return await KnowledgeRuntimeAdapter(scope, provider).search_knowledge(query, logical_kb=knowledge_base)
            except TypeError as exc:
                raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED) from exc

        def _sync_search(query: str, knowledge_base: str) -> Any:
            provider = getattr(original, "func", None)
            if provider is None:
                raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED)
            try:
                return provider(query, dataset_ids=[scope.resolve(knowledge_base)])
            except (KeyError, TypeError) as exc:
                raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED) from exc

        adapted.append(
            StructuredTool.from_function(
                func=_sync_search,
                coroutine=_async_search,
                name="knowledge_search",
                description=getattr(original, "description", ""),
                args_schema=KnowledgeSearchInput,
            )
        )
    return adapted
