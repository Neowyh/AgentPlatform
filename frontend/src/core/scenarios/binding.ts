import { useCallback, useMemo, useState } from "react";

import { SCENARIOS, getChipsByPill, getPillsByScenario } from "./config";
import type {
  ChipSelection,
  PillSelection,
  ScenarioId,
  TaskChip,
} from "./types";

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
  selectAgent: (agentSlug: string) => void;
  togglePill: (agentSlug: string) => void;
  toggleChip: (taskId: string) => void;
  consumePendingTemplate: () => void;
  setBindingState: (state: BindingState) => void;
  resetSelection: () => void;
}

type ResourceIdentity = {
  resource_id?: string;
  slug?: string;
  name?: string;
};

type AgentClosure = {
  skills: string[] | null;
};

export type ScenarioSubmissionBinding =
  | {
      valid: true;
      context: Record<string, unknown> & {
        mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
      };
    }
  | { valid: false; reason: string };

const SCENARIO_CONTEXT_KEYS = [
  "agent_name",
  "agent_resource_id",
  "skill_name",
  "skill_resource_id",
  "scenario_id",
  "agent_label",
  "task_id",
  "task_label",
  "prompt_template",
] as const;

function withoutScenarioContext(
  baseContext: Record<string, unknown> & {
    mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
  },
) {
  const context = { ...baseContext };
  for (const key of SCENARIO_CONTEXT_KEYS) {
    delete context[key];
  }
  return context;
}

function matchesResource(identity: ResourceIdentity, value: string) {
  return (
    identity.resource_id === value ||
    identity.slug === value ||
    identity.name === value
  );
}

function selectedTaskFor(selectedChip: ChipSelection): TaskChip | undefined {
  return selectedChip
    ? findTaskChip(
        selectedChip.scenarioId,
        selectedChip.agentSlug,
        selectedChip.taskId,
      )
    : undefined;
}

/**
 * Build the canonical Run context from the submission-time Scenario state.
 * Existing thread settings may contribute model/connector preferences but
 * never an Agent or Skill identity from a previous conversation state.
 */
export function buildScenarioSubmissionBinding({
  baseContext,
  selectedPill,
  selectedChip,
  agent,
  agentDetails,
  skills,
  connectorName,
}: {
  baseContext: Record<string, unknown> & {
    mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
  };
  selectedPill: PillSelection;
  selectedChip: ChipSelection;
  agent?: ResourceIdentity;
  agentDetails?: AgentClosure | null;
  skills: ResourceIdentity[];
  connectorName?: string | null;
}): ScenarioSubmissionBinding {
  const context = withoutScenarioContext(baseContext);
  context.connector_name = connectorName ?? undefined;
  if (!selectedPill) {
    return { valid: true, context };
  }
  if (!agent?.resource_id) {
    return { valid: false, reason: "当前专家仍在加载，请稍后再提交。" };
  }

  const pill = findPill(selectedPill.scenarioId, selectedPill.agentSlug);
  const task = selectedTaskFor(selectedChip);
  Object.assign(context, {
    context_source: "scenario_binding",
    scenario_id: selectedPill.scenarioId,
    agent_name: selectedPill.agentSlug,
    agent_resource_id: agent.resource_id,
    agent_label: pill?.label,
  });
  if (selectedPill.agentSlug === "fault-zeroing") {
    context.evidence_mode = "hybrid";
  }
  if (!task) {
    return { valid: true, context };
  }

  const skill = skills.find((item) => matchesResource(item, task.skillName));
  const closure = agentDetails?.skills;
  const inClosure = Boolean(
    skill?.resource_id &&
    closure?.some((value) => matchesResource(skill, value)),
  );
  if (!inClosure || !skill?.resource_id) {
    return {
      valid: false,
      reason: "请重新选择当前专家下的任务后再提交。",
    };
  }
  Object.assign(context, {
    skill_name: task.skillName,
    skill_resource_id: skill.resource_id,
    task_id: task.taskId,
    task_label: task.label,
    prompt_template: task.promptTemplate,
  });
  return { valid: true, context };
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

  const selectAgent = useCallback((agentSlug: string) => {
    const match = SCENARIOS.find((scenario) =>
      scenario.agentPills.some((pill) => pill.agentSlug === agentSlug),
    );
    if (!match) return;

    setSelectedScenario(match.id);
    setSelectedPill({ scenarioId: match.id, agentSlug });
    setSelectedChip(null);
    setPendingTemplate(null);
    setBindingState("idle");
  }, []);

  const togglePill = useCallback(
    (agentSlug: string) => {
      const targetScenario = selectedScenario;
      if (!findPill(targetScenario, agentSlug)) return;

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
    [selectedScenario],
  );

  const toggleChip = useCallback(
    (taskId: string) => {
      const scenarioId = selectedScenario;
      const agentSlug = selectedPill?.agentSlug;
      if (!agentSlug || !findTaskChip(scenarioId, agentSlug, taskId)) {
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
    selectAgent,
    togglePill,
    toggleChip,
    consumePendingTemplate: useCallback(() => {
      setPendingTemplate(null);
      setBindingState("idle");
    }, []),
    setBindingState,
    resetSelection,
  };
}
