import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/ui/terminal", () => ({
  Terminal: ({ children, ...props }: any) => (
    <div data-testid="terminal" {...props}>
      {children}
    </div>
  ),
  AnimatedSpan: ({ children, ...props }: any) => (
    <span {...props}>{children}</span>
  ),
  TypingAnimation: ({ children, ...props }: any) => (
    <span {...props}>{children}</span>
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

import { SandboxSection } from "@/components/landing/sections/sandbox-section";

afterEach(() => {
  cleanup();
});

describe("SandboxSection", () => {
  test("renders section title", () => {
    render(<SandboxSection />);
    expect(screen.getByText("Agent Runtime Environment")).toBeInTheDocument();
  });

  test("renders terminal component", () => {
    render(<SandboxSection />);
    expect(screen.getByTestId("terminal")).toBeInTheDocument();
  });

  test("renders AIO Sandbox heading", () => {
    render(<SandboxSection />);
    expect(screen.getByText("AIO Sandbox")).toBeInTheDocument();
  });

  test("renders feature tags", () => {
    render(<SandboxSection />);
    expect(screen.getByText("Isolated")).toBeInTheDocument();
    expect(screen.getByText("Safe")).toBeInTheDocument();
    expect(screen.getByText("Persistent")).toBeInTheDocument();
    expect(screen.getByText("Mountable FS")).toBeInTheDocument();
    expect(screen.getByText("Long-running")).toBeInTheDocument();
  });

  test("renders open-source label", () => {
    render(<SandboxSection />);
    expect(screen.getByText("Open-source")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<SandboxSection className="custom-sandbox" />);
    expect(screen.getByTestId("section")).toHaveClass("custom-sandbox");
  });
});
