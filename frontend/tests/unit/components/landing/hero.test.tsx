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

vi.mock("@/components/ui/flickering-grid", () => ({
  FlickeringGrid: (props: any) => <div data-testid="flickering-grid" />,
}));

vi.mock("@/components/ui/galaxy", () => ({
  __esModule: true,
  default: (props: any) => <div data-testid="galaxy" />,
}));

vi.mock("@/components/ui/word-rotate", () => ({
  WordRotate: ({ words }: any) => (
    <span data-testid="word-rotate">{words[0]}</span>
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

import { Hero } from "@/components/landing/hero";

afterEach(() => {
  cleanup();
});

describe("Hero", () => {
  test("renders hero heading", () => {
    render(<Hero />);
    expect(screen.getByText(/with iDeer/)).toBeInTheDocument();
  });

  test("renders word rotate animation", () => {
    render(<Hero />);
    expect(screen.getByTestId("word-rotate")).toBeInTheDocument();
  });

  test("renders galaxy background", () => {
    render(<Hero />);
    expect(screen.getByTestId("galaxy")).toBeInTheDocument();
  });

  test("renders flickering grid", () => {
    render(<Hero />);
    expect(screen.getByTestId("flickering-grid")).toBeInTheDocument();
  });

  test("renders get started button", () => {
    render(<Hero />);
    expect(screen.getByText("Get Started with 2.0")).toBeInTheDocument();
  });

  test("renders description text", () => {
    render(<Hero />);
    expect(screen.getByText(/open-source SuperAgent/)).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(<Hero className="custom-hero" />);
    expect(container.firstChild).toHaveClass("custom-hero");
  });
});
