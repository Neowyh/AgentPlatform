import { describe, expect, it } from "vitest";

import {
  classifyVisibilityChange,
  VISIBILITY_RANKS,
} from "@/core/visibility-applications/options";

describe("classifyVisibilityChange", () => {
  it("classifies upgrade when target rank is higher", () => {
    expect(classifyVisibilityChange("private", "department")).toBe("upgrade");
    expect(classifyVisibilityChange("private", "public")).toBe("upgrade");
    expect(classifyVisibilityChange("department", "public")).toBe("upgrade");
  });

  it("classifies downgrade when target rank is lower", () => {
    expect(classifyVisibilityChange("public", "department")).toBe("downgrade");
    expect(classifyVisibilityChange("public", "private")).toBe("downgrade");
    expect(classifyVisibilityChange("department", "private")).toBe("downgrade");
  });

  it("classifies unchanged when ranks are equal", () => {
    expect(classifyVisibilityChange("private", "private")).toBe("unchanged");
    expect(classifyVisibilityChange("department", "department")).toBe(
      "unchanged",
    );
    expect(classifyVisibilityChange("public", "public")).toBe("unchanged");
  });

  it("treats null/undefined current visibility as private", () => {
    expect(classifyVisibilityChange(null, "department")).toBe("upgrade");
    expect(classifyVisibilityChange(undefined, "private")).toBe("unchanged");
  });

  it("treats unknown target visibility as unchanged", () => {
    expect(classifyVisibilityChange("private", "invalid")).toBe("unchanged");
  });

  it("exposes ranks with private < department < public", () => {
    expect(VISIBILITY_RANKS.private!).toBeLessThan(
      VISIBILITY_RANKS.department!,
    );
    expect(VISIBILITY_RANKS.department!).toBeLessThan(VISIBILITY_RANKS.public!);
  });
});
