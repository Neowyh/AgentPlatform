"use client";

import { useAgents } from "@/core/agents/hooks";
import {
  findAgentForPill,
  agentDescription,
} from "@/core/scenarios/descriptions";
import type { AgentPill } from "@/core/scenarios/types";

import { ChipBar } from "./chip-bar";

interface AgentPillBarProps {
  pills: AgentPill[];
  selectedSlug: string | null;
  onSelect: (agentSlug: string) => void;
}

export function AgentPillBar({
  pills,
  selectedSlug,
  onSelect,
}: AgentPillBarProps) {
  const { agents } = useAgents();
  return (
    <ChipBar
      items={pills.map((pill) => {
        const agent = findAgentForPill(agents, pill.agentSlug);
        return {
          id: pill.agentSlug,
          label: pill.label,
          description: agent ? agentDescription(agent) : undefined,
        };
      })}
      selectedId={selectedSlug}
      onSelect={onSelect}
      variant="pill"
      testId="agent-pill-bar"
    />
  );
}
