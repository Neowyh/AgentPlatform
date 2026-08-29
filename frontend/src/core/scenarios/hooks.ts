import { useCallback, useMemo, useState } from "react";

import { getChipsByPill, getPillsByScenario } from "./config";
import type {
  ChipSelection,
  PillSelection,
  ScenarioBinding,
  ScenarioId,
} from "./types";

export function useScenarioBinding(initialScenario: ScenarioId = "creative") {
  const [selectedScenario, setSelectedScenario] =
    useState<ScenarioId>(initialScenario);
  const [selectedPill, setSelectedPill] = useState<PillSelection>(null);
  const [selectedChip, setSelectedChip] = useState<ChipSelection>(null);

  const selectScenario = useCallback((id: ScenarioId) => {
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
