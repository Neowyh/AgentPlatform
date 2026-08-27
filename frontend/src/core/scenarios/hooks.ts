import { useCallback, useState } from "react";

import type { ChipSelection, PillSelection, ScenarioId } from "./types";

export function useScenarioSelection() {
  const [selectedScenario, setSelectedScenario] = useState<ScenarioId | null>(
    null,
  );
  const [selectedPill, setSelectedPill] = useState<PillSelection>(null);
  const [selectedChip, setSelectedChip] = useState<ChipSelection>(null);

  const selectScenario = useCallback((id: ScenarioId | null) => {
    setSelectedScenario(id);
    setSelectedPill(null);
    setSelectedChip(null);
  }, []);

  const togglePill = useCallback(
    (scenarioId: ScenarioId, agentSlug: string) => {
      if (
        selectedPill?.scenarioId === scenarioId &&
        selectedPill?.agentSlug === agentSlug
      ) {
        setSelectedPill(null);
      } else {
        setSelectedPill({ scenarioId, agentSlug });
      }
      setSelectedChip(null);
    },
    [selectedPill],
  );

  const toggleChip = useCallback(
    (scenarioId: ScenarioId, agentSlug: string, taskId: string) => {
      if (
        selectedChip?.scenarioId === scenarioId &&
        selectedChip?.agentSlug === agentSlug &&
        selectedChip?.taskId === taskId
      ) {
        setSelectedChip(null);
      } else {
        setSelectedChip({ scenarioId, agentSlug, taskId });
      }
    },
    [selectedChip],
  );

  const resetSelection = useCallback(() => {
    setSelectedScenario(null);
    setSelectedPill(null);
    setSelectedChip(null);
  }, []);

  return {
    selectedScenario,
    selectedPill,
    selectedChip,
    selectScenario,
    togglePill,
    toggleChip,
    resetSelection,
  };
}
