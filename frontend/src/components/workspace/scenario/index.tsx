"use client";

import { getPillsByScenario } from "@/core/scenarios/config";
import { getTemplateForChip } from "@/core/scenarios/prompt-templates";
import type {
  ChipSelection,
  PillSelection,
  ScenarioId,
} from "@/core/scenarios/types";

import { AgentOrSkillBar } from "./agent-or-skill-bar";
import { ScenarioTabs } from "./scenario-tabs";

interface ScenarioCascadeBarProps {
  selectedScenario: ScenarioId | null;
  selectedPill: PillSelection;
  selectedChip: ChipSelection;
  onSelectScenario: (id: ScenarioId | null) => void;
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
  onSelectScenario,
  onTogglePill,
  onToggleChip,
  onInjectPrompt,
}: ScenarioCascadeBarProps) {
  const pills = selectedScenario ? getPillsByScenario(selectedScenario) : [];

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
    <div
      className="flex flex-col items-center gap-2"
      data-testid="scenario-cascade-bar"
    >
      <ScenarioTabs selected={selectedScenario} onSelect={onSelectScenario} />
      {selectedScenario && pills.length > 0 && (
        <AgentOrSkillBar
          pills={pills}
          selectedPill={selectedPill}
          selectedChip={selectedChip}
          onTogglePill={onTogglePill}
          onToggleChip={handleToggleChip}
          scenarioId={selectedScenario}
        />
      )}
    </div>
  );
}
