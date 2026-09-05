import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "@rstest/core";

const frontendRoot = join(import.meta.dirname, "../../../..");

// The landing page was simplified to a hero-only design (#landing-refresh):
// the Galaxy canvas, Magic Bento spotlight, and ProgressiveSkillsAnimation
// sections were removed from the route. The performance intent of this suite
// is unchanged — the landing route must not ship or mount any continuous
// decorative animation work — but the guarantee is now enforced at the
// composition level instead of inside section files that no longer render.
function readSource(relativePath: string): string {
  return readFileSync(join(frontendRoot, relativePath), "utf8");
}

describe("decorative animation scheduling", () => {
  it("ships a hero-only landing without decorative animation sections", () => {
    const page = readSource("src/app/page.tsx");

    expect(page).toContain("Hero");
    expect(page).not.toMatch(/galaxy/i);
    expect(page).not.toMatch(/magic-bento/i);
    expect(page).not.toContain("ProgressiveSkillsAnimation");
    expect(page).not.toContain("sections/");
  });

  it("keeps the hero free of canvas render loops", () => {
    const source = readSource("src/components/landing/hero.tsx");

    expect(source).not.toMatch(/galaxy/i);
    expect(source).not.toContain("useRenderActivity");
    expect(source).not.toContain("requestAnimationFrame");
  });

  it("does not render the removed decorative sections from anywhere on the landing route", () => {
    // The section components still exist on disk, so guard against them
    // sneaking back onto the landing page without their render-activity
    // scheduling (useRenderActivity + lazy dynamic imports).
    for (const section of [
      "whats-new-section",
      "case-study-section",
      "sandbox-section",
      "community-section",
      "skills-section",
    ]) {
      const page = readSource("src/app/page.tsx");
      expect(page).not.toContain(section);
    }
  });
});
