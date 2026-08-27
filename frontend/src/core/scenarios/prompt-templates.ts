import { SCENARIOS } from "./config";
import type { ScenarioId, TaskChip } from "./types";

export function getTemplateForChip(
  scenarioId: ScenarioId,
  agentSlug: string,
  taskId: string,
): TaskChip | undefined {
  const scenario = SCENARIOS.find((s) => s.id === scenarioId);
  const pill = scenario?.agentPills?.find((p) => p.agentSlug === agentSlug);
  return pill?.chips?.find((c) => c.taskId === taskId);
}
