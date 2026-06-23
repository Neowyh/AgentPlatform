import { describe, expect, test } from "vitest";

import * as skillsIndex from "@/core/skills/index";

describe("skills index", () => {
  test("re-exports api functions", () => {
    expect(skillsIndex).toHaveProperty("loadSkills");
    expect(skillsIndex).toHaveProperty("enableSkill");
    expect(skillsIndex).toHaveProperty("installSkill");
  });

  test("re-exports types", () => {
    expect(Object.keys(skillsIndex).length).toBeGreaterThan(0);
  });
});
