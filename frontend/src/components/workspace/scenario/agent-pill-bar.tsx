"use client";

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
  return (
    <ChipBar
      items={pills.map((pill) => ({ id: pill.agentSlug, label: pill.label }))}
      selectedId={selectedSlug}
      onSelect={onSelect}
      variant="pill"
      testId="agent-pill-bar"
    />
  );
}
