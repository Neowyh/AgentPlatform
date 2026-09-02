import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  SCENARIOS,
  getScenarioById,
  getPillsByScenario,
  getChipsByPill,
} from "@/core/scenarios/config";

const REPO_ROOT = resolve(import.meta.dirname, "../../../../..");

function bundledSlugs(type: "agent" | "skill") {
  const manifest = JSON.parse(
    readFileSync(resolve(REPO_ROOT, "bundled-resources.json"), "utf-8"),
  ) as { resources: Array<{ type: string; slug: string }> };

  return new Set(
    manifest.resources
      .filter((resource) => resource.type === type)
      .map((resource) => resource.slug),
  );
}

function agentSkills(agentSlug: string) {
  const config = readFileSync(
    resolve(REPO_ROOT, "resources", "agents", agentSlug, "config.yaml"),
    "utf-8",
  );
  const skillsBlock =
    /^skills:\s*\n((?:^[ \t]*-\s+.+(?:\n|$))*)/m.exec(config)?.[1] ?? "";

  return skillsBlock
    .split("\n")
    .map((line) => line.trimStart())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2));
}

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
      15,
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

  it("maps configured resources to the bundled catalog and agent closures", () => {
    const pills = SCENARIOS.flatMap((scenario) => scenario.agentPills);
    const chips = pills.flatMap((pill) => pill.chips ?? []);

    expect(pills.map((pill) => pill.agentSlug)).toHaveLength(
      new Set(pills.map((pill) => pill.agentSlug)).size,
    );
    expect(
      pills.every((pill) => bundledSlugs("agent").has(pill.agentSlug)),
    ).toBe(true);
    expect(
      chips.every((chip) => bundledSlugs("skill").has(chip.skillName)),
    ).toBe(true);

    for (const pill of pills) {
      const configuredSkills = new Set(
        (pill.chips ?? []).map((chip) => chip.skillName),
      );
      const declaredSkills = new Set(agentSkills(pill.agentSlug));

      if (pill.agentSlug === "code-dev") {
        expect(declaredSkills).toEqual(
          new Set([
            "ask-matt",
            "code-review",
            "codebase-design",
            "diagnosing-bugs",
            "domain-modeling",
            "grill-me",
            "grill-with-docs",
            "grilling",
            "handoff",
            "implement",
            "improve-codebase-architecture",
            "prototype",
            "research",
            "resolving-merge-conflicts",
            "setup-matt-pocock-skills",
            "tdd",
            "teach",
            "to-questionnaire",
            "to-spec",
            "to-tickets",
            "triage",
            "wait-what",
            "wayfinder",
            "wizard",
            "writing-for-agents",
            "srs-writing",
          ]),
        );
        expect(
          [...configuredSkills].every((skill) => declaredSkills.has(skill)),
        ).toBe(true);
      } else {
        expect(declaredSkills).toEqual(configuredSkills);
      }
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

  it("exposes the approved code-development task labels", () => {
    expect(
      getChipsByPill("professional", "code-dev").map((chip) => chip.label),
    ).toEqual([
      "方案质询",
      "需求规格化",
      "拆分研发任务",
      "按规格实现",
      "代码变更评审",
      "代码库架构改进",
      "疑难故障诊断",
    ]);
  });
});
