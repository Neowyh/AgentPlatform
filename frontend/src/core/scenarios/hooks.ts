import { useCallback, useMemo, useState } from "react";

import { getChipsByPill, getPillsByScenario } from "./config";
import type {
  ChipSelection,
  PillSelection,
  ScenarioBinding,
  ScenarioId,
} from "./types";

export function useScenarioBinding(
  initialScenario: ScenarioId | null = "creative",
) {
  const [selectedScenario, setSelectedScenario] = useState<ScenarioId | null>(
    initialScenario,
  );
  const [selectedPill, setSelectedPill] = useState<PillSelection>(null);
  const [selectedChip, setSelectedChip] = useState<ChipSelection>(null);

  const selectScenario = useCallback((id: ScenarioId | null) => {
    setSelectedScenario((current) => {
      if (current === id) return current;
      setSelectedPill(null);
      setSelectedChip(null);
      return id;
    });
  }, []);

  const togglePill = useCallback(
    (scenarioId: ScenarioId, agentSlug: string) => {
      setSelectedScenario(scenarioId);
      setSelectedPill((current) =>
        current?.scenarioId === scenarioId && current.agentSlug === agentSlug
          ? null
          : { scenarioId, agentSlug },
      );
      setSelectedChip(null);
    },
    [],
  );

  const toggleChip = useCallback(
    (scenarioId: ScenarioId, agentSlug: string, taskId: string) => {
      const chip = getChipsByPill(scenarioId, agentSlug).find(
        (item) => item.taskId === taskId,
      );
      if (!chip) return;
      setSelectedChip((current) =>
        current?.scenarioId === scenarioId &&
        current.agentSlug === agentSlug &&
        current.taskId === taskId
          ? null
          : { scenarioId, agentSlug, taskId },
      );
    },
    [],
  );

  const clear = useCallback(() => {
    setSelectedPill(null);
    setSelectedChip(null);
  }, []);

  const activeBinding = useMemo<ScenarioBinding | null>(() => {
    if (!selectedPill) return null;
    const pill = getPillsByScenario(selectedPill.scenarioId).find(
      (item) => item.agentSlug === selectedPill.agentSlug,
    );
    if (!pill) return null;
    const chip = selectedChip
      ? getChipsByPill(selectedPill.scenarioId, selectedPill.agentSlug).find(
          (item) => item.taskId === selectedChip.taskId,
        )
      : undefined;
    return {
      agentSlug: pill.agentSlug,
      agentName: pill.label,
      skillName: chip?.skillName ?? null,
      promptTemplate: chip?.promptTemplate ?? null,
      tags: [
        { id: `agent:${pill.agentSlug}`, label: pill.label },
        ...(chip ? [{ id: `task:${chip.taskId}`, label: chip.skillName }] : []),
      ],
    };
  }, [selectedChip, selectedPill]);

  return {
    selectedScenario,
    selectedPill,
    selectedChip,
    activeBinding,
    tags: activeBinding?.tags ?? [],
    selectScenario,
    togglePill,
    toggleChip,
    clear,
  };
}

/** @deprecated Use useScenarioBinding. Kept for one release as a migration adapter. */
export function useScenarioSelection() {
  const binding = useScenarioBinding(null);
  const resetSelection = useCallback(() => {
    binding.selectScenario(null);
  }, [binding.selectScenario]);

  return {
    selectedScenario: binding.selectedScenario,
    selectedPill: binding.selectedPill,
    selectedChip: binding.selectedChip,
    selectScenario: binding.selectScenario,
    togglePill: binding.togglePill,
    toggleChip: binding.toggleChip,
    resetSelection,
  };
}
