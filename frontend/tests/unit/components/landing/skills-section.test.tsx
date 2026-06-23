import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
}));

// Mock the entire ProgressiveSkillsAnimation to avoid its complex deps
vi.mock("@/components/landing/progressive-skills-animation", () => ({
  __esModule: true,
  default: () => <div data-testid="progressive-skills-animation" />,
}));

import { SkillsSection } from "@/components/landing/sections/skills-section";

afterEach(() => {
  cleanup();
});

describe("SkillsSection", () => {
  test("renders the section title", () => {
    render(<SkillsSection />);
    expect(screen.getByText("Agent Skills")).toBeInTheDocument();
  });

  test("renders the subtitle about progressive loading", () => {
    render(<SkillsSection />);
    expect(
      screen.getByText(/Agent Skills are loaded progressively/),
    ).toBeInTheDocument();
  });

  test("renders the ProgressiveSkillsAnimation", () => {
    render(<SkillsSection />);
    expect(
      screen.getByTestId("progressive-skills-animation"),
    ).toBeInTheDocument();
  });
});
