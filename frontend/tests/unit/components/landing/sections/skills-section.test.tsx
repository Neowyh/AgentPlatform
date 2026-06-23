import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/landing/progressive-skills-animation", () => ({
  __esModule: true,
  default: () => (
    <div data-testid="progressive-skills-animation">Animation</div>
  ),
}));

vi.mock("@/components/landing/section", () => ({
  Section: ({ children, title, subtitle, className }: any) => (
    <div data-testid="section" className={className}>
      <h2>{title}</h2>
      <div>{subtitle}</div>
      {children}
    </div>
  ),
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

import { SkillsSection } from "@/components/landing/sections/skills-section";

afterEach(() => {
  cleanup();
});

describe("SkillsSection", () => {
  test("renders section title", () => {
    render(<SkillsSection />);
    expect(screen.getByText("Agent Skills")).toBeInTheDocument();
  });

  test("renders subtitle text", () => {
    render(<SkillsSection />);
    expect(
      screen.getByText(/Agent Skills are loaded progressively/),
    ).toBeInTheDocument();
  });

  test("renders progressive skills animation", () => {
    render(<SkillsSection />);
    expect(
      screen.getByTestId("progressive-skills-animation"),
    ).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<SkillsSection className="custom-skills" />);
    expect(screen.getByTestId("section")).toHaveClass("custom-skills");
  });
});
