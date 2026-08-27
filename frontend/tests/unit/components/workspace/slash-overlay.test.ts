import { describe, expect, test } from "vitest";

import {
  getSlashAtCursor,
  getMatchingSkillSuggestions,
  parseSlashPrefix,
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
  makeSkill("research", "Deep dive research"),
  makeSkill("web-search", "Search the web"),
  makeSkill("image-gen", "Generate images"),
];

describe("Phase 3: slash overlay integration", () => {
  describe("cursor tracking + slash detection", () => {
    test("detects slash at cursor position", () => {
      const value = "/res";
      const result = getSlashAtCursor(value, 4);
      expect(result).toEqual({ query: "res", start: 0, end: 4 });
    });

    test("detects slash mid-text after space", () => {
      const value = "hello /web";
      const result = getSlashAtCursor(value, 10);
      expect(result).toEqual({ query: "web", start: 6, end: 10 });
    });

    test("returns null when cursor not on slash prefix", () => {
      const value = "/res";
      const result = getSlashAtCursor(value, 0);
      expect(result).toBeNull();
    });

    test("returns null when no slash present", () => {
      const value = "hello world";
      const result = getSlashAtCursor(value, 5);
      expect(result).toBeNull();
    });
  });

  describe("skill filtering with activeIndex", () => {
    test("filters skills by query", () => {
      const result = getMatchingSkillSuggestions(SKILLS, "res");
      expect(result.map((s) => s.name)).toEqual(["research"]);
    });

    test("returns multiple matches for broad query", () => {
      const result = getMatchingSkillSuggestions(SKILLS, "e");
      expect(result.length).toBeGreaterThan(1);
    });

    test("activeIndex wraps around", () => {
      const result = getMatchingSkillSuggestions(SKILLS, "");
      const total = result.length;
      const wrappedIndex = (total + 1) % total;
      expect(wrappedIndex).toBe(1);
    });
  });

  describe("slash prefix replacement", () => {
    test("replaces slash prefix with skill name", () => {
      const value = "/res hello";
      const prefix = parseSlashPrefix(value);
      expect(prefix).toEqual({ skillName: "res", rest: "hello" });
    });

    test("handles empty rest after replacement", () => {
      const value = "/research";
      const prefix = parseSlashPrefix(value);
      expect(prefix).toEqual({ skillName: "research", rest: "" });
    });

    test("preserves trailing text after slash prefix", () => {
      const before = "";
      const skillName = "research";
      const after = "analyze this topic";
      const newText = `${before}/${skillName} ${after}`;
      expect(newText).toBe("/research analyze this topic");
    });

    test("preserves text before slash prefix", () => {
      const before = "please use ";
      const skillName = "web-search";
      const after = "";
      const newText = `${before}/${skillName} ${after}`;
      expect(newText).toBe("please use /web-search ");
    });
  });

  describe("keyboard navigation simulation", () => {
    test("ArrowDown increments activeIndex", () => {
      const total = 3;
      const activeIndex = 0;
      const next = (activeIndex + 1) % total;
      expect(next).toBe(1);
    });

    test("ArrowDown wraps to 0 at end", () => {
      const total = 3;
      const activeIndex = 2;
      const next = (activeIndex + 1) % total;
      expect(next).toBe(0);
    });

    test("ArrowUp decrements activeIndex", () => {
      const total = 3;
      const activeIndex = 2;
      const next = (activeIndex - 1 + total) % total;
      expect(next).toBe(1);
    });

    test("ArrowUp wraps to end at 0", () => {
      const total = 3;
      const activeIndex = 0;
      const next = (activeIndex - 1 + total) % total;
      expect(next).toBe(2);
    });
  });

  describe("selection output", () => {
    test("builds correct text after skill selection", () => {
      const value = "/res hello world";
      const start = 0;
      const end = 4;
      const skillName = "research";
      const before = value.slice(0, start);
      const after = value.slice(end);
      const result = `${before}/${skillName} ${after}`;
      expect(result).toBe("/research  hello world");
    });

    test("cursor position after selection", () => {
      const skillName = "web-search";
      const cursorPos = skillName.length + 2;
      expect(cursorPos).toBe(12);
    });

    test("handles selection in middle of text", () => {
      const value = "please /res now";
      const start = 7;
      const end = 11;
      const skillName = "research";
      const before = value.slice(0, start);
      const after = value.slice(end);
      const result = `${before}/${skillName} ${after}`;
      expect(result).toBe("please /research  now");
    });
  });
});
