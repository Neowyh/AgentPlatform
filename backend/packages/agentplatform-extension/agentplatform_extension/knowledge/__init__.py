"""Run-scoped knowledge authorization for the AgentPlatform extension."""

from agentplatform_extension.knowledge.context import KnowledgeRuntimeContext
from agentplatform_extension.knowledge.retrieval_receipts import build_denied_retrieval_receipt, build_retrieval_receipt
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
    "build_retrieval_receipt",
    "build_denied_retrieval_receipt",
    "adapt_knowledge_tools",
]
