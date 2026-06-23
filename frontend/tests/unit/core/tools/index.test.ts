import { describe, expect, test } from "vitest";

import * as toolsIndex from "@/core/tools/index";

describe("tools index", () => {
  test("re-exports api functions", () => {
    expect(toolsIndex).toHaveProperty("listTools");
    expect(toolsIndex).toHaveProperty("getToolDetail");
    expect(toolsIndex).toHaveProperty("testTool");
  });

  test("has exported members", () => {
    expect(Object.keys(toolsIndex).length).toBeGreaterThan(0);
  });
});
