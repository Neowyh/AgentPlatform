"""AgentPlatform adapter binding frozen canonical Agents into DeerFlow assembly.

Enterprise resource resolution stays in the control plane.  This adapter is
the only Gateway-facing seam that bridges a frozen canonical Agent closure
(UUID / version / hash) into the DeerFlow lead assembly via
``FrozenAgentInputs`` — the assembly builds the graph from that frozen closure
instead of mutable on-disk agent state, and withholds agent self-mutation.
"""

from __future__ import annotations

from typing import Any

from deerflow.agents.lead_agent.agent import FrozenAgentInputs, assemble_lead_agent


def build_canonical_agent_factory(
    definition: Any,
    skills: list[Any],
    *,
    runner_tool_groups: frozenset[str] | None,
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
        },
    )

    def factory(config: Any, app_config: Any = None):
        return assemble_lead_agent(config, app_config=app_config, frozen=frozen).graph

    return factory
