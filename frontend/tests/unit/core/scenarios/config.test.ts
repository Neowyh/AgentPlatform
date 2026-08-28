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

  it("keeps the complete scenario entry inventory aligned with the release", () => {
    expect(SCENARIOS.flatMap((scenario) => scenario.agentPills)).toHaveLength(
      14,
    );
    expect(
      SCENARIOS.flatMap((scenario) =>
        scenario.agentPills.flatMap((pill) => pill.chips ?? []),
      ),
    ).toHaveLength(43);
  });

  it("assigns a unique task ID to every task entry", () => {
    const taskIds = SCENARIOS.flatMap((scenario) =>
      scenario.agentPills.flatMap((pill) =>
        (pill.chips ?? []).map((chip) => chip.taskId),
      ),
    );

    expect(taskIds).toHaveLength(new Set(taskIds).size);
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

  it("exposes the approved code-development task labels", () => {
    expect(
      getChipsByPill("professional", "code-dev").map((chip) => chip.label),
    ).toEqual([
      "方案质询",
      "需求规格化",
      "拆分研发任务",
      "按规格实现",
      "代码变更评审",
      "疑难故障诊断",
      "代码库架构改进",
      "需求规格说明撰写",
    ]);
  });
});
