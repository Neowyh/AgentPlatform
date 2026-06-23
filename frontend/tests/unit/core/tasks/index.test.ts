import { describe, expect, test } from "vitest";

import * as tasksIndex from "@/core/tasks/index";

describe("tasks index", () => {
  test("re-exports types", () => {
    // Tasks module should export something
    expect(tasksIndex).toBeDefined();
  });
});
