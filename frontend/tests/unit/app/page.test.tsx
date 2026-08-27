import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/landing/header", () => ({
  Header: () => <header data-testid="header">Header</header>,
}));

vi.mock("@/components/landing/hero", () => ({
  Hero: () => <div data-testid="hero">Hero</div>,
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

  test("does not render footer", () => {
    render(<LandingPage />);
    expect(screen.queryByTestId("footer")).not.toBeInTheDocument();
  });

  test("does not render case study section", () => {
    render(<LandingPage />);
    expect(screen.queryByTestId("case-study-section")).not.toBeInTheDocument();
  });

  test("does not render skills section", () => {
    render(<LandingPage />);
    expect(screen.queryByTestId("skills-section")).not.toBeInTheDocument();
  });

  test("does not render sandbox section", () => {
    render(<LandingPage />);
    expect(screen.queryByTestId("sandbox-section")).not.toBeInTheDocument();
  });

  test("does not render whats-new section", () => {
    render(<LandingPage />);
    expect(screen.queryByTestId("whats-new-section")).not.toBeInTheDocument();
  });

  test("does not render community section", () => {
    render(<LandingPage />);
    expect(screen.queryByTestId("community-section")).not.toBeInTheDocument();
  });

  test("renders main content area", () => {
    const { container } = render(<LandingPage />);
    expect(container.querySelector("main")).toBeInTheDocument();
  });
});
