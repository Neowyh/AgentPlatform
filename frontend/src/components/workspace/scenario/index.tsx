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
    skillName: string,
  ) => void;
  onInjectPrompt: (template: string) => void;
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
    skillName: string,
  ) => {
    const isDeselect =
      selectedChip?.scenarioId === scenarioId &&
      selectedChip?.agentSlug === agentSlug &&
      selectedChip?.skillName === skillName;

    onToggleChip(scenarioId, agentSlug, skillName);

    if (!isDeselect) {
      const chip = getTemplateForChip(scenarioId, agentSlug, skillName);
      if (chip) {
        onInjectPrompt(chip.promptTemplate);
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
          selectedSkillName={selectedChip?.skillName ?? null}
          onSelect={(skillName) =>
            handleToggleChip(
              selectedScenario!,
              selectedPill.agentSlug,
              skillName,
            )
          }
        />
      )}
    </div>
  );
}
