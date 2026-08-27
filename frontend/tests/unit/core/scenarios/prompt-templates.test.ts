import { describe, expect, it } from "vitest";

import { SCENARIOS } from "@/core/scenarios/config";
import { getTemplateForChip } from "@/core/scenarios/prompt-templates";

describe("getTemplateForChip", () => {
  it("returns the correct chip for daily/office-docs/anthropic-docx", () => {
    const chip = getTemplateForChip("daily", "office-docs", "anthropic-docx");
    expect(chip).toBeDefined();
    expect(chip?.skillName).toBe("anthropic-docx");
    expect(chip?.promptTemplate).toContain("[");
  });

  it("returns undefined for non-existent skill", () => {
    expect(
      getTemplateForChip("daily", "office-docs", "nonexistent"),
    ).toBeUndefined();
  });

  it("returns undefined for non-existent scenario", () => {
    expect(
      getTemplateForChip("nonexistent" as any, "office-docs", "anthropic-docx"),
    ).toBeUndefined();
  });

  it("returns undefined for non-existent agent slug", () => {
    expect(
      getTemplateForChip("daily", "nonexistent", "anthropic-docx"),
    ).toBeUndefined();
  });

  it("every chip in SCENARIOS has a promptTemplate", () => {
    for (const scenario of SCENARIOS) {
      for (const pill of scenario.agentPills) {
        for (const chip of pill.chips ?? []) {
          const result = getTemplateForChip(
            scenario.id,
            pill.agentSlug,
            chip.skillName,
          );
          expect(result).toBeDefined();
          expect(typeof result!.promptTemplate).toBe("string");
          expect(result!.promptTemplate.length).toBeGreaterThan(0);
        }
      }
    }
  });
});
