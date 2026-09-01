import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockSkills = [
  {
    resource_id: "skill-1-id",
    slug: "skill-1",
    name: "skill-1",
    description: "Skill 1 description",
  },
  {
    resource_id: "skill-2-id",
    slug: "skill-2",
    name: "skill-2",
    description: "Skill 2 description",
  },
];

vi.mock("@/core/skills", () => ({
  useSkills: () => ({
    skills: mockSkills,
    isLoading: false,
    refetch: vi.fn(),
  }),
  archiveSkill: vi.fn(),
  exportSkill: vi.fn(),
  importSkill: vi.fn(),
  toggleSkillFavorite: vi.fn(),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: {
        loading: "Loading...",
        favoritesOnly: "Favorites",
        import: "Import",
      },
      settings: {
        skills: {
          importSuccess: "Skill imported",
          archiveSuccess: "Skill archived",
          searchPlaceholder: "Search skills...",
          details: "Details",
          use: "Use",
          noResults: "No matching skills",
        },
      },
    },
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

  test("links to details and starts a prefilled skill conversation", () => {
    render(<SkillList />);

    expect(screen.getAllByRole("link", { name: "Details" })[0]).toHaveAttribute(
      "href",
      "/workspace/capabilities/skills/skill-1-id",
    );
    expect(screen.getAllByRole("link", { name: "Use" })[0]).toHaveAttribute(
      "href",
      "/workspace/chats/new?prompt=%2Fskill-1%20",
    );
  });

  test("clamps card descriptions to two lines while retaining full detail link", () => {
    render(<SkillList />);
    expect(screen.getByText("Skill 1 description")).toHaveClass(
      "line-clamp-2",
      "min-h-[3rem]",
    );
  });
});
