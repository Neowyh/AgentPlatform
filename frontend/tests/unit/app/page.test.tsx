import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/landing/header", () => ({
  Header: () => <header data-testid="header">Header</header>,
}));

vi.mock("@/components/landing/hero", () => ({
  Hero: () => <div data-testid="hero">Hero</div>,
}));

vi.mock("@/components/landing/footer", () => ({
  Footer: () => <footer data-testid="footer">Footer</footer>,
}));

vi.mock("@/components/landing/sections/case-study-section", () => ({
  CaseStudySection: () => (
    <div data-testid="case-study-section">Case Studies</div>
  ),
}));

vi.mock("@/components/landing/sections/community-section", () => ({
  CommunitySection: () => <div data-testid="community-section">Community</div>,
}));

vi.mock("@/components/landing/sections/sandbox-section", () => ({
  SandboxSection: () => <div data-testid="sandbox-section">Sandbox</div>,
}));

vi.mock("@/components/landing/sections/skills-section", () => ({
  SkillsSection: () => <div data-testid="skills-section">Skills</div>,
}));

vi.mock("@/components/landing/sections/whats-new-section", () => ({
  WhatsNewSection: () => <div data-testid="whats-new-section">Whats New</div>,
}));

import LandingPage from "@/app/page";

afterEach(() => {
  cleanup();
});

describe("LandingPage", () => {
  test("renders header", () => {
    render(<LandingPage />);
    expect(screen.getByTestId("header")).toBeInTheDocument();
  });

  test("renders hero", () => {
    render(<LandingPage />);
    expect(screen.getByTestId("hero")).toBeInTheDocument();
  });

  test("renders all sections", () => {
    render(<LandingPage />);
    expect(screen.getByTestId("case-study-section")).toBeInTheDocument();
    expect(screen.getByTestId("skills-section")).toBeInTheDocument();
    expect(screen.getByTestId("sandbox-section")).toBeInTheDocument();
    expect(screen.getByTestId("whats-new-section")).toBeInTheDocument();
    expect(screen.getByTestId("community-section")).toBeInTheDocument();
  });

  test("renders footer", () => {
    render(<LandingPage />);
    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });

  test("renders main content area", () => {
    const { container } = render(<LandingPage />);
    expect(container.querySelector("main")).toBeInTheDocument();
  });
});
