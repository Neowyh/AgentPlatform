import { describe, expect, test } from "vitest";

import * as memoryIndex from "@/core/memory/index";

describe("memory index", () => {
  test("re-exports api functions", () => {
    expect(memoryIndex).toHaveProperty("loadMemory");
    expect(memoryIndex).toHaveProperty("clearMemory");
    expect(memoryIndex).toHaveProperty("createMemoryFact");
    expect(memoryIndex).toHaveProperty("deleteMemoryFact");
    expect(memoryIndex).toHaveProperty("updateMemoryFact");
    expect(memoryIndex).toHaveProperty("importMemory");
  });

  test("re-exports types", () => {
    expect(Object.keys(memoryIndex).length).toBeGreaterThan(0);
  });
});
