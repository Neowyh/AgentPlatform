"use client";

import { BotIcon } from "lucide-react";
import Link from "next/link";

import { useAgents } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

import { agentRouteIdentity } from "./scene-suggestion-cards";

export function AgentShowcase({ max = 6 }: { max?: number }) {
  const { t } = useI18n();
  const { agents = [], isLoading, error } = useAgents();

  if (isLoading) {
    return null;
  }

  if (error && agents.length === 0) {
    return (
      <section className="space-y-2">
        <h2 className="text-muted-foreground text-sm font-medium">
          {t.workbench.agentsTitle}
        </h2>
        <p className="text-muted-foreground text-xs">{t.workbench.loadError}</p>
      </section>
    );
  }

  if (agents.length === 0) {
    return (
      <section className="space-y-2">
        <h2 className="text-muted-foreground text-sm font-medium">
          {t.workbench.agentsTitle}
        </h2>
        <p className="text-muted-foreground text-xs">
          {t.workbench.emptyAgents}
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-muted-foreground text-sm font-medium">
          {t.workbench.agentsTitle}
        </h2>
        <Link
          href="/workspace/agents"
          className="text-muted-foreground hover:text-foreground text-xs"
        >
          {t.workbench.viewAllAgents}
        </Link>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {agents.slice(0, max).map((agent) => (
          <Link
            key={agent.resource_id ?? agent.name}
            href={`/workspace/agents/${encodeURIComponent(agentRouteIdentity(agent))}/chats/new`}
            className="bg-background/5 hover:bg-background/10 flex items-center gap-2 rounded-xl border p-2.5 transition-colors"
            data-testid="workbench-agent-item"
          >
            <div className="bg-primary/10 text-primary flex size-8 shrink-0 items-center justify-center rounded-lg">
              <BotIcon className="size-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{agent.name}</p>
              {agent.description && (
                <p className="text-muted-foreground line-clamp-1 text-xs">
                  {agent.description}
                </p>
              )}
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
