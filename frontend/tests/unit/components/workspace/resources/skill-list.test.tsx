import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockSkills = [
  { name: "skill-1", description: "Skill 1 description" },
  { name: "skill-2", description: "Skill 2 description" },
];

vi.mock("@/core/skills", () => ({
  useSkills: () => ({
    skills: mockSkills,
    isLoading: false,
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let SkillList: typeof import("@/components/workspace/resources/skill-list").SkillList;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/resources/skill-list");
  SkillList = mod.SkillList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("SkillList", () => {
  test("displays list of skills", () => {
    render(<SkillList />);
    expect(screen.getByText("skill-1")).toBeInTheDocument();
    expect(screen.getByText("skill-2")).toBeInTheDocument();
  });

  test("displays skill descriptions", () => {
    render(<SkillList />);
    expect(screen.getByText("Skill 1 description")).toBeInTheDocument();
    expect(screen.getByText("Skill 2 description")).toBeInTheDocument();
  });
});
