import { useCallback, useState } from "react";

import { useScenarioBinding as useCanonicalScenarioBinding } from "./binding";
import type { ScenarioId } from "./types";

export function useScenarioBinding(initialScenario: ScenarioId = "creative") {
  const binding = useCanonicalScenarioBinding(initialScenario);

  return {
    ...binding,
    tags: binding.activeBinding.tags.map((tag) => ({
      id: tag.id,
      label: tag.text,
    })),
    clear: binding.resetSelection,
  };
}

/** @deprecated Use useScenarioBinding. Kept for one release as a migration adapter. */
export function useScenarioSelection() {
  const binding = useCanonicalScenarioBinding("creative");
  const {
    resetSelection: resetBinding,
    selectScenario: selectBindingScenario,
    togglePill: toggleBindingPill,
    toggleChip: toggleBindingChip,
    selectedPill,
    selectedChip,
  } = binding;
  const [selectedScenario, setSelectedScenario] = useState<ScenarioId | null>(
    null,
  );

  const selectScenario = useCallback(
    (id: ScenarioId | null) => {
      setSelectedScenario(id);
      if (id) {
        selectBindingScenario(id);
      } else {
        resetBinding();
      }
    },
    [resetBinding, selectBindingScenario],
  );
  const togglePill = useCallback(
    (scenarioId: ScenarioId, agentSlug: string) => {
      setSelectedScenario(scenarioId);
      toggleBindingPill(scenarioId, agentSlug);
    },
    [toggleBindingPill],
  );
  const toggleChip = useCallback(
    (scenarioId: ScenarioId, agentSlug: string, taskId: string) => {
      toggleBindingChip(scenarioId, agentSlug, taskId);
    },
    [toggleBindingChip],
  );
  const resetSelection = useCallback(() => {
    setSelectedScenario(null);
    resetBinding();
  }, [resetBinding]);

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

export type { ScenarioBinding } from "./binding";
