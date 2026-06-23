import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { CaseStudySection } from "@/components/landing/sections/case-study-section";

afterEach(() => {
  cleanup();
});

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
}));

describe("CaseStudySection", () => {
  test("renders the section title", () => {
    render(<CaseStudySection />);
    expect(screen.getByText("Case Studies")).toBeInTheDocument();
  });

  test("renders the subtitle", () => {
    render(<CaseStudySection />);
    expect(
      screen.getByText("See how iDeer is used in the wild"),
    ).toBeInTheDocument();
  });

  test("renders case study cards", () => {
    render(<CaseStudySection />);
    expect(screen.getByText(/Forecast 2026 Agent Trends/)).toBeInTheDocument();
    expect(screen.getByText(/Doraemon Explains the MOE/)).toBeInTheDocument();
  });
});
