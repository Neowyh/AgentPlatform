import type { Agent } from "@/core/agents/types";
import type { Skill } from "@/core/skills/type";

function nonEmpty(value: string | undefined | null): string | undefined {
  const text = value?.trim();
  if (!text) return undefined;
  return text;
}

/** Match an Agent Pill slug the same way the chat page does (slug, then name). */
export function findAgentForPill(
  agents: Agent[],
  agentSlug: string,
): Agent | undefined {
  return agents.find((agent) => (agent.slug ?? agent.name) === agentSlug);
}

/**
 * Match a Task Chip skill name the same way scenario binding does
 * (resource_id, slug, then name).
 */
export function findSkillForChip(
  skills: Skill[],
  skillName: string,
): Skill | undefined {
  return skills.find(
    (skill) =>
      skill.resource_id === skillName ||
      skill.slug === skillName ||
      skill.name === skillName,
  );
}

/** Short agent text for hover previews: summary first, blank-aware. */
export function agentDescription(agent: Agent): string | undefined {
  return nonEmpty(agent.summary) ?? nonEmpty(agent.description);
}

/**
 * Short skill text for hover previews, mirroring the skill list card:
 * Chinese prefers summary, other locales use description. Blank-aware.
 */
export function skillDescription(
  skill: Skill,
  locale: string,
): string | undefined {
  if (locale === "zh-CN") {
    return nonEmpty(skill.summary) ?? nonEmpty(skill.description);
  }
  return nonEmpty(skill.description);
}
