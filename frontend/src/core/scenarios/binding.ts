import { useCallback, useMemo, useState } from "react";

import { SCENARIOS, getChipsByPill, getPillsByScenario } from "./config";
import type {
  ChipSelection,
  PillSelection,
  ScenarioId,
  TaskChip,
} from "./types";

export const SCENARIO_IDS = SCENARIOS.map((scenario) => scenario.id) as [
  ScenarioId,
  ...ScenarioId[],
];

export type BindingState = "idle" | "pending" | "confirming";

export interface BindingTag {
  id: string;
  text: string;
  kind: "agent" | "task";
}

export interface ActiveBinding {
  scenarioId: ScenarioId;
  agentSlug: string | null;
  agentName: string | null;
  skillName: string | null;
  promptTemplate: string | null;
  tags: BindingTag[];
}

export interface ScenarioBinding {
  selectedScenario: ScenarioId;
  selectedPill: PillSelection;
  selectedChip: ChipSelection;
  pills: ReturnType<typeof getPillsByScenario>;
  chips: TaskChip[];
  activeBinding: ActiveBinding;
  bindingState: BindingState;
  pendingTemplate: string | null;
  selectScenario: (id: ScenarioId) => void;
  togglePill: {
    (agentSlug: string): void;
    (scenarioId: ScenarioId, agentSlug: string): void;
  };
  toggleChip: {
    (taskId: string): void;
    (scenarioId: ScenarioId, agentSlug: string, taskId: string): void;
  };
  consumePendingTemplate: () => void;
  setBindingState: (state: BindingState) => void;
  resetSelection: () => void;
}

function findPill(scenarioId: ScenarioId, agentSlug: string) {
  return getPillsByScenario(scenarioId).find(
    (pill) => pill.agentSlug === agentSlug,
  );
}

export function findTaskChip(
  scenarioId: ScenarioId,
  agentSlug: string,
  taskId: string,
) {
  return getChipsByPill(scenarioId, agentSlug).find(
    (chip) => chip.taskId === taskId,
  );
}

export function useScenarioBinding(
  initialScenario: ScenarioId = "creative",
): ScenarioBinding {
  const [selectedScenario, setSelectedScenario] =
    useState<ScenarioId>(initialScenario);
  const [selectedPill, setSelectedPill] = useState<PillSelection>(null);
  const [selectedChip, setSelectedChip] = useState<ChipSelection>(null);
  const [bindingState, setBindingState] = useState<BindingState>("idle");
  const [pendingTemplate, setPendingTemplate] = useState<string | null>(null);

  const selectScenario = useCallback((id: ScenarioId) => {
    setSelectedScenario((current) => (current === id ? current : id));
    setSelectedPill(null);
    setSelectedChip(null);
    setPendingTemplate(null);
    setBindingState("idle");
  }, []);

  const togglePill = useCallback(
    (scenarioOrAgent: ScenarioId | string, maybeAgent?: string) => {
      const scenarioId = maybeAgent
        ? (scenarioOrAgent as ScenarioId)
        : undefined;
      const agentSlug = maybeAgent ?? scenarioOrAgent;
      const targetScenario =
        scenarioId ?? SCENARIO_IDS.find((id) => findPill(id, agentSlug));
      if (!targetScenario || !findPill(targetScenario, agentSlug)) return;

      setSelectedScenario(targetScenario);
      setSelectedPill((current) =>
        current?.scenarioId === targetScenario &&
        current.agentSlug === agentSlug
          ? null
          : { scenarioId: targetScenario, agentSlug },
      );
      setSelectedChip(null);
      setPendingTemplate(null);
      setBindingState("idle");
    },
    [],
  );

  const toggleChip = useCallback(
    (first: string | ScenarioId, second?: string, third?: string) => {
      const scenarioId = third ? (first as ScenarioId) : selectedScenario;
      const agentSlug = third ? second : selectedPill?.agentSlug;
      const taskId = third ?? first;
      if (
        !agentSlug ||
        (third &&
          (selectedPill?.scenarioId !== scenarioId ||
            selectedPill.agentSlug !== agentSlug)) ||
        !findTaskChip(scenarioId, agentSlug, taskId)
      ) {
        return;
      }

      const next = {
        scenarioId,
        agentSlug,
        taskId,
      } satisfies NonNullable<ChipSelection>;
      const isDeselect =
        selectedChip?.scenarioId === next.scenarioId &&
        selectedChip.agentSlug === next.agentSlug &&
        selectedChip.taskId === next.taskId;
      const chip = findTaskChip(scenarioId, agentSlug, taskId);
      setSelectedChip(isDeselect ? null : next);
      setPendingTemplate(isDeselect ? null : (chip?.promptTemplate ?? null));
      setBindingState(isDeselect ? "idle" : "pending");
    },
    [selectedChip, selectedPill, selectedScenario],
  );

  const resetSelection = useCallback(() => {
    setSelectedScenario(initialScenario);
    setSelectedPill(null);
    setSelectedChip(null);
    setPendingTemplate(null);
    setBindingState("idle");
  }, [initialScenario]);

  const pills = useMemo(
    () => getPillsByScenario(selectedScenario),
    [selectedScenario],
  );
  const chips = useMemo(
    () =>
      selectedPill
        ? getChipsByPill(selectedPill.scenarioId, selectedPill.agentSlug)
        : [],
    [selectedPill],
  );
  const selectedTask = selectedChip
    ? findTaskChip(
        selectedChip.scenarioId,
        selectedChip.agentSlug,
        selectedChip.taskId,
      )
    : undefined;
  const activePill = selectedPill
    ? findPill(selectedPill.scenarioId, selectedPill.agentSlug)
    : undefined;
  const activeBinding = useMemo<ActiveBinding>(
    () => ({
      scenarioId: selectedScenario,
      agentSlug: selectedPill?.agentSlug ?? null,
      agentName: activePill?.label ?? null,
      skillName: selectedTask?.skillName ?? null,
      promptTemplate: selectedTask?.promptTemplate ?? null,
      tags: activePill
        ? [
            {
              id: `agent:${activePill.agentSlug}`,
              text: activePill.label,
              kind: "agent",
            },
            ...(selectedTask
              ? [
                  {
                    id: `task:${selectedTask.taskId}`,
                    text: selectedTask.skillName,
                    kind: "task" as const,
                  },
                ]
              : []),
          ]
        : [],
    }),
    [activePill, selectedScenario, selectedTask, selectedPill],
  );

  return {
    selectedScenario,
    selectedPill,
    selectedChip,
    pills,
    chips,
    activeBinding,
    bindingState,
    pendingTemplate,
    selectScenario,
    togglePill: togglePill as ScenarioBinding["togglePill"],
    toggleChip: toggleChip as ScenarioBinding["toggleChip"],
    consumePendingTemplate: useCallback(() => {
      setPendingTemplate(null);
      setBindingState("idle");
    }, []),
    setBindingState,
    resetSelection,
  };
}
