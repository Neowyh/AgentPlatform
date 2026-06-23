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

vi.mock("@/components/ui/aurora-text", () => ({
  AuroraText: ({ children }: any) => <span>{children}</span>,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, asChild, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("../section", () => ({
  Section: ({ children, title, subtitle }: any) => (
    <div data-testid="section">
      <div>{title}</div>
      <p>{subtitle}</p>
      {children}
    </div>
  ),
}));

import { CommunitySection } from "@/components/landing/sections/community-section";

afterEach(() => {
  cleanup();
});

describe("CommunitySection", () => {
  test("renders section title", () => {
    render(<CommunitySection />);
    expect(screen.getByText("Join the Community")).toBeInTheDocument();
  });

  test("renders subtitle", () => {
    render(<CommunitySection />);
    expect(screen.getByText(/Contribute brilliant ideas/)).toBeInTheDocument();
  });

  test("renders contribute button", () => {
    render(<CommunitySection />);
    expect(screen.getByText("Contribute Now")).toBeInTheDocument();
  });
});
