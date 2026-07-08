import { describe, expect, it } from "vitest";

import type {
  Agent,
  CreateAgentRequest,
  UpdateAgentRequest,
} from "@/core/agents/types";

describe("Agent", () => {
  it("can be constructed with required fields only", () => {
    const agent: Agent = {
      name: "test-agent",
      description: "A test agent",
      model: "gpt-4",
      tool_groups: ["tools"],
      skills: ["skill-1"],
      visibility: "public",
      owner_id: "u-1",
      department_id: null,
    };
    expect(agent.name).toBe("test-agent");
    expect(agent.visibility).toBe("public");
  });

  it("handles optional fields", () => {
    const agent: Agent = {
      name: "agent-2",
      description: "desc",
      model: null,
      tool_groups: null,
      skills: null,
      soul: "You are a helpful assistant",
      read_only: true,
      visibility: "private",
      owner_id: null,
      department_id: null,
      is_favorited: true,
    };
    expect(agent.soul).toBe("You are a helpful assistant");
    expect(agent.read_only).toBe(true);
    expect(agent.is_favorited).toBe(true);
  });

  it("handles null model and nullable array fields", () => {
    const agent: Agent = {
      name: "minimal",
      description: "",
      model: null,
      tool_groups: null,
      skills: null,
      visibility: "public",
      owner_id: null,
      department_id: null,
    };
    expect(agent.model).toBeNull();
    expect(agent.tool_groups).toBeNull();
    expect(agent.skills).toBeNull();
  });
});

describe("CreateAgentRequest", () => {
  it("can be constructed with only the required name field", () => {
    const req: CreateAgentRequest = { name: "new-agent" };
    expect(req.name).toBe("new-agent");
  });

  it("can be constructed with all optional fields", () => {
    const req: CreateAgentRequest = {
      name: "new-agent",
      description: "description",
      model: "gpt-4",
      tool_groups: ["tools"],
      skills: ["skill-1"],
      soul: "You are a bot",
      visibility: "department",
    };
    expect(req.tool_groups).toEqual(["tools"]);
  });
});

describe("UpdateAgentRequest", () => {
  it("can be constructed with partial updates", () => {
    const req: UpdateAgentRequest = {
      description: "updated",
      model: "claude-3",
    };
    expect(req.description).toBe("updated");
    expect(req.model).toBe("claude-3");
  });

  it("can be constructed with all fields", () => {
    const req: UpdateAgentRequest = {
      description: "updated",
      model: null,
      tool_groups: ["new-tools"],
      skills: ["new-skill"],
      soul: null,
      visibility: "private",
    };
    expect(req.model).toBeNull();
    expect(req.soul).toBeNull();
  });
});
