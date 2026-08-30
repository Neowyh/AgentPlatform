export interface TaskChip {
  taskId: string;
  /** Stable translation key; label is retained for the legacy adapter. */
  labelKey?: string;
  label: string;
  skillName: string;
  promptTemplate: string;
}

export interface AgentPill {
  agentSlug: string;
  /** Stable translation key; label is retained for the legacy adapter. */
  labelKey?: string;
  label: string;
  chips?: TaskChip[];
}

export interface ScenarioTab {
  id: ScenarioId;
  labelKey: string;
  icon: string;
  agentPills: AgentPill[];
}

export interface ScenarioBinding {
  agentSlug: string;
  agentName: string;
  skillName: string | null;
  promptTemplate: string | null;
  tags: Array<{ id: string; label: string }>;
}

export type ScenarioId = "daily" | "creative" | "professional";

export type PillSelection = {
  scenarioId: ScenarioId;
  agentSlug: string;
} | null;

export type ChipSelection = {
  scenarioId: ScenarioId;
  agentSlug: string;
  taskId: string;
} | null;
