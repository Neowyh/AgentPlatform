import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
}));

vi.mock("@/components/ui/terminal", () => ({
  Terminal: ({ children }: any) => <div data-testid="terminal">{children}</div>,
  TypingAnimation: ({ children }: any) => <span>{children}</span>,
  AnimatedSpan: ({ children }: any) => <span>{children}</span>,
}));

import { SandboxSection } from "@/components/landing/sections/sandbox-section";

afterEach(() => {
  cleanup();
});

describe("SandboxSection", () => {
  test("renders the section title", () => {
    render(<SandboxSection />);
    expect(screen.getByText("Agent Runtime Environment")).toBeInTheDocument();
  });

  test("renders the AIO Sandbox heading", () => {
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

  test("renders the terminal component", () => {
    render(<SandboxSection />);
    expect(screen.getByTestId("terminal")).toBeInTheDocument();
  });
});
