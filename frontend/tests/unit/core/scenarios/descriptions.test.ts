import { describe, it, expect } from "vitest";

import type { Agent } from "@/core/agents/types";
import {
  agentDescription,
  findAgentForPill,
  findSkillForChip,
  skillDescription,
} from "@/core/scenarios/descriptions";
import type { Skill } from "@/core/skills/type";

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    name: "Agent",
    description: "Description",
    model: null,
    tool_groups: null,
    skills: null,
    visibility: "public",
    owner_id: null,
    department_id: null,
    ...overrides,
  };
}

function skill(overrides: Partial<Skill> = {}): Skill {
  return {
    name: "Skill",
    description: "Description",
    category: "general",
    license: "MIT",
    enabled: true,
    ...overrides,
  };
}

describe("findAgentForPill", () => {
  const agents = [agent({ slug: "fault-zeroing", name: "故障归零专家" })];

  it("matches by slug first", () => {
    expect(findAgentForPill(agents, "fault-zeroing")).toBe(agents[0]);
  });

  it("falls back to matching by name when slug is absent", () => {
    const nameless = [agent({ name: "故障归零专家", slug: undefined })];
    expect(findAgentForPill(nameless, "故障归零专家")).toBe(nameless[0]);
  });

  it("returns undefined when nothing matches", () => {
    expect(findAgentForPill(agents, "nope")).toBeUndefined();
  });
});

describe("findSkillForChip", () => {
  const skills = [
    skill({ resource_id: "res-1", slug: "summarize", name: "智能摘要" }),
  ];

  it("matches by resource_id, slug, then name", () => {
    expect(findSkillForChip(skills, "res-1")).toBe(skills[0]);
    expect(findSkillForChip(skills, "summarize")).toBe(skills[0]);
    expect(findSkillForChip(skills, "智能摘要")).toBe(skills[0]);
  });

  it("returns undefined when nothing matches", () => {
    expect(findSkillForChip(skills, "nope")).toBeUndefined();
  });
});

describe("agentDescription", () => {
  it("prefers the summary", () => {
    expect(
      agentDescription(agent({ summary: "Short", description: "Long" })),
    ).toBe("Short");
  });

  it("falls back to the description when the summary is blank", () => {
    expect(
      agentDescription(agent({ summary: "  ", description: "Long" })),
    ).toBe("Long");
  });

  it("returns undefined when both are blank", () => {
    expect(
      agentDescription(agent({ summary: "", description: "  " })),
    ).toBeUndefined();
  });
});

describe("skillDescription", () => {
  it("zh-CN prefers the summary and treats blank as missing", () => {
    expect(
      skillDescription(
        skill({ summary: "Short", description: "Long" }),
        "zh-CN",
      ),
    ).toBe("Short");
    expect(
      skillDescription(skill({ summary: "", description: "Long" }), "zh-CN"),
    ).toBe("Long");
  });

  it("non-zh locales use the description", () => {
    expect(
      skillDescription(
        skill({ summary: "Short", description: "Long" }),
        "en-US",
      ),
    ).toBe("Long");
  });

  it("returns undefined when the picked text is blank", () => {
    expect(
      skillDescription(skill({ description: "" }), "en-US"),
    ).toBeUndefined();
  });
});
