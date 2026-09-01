import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, test } from "vitest";

import { SCENARIOS } from "@/core/scenarios/config";

describe("bundled scenario resources", () => {
  test("every configured Agent Pill has a bundled canonical Agent", () => {
    const manifest = JSON.parse(
      readFileSync(resolve(process.cwd(), "../bundled-resources.json"), "utf8"),
    ) as { resources: Array<{ type: string; slug: string }> };
    const bundledAgents = new Set(
      manifest.resources
        .filter((resource) => resource.type === "agent")
        .map((resource) => resource.slug),
    );
    const configuredPills = SCENARIOS.flatMap((scenario) =>
      scenario.agentPills.map((pill) => pill.agentSlug),
    );

    expect(new Set(configuredPills).size).toBe(configuredPills.length);
    expect(configuredPills.every((slug) => bundledAgents.has(slug))).toBe(true);
  });
});
