"use client";

import type {
  AgentPill,
  ChipSelection,
  PillSelection,
  ScenarioId,
} from "@/core/scenarios/types";

import { AgentPillBar } from "./agent-pill-bar";
import { TaskChipBar } from "./task-chip-bar";

interface AgentOrSkillBarProps {
  pills: AgentPill[];
  selectedPill: PillSelection;
  selectedChip: ChipSelection;
  onTogglePill: (scenarioId: ScenarioId, agentSlug: string) => void;
  onToggleChip: (
    scenarioId: ScenarioId,
    agentSlug: string,
    taskId: string,
  ) => void;
  scenarioId: ScenarioId;
}

export function AgentOrSkillBar({
  pills,
  selectedPill,
  selectedChip,
  onTogglePill,
  onToggleChip,
  scenarioId,
}: AgentOrSkillBarProps) {
  const activePill = pills.find((p) => p.agentSlug === selectedPill?.agentSlug);

  return (
    <div className="flex items-center gap-2" data-testid="agent-or-skill-bar">
      <AgentPillBar
        pills={pills}
        selectedSlug={selectedPill?.agentSlug ?? null}
        onSelect={(slug) => onTogglePill(scenarioId, slug)}
      />
      {activePill?.chips && activePill.chips.length > 0 && (
        <>
          <div className="text-muted-foreground/40 h-4 w-px shrink-0 bg-current" />
          <TaskChipBar
            chips={activePill.chips}
            selectedTaskId={selectedChip?.taskId ?? null}
            onSelect={(taskId) =>
              onToggleChip(scenarioId, activePill.agentSlug, taskId)
            }
          />
        </>
      )}
    </div>
  );
}
