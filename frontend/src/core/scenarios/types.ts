export interface TaskChip {
  label: string;
  skillName: string;
  promptTemplate: string;
}

export interface AgentPill {
  agentSlug: string;
  label: string;
  chips?: TaskChip[];
}

export interface ScenarioTab {
  id: ScenarioId;
  labelKey: string;
  icon: string;
  agentPills: AgentPill[];
}

export type ScenarioId = "daily" | "creative" | "professional";

export type PillSelection = {
  scenarioId: ScenarioId;
  agentSlug: string;
} | null;

export type ChipSelection = {
  scenarioId: ScenarioId;
  agentSlug: string;
  skillName: string;
} | null;
