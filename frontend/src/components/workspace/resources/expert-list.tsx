"use client";

import { AgentCard } from "@/components/workspace/agents/agent-card";
import { useAgents } from "@/core/agents";

export function ExpertList() {
  const { agents, isLoading } = useAgents();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (!agents || agents.length === 0) {
    return <div className="text-muted-foreground">No experts found</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {agents.map((agent) => (
        <AgentCard key={agent.name} agent={agent} />
      ))}
    </div>
  );
}
