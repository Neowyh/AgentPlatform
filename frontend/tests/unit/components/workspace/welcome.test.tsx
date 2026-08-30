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
        greeting: "iDeer，落地你的idea",
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
  test("renders the localized greeting by default", () => {
    render(<Welcome />);
    expect(screen.getByText("iDeer，落地你的idea")).toBeInTheDocument();
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

  test("does not show the localized greeting in skill mode", () => {
    mockSearchParams = new URLSearchParams("mode=skill");
    render(<Welcome />);
    expect(screen.queryByText("iDeer")).not.toBeInTheDocument();
    expect(screen.queryByText("iDeer，落地你的idea")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(<Welcome className="my-class" />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("my-class"),
    );
  });

  test("renders with display font in non-ultra mode", () => {
    render(<Welcome />);
    expect(screen.getByText("iDeer，落地你的idea")).toBeInTheDocument();
    const title = screen.getByText("iDeer，落地你的idea").closest("div");
    expect(title?.className).toMatch(/tracking-\[-0\.04em\]/);
  });

  test("renders same title in ultra mode (no AuroraText)", () => {
    render(<Welcome mode="ultra" />);
    expect(screen.getByText("iDeer，落地你的idea")).toBeInTheDocument();
    expect(screen.getByText("iDeer，落地你的idea")).toBeInTheDocument();
  });

  test("does not render a greeting emoji", () => {
    render(<Welcome />);
    expect(screen.queryByText("👋")).not.toBeInTheDocument();
  });

  test("keeps the localized greeting in ultra mode", () => {
    render(<Welcome mode="ultra" />);
    expect(screen.getByText("iDeer，落地你的idea")).toBeInTheDocument();
    expect(screen.getByText("iDeer，落地你的idea")).toBeInTheDocument();
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
