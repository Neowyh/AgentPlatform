import { describe, expect, test } from "vitest";

import * as modelsIndex from "@/core/models/index";

describe("models index", () => {
  test("re-exports api functions", () => {
    expect(modelsIndex).toHaveProperty("loadModels");
  });

  test("re-exports types", () => {
    // Module should be importable and have exported members
    expect(Object.keys(modelsIndex).length).toBeGreaterThan(0);
  });
});
