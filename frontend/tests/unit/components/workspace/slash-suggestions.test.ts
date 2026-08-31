import { describe, expect, test } from "vitest";

import {
  getSlashAtCursor,
  filterSkillsByAllowedNames,
  getMatchingSkillSuggestions,
  parseSlashPrefix,
  RESERVED_SLASH_SKILL_NAMES,
} from "@/components/workspace/slash-suggestions";
import type { Skill } from "@/core/skills/type";

const makeSkill = (name: string, description = `${name} desc`): Skill => ({
  name,
  description,
  category: "public",
  license: "",
  enabled: true,
});

const SKILLS: Skill[] = [
  makeSkill("anthropic-docx", "Word document processing"),
  makeSkill("skill-creator", "Create new skills"),
  makeSkill("consulting-analysis", "Professional research reports"),
  makeSkill("research", "Deep dive research"),
  makeSkill("web-search", "Search the web"),
  makeSkill("image-gen", "Generate images"),
  makeSkill("video-gen", "Generate videos"),
];

describe("RESERVED_SLASH_SKILL_NAMES", () => {
  test("contains expected reserved names", () => {
    expect(RESERVED_SLASH_SKILL_NAMES.has("bootstrap")).toBe(true);
    expect(RESERVED_SLASH_SKILL_NAMES.has("help")).toBe(true);
    expect(RESERVED_SLASH_SKILL_NAMES.has("goal")).toBe(true);
    expect(RESERVED_SLASH_SKILL_NAMES.has("memory")).toBe(true);
    expect(RESERVED_SLASH_SKILL_NAMES.has("models")).toBe(true);
    expect(RESERVED_SLASH_SKILL_NAMES.has("new")).toBe(true);
    expect(RESERVED_SLASH_SKILL_NAMES.has("status")).toBe(true);
  });

  test("does not contain skill-creator", () => {
    expect(RESERVED_SLASH_SKILL_NAMES.has("skill-creator")).toBe(false);
  });
});

describe("getSlashAtCursor", () => {
  test("triggers at start of empty string", () => {
    expect(getSlashAtCursor("/", 1)).toEqual({ query: "", start: 0, end: 1 });
  });

  test("triggers at start of text", () => {
    expect(getSlashAtCursor("/res", 4)).toEqual({
      query: "res",
      start: 0,
      end: 4,
    });
  });

  test("triggers after a space", () => {
    expect(getSlashAtCursor("hello /res", 10)).toEqual({
      query: "res",
      start: 6,
      end: 10,
    });
  });

  test("triggers after a newline", () => {
    expect(getSlashAtCursor("line1\n/res", 10)).toEqual({
      query: "res",
      start: 6,
      end: 10,
    });
  });

  test("triggers after a tab", () => {
    expect(getSlashAtCursor("hello\t/res", 10)).toEqual({
      query: "res",
      start: 6,
      end: 10,
    });
  });

  test("does not trigger on double slash", () => {
    expect(getSlashAtCursor("//res", 5)).toBeNull();
  });

  test("does not trigger when slash is mid-word", () => {
    expect(getSlashAtCursor("abc/res", 7)).toBeNull();
  });

  test("does not trigger when query contains space", () => {
    expect(getSlashAtCursor("/res abc", 4)).toEqual({
      query: "res",
      start: 0,
      end: 4,
    });
  });

  test("does not trigger when slash is mid-word even with later valid slash", () => {
    expect(getSlashAtCursor("re/s", 5)).toBeNull();
  });

  test("uses cursor position, not end of string", () => {
    expect(getSlashAtCursor("hello /res world", 10)).toEqual({
      query: "res",
      start: 6,
      end: 10,
    });
  });

  test("returns null when cursor is before the slash", () => {
    expect(getSlashAtCursor("/res", 0)).toBeNull();
  });

  test("returns null for uppercase query (strict lowercase)", () => {
    expect(getSlashAtCursor("/RES", 4)).toBeNull();
  });

  test("returns null when cursor exceeds string length", () => {
    expect(getSlashAtCursor("/res", 10)).toBeNull();
  });

  test("allows hyphen in query", () => {
    expect(getSlashAtCursor("/anthropic-docx", 15)).toEqual({
      query: "anthropic-docx",
      start: 0,
      end: 15,
    });
  });

  test("rejects non-alphanumeric-hyphen chars in query", () => {
    expect(getSlashAtCursor("/res!", 5)).toBeNull();
  });

  test("returns empty query for bare slash", () => {
    expect(getSlashAtCursor("/", 1)).toEqual({ query: "", start: 0, end: 1 });
  });
});

describe("getMatchingSkillSuggestions", () => {
  test("returns all matching enabled items", () => {
    const many = Array.from({ length: 20 }, (_, i) =>
      makeSkill(`skill-${String(i).padStart(2, "0")}`),
    );
    expect(getMatchingSkillSuggestions(many, "").length).toBe(20);
  });

  test("filters by name prefix (case insensitive)", () => {
    const result = getMatchingSkillSuggestions(SKILLS, "res");
    expect(result.map((s) => s.name)).toContain("research");
    expect(result[0]!.name).toBe("research");
  });

  test("filters by name substring", () => {
    expect(
      getMatchingSkillSuggestions(SKILLS, "doc").map((s) => s.name),
    ).toEqual(["anthropic-docx"]);
  });

  test("filters by description", () => {
    expect(
      getMatchingSkillSuggestions(SKILLS, "research reports").map(
        (s) => s.name,
      ),
    ).toEqual(["consulting-analysis"]);
  });

  test("returns all skills for empty query", () => {
    expect(getMatchingSkillSuggestions(SKILLS, "").length).toBe(SKILLS.length);
  });

  test("prefers startsWith matches over substring matches", () => {
    const skills = [makeSkill("my-research"), makeSkill("research")];
    expect(getMatchingSkillSuggestions(skills, "research")[0]!.name).toBe(
      "research",
    );
  });

  test("excludes reserved names", () => {
    const skills = [
      makeSkill("help"),
      makeSkill("my-help"),
      makeSkill("research"),
    ];
    expect(
      getMatchingSkillSuggestions(skills, "help").map((s) => s.name),
    ).toEqual(["my-help"]);
  });

  test("excludes disabled skills", () => {
    const skills = [
      makeSkill("research"),
      { ...makeSkill("research-pro"), enabled: false },
    ];
    expect(
      getMatchingSkillSuggestions(skills, "research").map((s) => s.name),
    ).toEqual(["research"]);
  });

  test("matches case insensitively", () => {
    const result = getMatchingSkillSuggestions(SKILLS, "RESEARCH");
    expect(result[0]!.name).toBe("research");
  });

  test("returns empty array when no match", () => {
    expect(getMatchingSkillSuggestions(SKILLS, "zzzzz")).toEqual([]);
  });

  test("restricts suggestions to the selected Agent skill closure", () => {
    expect(
      getMatchingSkillSuggestions(SKILLS, "", ["anthropic-docx"]).map(
        (skill) => skill.name,
      ),
    ).toEqual(["anthropic-docx"]);
  });

  test("matches Agent closure entries by resource id", () => {
    const skill = {
      ...makeSkill("officecli"),
      resource_id: "skill-resource-id",
    };

    expect(filterSkillsByAllowedNames([skill], ["skill-resource-id"])).toEqual([
      skill,
    ]);
    expect(
      getMatchingSkillSuggestions([skill], "", ["skill-resource-id"]),
    ).toEqual([skill]);
  });
});

describe("parseSlashPrefix", () => {
  test("parses valid slash prefix with rest", () => {
    expect(parseSlashPrefix("/anthropic-docx help me")).toEqual({
      skillName: "anthropic-docx",
      rest: "help me",
    });
  });

  test("parses valid slash prefix without rest", () => {
    expect(parseSlashPrefix("/research")).toEqual({
      skillName: "research",
      rest: "",
    });
  });

  test("parses with trailing spaces", () => {
    expect(parseSlashPrefix("/research   ")).toEqual({
      skillName: "research",
      rest: "",
    });
  });

  test("returns null for non-slash text", () => {
    expect(parseSlashPrefix("hello world")).toBeNull();
  });

  test("returns null for double slash", () => {
    expect(parseSlashPrefix("//research")).toBeNull();
  });

  test("parses slash with rest", () => {
    expect(parseSlashPrefix("/research tool")).toEqual({
      skillName: "research",
      rest: "tool",
    });
  });

  test("returns null for slash with empty name", () => {
    expect(parseSlashPrefix("/ ")).toBeNull();
  });

  test("returns null for bare slash", () => {
    expect(parseSlashPrefix("/")).toBeNull();
  });

  test("returns null for slash with uppercase", () => {
    expect(parseSlashPrefix("/Research")).toBeNull();
  });

  test("handles hyphenated skill names", () => {
    expect(parseSlashPrefix("/consulting-analysis analyze this")).toEqual({
      skillName: "consulting-analysis",
      rest: "analyze this",
    });
  });
});
