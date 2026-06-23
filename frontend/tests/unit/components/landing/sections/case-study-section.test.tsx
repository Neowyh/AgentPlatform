import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("next/link", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: React.forwardRef(({ children, href, ...props }: any, ref: any) =>
      React.createElement("a", { ...props, ref, href }, children),
    ),
  };
});

vi.mock("@/components/ui/card", () => ({
  Card: ({ children, ...props }: any) => <div {...props}>{children}</div>,
}));

vi.mock("@/core/threads/utils", () => ({
  pathOfThread: (id: string) => `/mock/${id}`,
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

vi.mock("@/components/landing/section", () => ({
  Section: ({ children, title, subtitle, className }: any) => (
    <div data-testid="section" className={className}>
      <h2>{title}</h2>
      <p>{subtitle}</p>
      {children}
    </div>
  ),
}));

import { CaseStudySection } from "@/components/landing/sections/case-study-section";

afterEach(() => {
  cleanup();
});

describe("CaseStudySection", () => {
  test("renders section title", () => {
    render(<CaseStudySection />);
    expect(screen.getByText("Case Studies")).toBeInTheDocument();
  });

  test("renders subtitle", () => {
    render(<CaseStudySection />);
    expect(
      screen.getByText("See how iDeer is used in the wild"),
    ).toBeInTheDocument();
  });

  test("renders case study cards", () => {
    render(<CaseStudySection />);
    expect(screen.getByText(/Forecast 2026 Agent Trends/)).toBeInTheDocument();
    expect(screen.getByText(/Doraemon Explains/)).toBeInTheDocument();
  });

  test("renders correct number of case studies", () => {
    render(<CaseStudySection />);
    const links = screen.getAllByRole("link");
    expect(links.length).toBe(6);
  });

  test("applies custom className", () => {
    render(<CaseStudySection className="custom-cases" />);
    expect(screen.getByTestId("section")).toHaveClass("custom-cases");
  });
});
