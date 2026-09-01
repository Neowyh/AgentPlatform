"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { AgentCard } from "@/components/workspace/agents/agent-card";
import { useAgents } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

export function ExpertList() {
  const { t } = useI18n();
  const { agents, isLoading } = useAgents();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button asChild>
          <Link href="/workspace/agents/new">{t.agents.newAgent}</Link>
        </Button>
      </div>
      {agents && agents.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <AgentCard key={agent.name} agent={agent} />
          ))}
        </div>
      ) : (
        <div className="text-muted-foreground">No experts found</div>
      )}
    </div>
  );
}
