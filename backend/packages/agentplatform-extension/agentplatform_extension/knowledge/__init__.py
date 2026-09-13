"""Run-scoped knowledge authorization for the AgentPlatform extension."""

from agentplatform_extension.knowledge.context import KnowledgeRuntimeContext
from agentplatform_extension.knowledge.runtime_adapter import (
    KNOWLEDGE_ACCESS_DENIED,
    KnowledgeAccessDenied,
    KnowledgeRuntimeAdapter,
    adapt_knowledge_tools,
)
from agentplatform_extension.knowledge.scope import KnowledgeScope

__all__ = [
    "KNOWLEDGE_ACCESS_DENIED",
    "KnowledgeAccessDenied",
    "KnowledgeRuntimeAdapter",
    "KnowledgeRuntimeContext",
    "KnowledgeScope",
    "adapt_knowledge_tools",
]
