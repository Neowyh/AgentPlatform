import { describe, expect, test } from "vitest";

import * as workflowsIndex from "@/core/workflows/index";

describe("workflows index", () => {
  test("re-exports api functions", () => {
    expect(workflowsIndex).toHaveProperty("listWorkflows");
    expect(workflowsIndex).toHaveProperty("getWorkflow");
    expect(workflowsIndex).toHaveProperty("createWorkflow");
    expect(workflowsIndex).toHaveProperty("updateWorkflow");
    expect(workflowsIndex).toHaveProperty("deleteWorkflow");
  });

  test("re-exports hooks", () => {
    expect(workflowsIndex).toHaveProperty("useWorkflows");
    expect(workflowsIndex).toHaveProperty("useWorkflow");
  });
});
