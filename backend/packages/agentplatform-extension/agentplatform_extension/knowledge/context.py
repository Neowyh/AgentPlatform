"""Serializable runtime context for a frozen knowledge scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentplatform_extension.knowledge.scope import KnowledgeScope


@dataclass(frozen=True, slots=True)
class KnowledgeRuntimeContext:
    """Run identity and immutable knowledge authorization projection."""

    run_id: str
    scope: KnowledgeScope

    def as_mapping(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "knowledge_scope": self.scope.as_mapping()}

    def for_delegation(self, child_scope: KnowledgeScope | None = None) -> KnowledgeRuntimeContext:
        """Carry the parent scope into a child; delegation can only narrow it."""
        return KnowledgeRuntimeContext(self.run_id, self.scope.intersect(child_scope) if child_scope else self.scope)
