import type { Skill } from "@/core/skills/type";
import { parseTaskSkillPrefix } from "@/core/threads/task-input";

export const RESERVED_SLASH_SKILL_NAMES: ReadonlySet<string> = new Set([
  "bootstrap",
  "goal",
  "help",
  "memory",
  "models",
  "new",
  "status",
]);

export function getSlashAtCursor(
  value: string,
  selectionStart: number,
): { query: string; start: number; end: number } | null {
  if (selectionStart <= 0 || selectionStart > value.length) return null;

  const before = value.slice(0, selectionStart);
  const lastSlash = before.lastIndexOf("/");
  if (lastSlash < 0) return null;
  if (lastSlash > 0 && !/\s/.test(before[lastSlash - 1]!)) return null;

  const queryRaw = before.slice(lastSlash + 1);
  if (queryRaw.length > 0 && !/^[a-z0-9-]+$/.test(queryRaw)) return null;

  return {
    query: queryRaw.toLowerCase(),
    start: lastSlash,
    end: selectionStart,
  };
}

export function filterSkillsByAllowedNames(
  skills: Skill[],
  allowedSkillNames?: readonly string[],
): Skill[] {
  if (allowedSkillNames === undefined) return skills;

  const allowed = new Set(allowedSkillNames.map((name) => name.toLowerCase()));
  return skills.filter(
    (skill) =>
      allowed.has(skill.name.toLowerCase()) ||
      (skill.slug !== undefined && allowed.has(skill.slug.toLowerCase())) ||
      (skill.resource_id !== undefined &&
        allowed.has(skill.resource_id.toLowerCase())),
  );
}

export function getMatchingSkillSuggestions(
  skills: Skill[],
  query: string,
  allowedSkillNames?: readonly string[],
): Skill[] {
  const q = query.toLowerCase();
  const enabled = filterSkillsByAllowedNames(skills, allowedSkillNames).filter(
    (skill) => skill.enabled,
  );

  const candidates = enabled
    .map((skill, index) => {
      const name = skill.name.toLowerCase();
      const description = skill.description.toLowerCase();
      const matches = !q || name.includes(q) || description.includes(q);
      return { skill, index, name, matches };
    })
    .filter(
      ({ name, matches }) => matches && !RESERVED_SLASH_SKILL_NAMES.has(name),
    )
    .sort((a, b) => {
      const aStarts = a.name.startsWith(q);
      const bStarts = b.name.startsWith(q);
      if (aStarts !== bStarts) return aStarts ? -1 : 1;
      return a.index - b.index;
    });

  return candidates.map(({ skill }) => skill);
}

export const parseSlashPrefix = parseTaskSkillPrefix;
