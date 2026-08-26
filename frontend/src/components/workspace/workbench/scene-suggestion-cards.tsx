"use client";

import { BotIcon, ChevronRightIcon } from "lucide-react";
import Link from "next/link";

import { type Agent, useAgents } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

export function agentRouteIdentity(agent: Agent) {
  return agent.resource_id ?? agent.name;
}

export function buildAgentPrompt(template: string, agent: Agent) {
  return template.replace("{name}", agent.name);
}

export function agentChatUrlWithPrompt(agent: Agent, prompt: string) {
  return `/workspace/agents/${encodeURIComponent(agentRouteIdentity(agent))}/chats/new?prompt=${encodeURIComponent(prompt)}`;
}

export function SceneSuggestionCards({ max = 4 }: { max?: number }) {
  const { t } = useI18n();
  const { agents = [] } = useAgents();

  if (agents.length === 0) {
    return null;
  }

  return (
    <section className="space-y-2">
      <h2 className="text-muted-foreground text-sm font-medium">
        {t.workbench.tryAsking}
      </h2>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {agents.slice(0, max).map((agent) => (
          <Link
            key={agent.resource_id ?? agent.name}
            href={agentChatUrlWithPrompt(
              agent,
              buildAgentPrompt(t.workbench.promptTemplate, agent),
            )}
            className="bg-background/5 hover:bg-background/10 group flex flex-col gap-1 rounded-xl border p-3 transition-colors"
            data-testid="workbench-suggestion-card"
          >
            <span className="flex items-center gap-1.5 text-sm font-medium">
              <BotIcon className="text-primary size-4 shrink-0" />
              <span className="truncate">{agent.name}</span>
              <ChevronRightIcon className="text-muted-foreground ml-auto size-4 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
            </span>
            {agent.description && (
              <span className="text-muted-foreground line-clamp-2 text-xs">
                {agent.description}
              </span>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
