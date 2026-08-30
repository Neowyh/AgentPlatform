"use client";

import { getPillsByScenario, getChipsByPill } from "@/core/scenarios/config";
import { getTemplateForChip } from "@/core/scenarios/prompt-templates";
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
  onTogglePill: (scenarioId: ScenarioId, agentSlug: string) => void;
  onToggleChip: (
    scenarioId: ScenarioId,
    agentSlug: string,
    taskId: string,
  ) => void;
  /** @deprecated Prompt state is derived from useScenarioBinding by the page. */
  onInjectPrompt?: (template: string) => void;
}

export function ScenarioCascadeBar({
  selectedScenario,
  selectedPill,
  selectedChip,
  onTogglePill,
  onToggleChip,
  onInjectPrompt,
}: ScenarioCascadeBarProps) {
  const pills = selectedScenario ? getPillsByScenario(selectedScenario) : [];
  const chips =
    selectedPill && selectedScenario
      ? getChipsByPill(selectedScenario, selectedPill.agentSlug)
      : [];

  const handleToggleChip = (
    scenarioId: ScenarioId,
    agentSlug: string,
    taskId: string,
  ) => {
    const isDeselect =
      selectedChip?.scenarioId === scenarioId &&
      selectedChip?.agentSlug === agentSlug &&
      selectedChip?.taskId === taskId;

    onToggleChip(scenarioId, agentSlug, taskId);

    if (!isDeselect) {
      const chip = getTemplateForChip(scenarioId, agentSlug, taskId);
      if (chip) {
        onInjectPrompt?.(chip.promptTemplate);
      }
    }
  };

  return (
    <div className="min-h-10 w-full" data-testid="scenario-cascade-bar">
      {selectedScenario && !selectedPill && pills.length > 0 && (
        <AgentPillBar
          pills={pills}
          selectedSlug={null}
          onSelect={(agentSlug) => onTogglePill(selectedScenario, agentSlug)}
        />
      )}
      {selectedPill && chips.length > 0 && (
        <TaskChipBar
          chips={chips}
          selectedTaskId={selectedChip?.taskId ?? null}
          onSelect={(taskId) =>
            handleToggleChip(selectedScenario!, selectedPill.agentSlug, taskId)
          }
        />
      )}
    </div>
  );
}
