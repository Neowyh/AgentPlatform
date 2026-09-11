"""Tool-boundary enforcement for logical knowledge selectors."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any

from agentplatform_extension.knowledge.scope import KnowledgeScope

KNOWLEDGE_ACCESS_DENIED = "KNOWLEDGE_ACCESS_DENIED"


class KnowledgeAccessDenied(PermissionError):
    code = KNOWLEDGE_ACCESS_DENIED


class KnowledgeRuntimeAdapter:
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
        result = self.search(query, dataset_ids=[resolved])
        return await result if inspect.isawaitable(result) else result


def adapt_knowledge_tools(tools: list[Any], scope: KnowledgeScope) -> list[Any]:
    """Replace a provider knowledge tool with a scope-enforcing wrapper."""
    adapted: list[Any] = []
    for tool in tools:
        if getattr(tool, "name", None) != "knowledge_search":
            adapted.append(tool)
            continue
        original = tool

        class _ScopedTool:
            name = "knowledge_search"
            description = getattr(original, "description", "")

            @staticmethod
            def _arguments(args: Mapping[str, Any]) -> tuple[str, str]:
                query = args.get("query")
                logical_kb = args.get("knowledge_base")
                if not isinstance(query, str) or not isinstance(logical_kb, str):
                    raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED)
                return query, logical_kb

            async def ainvoke(self, args: Mapping[str, Any]) -> Any:
                query, logical_kb = self._arguments(args)
                provider = original.ainvoke if hasattr(original, "ainvoke") else original.invoke
                return await KnowledgeRuntimeAdapter(scope, provider).search_knowledge(query, logical_kb=logical_kb)

            def invoke(self, args: Mapping[str, Any]) -> Any:
                query, logical_kb = self._arguments(args)
                provider = original.invoke
                try:
                    return provider(query, dataset_ids=[scope.resolve(logical_kb)])
                except KeyError as exc:
                    raise KnowledgeAccessDenied(KNOWLEDGE_ACCESS_DENIED) from exc

        adapted.append(_ScopedTool())
    return adapted
