import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      welcome: {
        description: "How can I help you today?",
        createYourOwnSkill: "Create Your Own Skill",
        createYourOwnSkillDescription: "Build custom skills for your workflow",
      },
    },
  }),
}));

vi.mock("@/components/ui/aurora-text", () => ({
  AuroraText: ({
    children,
    colors,
  }: {
    children: React.ReactNode;
    colors?: string[];
  }) => (
    <span data-testid="aurora-text" data-colors={JSON.stringify(colors)}>
      {children}
    </span>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let Welcome: typeof import("@/components/workspace/welcome").Welcome;

beforeEach(async () => {
  vi.clearAllMocks();
  mockSearchParams = new URLSearchParams();
  const mod = await import("@/components/workspace/welcome");
  Welcome = mod.Welcome;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("Welcome", () => {
  test("renders the iDeer title by default", () => {
    render(<Welcome />);
    expect(screen.getByText("iDeer")).toBeInTheDocument();
  });

  test("does not render a description by default", () => {
    render(<Welcome />);
    expect(
      screen.queryByText("How can I help you today?"),
    ).not.toBeInTheDocument();
  });

  test("renders in skill mode when search param mode=skill", () => {
    mockSearchParams = new URLSearchParams("mode=skill");
    render(<Welcome />);
    expect(screen.getByText(/Create Your Own Skill/)).toBeInTheDocument();
  });

  test("renders skill description in skill mode", () => {
    mockSearchParams = new URLSearchParams("mode=skill");
    render(<Welcome />);
    expect(
      screen.getByText("Build custom skills for your workflow"),
    ).toBeInTheDocument();
  });

  test("does not show the iDeer title in skill mode", () => {
    mockSearchParams = new URLSearchParams("mode=skill");
    render(<Welcome />);
    expect(screen.queryByText("iDeer")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(<Welcome className="my-class" />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("my-class"),
    );
  });

  test("renders AuroraText with default colors in non-ultra mode", () => {
    render(<Welcome />);
    const aurora = screen.getByTestId("aurora-text");
    expect(aurora).toBeInTheDocument();
    const colors = JSON.parse(aurora.getAttribute("data-colors") ?? "[]");
    expect(colors).toEqual(["var(--color-foreground)"]);
  });

  test("renders AuroraText with ultra colors in ultra mode", () => {
    render(<Welcome mode="ultra" />);
    const aurora = screen.getByTestId("aurora-text");
    const colors = JSON.parse(aurora.getAttribute("data-colors") ?? "[]");
    expect(colors).toEqual(["#efefbb", "#e9c665", "#e3a812"]);
  });

  test("does not render a greeting emoji", () => {
    render(<Welcome />);
    expect(screen.queryByText("👋")).not.toBeInTheDocument();
  });

  test("keeps the iDeer title in ultra mode", () => {
    render(<Welcome mode="ultra" />);
    expect(screen.getByText("iDeer")).toBeInTheDocument();
  });

  test("renders centered layout", () => {
    const { container } = render(<Welcome />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("items-center"),
    );
  });
});
