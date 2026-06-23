import { describe, expect, test } from "vitest";

import * as mcpIndex from "@/core/mcp/index";

describe("mcp index", () => {
  test("re-exports api functions", () => {
    expect(mcpIndex).toHaveProperty("loadMCPConfig");
    expect(mcpIndex).toHaveProperty("updateMCPConfig");
  });

  test("re-exports types", () => {
    expect(Object.keys(mcpIndex).length).toBeGreaterThan(0);
  });
});
