"use client";

import { getPillsByScenario, getChipsByPill } from "@/core/scenarios/config";
import { getTemplateForChip } from "@/core/scenarios/prompt-templates";
import type {
  ChipSelection,
  PillSelection,
  ScenarioId,
} from "@/core/scenarios/types";

import { FeatureChipBar } from "./feature-chip-bar";
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
    <div
      className="flex flex-col items-center gap-2"
      data-testid="scenario-cascade-bar"
    >
      <ScenarioTabs selected={selectedScenario} onSelect={onSelectScenario} />
      {selectedScenario && !selectedPill && pills.length > 0 && (
        <FeatureChipBar
          items={pills.map((p) => ({
            id: p.agentSlug,
            label: p.label,
          }))}
          onSelect={(id) => onTogglePill(selectedScenario, id)}
        />
      )}
      {selectedPill && chips.length > 0 && (
        <FeatureChipBar
          items={chips.map((c) => ({
            id: c.skillName,
            label: c.label,
          }))}
          onSelect={(id) =>
            handleToggleChip(selectedScenario!, selectedPill.agentSlug, id)
          }
        />
      )}
    </div>
  );
}
