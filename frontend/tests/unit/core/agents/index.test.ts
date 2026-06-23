import { describe, expect, test } from "vitest";

import * as agentsIndex from "@/core/agents/index";

describe("agents index", () => {
  test("re-exports api module", () => {
    expect(agentsIndex).toHaveProperty("listAgents");
    expect(agentsIndex).toHaveProperty("getAgent");
    expect(agentsIndex).toHaveProperty("createAgent");
    expect(agentsIndex).toHaveProperty("updateAgent");
    expect(agentsIndex).toHaveProperty("deleteAgent");
  });

  test("re-exports hooks module", () => {
    expect(agentsIndex).toHaveProperty("useAgents");
    expect(agentsIndex).toHaveProperty("useAgent");
  });
});
