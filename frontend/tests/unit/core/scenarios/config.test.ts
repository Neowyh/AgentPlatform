import { describe, expect, it } from "vitest";

import {
  SCENARIOS,
  getScenarioById,
  getPillsByScenario,
  getChipsByPill,
} from "@/core/scenarios/config";

describe("SCENARIOS config", () => {
  it("has 3 scenario tabs", () => {
    expect(SCENARIOS).toHaveLength(3);
  });

  it("has daily, creative, professional ids", () => {
    const ids = SCENARIOS.map((s) => s.id);
    expect(ids).toEqual(["daily", "creative", "professional"]);
  });

  it("each scenario has at least one pill", () => {
    for (const scenario of SCENARIOS) {
      expect(scenario.agentPills.length).toBeGreaterThanOrEqual(1);
    }
  });
});

describe("getScenarioById", () => {
  it("returns scenario for valid id", () => {
    expect(getScenarioById("daily")?.id).toBe("daily");
  });

  it("returns undefined for invalid id", () => {
    expect(getScenarioById("nonexistent" as any)).toBeUndefined();
  });
});

describe("getPillsByScenario", () => {
  it("returns pills for daily scenario", () => {
    const pills = getPillsByScenario("daily");
    expect(pills.length).toBeGreaterThanOrEqual(1);
    expect(pills.map((p) => p.agentSlug)).toContain("office-docs");
  });

  it("returns empty array for invalid scenario", () => {
    expect(getPillsByScenario("nonexistent" as any)).toEqual([]);
  });
});

describe("getChipsByPill", () => {
  it("returns chips for office-docs pill", () => {
    const chips = getChipsByPill("daily", "office-docs");
    expect(chips.length).toBeGreaterThanOrEqual(1);
    expect(chips.some((c) => c.skillName === "anthropic-docx")).toBe(true);
  });

  it("returns empty array for invalid pill", () => {
    expect(getChipsByPill("daily", "nonexistent")).toEqual([]);
  });
});
