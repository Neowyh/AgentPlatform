"""AgentPlatform adapter binding frozen canonical Agents into DeerFlow assembly.

Enterprise resource resolution stays in the control plane.  This adapter is
the only Gateway-facing seam that bridges a frozen canonical Agent closure
(UUID / version / hash) into the DeerFlow lead assembly via
``FrozenAgentInputs`` — the assembly builds the graph from that frozen closure
instead of mutable on-disk agent state, and withholds agent self-mutation.
"""

from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from typing import Any

from agentplatform_extension.knowledge.runtime_adapter import adapt_knowledge_tools
from agentplatform_extension.knowledge.scope import KnowledgeScope
from agentplatform_extension.local_runtime import (
    LocalAuthorization,
    LocalToolExecutor,
    build_langchain_local_tools,
)

from deerflow.agents.lead_agent.agent import FrozenAgentInputs, assemble_lead_agent

_KNOWLEDGE_TOOL_ASSEMBLY_LOCK = Lock()


def build_canonical_agent_factory(
    definition: Any,
    skills: list[Any],
    *,
    runner_tool_groups: frozenset[str] | None,
    knowledge_scope: KnowledgeScope | None = None,
    local_authorization: LocalAuthorization | None = None,
    local_tool_executor: LocalToolExecutor | None = None,
    local_tool_descriptors: Mapping[str, Mapping[str, Any]] | None = None,
):
    """Return a factory bound to one immutable canonical resource snapshot."""

    frozen = FrozenAgentInputs(
        agent_name=definition.resource_id,
        config=definition.config,
        soul=definition.soul,
        skills=list(skills),
        runner_tool_groups=runner_tool_groups,
        resource={
            "resource_id": definition.resource_id,
            "version": definition.version,
            "content_hash": definition.content_hash,
            **(
                {"knowledge_scope": knowledge_scope.model_mapping()}
                if knowledge_scope is not None
                else {}
            ),
        },
    )

    def factory(config: Any, app_config: Any = None):
        if knowledge_scope is None and local_tool_executor is None:
            return assemble_lead_agent(
                config, app_config=app_config, frozen=frozen
            ).graph
        # The upstream assembly resolves tools before compiling the graph. A
        # short-lived module-level seam lets the extension replace only the
        # knowledge tool at that point, without changing the DeerFlow fork.
        import deerflow.tools as deerflow_tools

        with _KNOWLEDGE_TOOL_ASSEMBLY_LOCK:
            original = deerflow_tools.get_available_tools

            def scoped_tools(*args: Any, **kwargs: Any) -> list[Any]:
                tools = original(*args, **kwargs)
                if knowledge_scope is not None:
                    tools = adapt_knowledge_tools(tools, knowledge_scope)
                if local_tool_executor is not None and local_authorization is not None:
                    tools = [
                        *tools,
                        *build_langchain_local_tools(
                            local_authorization,
                            local_tool_executor,
                            descriptors=local_tool_descriptors,
                        ),
                    ]
                return tools

            deerflow_tools.get_available_tools = scoped_tools
            try:
                return assemble_lead_agent(
                    config, app_config=app_config, frozen=frozen
                ).graph
            finally:
                deerflow_tools.get_available_tools = original

    factory.knowledge_scope = (
        knowledge_scope.model_mapping() if knowledge_scope is not None else None
    )
    return factory
