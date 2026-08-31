"use client";

import { getPillsByScenario, getChipsByPill } from "@/core/scenarios/config";
import type {
  ChipSelection,
  PillSelection,
  ScenarioId,
} from "@/core/scenarios/types";

import { AgentPillBar } from "./agent-pill-bar";
import { TaskChipBar } from "./task-chip-bar";

interface ScenarioCascadeBarProps {
  selectedScenario: ScenarioId | null;
  selectedPill: PillSelection;
  selectedChip: ChipSelection;
  onTogglePill: (agentSlug: string) => void;
  onToggleChip: (taskId: string) => void;
}

export function ScenarioCascadeBar({
  selectedScenario,
  selectedPill,
  selectedChip,
  onTogglePill,
  onToggleChip,
}: ScenarioCascadeBarProps) {
  const pills = selectedScenario ? getPillsByScenario(selectedScenario) : [];
  const chips =
    selectedPill && selectedScenario
      ? getChipsByPill(selectedScenario, selectedPill.agentSlug)
      : [];

  return (
    <div className="min-h-10 w-full" data-testid="scenario-cascade-bar">
      {selectedScenario && !selectedPill && pills.length > 0 && (
        <AgentPillBar
          pills={pills}
          selectedSlug={null}
          onSelect={onTogglePill}
        />
      )}
      {selectedPill && chips.length > 0 && (
        <TaskChipBar
          chips={chips}
          selectedTaskId={selectedChip?.taskId ?? null}
          onSelect={onToggleChip}
        />
      )}
    </div>
  );
}
